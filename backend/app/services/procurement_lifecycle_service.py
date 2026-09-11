"""Canonical Procurement Lifecycle & Technical Scrutiny Orchestration Service.

Integrates the multi-layer verification pipeline (L1-L6) into an authoritative officer-facing
backend workflow with deterministic state transitions, audit logging, and Cover 2 readiness gating.
"""

from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from fastapi import HTTPException, status

try:
    from app.db.client import (
        get_audit_logs_db,
        get_bid_evaluations,
        get_clarification_db,
        get_procurement_detail_db,
        get_procurement_processing_metadata_db,
        get_submission_detail_db,
        get_tender_detail_db,
        get_tender_requirements,
        insert_audit_log_db,
        insert_bid_evaluation,
        list_clarifications_db,
        update_procurement_status_db,
        update_submission_freeze_db,
    )
    from app.models.clarification import ClarificationRecord, ClarificationStatus
    from app.models.evaluation import ComplianceState
    from app.models.evidence import BidderClaim, EvidenceObservation
    from app.models.procurement import (
        Cover2ReadinessResponse,
        Cover2ReadinessSummary,
        Document,
        OfficerBidderTechnicalSummary,
        OfficerClarificationSummary,
        OfficerFindingSummary,
        OfficerFreezeSummary,
        OfficerRequirementSummary,
        OfficerObservationCreate,
        OfficerObservationRecord,
        OfficerTechnicalCheckPresentation,
        OfficerTechnicalLayerPresentation,
        ProcurementStatus,
        ProcurementTechnicalReviewResponse,
        TechnicalFreezeStatus,
        TechnicalScrutinyRunResponse,
    )
    from app.models.financial import ProcurementFinancialEvaluationResponse
    from app.models.tender_contract import RequirementEvaluationContract, TenderEvaluationContract
    from app.models.verification import (
        FindingSeverity,
        VerificationContext,
        VerificationEngineReport,
        VerificationFinding,
        VerificationLayer,
    )
    from app.rules.verification_engine import canonical_verification_engine
    from app.services.claim_extraction_service import process_document_evidence
    from app.services.master_pipeline import evaluate_canonical_submission_by_id
    from app.services.tender_contract_service import get_tender_evaluation_contract
except ImportError:
    from db.client import (
        get_audit_logs_db,
        get_bid_evaluations,
        get_clarification_db,
        get_procurement_detail_db,
        get_procurement_processing_metadata_db,
        get_submission_detail_db,
        get_tender_detail_db,
        get_tender_requirements,
        insert_audit_log_db,
        insert_bid_evaluation,
        list_clarifications_db,
        update_procurement_status_db,
        update_submission_freeze_db,
    )
    from models.clarification import ClarificationRecord, ClarificationStatus
    from models.evaluation import ComplianceState
    from models.evidence import BidderClaim, EvidenceObservation
    from models.financial import ProcurementFinancialEvaluationResponse
    from models.procurement import (
        Cover2ReadinessResponse,
        Cover2ReadinessSummary,
        Document,
        OfficerBidderTechnicalSummary,
        OfficerClarificationSummary,
        OfficerFindingSummary,
        OfficerFreezeSummary,
        OfficerRequirementSummary,
        OfficerTechnicalCheckPresentation,
        OfficerTechnicalLayerPresentation,
        ProcurementStatus,
        ProcurementTechnicalReviewResponse,
        TechnicalFreezeStatus,
        TechnicalScrutinyRunResponse,
    )
    from models.tender_contract import RequirementEvaluationContract, TenderEvaluationContract
    from models.verification import (
        FindingSeverity,
        VerificationContext,
        VerificationEngineReport,
        VerificationFinding,
        VerificationLayer,
    )
    from rules.verification_engine import canonical_verification_engine
    from services.claim_extraction_service import process_document_evidence
    from services.master_pipeline import evaluate_canonical_submission_by_id
    from services.tender_contract_service import get_tender_evaluation_contract

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Legal State Machine Transitions
# ---------------------------------------------------------------------------
LEGAL_PROCUREMENT_TRANSITIONS: Dict[ProcurementStatus, Set[ProcurementStatus]] = {
    ProcurementStatus.IMPORTED: {
        ProcurementStatus.READY_FOR_TECHNICAL_SCRUTINY,
        ProcurementStatus.TECHNICAL_SCRUTINY_RUNNING,
        ProcurementStatus.READY,
        ProcurementStatus.PROCESSING,
        ProcurementStatus.FAILED,
    },
    ProcurementStatus.READY_FOR_TECHNICAL_SCRUTINY: {
        ProcurementStatus.TECHNICAL_SCRUTINY_RUNNING,
        ProcurementStatus.FAILED,
    },
    ProcurementStatus.TECHNICAL_SCRUTINY_RUNNING: {
        ProcurementStatus.TECHNICAL_REVIEW,
        ProcurementStatus.FAILED,
    },
    ProcurementStatus.TECHNICAL_REVIEW: {
        ProcurementStatus.TECHNICAL_SCRUTINY_RUNNING,
        ProcurementStatus.CLARIFICATION_OPEN,
        ProcurementStatus.TECHNICAL_FREEZE,
        ProcurementStatus.COVER_2_READY,
        ProcurementStatus.FINANCIAL_EVALUATION_RUNNING,
        ProcurementStatus.FAILED,
    },
    ProcurementStatus.CLARIFICATION_OPEN: {
        ProcurementStatus.RE_EVALUATION_RUNNING,
        ProcurementStatus.TECHNICAL_REVIEW,
        ProcurementStatus.TECHNICAL_FREEZE,
        ProcurementStatus.TECHNICAL_SCRUTINY_RUNNING,
        ProcurementStatus.FAILED,
    },
    ProcurementStatus.RE_EVALUATION_RUNNING: {
        ProcurementStatus.TECHNICAL_REVIEW,
        ProcurementStatus.CLARIFICATION_OPEN,
        ProcurementStatus.FAILED,
    },
    ProcurementStatus.TECHNICAL_FREEZE: {
        ProcurementStatus.COVER_2_READY,
        ProcurementStatus.FINANCIAL_EVALUATION_RUNNING,
        ProcurementStatus.TECHNICAL_REVIEW,
        ProcurementStatus.FAILED,
    },
    ProcurementStatus.COVER_2_READY: {
        ProcurementStatus.FINANCIAL_EVALUATION_RUNNING,
        ProcurementStatus.FINANCIAL_REVIEW,
        ProcurementStatus.L1_DETERMINED,
        ProcurementStatus.TECHNICAL_FREEZE,
        ProcurementStatus.TECHNICAL_REVIEW,
        ProcurementStatus.FAILED,
    },
    ProcurementStatus.FINANCIAL_EVALUATION_RUNNING: {
        ProcurementStatus.FINANCIAL_REVIEW,
        ProcurementStatus.L1_DETERMINED,
        ProcurementStatus.COVER_2_READY,
        ProcurementStatus.FAILED,
    },
    ProcurementStatus.FINANCIAL_REVIEW: {
        ProcurementStatus.FINANCIAL_EVALUATION_RUNNING,
        ProcurementStatus.L1_DETERMINED,
        ProcurementStatus.COVER_2_READY,
        ProcurementStatus.FAILED,
    },
    ProcurementStatus.L1_DETERMINED: {
        ProcurementStatus.FINANCIAL_EVALUATION_RUNNING,
        ProcurementStatus.FINANCIAL_REVIEW,
        ProcurementStatus.COVER_2_READY,
        ProcurementStatus.FAILED,
    },
    ProcurementStatus.FAILED: {
        ProcurementStatus.READY_FOR_TECHNICAL_SCRUTINY,
        ProcurementStatus.TECHNICAL_SCRUTINY_RUNNING,
        ProcurementStatus.TECHNICAL_REVIEW,
        ProcurementStatus.COVER_2_READY,
    },
    # Aliases
    ProcurementStatus.READY: {
        ProcurementStatus.READY_FOR_TECHNICAL_SCRUTINY,
        ProcurementStatus.TECHNICAL_SCRUTINY_RUNNING,
        ProcurementStatus.TECHNICAL_REVIEW,
        ProcurementStatus.PROCESSING,
        ProcurementStatus.FAILED,
    },
    ProcurementStatus.PROCESSING: {
        ProcurementStatus.READY_FOR_TECHNICAL_SCRUTINY,
        ProcurementStatus.TECHNICAL_SCRUTINY_RUNNING,
        ProcurementStatus.TECHNICAL_REVIEW,
        ProcurementStatus.READY,
        ProcurementStatus.FAILED,
    },
}


