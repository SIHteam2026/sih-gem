"""Canonical Clarification Lifecycle and Technical Freeze Service.

Implements Cover 1 Technical Freeze gating, formal bidder shortfall / clarification
cycles, document evidence ingestion for clarifications, and targeted single-requirement
re-evaluation without mutating unrelated findings or making autonomous qualification decisions.
"""

from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException, status

try:
    from app.db.client import (
        get_clarification_db,
        get_procurement_detail_db,
        get_procurement_hierarchy,
        get_submission_detail_db,
        insert_audit_log_db,
        insert_clarification_db,
        insert_document,
        list_clarifications_db,
        update_clarification_db,
        update_procurement_status_db,
        update_submission_freeze_db,
    )
    from app.models.clarification import (
        ClarificationCreate,
        ClarificationDraftRequest,
        ClarificationDraftResponse,
        ClarificationListResponse,
        ClarificationRecord,
        ClarificationResolutionRequest,
        ClarificationResponseInput,
        ClarificationStatus,
        TechnicalFreezeRequest,
        TechnicalFreezeResponse,
    )
    from app.models.procurement import Document, IngestionDocumentInput, ProcurementStatus, TechnicalFreezeStatus
    from app.services.claim_extraction_service import process_document_evidence
    from app.services.master_pipeline import evaluate_canonical_submission_by_id
    from app.services.tender_contract_service import get_tender_evaluation_contract
    from app.rules.verification_engine import canonical_verification_engine
    from app.models.verification import VerificationContext
    from app.services.ai_router import ai_router
except ImportError:
    from db.client import (
        get_clarification_db,
        get_procurement_detail_db,
        get_procurement_hierarchy,
        get_submission_detail_db,
        insert_audit_log_db,
        insert_clarification_db,
        insert_document,
        list_clarifications_db,
        update_clarification_db,
        update_procurement_status_db,
        update_submission_freeze_db,
    )
    from models.clarification import (
        ClarificationCreate,
        ClarificationDraftRequest,
        ClarificationDraftResponse,
        ClarificationListResponse,
        ClarificationRecord,
        ClarificationResolutionRequest,
        ClarificationResponseInput,
        ClarificationStatus,
        TechnicalFreezeRequest,
        TechnicalFreezeResponse,
    )
    from models.procurement import Document, IngestionDocumentInput, ProcurementStatus, TechnicalFreezeStatus
    from services.claim_extraction_service import process_document_evidence
    from services.master_pipeline import evaluate_canonical_submission_by_id
    from services.tender_contract_service import get_tender_evaluation_contract
    from rules.verification_engine import canonical_verification_engine
    from models.verification import VerificationContext
    try:
        from services.ai_router import ai_router
    except ImportError:
        ai_router = None

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Technical Freeze (Cover 1) Operations
# ---------------------------------------------------------------------------
async def freeze_submission_service(
    submission_id: str,
    freeze_request: TechnicalFreezeRequest,
    procurement_id: Optional[str] = None,
) -> TechnicalFreezeResponse:
    """Applies or modifies the Technical Freeze state of a bidder submission."""
    sub_data = await get_submission_detail_db(submission_id)
    if not sub_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bid submission '{submission_id}' not found.",
        )

    resolved_procurement_id = procurement_id or sub_data.get("procurement_id", "")
    now_iso = datetime.now(timezone.utc).isoformat()

    if freeze_request.freeze:
        new_status = TechnicalFreezeStatus.FROZEN
        is_locked = True
        frozen_at = now_iso
        frozen_by = freeze_request.officer_id or "OFFICER"
        freeze_reason = freeze_request.freeze_reason or "Technical evaluation window closed / Cover 1 freeze applied."
        event_type = "TECHNICAL_FREEZE_APPLIED"
        message = f"Bid submission '{submission_id}' has been technically frozen (locked)."
    else:
        new_status = TechnicalFreezeStatus.NOT_FROZEN
        is_locked = False
        frozen_at = None
        frozen_by = None
        freeze_reason = freeze_request.freeze_reason or "Technical freeze unlocked by procurement officer."
        event_type = "TECHNICAL_FREEZE_UNLOCKED"
        message = f"Bid submission '{submission_id}' technical freeze has been unlocked."

    updated_record = await update_submission_freeze_db(
        submission_id=submission_id,
        technical_freeze_status=new_status.value,
        is_locked=is_locked,
        frozen_at=frozen_at,
        frozen_by=frozen_by,
        freeze_reason=freeze_reason,
    )

    await insert_audit_log_db({
        "event_type": event_type,
        "procurement_id": resolved_procurement_id,
        "submission_id": submission_id,
        "tender_id": sub_data.get("tender_id"),
        "bidder_id": sub_data.get("bidder_id"),
        "actor": freeze_request.officer_id or "OFFICER",
        "details": {
            "status": new_status.value,
            "is_locked": is_locked,
            "reason": freeze_reason,
            "timestamp": now_iso,
        },
    })

    # Sync parent procurement status
    if resolved_procurement_id:
        try:
            proc = await get_procurement_detail_db(resolved_procurement_id)
            if proc:
                tenders = proc.get("tenders", []) or []
                all_subs = [s for t in tenders for s in (t.get("submissions", []) or [])]
                all_subs_frozen = all_subs and all(s.get("technical_freeze_status") == TechnicalFreezeStatus.FROZEN.value for s in all_subs)
                from app.services.procurement_lifecycle_service import transition_procurement_state
                target_st = ProcurementStatus.TECHNICAL_FREEZE if all_subs_frozen else ProcurementStatus.TECHNICAL_REVIEW
                try:
                    await transition_procurement_state(
                        procurement_id=resolved_procurement_id,
                        target_status=target_st,
                        actor=freeze_request.officer_id or "OFFICER",
                        reason=f"Submission {submission_id} freeze state updated",
                    )
                except Exception as exc:
                    logger.debug("Procurement status transition skipped: %s", exc)
        except Exception as exc:
            logger.debug("Procurement status sync skipped on freeze: %s", exc)

    return TechnicalFreezeResponse(
        submission_id=submission_id,
        technical_freeze_status=new_status,
        is_locked=is_locked,
        frozen_at=datetime.fromisoformat(frozen_at) if frozen_at else None,
        frozen_by=frozen_by,
        freeze_reason=freeze_reason,
        message=message,
    )


