"""Action Studio Core Orchestration Service.

Manages the lifecycle of officer-controlled Action Studio documents:
creation, bounded AI draft generation, regeneration, human officer editing,
version history tracking, approval boundary, and structured audit events.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

try:
    from app.models.action_studio import (
        ActionDocumentStatus,
        ActionDocumentType,
        ActionStudioAuditEvent,
        ActionStudioDocument,
        ActionStudioDocumentSummary,
        ActionStudioDocumentVersion,
        ActionStudioListResponse,
        ApproveDraftRequest,
        CreateDraftRequest,
        UpdateDraftRequest,
    )
    from app.services.action_studio_ai_service import ActionStudioAiDraftingService
    from app.services.action_studio_context_service import ActionStudioContextService
    from app.db import client as db_client
except ImportError:
    from app.models.action_studio import (
        ActionDocumentStatus,
        ActionDocumentType,
        ActionStudioAuditEvent,
        ActionStudioDocument,
        ActionStudioDocumentSummary,
        ActionStudioDocumentVersion,
        ActionStudioListResponse,
        ApproveDraftRequest,
        CreateDraftRequest,
        UpdateDraftRequest,
    )
    from app.services.action_studio_ai_service import ActionStudioAiDraftingService
    from app.services.action_studio_context_service import ActionStudioContextService
    from app.db import client as db_client

logger = logging.getLogger(__name__)

# Global in-memory storage for Action Studio entities (with file-backed local store support)
_ACTION_STUDIO_DRAFTS: Dict[str, Dict[str, Any]] = {}
_ACTION_STUDIO_VERSIONS: Dict[str, List[Dict[str, Any]]] = {}
_ACTION_STUDIO_AUDIT_LOGS: List[Dict[str, Any]] = []


class ActionStudioService:
    """Core orchestration service for Action Studio backend workflow."""

    @classmethod
    async def create_draft(
        cls,
        procurement_id: str,
        request: CreateDraftRequest,
    ) -> ActionStudioDocument:
        """Creates a new Action Studio document draft.

        Args:
            procurement_id (str): Target procurement workspace UUID.
            request (CreateDraftRequest): Creation parameters.

        Returns:
            ActionStudioDocument: Initialized document draft.
        """
        # 1. Build canonical evidence context
        context = await ActionStudioContextService.build_evidence_context(procurement_id)

        # Resolve target bidder legal name if provided
        target_bidder_name = None
        if request.target_bidder_id:
            excluded = context.get("technical", {}).get("excluded_bidders", [])
            eligible = context.get("technical", {}).get("technically_eligible_bidders", [])
            for b in excluded + eligible:
                if b.get("bidder_id") == request.target_bidder_id or b.get("legal_name") == request.target_bidder_id:
                    target_bidder_name = b.get("legal_name")
                    break

        # 2. Generate content and evidence references
        content, evidence_refs, is_ai = await ActionStudioAiDraftingService.generate_draft(
            document_type=request.document_type,
            context=context,
            target_bidder_id=request.target_bidder_id,
        )

        doc_id = str(uuid.uuid4())
        default_title = f"{request.document_type.value.replace('_', ' ').title()} - {context.get('external_reference')}"
        if target_bidder_name:
            default_title += f" ({target_bidder_name})"
        title = request.title or default_title

        now = datetime.now(timezone.utc)

        doc = ActionStudioDocument(
            id=doc_id,
            procurement_id=procurement_id,
            document_type=request.document_type,
            title=title,
            status=ActionDocumentStatus.DRAFT,
            created_at=now,
            updated_at=now,
            created_by=request.created_by or "HUMAN_PROCUREMENT_OFFICER",
            decision_authority="HUMAN_PROCUREMENT_OFFICER",
            source_evaluation_references={
                "procurement_id": procurement_id,
                "external_reference": context.get("external_reference"),
                "technical_freeze_completed": context.get("technical", {}).get("technical_freeze_completed"),
                "financial_evaluation_completed": context.get("financial", {}).get("financial_evaluation_completed"),
                "l1_bidder": context.get("financial", {}).get("l1_bidder"),
            },
            content=content,
            evidence_references=evidence_refs,
            is_ai_generated=is_ai,
            is_draft=True,
            version=1,
            target_bidder_id=request.target_bidder_id,
            target_bidder_name=target_bidder_name,
        )

        # Store document
        doc_dict = doc.model_dump()
        _ACTION_STUDIO_DRAFTS[doc_id] = doc_dict

        # Create initial version snapshot
        version_entry = ActionStudioDocumentVersion(
            id=str(uuid.uuid4()),
            document_id=doc_id,
            version=1,
            content=content,
            status=ActionDocumentStatus.DRAFT,
            updated_by=doc.created_by,
            updated_at=now,
            change_summary="Initial AI / evidence-grounded draft creation.",
        )
        if doc_id not in _ACTION_STUDIO_VERSIONS:
            _ACTION_STUDIO_VERSIONS[doc_id] = []
        _ACTION_STUDIO_VERSIONS[doc_id].append(version_entry.model_dump())

        # Audit Event
        await cls._record_audit_event(
            event_type="ACTION_DRAFT_CREATED",
            procurement_id=procurement_id,
            document_id=doc_id,
            document_type=request.document_type,
            actor=doc.created_by,
            source_evaluation_references=doc.source_evaluation_references,
            version=1,
            details={"is_ai_generated": is_ai, "target_bidder_id": request.target_bidder_id},
        )

        logger.info("Created Action Studio draft '%s' (%s) for procurement %s", doc_id, request.document_type.value, procurement_id)
        return doc

    @classmethod
    async def regenerate_draft(
        cls,
        draft_id: str,
        actor: str = "HUMAN_PROCUREMENT_OFFICER",
    ) -> ActionStudioDocument:
        """Regenerates an existing Action Studio draft using updated evidence context.

        Args:
            draft_id (str): Existing document UUID.
            actor (str): Requesting officer actor.

        Returns:
            ActionStudioDocument: Regenerated document.
        """
        doc_dict = _ACTION_STUDIO_DRAFTS.get(draft_id)
        if not doc_dict:
            raise ValueError(f"Action Studio draft with ID '{draft_id}' was not found.")

        if doc_dict.get("status") == ActionDocumentStatus.APPROVED:
            raise ValueError("Approved document drafts cannot be regenerated.")

        procurement_id = doc_dict["procurement_id"]
        doc_type = ActionDocumentType(doc_dict["document_type"])
        target_bidder_id = doc_dict.get("target_bidder_id")

        # Re-fetch context
        context = await ActionStudioContextService.build_evidence_context(procurement_id)

        # Re-generate content
        content, evidence_refs, is_ai = await ActionStudioAiDraftingService.generate_draft(
            document_type=doc_type,
            context=context,
            target_bidder_id=target_bidder_id,
        )

        now = datetime.now(timezone.utc)
        new_version = doc_dict.get("version", 1) + 1

        doc_dict["content"] = content
        doc_dict["evidence_references"] = [r.model_dump() for r in evidence_refs]
        doc_dict["is_ai_generated"] = is_ai
        doc_dict["version"] = new_version
        doc_dict["updated_at"] = now.isoformat()

        _ACTION_STUDIO_DRAFTS[draft_id] = doc_dict

        # Version Snapshot
        version_entry = ActionStudioDocumentVersion(
            id=str(uuid.uuid4()),
            document_id=draft_id,
            version=new_version,
            content=content,
            status=ActionDocumentStatus(doc_dict["status"]),
            updated_by=actor,
            updated_at=now,
            change_summary="Regenerated draft content from canonical evidence.",
        )
        if draft_id not in _ACTION_STUDIO_VERSIONS:
            _ACTION_STUDIO_VERSIONS[draft_id] = []
        _ACTION_STUDIO_VERSIONS[draft_id].append(version_entry.model_dump())

        # Audit Event
        await cls._record_audit_event(
            event_type="ACTION_DRAFT_REGENERATED",
            procurement_id=procurement_id,
            document_id=draft_id,
            document_type=doc_type,
            actor=actor,
            source_evaluation_references=doc_dict.get("source_evaluation_references", {}),
            version=new_version,
            details={"is_ai_generated": is_ai},
        )

        logger.info("Regenerated Action Studio draft '%s' to version %d", draft_id, new_version)
        return ActionStudioDocument.model_validate(doc_dict)

    @classmethod
    async def update_draft_content(
        cls,
        draft_id: str,
        request: UpdateDraftRequest,
    ) -> ActionStudioDocument:
        """Updates the content of an Action Studio draft (officer editing).

        Args:
            draft_id (str): Document UUID.
            request (UpdateDraftRequest): Edit request payload.

        Returns:
            ActionStudioDocument: Updated document.
        """
        doc_dict = _ACTION_STUDIO_DRAFTS.get(draft_id)
        if not doc_dict:
            raise ValueError(f"Action Studio draft with ID '{draft_id}' was not found.")

        if doc_dict.get("status") == ActionDocumentStatus.APPROVED:
            raise ValueError("Approved document drafts cannot be modified.")

        now = datetime.now(timezone.utc)
        new_version = doc_dict.get("version", 1) + 1
        new_status = ActionDocumentStatus.READY_FOR_APPROVAL if request.mark_ready_for_approval else ActionDocumentStatus.EDITED

        doc_dict["content"] = request.content
        doc_dict["status"] = new_status.value
        doc_dict["version"] = new_version
        doc_dict["updated_at"] = now.isoformat()

        _ACTION_STUDIO_DRAFTS[draft_id] = doc_dict

        actor = request.updated_by or "HUMAN_PROCUREMENT_OFFICER"

        # Version Snapshot
        version_entry = ActionStudioDocumentVersion(
            id=str(uuid.uuid4()),
            document_id=draft_id,
            version=new_version,
            content=request.content,
            status=new_status,
            updated_by=actor,
            updated_at=now,
            change_summary=request.change_summary or "Officer content edit.",
        )
        if draft_id not in _ACTION_STUDIO_VERSIONS:
            _ACTION_STUDIO_VERSIONS[draft_id] = []
        _ACTION_STUDIO_VERSIONS[draft_id].append(version_entry.model_dump())

        # Audit Event
        await cls._record_audit_event(
            event_type="ACTION_DRAFT_EDITED",
            procurement_id=doc_dict["procurement_id"],
            document_id=draft_id,
            document_type=ActionDocumentType(doc_dict["document_type"]),
            actor=actor,
            source_evaluation_references=doc_dict.get("source_evaluation_references", {}),
            version=new_version,
            details={"change_summary": request.change_summary},
        )
        await cls._record_audit_event(
            event_type="ACTION_DRAFT_VERSION_CREATED",
            procurement_id=doc_dict["procurement_id"],
            document_id=draft_id,
            document_type=ActionDocumentType(doc_dict["document_type"]),
            actor=actor,
            source_evaluation_references=doc_dict.get("source_evaluation_references", {}),
            version=new_version,
            details={},
        )

        logger.info("Updated content for Action Studio draft '%s' to version %d (Status: %s)", draft_id, new_version, new_status.value)
        return ActionStudioDocument.model_validate(doc_dict)

    @classmethod
    async def approve_draft(
        cls,
        draft_id: str,
        request: ApproveDraftRequest,
    ) -> ActionStudioDocument:
        """Formally approves an Action Studio draft document.

        Approval requirements:
        - Must require a human procurement officer actor.
        - Records timestamp and approving actor.
        - Stores content/version approved.
        - Generates ACTION_DRAFT_APPROVED audit event.
        - Does NOT dispatch or alter technical/financial findings.

        Args:
            draft_id (str): Target document UUID.
            request (ApproveDraftRequest): Approval request payload.

        Returns:
            ActionStudioDocument: Approved document.
        """
        doc_dict = _ACTION_STUDIO_DRAFTS.get(draft_id)
        if not doc_dict:
            raise ValueError(f"Action Studio draft with ID '{draft_id}' was not found.")

        if not request.officer_actor or not request.officer_actor.strip():
            raise ValueError("Approval requires a valid human officer actor identity.")

        if doc_dict.get("status") == ActionDocumentStatus.APPROVED:
            raise ValueError("Draft has already been approved.")

        now = datetime.now(timezone.utc)
        doc_dict["status"] = ActionDocumentStatus.APPROVED.value
        doc_dict["approved_by"] = request.officer_actor
        doc_dict["approved_at"] = now.isoformat()
        doc_dict["updated_at"] = now.isoformat()
        doc_dict["is_draft"] = False

        _ACTION_STUDIO_DRAFTS[draft_id] = doc_dict

        # Audit Event
        await cls._record_audit_event(
            event_type="ACTION_DRAFT_APPROVED",
            procurement_id=doc_dict["procurement_id"],
            document_id=draft_id,
            document_type=ActionDocumentType(doc_dict["document_type"]),
            actor=request.officer_actor,
            source_evaluation_references=doc_dict.get("source_evaluation_references", {}),
            version=doc_dict.get("version", 1),
            details={"notes": request.notes},
        )

        logger.info("Formally APPROVED Action Studio draft '%s' by officer '%s'", draft_id, request.officer_actor)
        return ActionStudioDocument.model_validate(doc_dict)

    @classmethod
    async def get_draft(cls, draft_id: str) -> Optional[ActionStudioDocument]:
        """Retrieves a single Action Studio document draft by ID."""
        doc_dict = _ACTION_STUDIO_DRAFTS.get(draft_id)
        if not doc_dict:
            return None
        return ActionStudioDocument.model_validate(doc_dict)

    @classmethod
    async def list_procurement_drafts(cls, procurement_id: str) -> ActionStudioListResponse:
        """Lists all Action Studio document drafts for a procurement workspace."""
        matching = [
            ActionStudioDocumentSummary.model_validate(d)
            for d in _ACTION_STUDIO_DRAFTS.values()
            if d.get("procurement_id") == procurement_id
        ]
        return ActionStudioListResponse(
            procurement_id=procurement_id,
            total=len(matching),
            documents=matching,
        )

    @classmethod
    async def check_readiness(cls, procurement_id: str) -> Dict[str, Any]:
        """Checks whether Action Studio is unlocked based on backend workflow state."""
        context = await ActionStudioContextService.build_evidence_context(procurement_id)
        tech = context.get("technical", {})
        fin = context.get("financial", {})

        tech_freeze = tech.get("technical_freeze_completed", False)
        fin_eval = fin.get("financial_evaluation_completed", False)
        l1_bidder = fin.get("l1_bidder")
        has_l1 = bool(l1_bidder)

        if not tech_freeze:
            return {
                "procurement_id": procurement_id,
                "is_unlocked": False,
                "status": "TECHNICAL_FREEZE_PENDING",
                "blocker_reason": "Technical evaluation freeze has not completed.",
                "technical_freeze_completed": False,
                "financial_evaluation_completed": fin_eval,
                "has_l1_bidder": has_l1,
            }

        if not fin_eval:
            return {
                "procurement_id": procurement_id,
                "is_unlocked": False,
                "status": "FINANCIAL_EVALUATION_PENDING",
                "blocker_reason": "Cover 2 commercial evaluation has not completed.",
                "technical_freeze_completed": True,
                "financial_evaluation_completed": False,
                "has_l1_bidder": has_l1,
            }

        return {
            "procurement_id": procurement_id,
            "is_unlocked": True,
            "status": "COMMERCIAL_REVIEW_COMPLETE",
            "blocker_reason": None,
            "technical_freeze_completed": True,
            "financial_evaluation_completed": True,
            "has_l1_bidder": has_l1,
        }

    @classmethod
    async def get_audit_events(cls, procurement_id: str, document_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists audit events for a procurement or specific document."""
        return [
            log for log in _ACTION_STUDIO_AUDIT_LOGS
            if log.get("procurement_id") == procurement_id and (not document_id or log.get("document_id") == document_id)
        ]

    @classmethod
    async def list_draft_versions(cls, draft_id: str) -> List[ActionStudioDocumentVersion]:
        """Lists all version snapshot entries for a draft document."""
        if draft_id not in _ACTION_STUDIO_VERSIONS:
            return []
        return [ActionStudioDocumentVersion.model_validate(v) for v in _ACTION_STUDIO_VERSIONS[draft_id]]

    @classmethod
    async def _record_audit_event(
        cls,
        event_type: str,
        procurement_id: str,
        document_id: str,
        document_type: ActionDocumentType,
        actor: str,
        source_evaluation_references: Dict[str, Any],
        version: int,
        details: Dict[str, Any],
    ) -> None:
        """Records an Action Studio audit event in the global audit trail."""
        event = ActionStudioAuditEvent(
            id=str(uuid.uuid4()),
            event_type=event_type,
            procurement_id=procurement_id,
            document_id=document_id,
            document_type=document_type,
            actor=actor,
            timestamp=datetime.now(timezone.utc),
            source_evaluation_references=source_evaluation_references,
            version=version,
            details=details,
        )
        event_dict = event.model_dump()
        _ACTION_STUDIO_AUDIT_LOGS.append(event_dict)
        logger.info("Recorded Audit Event [%s] for doc %s (Actor: %s)", event_type, document_id, actor)