def validate_procurement_state_transition(
    current_status: ProcurementStatus,
    target_status: ProcurementStatus,
) -> bool:
    """Validates if transitioning from current_status to target_status is permitted."""
    if current_status == target_status:
        return True
    allowed = LEGAL_PROCUREMENT_TRANSITIONS.get(current_status, set())
    return target_status in allowed


async def transition_procurement_state(
    procurement_id: str,
    target_status: ProcurementStatus,
    actor: str = "PROCUREMENT_OFFICER",
    reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Authoritatively transitions procurement lifecycle state and logs an immutable audit event."""
    proc = await get_procurement_detail_db(procurement_id)
    if not proc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Procurement workspace '{procurement_id}' was not found.",
        )

    raw_current = proc.get("status", ProcurementStatus.IMPORTED.value)
    try:
        current_status = ProcurementStatus(raw_current)
    except ValueError:
        current_status = ProcurementStatus.IMPORTED

    if not validate_procurement_state_transition(current_status, target_status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Illegal state transition from '{current_status.value}' to '{target_status.value}' "
                f"for procurement '{procurement_id}'."
            ),
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    processing_metadata = proc.get("processing_metadata") or {}
    processing_metadata["last_status_transition"] = {
        "from_status": current_status.value,
        "to_status": target_status.value,
        "actor": actor,
        "reason": reason,
        "timestamp": now_iso,
    }
    if metadata:
        processing_metadata.update(metadata)

    updated = await update_procurement_status_db(
        procurement_id=procurement_id,
        status=target_status.value,
        processing_metadata=processing_metadata,
    )

    await insert_audit_log_db({
        "event_type": "PROCUREMENT_STATE_TRANSITION",
        "procurement_id": procurement_id,
        "actor": actor,
        "details": {
            "from_status": current_status.value,
            "to_status": target_status.value,
            "reason": reason,
            "timestamp": now_iso,
            "metadata": metadata or {},
        },
    })

    return updated or {**proc, "status": target_status.value}


# ---------------------------------------------------------------------------
# Authoritative Technical Scrutiny Command
# ---------------------------------------------------------------------------
async def run_technical_scrutiny_command(
    procurement_id: str,
    actor: str = "PROCUREMENT_OFFICER",
    force: bool = False,
    notes: Optional[str] = None,
) -> TechnicalScrutinyRunResponse:
    """Executes the single authoritative Technical Scrutiny pipeline (L1-L6) across all submissions."""
    start_time = time.perf_counter()
    proc = await get_procurement_detail_db(procurement_id)
    if not proc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Procurement workspace '{procurement_id}' was not found.",
        )

    raw_current = proc.get("status", ProcurementStatus.IMPORTED.value)
    try:
        current_status = ProcurementStatus(raw_current)
    except ValueError:
        current_status = ProcurementStatus.IMPORTED

    # Check effective technical scrutiny deadline.
    # In demo mode, demo_effective_deadline takes precedence over the real tender deadline.
    tenders = proc.get("tenders", []) or []
    if not tenders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Technical scrutiny cannot be executed: no tender specification document found.",
        )

    submission_deadline = tenders[0].get("submission_deadline")
    demo_effective_deadline = tenders[0].get("demo_effective_deadline")
    gate_deadline_str = demo_effective_deadline or submission_deadline

    if not gate_deadline_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Technical scrutiny cannot be executed: the submission deadline is not established.",
        )

    deadline_dt = datetime.fromisoformat(gate_deadline_str.replace("Z", "+00:00"))

    if datetime.now(timezone.utc) < deadline_dt and not force:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Technical scrutiny is locked: the submission deadline has not yet passed.",
        )

    # Transition to TECHNICAL_SCRUTINY_RUNNING
    await transition_procurement_state(
        procurement_id=procurement_id,
        target_status=ProcurementStatus.TECHNICAL_SCRUTINY_RUNNING,
        actor=actor,
        reason=notes or "Initiating authoritative technical scrutiny pipeline (L1-L6).",
    )

    await insert_audit_log_db({
        "event_type": "TECHNICAL_SCRUTINY_STARTED",
        "procurement_id": procurement_id,
        "actor": actor,
        "details": {"force": force, "notes": notes},
    })

    # Collect tenders, requirements, bidders, submissions, and documents
    tenders = proc.get("tenders", []) or []
    all_requirements: List[Any] = []
    all_bidders: List[Dict[str, Any]] = []
    all_submissions: List[Dict[str, Any]] = []
    all_documents: List[Any] = list(proc.get("documents", []) or [])

    tender_ids: List[str] = []
    for t in tenders:
        t_id = str(t.get("id"))
        tender_ids.append(t_id)
        t_docs = t.get("documents", []) or []
        all_documents.extend(t_docs)

        # Requirements
        try:
            contract_pkg = await get_tender_evaluation_contract(t_id)
            if contract_pkg and contract_pkg.requirements:
                all_requirements.extend(contract_pkg.requirements)
        except Exception as e:
            logger.warning("Could not fetch contract package for tender '%s': %s", t_id, e)

        subs = t.get("submissions", []) or []
        for s in subs:
            all_submissions.append(s)
            s_docs = s.get("documents", []) or []
            all_documents.extend(s_docs)
            b = s.get("bidder")
            if b and b not in all_bidders:
                all_bidders.append(b)

    # HARD GATE: Technical Scrutiny cannot produce meaningful findings without requirements.
    # 0 requirements almost certainly means Tender Intelligence failed during ingestion.
    # Block here rather than produce a misleadingly successful run with all bidders showing UNVERIFIED.
    if not all_requirements and not force:
        await transition_procurement_state(
            procurement_id=procurement_id,
            target_status=ProcurementStatus.FAILED,
            actor=actor,
            reason="Technical Scrutiny aborted: no requirements were extracted from the tender. "
                   "Re-ingest the tender document to trigger Tender Intelligence.",
        )
        await insert_audit_log_db({
            "event_type": "TECHNICAL_SCRUTINY_ABORTED_NO_REQUIREMENTS",
            "procurement_id": procurement_id,
            "actor": actor,
            "details": {"tender_ids": tender_ids, "force": force},
        })
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Technical Scrutiny cannot proceed: 0 compliance requirements were found for this tender. "
                "This indicates Tender Intelligence (requirement extraction) did not run or failed during ingestion. "
                "Re-upload the tender PDF to re-trigger requirement analysis."
            ),
        )
    # Ingest claims and observations for verification engine context
    all_claims: List[BidderClaim] = []
    all_observations: List[EvidenceObservation] = []

    for sub in all_submissions:
        sub_id = sub.get("id")
        bidder_id = sub.get("bidder_id")
        s_docs = sub.get("documents", []) or []
        for doc_item in s_docs:
            if isinstance(doc_item, dict):
                doc_model = Document(
                    id=str(doc_item.get("id") or uuid.uuid4()),
                    procurement_id=procurement_id,
                    tender_id=str(sub.get("tender_id") or (tender_ids[0] if tender_ids else "")),
                    bid_submission_id=sub_id,
                    filename=doc_item.get("filename", "evidence.pdf"),
                    document_type=doc_item.get("document_type") or "OTHER",
                    mime_type=doc_item.get("mime_type", "application/pdf"),
                    file_size=doc_item.get("file_size"),
                    storage_path=doc_item.get("storage_path"),
                    content_text=doc_item.get("content_text") or (json.dumps([{"page": 1, "text": doc_item["text"]}]) if "text" in doc_item else None),
                    processing_status=doc_item.get("processing_status", "COMPLETED"),
                )
            elif isinstance(doc_item, Document):
                doc_model = doc_item
            else:
                continue

            extracted = process_document_evidence(
                doc=doc_model,
                tender_context={"bidder_id": bidder_id, "bid_submission_id": sub_id},
            )
            all_claims.extend(extracted.get("claims", []))
            all_observations.extend(extracted.get("observations", []))

    # Execute Canonical Verification Engine across full context (L1-L6)
    v_context = VerificationContext(
        procurement_id=procurement_id,
        tender_id=tender_ids[0] if tender_ids else "TENDER-DEFAULT",
        tender_metadata=proc,
        requirements=all_requirements,
        bidders=all_bidders,
        submissions=all_submissions,
        documents=all_documents,
        claims=all_claims,
        observations=all_observations,
        external_verifications={},
        extra_context={"procurement_id": procurement_id, "actor": actor},
    )

    engine_report: VerificationEngineReport = await canonical_verification_engine.run_verification(v_context)

    # Evaluate each submission and persist evaluation records
    disqualified_count = 0
    review_count = 0
    qualified_count = 0

    for sub in all_submissions:
        sub_id = sub.get("id")
        t_id = sub.get("tender_id") or (tender_ids[0] if tender_ids else "TENDER-DEFAULT")
        try:
            eval_res = await evaluate_canonical_submission_by_id(
                submission_id=sub_id,
                tender_id_or_ref=t_id,
                context={"procurement_id": procurement_id, "engine_report": engine_report.model_dump()},
            )
            # Persist to database/in-memory store
            bidder_obj = sub.get("bidder") or {}
            bidder_name = bidder_obj.get("legal_name") if isinstance(bidder_obj, dict) else "Bidder"
            await insert_bid_evaluation(
                tender_id=t_id,
                bidder_name=bidder_name,
                evaluation_data=eval_res,
                bid_id=sub_id,
            )

            # Analyze pass / fail / review counts
            machine_summary = eval_res.get("machine_review_summary", {})
            fails = machine_summary.get(ComplianceState.FAIL.value, 0)
            reviews = machine_summary.get(ComplianceState.REVIEW.value, 0) + machine_summary.get(ComplianceState.UNVERIFIED.value, 0)

            if fails > 0:
                disqualified_count += 1
            elif reviews > 0 or eval_res.get("review_required", False):
                review_count += 1
            else:
                qualified_count += 1

        except Exception as eval_exc:
            logger.exception(
                "Canonical evaluation FAILED for submission '%s' (tender '%s').",
                sub_id,
                t_id,
            )

            await insert_audit_log_db({
                "event_type": "TECHNICAL_SUBMISSION_EVALUATION_FAILED",
                "procurement_id": procurement_id,
                "actor": actor,
                "details": {
                    "submission_id": sub_id,
                    "tender_id": t_id,
                    "error": str(eval_exc),
                },
            })

            review_count += 1

    # Check open clarifications
    clarifications = await list_clarifications_db(procurement_id=procurement_id)
    open_clarifications = [c for c in clarifications if c.get("status") in (ClarificationStatus.OPEN.value, ClarificationStatus.RESPONDED.value)]

    # Complete Scrutiny & Transition to TECHNICAL_REVIEW
    await transition_procurement_state(
        procurement_id=procurement_id,
        target_status=ProcurementStatus.TECHNICAL_REVIEW,
        actor=actor,
        reason="Technical scrutiny execution completed.",
        metadata={
            "bidders_evaluated": len(all_submissions),
            "disqualified_count": disqualified_count,
            "review_count": review_count,
            "qualified_count": qualified_count,
            "total_findings": engine_report.total_findings,
        },
    )

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

    await insert_audit_log_db({
        "event_type": "TECHNICAL_SCRUTINY_COMPLETED",
        "procurement_id": procurement_id,
        "actor": actor,
        "details": {
            "bidders_evaluated": len(all_submissions),
            "disqualified_count": disqualified_count,
            "review_count": review_count,
            "qualified_count": qualified_count,
            "open_clarifications_count": len(open_clarifications),
            "execution_time_ms": elapsed_ms,
        },
    })

    executed_layers = [
        VerificationLayer.INGESTION_AND_DOCUMENT_INTEGRITY.value,
        VerificationLayer.ADMINISTRATIVE_AND_IDENTITY.value,
        VerificationLayer.CORPORATE_EXISTENCE_AND_RISK.value,
        VerificationLayer.ANTI_COLLUSION_AND_RELATEDNESS.value,
        VerificationLayer.ADVERSARIAL_TECHNICAL.value,
        VerificationLayer.PAST_PERFORMANCE_AND_CAPACITY.value,
    ]

    return TechnicalScrutinyRunResponse(
        procurement_id=procurement_id,
        status=ProcurementStatus.TECHNICAL_REVIEW,
        executed_layers=executed_layers,
        bidders_evaluated=len(all_submissions),
        disqualified_count=disqualified_count,
        review_count=review_count,
        qualified_count=qualified_count,
        open_clarifications_count=len(open_clarifications),
        execution_time_ms=elapsed_ms,
        message="Technical Scrutiny pipeline executed successfully across all submission evidence.",
    )


# ---------------------------------------------------------------------------
# Structured Officer-Facing Technical Review Representation
# ---------------------------------------------------------------------------
async def get_procurement_technical_review_service(
    procurement_id: str,
) -> ProcurementTechnicalReviewResponse:
    """Aggregates the complete officer-facing Technical Review representation."""
    proc = await get_procurement_detail_db(procurement_id)
    if not proc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Procurement workspace '{procurement_id}' was not found.",
        )

    raw_status = proc.get("status", ProcurementStatus.IMPORTED.value)
    try:
        proc_status = ProcurementStatus(raw_status)
    except ValueError:
        proc_status = ProcurementStatus.IMPORTED

    tenders = proc.get("tenders", []) or []
    all_requirements: List[Any] = []
    all_submissions: List[Dict[str, Any]] = []
    all_bidders: List[Dict[str, Any]] = []

    for t in tenders:
        t_id = str(t.get("id"))
        try:
            pkg = await get_tender_evaluation_contract(t_id)
            if pkg and pkg.requirements:
                for req in pkg.requirements:
                    if req not in all_requirements:
                        all_requirements.append(req)
        except Exception:
            pass

        subs = t.get("submissions", []) or []
        for s in subs:
            all_submissions.append(s)
            b = s.get("bidder")
            if b and b not in all_bidders:
                all_bidders.append(b)

    # Clarifications
    clarification_records = await list_clarifications_db(procurement_id=procurement_id)
    clarification_summaries: List[OfficerClarificationSummary] = []
    open_clarifications_count = 0

    for c in clarification_records:
        c_status = c.get("status", "OPEN")
        if c_status in (ClarificationStatus.OPEN.value, ClarificationStatus.RESPONDED.value):
            open_clarifications_count += 1

        b_id = c.get("bidder_id", "")
        matching_b = next((b for b in all_bidders if b.get("id") == b_id), {})
        b_name = matching_b.get("legal_name") or "Bidder"

        created_at_val = None
        if c.get("created_at"):
            try:
                created_at_val = datetime.fromisoformat(c["created_at"])
            except Exception:
                pass

        clarification_summaries.append(
            OfficerClarificationSummary(
                clarification_id=c.get("id", ""),
                bidder_id=b_id,
                bidder_name=b_name,
                requirement_id=c.get("requirement_id"),
                subject=c.get("question") or "Clarification Request",
                status=c_status,
                created_at=created_at_val,
            )
        )

    # Bidder Summaries & Finding Compilation
    bidder_summaries: List[OfficerBidderTechnicalSummary] = []
    finding_summaries: List[OfficerFindingSummary] = []
    req_compliance_by_bidder: Dict[str, Dict[str, str]] = {}

    all_frozen = len(all_submissions) > 0
    freeze_reasons: List[str] = []
    frozen_by_list: List[str] = []
    frozen_at_list: List[str] = []
    qualified_bidder_names: List[str] = []
    disqualified_bidder_names: List[str] = []

    for sub in all_submissions:
        sub_id = sub.get("id", "")
        b_id = sub.get("bidder_id", "")
        b_obj = sub.get("bidder") or {}
        b_name = b_obj.get("legal_name") or "Bidder"

        # Check freeze state
        f_status_raw = sub.get("technical_freeze_status", TechnicalFreezeStatus.NOT_FROZEN.value)
        try:
            sub_freeze_status = TechnicalFreezeStatus(f_status_raw)
        except ValueError:
            sub_freeze_status = TechnicalFreezeStatus.NOT_FROZEN

        if sub_freeze_status != TechnicalFreezeStatus.FROZEN:
            all_frozen = False
        else:
            if sub.get("freeze_reason"):
                freeze_reasons.append(sub["freeze_reason"])
            if sub.get("frozen_by"):
                frozen_by_list.append(sub["frozen_by"])
            if sub.get("frozen_at"):
                frozen_at_list.append(sub["frozen_at"])

        # Check open clarifications for this bidder
        bidder_has_open_c = any(
            c.get("bidder_id") == b_id and c.get("status") in (ClarificationStatus.OPEN.value, ClarificationStatus.RESPONDED.value)
            for c in clarification_records
        )

        # Run or resolve evaluation results
        t_id = sub.get("tender_id") or (tenders[0].get("id") if tenders else "")
        eval_res = {}
        try:
            persisted_evals = await get_bid_evaluations(t_id)
            for rec in persisted_evals:
                ed = rec.get("evaluation_data") or {}
                if ed.get("submission_id") in (sub_id, sub.get("external_submission_reference")) or rec.get("bidder_name") == b_name or ed.get("bidder_name") == b_name:
                    eval_res = ed
                    break
        except Exception:
            eval_res = {}

        if not eval_res:
            try:
                eval_res = await evaluate_canonical_submission_by_id(
                    submission_id=sub_id,
                    tender_id_or_ref=t_id,
                )
            except Exception as eval_exc:
                logger.exception(
                    "Failed to reconstruct evaluation for submission '%s'.",
                    sub_id,
                )
                eval_res = {
                    "submission_id": sub_id,
                    "bidder_id": b_id,
                    "machine_review_summary": {
                        ComplianceState.UNVERIFIED.value: 1
                    },
                    "requirement_results": [],
                    "review_required": True,
                    "evaluation_error": str(eval_exc),
                }

        machine_summary = eval_res.get("machine_review_summary", {})
        pass_count = machine_summary.get(ComplianceState.PASS.value, 0)
        fail_count = machine_summary.get(ComplianceState.FAIL.value, 0)
        review_count = machine_summary.get(ComplianceState.REVIEW.value, 0) + machine_summary.get(ComplianceState.UNVERIFIED.value, 0)

        # Populate requirement-level matrix and gather bidder-specific blockers
        bidder_blockers: List[str] = []
        bidder_unresolved_c: List[str] = []
        bidder_pending_re_eval = False

        for c in clarification_records:
            if c.get("bidder_id") == b_id:
                c_st = c.get("status")
                c_id_val = c.get("id", "")
                if c_st in (ClarificationStatus.OPEN.value, ClarificationStatus.RESPONDED.value, ClarificationStatus.UNDER_REVIEW.value, ClarificationStatus.REQUIRES_FURTHER_CLARIFICATION.value):
                    bidder_unresolved_c.append(c_id_val)
                    if c_st == ClarificationStatus.RESPONDED.value:
                        bidder_pending_re_eval = True
                    bidder_blockers.append(f"Unresolved clarification on requirement {c.get('requirement_id')}")

        for r_res in eval_res.get("requirement_results", []):
            req_id = getattr(r_res, "requirement_id", None) or (r_res.get("requirement_id") if isinstance(r_res, dict) else None)
            st_val = getattr(r_res, "state", None) or (r_res.get("state") if isinstance(r_res, dict) else None)
            st_str = st_val.value if hasattr(st_val, "value") else str(st_val or "UNVERIFIED")
            is_mand = getattr(r_res, "mandatory", True) if hasattr(r_res, "mandatory") else True
            reason_str = getattr(r_res, "reason", "") or (r_res.get("reason", "") if isinstance(r_res, dict) else "")

            if req_id:
                req_compliance_by_bidder.setdefault(req_id, {})[b_id] = st_str

            if is_mand and st_str in ("FAIL", "REVIEW", "UNVERIFIED"):
                bidder_blockers.append(f"{req_id} [{st_str}]: {reason_str or 'Mandatory requirement not satisfied'}")

            # Extract findings from requirement evaluations
            c_findings = getattr(r_res, "contradiction_findings", []) or (r_res.get("contradiction_findings", []) if isinstance(r_res, dict) else [])
            for c_f in c_findings:
                # Find associated clarification if any
                matching_c = next((c for c in clarification_records if c.get("bidder_id") == b_id and c.get("requirement_id") == req_id), None)
                c_id_linked = matching_c.get("id") if matching_c else None
                c_st_linked = matching_c.get("status") if matching_c else None

                finding_summaries.append(
                    OfficerFindingSummary(
                        finding_id=str(uuid.uuid4()),
                        bidder_id=b_id,
                        bidder_name=b_name,
                        layer="CONTRADICTION_DETECTION",
                        severity=FindingSeverity.MEDIUM.value if getattr(c_f, "severity", None) is None else getattr(c_f, "severity"),
                        title=f"Contradiction in {req_id}",
                        detail=getattr(c_f, "description", str(c_f)),
                        evidence_pointer=getattr(c_f, "evidence_pointer", None),
                        source_reference=req_id,
                        requires_clarification=True,
                        is_blocking=is_mand,
                        clarification_id=c_id_linked,
                        clarification_status=c_st_linked,
                    )
                )

        # Overall recommendation
        if fail_count > 0:
            compliance_status = "FAIL"
            is_eligible = False
            disqualified_bidder_names.append(b_name)
        elif review_count > 0 or bidder_has_open_c:
            compliance_status = "REVIEW"
            is_eligible = False
        elif pass_count > 0 and len(bidder_blockers) == 0:
            compliance_status = "PASS"
            is_eligible = True
            qualified_bidder_names.append(b_name)
        else:
            compliance_status = "UNVERIFIED"
            is_eligible = False

        if not is_eligible and len(bidder_blockers) == 0:
            bidder_blockers.append(f"Technical verification {compliance_status}: Officer review or re-evaluation required")

        is_bidder_blocking = len(bidder_blockers) > 0 or not is_eligible
        officer_action_needed = (compliance_status in ("REVIEW", "UNVERIFIED")) or len(bidder_unresolved_c) > 0

        bidder_summaries.append(
            OfficerBidderTechnicalSummary(
                bidder_id=b_id,
                legal_name=b_name,
                submission_id=sub_id,
                technical_freeze_status=sub_freeze_status,
                compliance_status=compliance_status,
                passed_requirements_count=pass_count,
                failed_requirements_count=fail_count,
                review_requirements_count=review_count,
                findings_count=len([f for f in finding_summaries if f.bidder_id == b_id]),
                has_open_clarifications=bidder_has_open_c,
                is_technically_eligible=is_eligible,
                is_blocking=is_bidder_blocking,
                officer_action_required=officer_action_needed,
                blockers=bidder_blockers,
                unresolved_clarifications=bidder_unresolved_c,
                pending_re_evaluation=bidder_pending_re_eval,
                summary_notes=f"Passed {pass_count} criteria, {fail_count} failed, {review_count} require review.",
            )
        )

    # Requirement Summaries
    req_summaries: List[OfficerRequirementSummary] = []
    for r in all_requirements:
        r_id = getattr(r, "requirement_id", None) or (r.get("requirement_id") if isinstance(r, dict) else str(r))
        cat = getattr(r, "category", None) or (r.get("category") if isinstance(r, dict) else "GENERAL")
        title = getattr(r, "title", None) or (r.get("title") if isinstance(r, dict) else (getattr(r, "description", "")[:60] or r_id))
        desc = getattr(r, "description", None) or (r.get("description") if isinstance(r, dict) else None)
        is_mand = getattr(r, "is_mandatory", True) if hasattr(r, "is_mandatory") else (r.get("is_mandatory", True) if isinstance(r, dict) else True)

        req_summaries.append(
            OfficerRequirementSummary(
                requirement_id=r_id,
                category=cat.value if hasattr(cat, "value") else str(cat),
                title=title,
                description=desc,
                is_mandatory=is_mand,
                compliance_by_bidder=req_compliance_by_bidder.get(r_id, {}),
            )
        )

    # Freeze summary
    freeze_summary = OfficerFreezeSummary(
        is_frozen=all_frozen,
        frozen_at=datetime.fromisoformat(frozen_at_list[0]) if frozen_at_list else None,
        frozen_by=frozen_by_list[0] if frozen_by_list else None,
        freeze_reason=freeze_reasons[0] if freeze_reasons else None,
        qualified_bidders=qualified_bidder_names,
        disqualified_bidders=disqualified_bidder_names,
    )

    # Cover 2 & Freeze Blocker Evaluation
    global_blockers: List[str] = []
    warnings: List[str] = []

    if not all_frozen:
        global_blockers.append("Technical Freeze (Cover 1) must be applied to all submissions before opening Cover 2.")

    if open_clarifications_count > 0:
        global_blockers.append(f"There are {open_clarifications_count} unresolved clarification(s) pending.")

    unresolved_technical_blockers = [
        b for b in bidder_summaries
        if b.compliance_status in ("REVIEW", "UNVERIFIED") or b.pending_re_evaluation or len(b.unresolved_clarifications) > 0
    ]
    if len(unresolved_technical_blockers) > 0:
        global_blockers.append(f"{len(unresolved_technical_blockers)} bidder(s) have unresolved technical findings (REVIEW/UNVERIFIED) awaiting review.")

    # Freeze readiness check
    eligible_bidders = [b.legal_name for b in bidder_summaries if b.is_technically_eligible]
    can_freeze = (len(all_submissions) > 0 and open_clarifications_count == 0 and len(unresolved_technical_blockers) == 0)
    is_cover2_ready = (all_frozen and open_clarifications_count == 0 and len(eligible_bidders) > 0 and len(unresolved_technical_blockers) == 0)

    cover2_summary = Cover2ReadinessSummary(
        is_ready=is_cover2_ready,
        blockers=global_blockers,
        warnings=warnings,
        eligible_bidder_count=len(eligible_bidders),
        eligible_bidders=eligible_bidders,
        technical_freeze_enforced=all_frozen,
        open_clarifications_count=open_clarifications_count,
    )

    last_eval_time = None
    if proc.get("updated_at"):
        try:
            last_eval_time = datetime.fromisoformat(proc["updated_at"])
        except Exception:
            pass

    from app.db.client import list_officer_observations_db
    from app.models.procurement import OfficerObservationRecord

    obs_list = await list_officer_observations_db(procurement_id)
    observation_records = [OfficerObservationRecord(**o) for o in obs_list]

    # -------------------------------------------------------------------------
    # PRESENTATION DTO GENERATION
    # -------------------------------------------------------------------------
  

    layer_keys = [
        "INGESTION_AND_DOCUMENT_INTEGRITY",
        "ADMINISTRATIVE_AND_IDENTITY",
        "CORPORATE_EXISTENCE_AND_RISK",
        "ANTI_COLLUSION_AND_RELATEDNESS",
        "ADVERSARIAL_TECHNICAL",
        "PAST_PERFORMANCE_AND_CAPACITY",
    ]

    layer_names = {
        "INGESTION_AND_DOCUMENT_INTEGRITY": "1. Ingestion & Integrity",
        "ADMINISTRATIVE_AND_IDENTITY": "2. Administrative & Identity",
        "CORPORATE_EXISTENCE_AND_RISK": "3. Corporate Existence & Risk",
        "ANTI_COLLUSION_AND_RELATEDNESS": "4. Anti-Collusion & Relatedness",
        "ADVERSARIAL_TECHNICAL": "5. Adversarial Technical",
        "PAST_PERFORMANCE_AND_CAPACITY": "6. Past Performance & Capacity",
    }

    presentation_layers = []

    # -------------------------------------------------------------------------
    # Use the persisted verification-engine report as the authoritative source
    # for layer-level findings.
    # -------------------------------------------------------------------------
    findings_by_layer: Dict[str, List[Dict[str, Any]]] = {
        layer_key: [] for layer_key in layer_keys
    }

    for sub in all_submissions:
        sub_id = sub.get("id", "")
        b_id = sub.get("bidder_id", "")
        b_obj = sub.get("bidder") or {}
        b_name = b_obj.get("legal_name") or "Bidder"

        t_id = sub.get("tender_id") or (tenders[0].get("id") if tenders else "")

        eval_res: Dict[str, Any] = {}

        try:
            persisted_evals = await get_bid_evaluations(t_id)

            for rec in persisted_evals:
                ed = rec.get("evaluation_data") or {}

                if (
                    ed.get("submission_id") in (
                        sub_id,
                        sub.get("external_submission_reference"),
                    )
                    or rec.get("bidder_name") == b_name
                    or ed.get("bidder_name") == b_name
                ):
                    eval_res = ed
                    break
        except Exception:
            eval_res = {}

        engine_report = eval_res.get("verification_engine_report") or {}
        engine_findings = engine_report.get("findings_by_layer") or {}

        for layer_key in layer_keys:
            layer_findings = engine_findings.get(layer_key) or []

            for finding in layer_findings:
                if not isinstance(finding, dict):
                    continue

                finding_copy = dict(finding)
                finding_copy["_bidder_id"] = b_id
                finding_copy["_bidder_name"] = b_name

                findings_by_layer[layer_key].append(finding_copy)

    # -------------------------------------------------------------------------
    # Build officer-facing presentation layers.
    # -------------------------------------------------------------------------
    for layer_key in layer_keys:
        layer_checks = []

        layer_findings = findings_by_layer.get(layer_key, [])

        for finding in layer_findings:
            raw_status = (
                finding.get("status")
                or finding.get("state")
                or finding.get("severity")
                or "REVIEW"
            )

            status_value = (
                raw_status.value
                if hasattr(raw_status, "value")
                else str(raw_status)
            )

            # Normalize verification-engine states to officer-facing states.
            if status_value not in {
                "PASS",
                "FAIL",
                "REVIEW",
                "UNVERIFIED",
                "NOT_APPLICABLE",
            }:
                status_value = "REVIEW"

            evidence_references = finding.get("evidence_references")

            if evidence_references is None:
                evidence_pointer = finding.get("evidence_pointer")
                evidence_references = (
                    [evidence_pointer] if evidence_pointer else []
                )

            layer_checks.append(
                {
                    "check_id": (
                        finding.get("finding_id")
                        or finding.get("id")
                        or str(uuid.uuid4())
                    ),
                    "title": (
                        finding.get("title")
                        or finding.get("check_name")
                        or "Verification Finding"
                    ),
                    "status": status_value,
                    "bidders": {
                        finding.get("_bidder_id"): status_value
                    } if finding.get("_bidder_id") else {},
                    "explanation": (
                        finding.get("detail")
                        or finding.get("description")
                        or finding.get("reason")
                        or "Verification finding reported by the verification engine."
                    ),
                    "evidence_references": evidence_references,
                    "blocking": bool(
                        finding.get("is_blocking")
                        or finding.get("blocking")
                        or False
                    ),
                    "clarification_status": finding.get("clarification_status"),
                }
            )

        # Keep every technical layer visible even when it has no adverse finding.
        if not layer_checks:
            layer_checks.append(
                {
                    "check_id": f"{layer_key}_COMPLETED",
                    "title": "Verification completed",
                    "status": "PASS",
                    "bidders": {
                        sub.get("bidder_id", ""): "PASS"
                        for sub in all_submissions
                        if sub.get("bidder_id")
                    },
                    "explanation": (
                        "Verification executed successfully with no adverse "
                        "findings reported by the verification engine."
                    ),
                    "evidence_references": [],
                    "blocking": False,
                    "clarification_status": None,
                }
            )

        presentation_layers.append(
            OfficerTechnicalLayerPresentation(
                layer_key=layer_key,
                display_name=layer_names[layer_key],
                checks=[
                    OfficerTechnicalCheckPresentation(**check)
                    for check in layer_checks
                ],
            )
        )

    return ProcurementTechnicalReviewResponse(
        procurement_id=procurement_id,
        external_reference=proc.get("external_reference", ""),
        title=proc.get("title", "Procurement Workspace"),
        status=proc_status,
        total_bidders=len(all_submissions),
        qualified_bidders_count=len(qualified_bidder_names),
        excluded_bidders_count=len(disqualified_bidder_names),
        review_required_bidders_count=len([b for b in bidder_summaries if b.compliance_status in ("REVIEW", "UNVERIFIED")]),
        unresolved_blockers=global_blockers,
        can_freeze=can_freeze,
        can_open_cover2=is_cover2_ready,
        bidders=bidder_summaries,
        requirements=req_summaries,
        key_findings=finding_summaries,
        clarifications=clarification_summaries,
        observations=observation_records,
        presentation_layers=presentation_layers,
        freeze_status=freeze_summary,
        cover2_readiness=cover2_summary,
        decision_authority="HUMAN_PROCUREMENT_OFFICER",
        last_evaluated_at=last_eval_time,
    )


# ---------------------------------------------------------------------------
# Cover 2 Readiness Gate Service
# ---------------------------------------------------------------------------
async def evaluate_cover2_gate_service(
    procurement_id: str,
    actor: str = "PROCUREMENT_OFFICER",
) -> Cover2ReadinessResponse:
    """Evaluates readiness gate for unlocking Cover 2 Financial Opening."""
    review_rep = await get_procurement_technical_review_service(procurement_id)
    c2_summary = review_rep.cover2_readiness

    now_dt = datetime.now(timezone.utc)

    if c2_summary.is_ready:
        # Move procurement state to COVER_2_READY if currently in TECHNICAL_FREEZE or TECHNICAL_REVIEW
        if review_rep.status in (ProcurementStatus.TECHNICAL_FREEZE, ProcurementStatus.TECHNICAL_REVIEW):
            await transition_procurement_state(
                procurement_id=procurement_id,
                target_status=ProcurementStatus.COVER_2_READY,
                actor=actor,
                reason="Cover 2 readiness gate passed successfully.",
            )

        await insert_audit_log_db({
            "event_type": "COVER_2_GATE_PASSED",
            "procurement_id": procurement_id,
            "actor": actor,
            "details": {
                "eligible_bidders": c2_summary.eligible_bidders,
                "eligible_bidder_count": c2_summary.eligible_bidder_count,
                "technical_freeze_enforced": c2_summary.technical_freeze_enforced,
            },
        })
    else:
        await insert_audit_log_db({
            "event_type": "COVER_2_GATE_BLOCKED",
            "procurement_id": procurement_id,
            "actor": actor,
            "details": {
                "blockers": c2_summary.blockers,
                "warnings": c2_summary.warnings,
                "open_clarifications_count": c2_summary.open_clarifications_count,
                "technical_freeze_enforced": c2_summary.technical_freeze_enforced,
            },
        })

    return Cover2ReadinessResponse(
        procurement_id=procurement_id,
        status=ProcurementStatus.COVER_2_READY if c2_summary.is_ready else review_rep.status,
        cover2_readiness=c2_summary,
        decision_authority="HUMAN_PROCUREMENT_OFFICER",
        evaluated_at=now_dt,
    )


# ---------------------------------------------------------------------------
# Procurement-Level Technical Freeze Hardening
# ---------------------------------------------------------------------------
async def freeze_procurement_technical_service(
    procurement_id: str,
    actor: str = "PROCUREMENT_OFFICER",
    reason: Optional[str] = None,
) -> ProcurementTechnicalReviewResponse:
    """Applies technical freeze across all submissions in a procurement workspace after verifying canonical blockers."""
    proc = await get_procurement_detail_db(procurement_id)
    if not proc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Procurement workspace '{procurement_id}' not found.",
        )

    review_rep = await get_procurement_technical_review_service(procurement_id)

    # Idempotency check: if already frozen, return existing state
    if review_rep.status == ProcurementStatus.TECHNICAL_FREEZE and review_rep.freeze_status.is_frozen:
        return review_rep

    # Validate prerequisites
    if not review_rep.can_freeze:
        reasons = []
        if review_rep.cover2_readiness.open_clarifications_count > 0:
            reasons.append(f"{review_rep.cover2_readiness.open_clarifications_count} open clarification(s) must be resolved")
        if review_rep.review_required_bidders_count > 0:
            reasons.append(f"{review_rep.review_required_bidders_count} bidder(s) have unresolved technical findings (REVIEW/UNVERIFIED)")
        if review_rep.total_bidders == 0:
            reasons.append("No bidder submissions found to freeze")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot freeze procurement '{procurement_id}': " + "; ".join(reasons or ["Prerequisites not met"]),
        )

    # Freeze all submissions
    now_iso = datetime.now(timezone.utc).isoformat()
    freeze_note = reason or "Cover 1 Technical Freeze applied by officer."

    tenders = proc.get("tenders", []) or []
    for t in tenders:
        for s in (t.get("submissions", []) or []):
            s_id = s.get("id")
            if s_id:
                await update_submission_freeze_db(
                    submission_id=s_id,
                    technical_freeze_status=TechnicalFreezeStatus.FROZEN.value,
                    is_locked=True,
                    frozen_at=now_iso,
                    frozen_by=actor,
                    freeze_reason=freeze_note,
                )

    # Transition procurement state
    await transition_procurement_state(
        procurement_id=procurement_id,
        target_status=ProcurementStatus.TECHNICAL_FREEZE,
        actor=actor,
        reason=freeze_note,
        metadata={"frozen_submissions_count": review_rep.total_bidders},
    )

    await insert_audit_log_db({
        "event_type": "TECHNICAL_FREEZE_APPLIED",
        "procurement_id": procurement_id,
        "actor": actor,
        "details": {
            "submissions_frozen": review_rep.total_bidders,
            "reason": freeze_note,
            "timestamp": now_iso,
        },
    })

    return await get_procurement_technical_review_service(procurement_id)


# ---------------------------------------------------------------------------
# Cover 2 Financial Opening & Evaluation Orchestration
# ---------------------------------------------------------------------------
async def run_cover2_financial_evaluation_service(
    procurement_id: str,
    actor: str = "PROCUREMENT_OFFICER",
    force: bool = False,
    notes: Optional[str] = None,
) -> ProcurementFinancialEvaluationResponse:
    """Authoritatively executes Cover 2 Financial Opening and Commercial Evaluation.

    Invariants Enforced:
    1. Gatekeeper Verification: Technical Freeze must be enforced, zero open clarifications,
       and zero unresolved mandatory technical blockers before Cover 2 opening.
    2. Lifecycle Transitions: Transitions state from TECHNICAL_FREEZE/COVER_2_READY ->
       FINANCIAL_EVALUATION_RUNNING -> FINANCIAL_REVIEW / L1_DETERMINED.
    3. Audit Logging: Emits immutable structured audit logs for all stages.
    4. Officer Decision Authority: Emits decision_authority = 'HUMAN_PROCUREMENT_OFFICER'.
    """
    try:
        from app.services.financial_evaluation_service import (
            execute_cover2_financial_evaluation,
            get_procurement_financial_evaluation_service,
        )
    except ImportError:
        from services.financial_evaluation_service import (
            execute_cover2_financial_evaluation,
            get_procurement_financial_evaluation_service,
        )

    # 1. Fetch procurement technical review representation
    review_rep = await get_procurement_technical_review_service(procurement_id)
    c2_summary = review_rep.cover2_readiness

    # 2. Enforce Cover 2 readiness gate blockers (unless force is requested)
    if not force and not c2_summary.is_ready:
        blockers = c2_summary.blockers or ["Prerequisites for Cover 2 financial opening not met."]
        await insert_audit_log_db({
            "event_type": "COVER2_OPEN_BLOCKED",
            "procurement_id": procurement_id,
            "actor": actor,
            "details": {
                "blockers": blockers,
                "open_clarifications_count": c2_summary.open_clarifications_count,
                "technical_freeze_enforced": c2_summary.technical_freeze_enforced,
                "eligible_bidder_count": c2_summary.eligible_bidder_count,
            },
        })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot open Cover 2 for procurement '{procurement_id}': " + "; ".join(blockers),
        )

    now_iso = datetime.now(timezone.utc).isoformat()

    # 3. Log attempt and transition state to FINANCIAL_EVALUATION_RUNNING
    await insert_audit_log_db({
        "event_type": "COVER2_OPEN_ATTEMPTED",
        "procurement_id": procurement_id,
        "actor": actor,
        "details": {
            "eligible_bidder_count": c2_summary.eligible_bidder_count,
            "eligible_bidders": c2_summary.eligible_bidders,
            "notes": notes,
            "timestamp": now_iso,
        },
    })

    if review_rep.status != ProcurementStatus.FINANCIAL_EVALUATION_RUNNING:
        await transition_procurement_state(
            procurement_id=procurement_id,
            target_status=ProcurementStatus.FINANCIAL_EVALUATION_RUNNING,
            actor=actor,
            reason=notes or "Cover 2 Financial Opening initiated by officer.",
        )

    await insert_audit_log_db({
        "event_type": "COVER2_OPENED",
        "procurement_id": procurement_id,
        "actor": actor,
        "details": {
            "eligible_bidders": c2_summary.eligible_bidders,
            "eligible_bidder_count": c2_summary.eligible_bidder_count,
            "timestamp": now_iso,
        },
    })

    await insert_audit_log_db({
        "event_type": "FINANCIAL_EVALUATION_STARTED",
        "procurement_id": procurement_id,
        "actor": actor,
        "details": {
            "timestamp": now_iso,
        },
    })

    # 4. Execute canonical financial evaluation
    eval_result: ProcurementFinancialEvaluationResponse = await execute_cover2_financial_evaluation(procurement_id)

    # 5. Transition to L1_DETERMINED (if L1 exists) or FINANCIAL_REVIEW
    final_status = ProcurementStatus.L1_DETERMINED if eval_result.l1_bidder_id else ProcurementStatus.FINANCIAL_REVIEW
    await transition_procurement_state(
        procurement_id=procurement_id,
        target_status=final_status,
        actor=actor,
        reason=f"Cover 2 financial evaluation completed. L1: {eval_result.l1_bidder_name or 'None'}.",
    )

    await insert_audit_log_db({
        "event_type": "FINANCIAL_EVALUATION_COMPLETED",
        "procurement_id": procurement_id,
        "actor": actor,
        "details": {
            "eligible_bidders_count": eval_result.eligible_bidders_count,
            "excluded_bidders_count": eval_result.excluded_bidders_count,
            "l1_bidder": eval_result.l1_bidder_name,
            "l1_amount": eval_result.l1_evaluated_amount,
            "anomalies_detected": len(eval_result.comparative_signals),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    })

    if eval_result.l1_bidder_id:
        await insert_audit_log_db({
            "event_type": "L1_DETERMINED",
            "procurement_id": procurement_id,
            "actor": actor,
            "details": {
                "l1_bidder_id": eval_result.l1_bidder_id,
                "l1_bidder_name": eval_result.l1_bidder_name,
                "l1_evaluated_amount": eval_result.l1_evaluated_amount,
                "currency": eval_result.currency,
                "decision_authority": "HUMAN_PROCUREMENT_OFFICER",
            },
        })

    return eval_result

async def record_officer_observation_service(
    procurement_id: str,
    payload: "OfficerObservationCreate",
    actor: str,
) -> "OfficerObservationRecord":
    from app.db.client import get_procurement_detail_db, insert_officer_observation_db, insert_audit_log_db, list_officer_observations_db
    from app.models.procurement import OfficerObservationRecord
    from fastapi import HTTPException, status
    
    proc = await get_procurement_detail_db(procurement_id)
    if not proc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Procurement '{procurement_id}' not found."
        )
    
    # Idempotency check: Don't duplicate exact same text for same layer and actor.
    existing = await list_officer_observations_db(procurement_id)
    for obs in existing:
        if obs.get("layer") == payload.layer and obs.get("observation") == payload.observation and obs.get("actor") == actor:
            return OfficerObservationRecord(**obs)
            
    obs_data = {
        "procurement_id": procurement_id,
        "layer": payload.layer,
        "actor": actor,
        "observation": payload.observation,
    }
    
    record_dict = await insert_officer_observation_db(obs_data)
    record = OfficerObservationRecord(**record_dict)
    
    await insert_audit_log_db({
        "event_type": "OFFICER_OBSERVATION_RECORDED",
        "procurement_id": procurement_id,
        "actor": actor,
        "details": {
            "layer": payload.layer,
            "observation_id": record.observation_id
        }
    })
    
    return record