async def get_submission_freeze_status_service(submission_id: str) -> TechnicalFreezeResponse:
    """Retrieves current Technical Freeze and lock state for a submission."""
    sub_data = await get_submission_detail_db(submission_id)
    if not sub_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bid submission '{submission_id}' not found.",
        )

    freeze_status_str = sub_data.get("technical_freeze_status", TechnicalFreezeStatus.NOT_FROZEN.value)
    try:
        freeze_status = TechnicalFreezeStatus(freeze_status_str)
    except ValueError:
        freeze_status = TechnicalFreezeStatus.NOT_FROZEN

    is_locked = bool(sub_data.get("is_locked", False))
    frozen_at_raw = sub_data.get("frozen_at")
    frozen_at = datetime.fromisoformat(frozen_at_raw) if frozen_at_raw else None
    frozen_by = sub_data.get("frozen_by")
    freeze_reason = sub_data.get("freeze_reason")

    return TechnicalFreezeResponse(
        submission_id=submission_id,
        technical_freeze_status=freeze_status,
        is_locked=is_locked,
        frozen_at=frozen_at,
        frozen_by=frozen_by,
        freeze_reason=freeze_reason,
        message=f"Submission is currently {freeze_status.value} (is_locked={is_locked}).",
    )


# ---------------------------------------------------------------------------
# AI Clarification Draft Generation
# ---------------------------------------------------------------------------
async def generate_clarification_draft_service(
    payload: ClarificationDraftRequest,
) -> ClarificationDraftResponse:
    """Generates an evidence-grounded draft clarification notice for procurement officer review and editing.
    
    Safety:
    - Never makes autonomous qualification decisions.
    - Strictly marked as a draft.
    - Grounded only in existing tender requirement, bidder, and observed findings.
    - Uses configured Gemini model with fallback to Groq AI router and deterministic evidence fallback.
    """
    sub_data = await get_submission_detail_db(payload.submission_id)
    if not sub_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bid submission '{payload.submission_id}' not found.",
        )

    proc = await get_procurement_detail_db(payload.procurement_id) or {}
    tender_ref = proc.get("external_reference") or sub_data.get("tender_id") or "TENDER-REF"
    bidder_obj = sub_data.get("bidder") or {}
    bidder_name = bidder_obj.get("legal_name") or "Participating Bidder"

    # Fetch requirement details
    tender_id = sub_data.get("tender_id") or (proc.get("tenders", [{}])[0].get("id") if proc.get("tenders") else "TENDER-DEFAULT")
    req_title = payload.requirement_id
    req_desc = ""
    evidence_req = ""
    try:
        contract_pkg = await get_tender_evaluation_contract(str(tender_id))
        target_req = next((r for r in contract_pkg.requirements if getattr(r, "requirement_id", None) == payload.requirement_id or (isinstance(r, dict) and r.get("requirement_id") == payload.requirement_id)), None)
        if target_req:
            req_title = getattr(target_req, "title", None) or getattr(target_req, "description", payload.requirement_id)[:80]
            req_desc = getattr(target_req, "description", "")
            evidence_req = ", ".join(getattr(target_req, "evidence_required", []) or [])
    except Exception as e:
        logger.debug("Tender contract fetch for drafting: %s", e)

    # Collect existing evidence quotes from submission
    raw_docs = sub_data.get("documents", []) or []
    doc_refs = [d.get("filename") for d in raw_docs if isinstance(d, dict) and d.get("filename")]

    # Evaluate current finding to determine specific observed shortfall
    eval_res = {}
    try:
        eval_res = await evaluate_canonical_submission_by_id(submission_id=payload.submission_id, tender_id_or_ref=str(tender_id))
    except Exception as exc:
        logger.debug("Evaluation fetch for draft: %s", exc)

    observed_shortfall = "Mandatory documentary proof or certificate requires officer clarification."
    req_res_list = eval_res.get("requirement_results", [])
    for r_res in req_res_list:
        r_id = getattr(r_res, "requirement_id", None) or (r_res.get("requirement_id") if isinstance(r_res, dict) else None)
        if r_id == payload.requirement_id:
            reason = getattr(r_res, "reason", None) or (r_res.get("reason") if isinstance(r_res, dict) else None)
            if reason:
                observed_shortfall = reason
            break

    # Build prompt for grounded draft generation
    prompt = f"""You are an assistant to a government procurement officer on GeM.
Draft a formal, objective, and professional Shortfall / Clarification Notice to a bidder.
DO NOT make a final qualification decision.
DO NOT fabricate evidence, fake government verifications, or arbitrary legal conclusions.
DO NOT invent deadlines.

TENDER REFERENCE: {tender_ref}
BIDDER NAME: {bidder_name}
REQUIREMENT ID: {payload.requirement_id}
REQUIREMENT TITLE: {req_title}
REQUIREMENT DESCRIPTION: {req_desc}
REQUIRED EVIDENCE: {evidence_req}
SUBMISSION DOCUMENTS PROVIDED: {json.dumps(doc_refs)}
OBSERVED SHORTFALL / GAP: {observed_shortfall}
OFFICER CUSTOM INSTRUCTION: {payload.custom_instruction or 'None'}

Return a JSON object with this EXACT structure:
{{
  "subject": "Formal Shortfall Notice / Clarification Request - [Tender Ref] - [Requirement ID]",
  "observed_shortfall": "Clear and factual description of the observed discrepancy or missing evidence based strictly on the requirement.",
  "requested_clarification": "Specific document(s), certified undertakings, or factual clarification requested from the bidder."
}}
"""

    draft_subject = f"Shortfall / Clarification Notice: {tender_ref} - {payload.requirement_id}"
    draft_shortfall = observed_shortfall
    draft_requested = f"Please provide documentary evidence and clarification satisfying {req_title}."

    # Attempt 1: Gemini API with configured model
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    gemini_key = os.getenv("GEMINI_API_KEY")
    generation_done = False

    if genai and gemini_key:
        try:
            client = genai.Client(api_key=gemini_key)
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            )
            resp = client.models.generate_content(
                model=gemini_model,
                contents=prompt,
                config=config,
            )
            if resp and resp.text:
                parsed = json.loads(resp.text.strip())
                if isinstance(parsed, dict):
                    draft_subject = parsed.get("subject", draft_subject)
                    draft_shortfall = parsed.get("observed_shortfall", draft_shortfall)
                    draft_requested = parsed.get("requested_clarification", draft_requested)
                    generation_done = True
        except Exception as gemini_err:
            logger.warning("Gemini draft generation failed (%s): %s", gemini_model, gemini_err)

    # Attempt 2: Groq AI Router Fallback
    if not generation_done and ai_router:
        try:
            parsed = await ai_router.generate_json(prompt=prompt, temperature=0.1)
            if isinstance(parsed, dict):
                draft_subject = parsed.get("subject", draft_subject)
                draft_shortfall = parsed.get("observed_shortfall", draft_shortfall)
                draft_requested = parsed.get("requested_clarification", draft_requested)
                generation_done = True
        except Exception as groq_err:
            logger.warning("Groq AI Router draft generation failed: %s", groq_err)

    # Record audit log
    await insert_audit_log_db({
        "event_type": "CLARIFICATION_DRAFT_GENERATED",
        "procurement_id": payload.procurement_id,
        "submission_id": payload.submission_id,
        "actor": "AI_DRAFT_ASSISTANT",
        "details": {
            "requirement_id": payload.requirement_id,
            "bidder_name": bidder_name,
            "subject": draft_subject,
            "is_draft": True,
        },
    })

    return ClarificationDraftResponse(
        subject=draft_subject,
        recipient_bidder=bidder_name,
        tender_reference=str(tender_ref),
        requirement_id=payload.requirement_id,
        requirement_title=req_title,
        observed_shortfall=draft_shortfall,
        requested_clarification=draft_requested,
        suggested_deadline_days=None,
        supporting_evidence_references=doc_refs,
        is_draft=True,
        decision_authority="HUMAN_PROCUREMENT_OFFICER",
    )


# ---------------------------------------------------------------------------
# Clarification Lifecycle Operations
# ---------------------------------------------------------------------------
async def create_clarification_service(
    payload: ClarificationCreate,
    procurement_id: Optional[str] = None,
) -> ClarificationRecord:
    """Initiates a formal shortfall / clarification request linked to a specific requirement and finding."""
    sub_data = await get_submission_detail_db(payload.submission_id)
    if not sub_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target bid submission '{payload.submission_id}' not found.",
        )

    # Check lock / freeze state
    if sub_data.get("is_locked") or sub_data.get("technical_freeze_status") == TechnicalFreezeStatus.FROZEN.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot create clarification on technically frozen submission '{payload.submission_id}'. Unlock submission first.",
        )

    resolved_proc_id = payload.procurement_id or sub_data.get("procurement_id") or procurement_id
    if not resolved_proc_id:
        resolved_proc_id = "PROC-DEFAULT"

    # Validate procurement state - must be in TECHNICAL_REVIEW or CLARIFICATION_OPEN
    proc = await get_procurement_detail_db(resolved_proc_id)
    if proc:
        proc_st = proc.get("status")
        if proc_st in (ProcurementStatus.TECHNICAL_FREEZE.value, ProcurementStatus.COVER_2_READY.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot initiate clarifications when procurement is in status '{proc_st}'.",
            )
        if proc_st not in (ProcurementStatus.TECHNICAL_REVIEW.value, ProcurementStatus.CLARIFICATION_OPEN.value, ProcurementStatus.READY_FOR_TECHNICAL_SCRUTINY.value, ProcurementStatus.READY.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Clarification can only be opened from TECHNICAL_REVIEW or CLARIFICATION_OPEN state (currently '{proc_st}').",
            )

    # Idempotency check: check if an identical open clarification already exists for this submission and requirement
    existing_all = await list_clarifications_db(submission_id=payload.submission_id, requirement_id=payload.requirement_id)
    existing_open = [c for c in existing_all if c.get("status") in (ClarificationStatus.OPEN.value, ClarificationStatus.RESPONDED.value, ClarificationStatus.UNDER_REVIEW.value)]
    if existing_open:
        return ClarificationRecord.model_validate(existing_open[0])

    resolved_tender_id = payload.tender_id or sub_data.get("tender_id") or "TENDER-DEFAULT"
    resolved_bidder_id = payload.bidder_id or sub_data.get("bidder_id") or "BIDDER-DEFAULT"

    clarification_id = str(uuid.uuid4())
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    audit_entry = {
        "event": "CLARIFICATION_CREATED",
        "actor": payload.created_by or "OFFICER",
        "timestamp": now_iso,
        "details": {
            "requirement_id": payload.requirement_id,
            "originating_finding_id": payload.originating_finding_id,
            "question": payload.question,
            "due_at": payload.due_at.isoformat() if payload.due_at else None,
        },
    }

    record_dict = {
        "id": clarification_id,
        "procurement_id": resolved_proc_id,
        "tender_id": resolved_tender_id,
        "bidder_id": resolved_bidder_id,
        "submission_id": payload.submission_id,
        "requirement_id": payload.requirement_id,
        "originating_finding_id": payload.originating_finding_id,
        "question": payload.question,
        "status": ClarificationStatus.OPEN.value,
        "created_at": now_iso,
        "created_by": payload.created_by or "OFFICER",
        "due_at": payload.due_at.isoformat() if payload.due_at else None,
        "response_text": None,
        "response_documents": [],
        "responded_at": None,
        "responded_by": None,
        "re_evaluation_status": None,
        "resulting_finding": None,
        "audit_history": [audit_entry],
    }

    inserted = await insert_clarification_db(record_dict)

    await insert_audit_log_db({
        "event_type": "CLARIFICATION_CREATED",
        "procurement_id": resolved_proc_id,
        "submission_id": payload.submission_id,
        "tender_id": resolved_tender_id,
        "bidder_id": resolved_bidder_id,
        "clarification_id": clarification_id,
        "actor": payload.created_by or "OFFICER",
        "details": audit_entry["details"],
    })

    if resolved_proc_id:
        try:
            if proc and proc.get("status") in (ProcurementStatus.TECHNICAL_REVIEW.value, ProcurementStatus.READY_FOR_TECHNICAL_SCRUTINY.value, ProcurementStatus.READY.value):
                from app.services.procurement_lifecycle_service import transition_procurement_state
                await transition_procurement_state(
                    procurement_id=resolved_proc_id,
                    target_status=ProcurementStatus.CLARIFICATION_OPEN,
                    actor=payload.created_by or "OFFICER",
                    reason=f"Clarification created on requirement {payload.requirement_id}",
                )
        except Exception as exc:
            logger.debug("Procurement status transition skipped on clarification create: %s", exc)

    return ClarificationRecord.model_validate(inserted)


async def respond_to_clarification_service(
    clarification_id: str,
    response_payload: ClarificationResponseInput,
) -> ClarificationRecord:
    """Submits bidder response text and attaches supporting evidence proofs to the clarification."""
    existing = await get_clarification_db(clarification_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clarification request '{clarification_id}' not found.",
        )

    current_status = existing.get("status")
    if current_status in (ClarificationStatus.RESOLVED.value, ClarificationStatus.CANCELLED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Clarification '{clarification_id}' is already {current_status} and cannot receive further responses.",
        )

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    # Ingest newly attached clarification evidence documents
    ingested_docs: List[Dict[str, Any]] = []
    for doc_input in response_payload.documents:
        doc_id = str(uuid.uuid4())
        doc_dict = {
            "id": doc_id,
            "procurement_id": existing.get("procurement_id"),
            "tender_id": existing.get("tender_id"),
            "bid_submission_id": existing.get("submission_id"),
            "filename": doc_input.filename,
            "document_type": doc_input.document_type.value if hasattr(doc_input.document_type, "value") else (doc_input.document_type or "OTHER"),
            "mime_type": doc_input.mime_type or "application/pdf",
            "file_size": doc_input.file_size,
            "storage_path": doc_input.storage_path,
            "content_text": doc_input.content_text or json.dumps([{"page": 1, "text": f"Clarification proof: {doc_input.filename}"}]),
            "processing_status": "COMPLETED",
            "allow_locked": True,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        await insert_document(doc_dict)
        ingested_docs.append(doc_dict)

    existing_docs = existing.get("response_documents", []) or []
    all_response_docs = existing_docs + ingested_docs

    audit_entry = {
        "event": "CLARIFICATION_RESPONSE_SUBMITTED",
        "actor": response_payload.responded_by or "BIDDER",
        "timestamp": now_iso,
        "details": {
            "response_text": response_payload.response_text,
            "attached_document_count": len(ingested_docs),
            "document_names": [d["filename"] for d in ingested_docs],
        },
    }

    existing_audit = existing.get("audit_history", []) or []
    updated_audit = existing_audit + [audit_entry]

    update_payload = {
        "response_text": response_payload.response_text,
        "response_documents": all_response_docs,
        "responded_at": now_iso,
        "responded_by": response_payload.responded_by or "BIDDER",
        "status": ClarificationStatus.RESPONDED.value,
        "audit_history": updated_audit,
    }

    updated = await update_clarification_db(clarification_id, update_payload)

    await insert_audit_log_db({
        "event_type": "CLARIFICATION_RESPONSE_SUBMITTED",
        "procurement_id": existing.get("procurement_id"),
        "submission_id": existing.get("submission_id"),
        "tender_id": existing.get("tender_id"),
        "bidder_id": existing.get("bidder_id"),
        "clarification_id": clarification_id,
        "actor": response_payload.responded_by or "BIDDER",
        "details": audit_entry["details"],
    })

    return ClarificationRecord.model_validate(updated or {**existing, **update_payload})


async def re_evaluate_clarification_service(
    clarification_id: str,
) -> ClarificationRecord:
    """Executes targeted re-evaluation for the single requirement affected by the clarification response."""
    clarification = await get_clarification_db(clarification_id)
    if not clarification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clarification '{clarification_id}' not found.",
        )

    c_status = clarification.get("status")
    if c_status in (ClarificationStatus.CANCELLED.value, ClarificationStatus.REJECTED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot execute re-evaluation on clarification '{clarification_id}' in terminal state '{c_status}'.",
        )

    proc_id = clarification.get("procurement_id")
    if proc_id:
        try:
            from app.services.procurement_lifecycle_service import transition_procurement_state
            await transition_procurement_state(
                procurement_id=proc_id,
                target_status=ProcurementStatus.RE_EVALUATION_RUNNING,
                actor="CANONICAL_ENGINE",
                reason=f"Targeted re-evaluation started for clarification {clarification_id}",
            )
        except Exception as exc:
            logger.debug("Procurement status transition skipped on re-eval start: %s", exc)

    submission_id = clarification.get("submission_id")
    target_req_id = clarification.get("requirement_id")
    tender_id = clarification.get("tender_id")
    bidder_id = clarification.get("bidder_id")

    sub_data = await get_submission_detail_db(submission_id)
    if not sub_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Associated bid submission '{submission_id}' not found.",
        )

    tender_contract_pkg = await get_tender_evaluation_contract(str(tender_id))
    requirements = tender_contract_pkg.requirements

    # Find the target requirement
    target_req = next((r for r in requirements if getattr(r, "requirement_id", None) == target_req_id or (isinstance(r, dict) and r.get("requirement_id") == target_req_id)), None)

    # Gather evidence from all base submission docs + clarification response docs
    base_docs = sub_data.get("documents", []) or []
    clarification_docs = clarification.get("response_documents", []) or []
    all_raw_docs = base_docs + clarification_docs

    all_claims = []
    all_observations = []

    for raw_doc in all_raw_docs:
        if isinstance(raw_doc, Document):
            doc_model = raw_doc
        elif isinstance(raw_doc, dict):
            doc_model = Document(
                id=str(raw_doc.get("id") or uuid.uuid4()),
                procurement_id=str(raw_doc.get("procurement_id") or clarification.get("procurement_id", "")),
                tender_id=str(raw_doc.get("tender_id") or tender_id),
                bid_submission_id=submission_id,
                filename=raw_doc.get("filename", "evidence.pdf"),
                document_type=raw_doc.get("document_type") or "OTHER",
                mime_type=raw_doc.get("mime_type", "application/pdf"),
                file_size=raw_doc.get("file_size"),
                storage_path=raw_doc.get("storage_path"),
                content_text=raw_doc.get("content_text") or (json.dumps([{"page": 1, "text": raw_doc["text"]}]) if "text" in raw_doc else None),
                processing_status=raw_doc.get("processing_status", "COMPLETED"),
            )
        else:
            continue

        extracted = process_document_evidence(
            doc=doc_model,
            tender_context={"bidder_id": bidder_id, "bid_submission_id": submission_id},
        )
        all_claims.extend(extracted.get("claims", []))
        all_observations.extend(extracted.get("observations", []))

    # Evaluate target requirement using canonical verification engine
    target_req_list = [target_req] if target_req else requirements
    v_context = VerificationContext(
        procurement_id=clarification.get("procurement_id"),
        tender_id=tender_id,
        requirements=target_req_list,
        bidders=[sub_data.get("bidder", {"id": bidder_id, "legal_name": "Bidder"})] if sub_data.get("bidder") else [{"id": bidder_id, "legal_name": "Bidder"}],
        submissions=[{"id": submission_id, "bidder_id": bidder_id}],
        documents=all_raw_docs,
        claims=all_claims,
        observations=all_observations,
        external_verifications={},
        extra_context={"clarification_id": clarification_id, "clarification_response": clarification.get("response_text")},
    )

    report = await canonical_verification_engine.run_verification(v_context)

    # Locate finding for target requirement
    req_findings = report.findings_by_requirement.get(target_req_id, [])
    if not req_findings:
        for f_list in report.findings_by_layer.values():
            for f in f_list:
                if f.requirement_id == target_req_id:
                    req_findings.append(f)
    target_finding = req_findings[0] if req_findings else None

    resulting_finding_dict = target_finding.model_dump() if target_finding else {
        "finding_id": str(uuid.uuid4()),
        "requirement_id": target_req_id,
        "status": "REVIEW" if not clarification.get("response_documents") else "REVIEW",
        "description": "Targeted re-evaluation completed with provided clarification evidence.",
        "layer": "EVIDENCE_EXTRACTION",
        "severity": "INFO",
        "review_required": True,
    }

    now_iso = datetime.now(timezone.utc).isoformat()
    audit_entry = {
        "event": "TARGETED_REEVALUATION_TRIGGERED",
        "actor": "CANONICAL_ENGINE",
        "timestamp": now_iso,
        "details": {
            "requirement_id": target_req_id,
            "resulting_status": resulting_finding_dict.get("status"),
            "review_required": resulting_finding_dict.get("review_required"),
            "finding_summary": resulting_finding_dict.get("description"),
        },
    }

    existing_audit = clarification.get("audit_history", []) or []
    updated_audit = existing_audit + [audit_entry]

    update_payload = {
        "status": ClarificationStatus.RESOLVED.value,
        "re_evaluation_status": "RESOLVED",
        "resulting_finding": resulting_finding_dict,
        "audit_history": updated_audit,
    }

    updated = await update_clarification_db(clarification_id, update_payload)

    await insert_audit_log_db({
        "event_type": "FINDING_UPDATED_POST_CLARIFICATION",
        "procurement_id": clarification.get("procurement_id"),
        "submission_id": submission_id,
        "tender_id": tender_id,
        "bidder_id": bidder_id,
        "clarification_id": clarification_id,
        "actor": "CANONICAL_ENGINE",
        "details": audit_entry["details"],
    })

    if proc_id:
        try:
            from app.services.procurement_lifecycle_service import transition_procurement_state
            all_c = await list_clarifications_db(procurement_id=proc_id)
            has_open = any(c.get("status") in (ClarificationStatus.OPEN.value, ClarificationStatus.RESPONDED.value, ClarificationStatus.UNDER_REVIEW.value, ClarificationStatus.REQUIRES_FURTHER_CLARIFICATION.value) for c in all_c if c.get("id") != clarification_id)
            next_status = ProcurementStatus.CLARIFICATION_OPEN if has_open else ProcurementStatus.TECHNICAL_REVIEW
            await transition_procurement_state(
                procurement_id=proc_id,
                target_status=next_status,
                actor="CANONICAL_ENGINE",
                reason=f"Re-evaluation concluded for clarification {clarification_id}",
            )
        except Exception as exc:
            logger.debug("Procurement status transition skipped on re-eval end: %s", exc)

    return ClarificationRecord.model_validate(updated or {**clarification, **update_payload})


async def resolve_clarification_service(
    clarification_id: str,
    payload: ClarificationResolutionRequest,
) -> ClarificationRecord:
    """Explicitly resolves, requests further info on, or rejects a clarification record with an audit event."""
    clarification = await get_clarification_db(clarification_id)
    if not clarification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clarification '{clarification_id}' not found.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    actor = payload.officer_id or "OFFICER"
    target_status = payload.resolution_status

    audit_entry = {
        "event": "CLARIFICATION_RESOLVED",
        "actor": actor,
        "timestamp": now_iso,
        "details": {
            "resolution_status": target_status.value,
            "resolution_notes": payload.resolution_notes,
        },
    }

    existing_audit = clarification.get("audit_history", []) or []
    updated_audit = existing_audit + [audit_entry]

    update_payload = {
        "status": target_status.value,
        "audit_history": updated_audit,
    }

    updated = await update_clarification_db(clarification_id, update_payload)

    proc_id = clarification.get("procurement_id")
    await insert_audit_log_db({
        "event_type": "CLARIFICATION_RESOLVED",
        "procurement_id": proc_id,
        "submission_id": clarification.get("submission_id"),
        "tender_id": clarification.get("tender_id"),
        "bidder_id": clarification.get("bidder_id"),
        "clarification_id": clarification_id,
        "actor": actor,
        "details": audit_entry["details"],
    })

    if proc_id:
        try:
            from app.services.procurement_lifecycle_service import transition_procurement_state
            all_c = await list_clarifications_db(procurement_id=proc_id)
            has_open = any(
                (target_status.value if c.get("id") == clarification_id else c.get("status")) in (
                    ClarificationStatus.OPEN.value,
                    ClarificationStatus.RESPONDED.value,
                    ClarificationStatus.UNDER_REVIEW.value,
                    ClarificationStatus.REQUIRES_FURTHER_CLARIFICATION.value,
                )
                for c in all_c
            )
            next_status = ProcurementStatus.CLARIFICATION_OPEN if has_open else ProcurementStatus.TECHNICAL_REVIEW
            await transition_procurement_state(
                procurement_id=proc_id,
                target_status=next_status,
                actor=actor,
                reason=f"Clarification {clarification_id} resolved with status {target_status.value}",
            )
        except Exception as exc:
            logger.debug("Procurement status transition skipped on clarification resolution: %s", exc)

    return ClarificationRecord.model_validate(updated or {**clarification, **update_payload})


async def list_clarifications_service(
    procurement_id: Optional[str] = None,
    submission_id: Optional[str] = None,
    bidder_id: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> ClarificationListResponse:
    """Lists clarification records matching the specified filters."""
    records = await list_clarifications_db(
        procurement_id=procurement_id,
        submission_id=submission_id,
        bidder_id=bidder_id,
        status=status_filter,
    )
    clarifications = [ClarificationRecord.model_validate(r) for r in records]
    return ClarificationListResponse(
        total=len(clarifications),
        clarifications=clarifications,
    )


async def get_clarification_detail_service(clarification_id: str) -> ClarificationRecord:
    """Retrieves a single clarification record by ID."""
    record = await get_clarification_db(clarification_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clarification request '{clarification_id}' was not found.",
        )
    return ClarificationRecord.model_validate(record)
