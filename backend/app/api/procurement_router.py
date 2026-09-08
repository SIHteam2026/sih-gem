"""API router for OPAL Procurement Workspace read endpoints.

Provides read-only query access for navigating procurements, tenders, bidder submissions,
and bidder profiles. Thin route handlers delegate business logic to procurement_read_service.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

try:
    from app.models.procurement import (
        BidderSummaryResponse,
        Cover2ReadinessResponse,
        ProcurementDetailResponse,
        ProcurementListResponse,
        ProcurementProcessingStatusResponse,
        ProcurementTechnicalReviewResponse,
        StartProcessingResponse,
        SubmissionSummaryResponse,
        TenderWorkspaceDetailResponse,
        TechnicalFreezeStatus,
        TechnicalScrutinyRunRequest,
        TechnicalScrutinyRunResponse,
    )
    from app.models.clarification import (
        ClarificationCreate,
        ClarificationListResponse,
        ClarificationRecord,
        ClarificationResponseInput,
        ClarificationStatus,
        TechnicalFreezeRequest,
        TechnicalFreezeResponse,
    )
    from app.models.financial import ProcurementFinancialEvaluationResponse
    from app.services import (
        clarification_service,
        procurement_lifecycle_service,
        procurement_processing_service,
        procurement_read_service,
    )
except ImportError:
    from models.procurement import (
        BidderSummaryResponse,
        Cover2ReadinessResponse,
        ProcurementDetailResponse,
        ProcurementListResponse,
        ProcurementProcessingStatusResponse,
        ProcurementTechnicalReviewResponse,
        StartProcessingResponse,
        SubmissionSummaryResponse,
        TenderWorkspaceDetailResponse,
        TechnicalFreezeStatus,
        TechnicalScrutinyRunRequest,
        TechnicalScrutinyRunResponse,
    )
    from models.clarification import (
        ClarificationCreate,
        ClarificationListResponse,
        ClarificationRecord,
        ClarificationResponseInput,
        ClarificationStatus,
        TechnicalFreezeRequest,
        TechnicalFreezeResponse,
    )
    from models.financial import ProcurementFinancialEvaluationResponse
    from services import (
        clarification_service,
        procurement_lifecycle_service,
        procurement_processing_service,
        procurement_read_service,
    )

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Procurement Workspace"])



@router.get(
    "/procurements",
    response_model=ProcurementListResponse,
    summary="List Procurement Workspaces",
    description="Retrieves a paginated list of top-level procurement workspaces with high-level summaries and entity counts.",
)
async def list_procurements(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of procurements to return."),
    offset: int = Query(0, ge=0, description="Offset for pagination."),
) -> ProcurementListResponse:
    """Lists procurement workspaces with pagination."""
    try:
        return await procurement_read_service.list_procurements_service(limit=limit, offset=offset)
    except Exception as exc:
        logger.error("Failed to list procurements: %s", exc)
        raise HTTPException(status_code=500, detail="Internal error retrieving procurement list.")


@router.get(
    "/procurements/{procurement_id}",
    response_model=ProcurementDetailResponse,
    summary="Get Procurement Workspace Detail",
    description="Retrieves detailed procurement workspace data including associated tenders and document metadata.",
)
async def get_procurement_detail(procurement_id: str) -> ProcurementDetailResponse:
    """Gets single procurement workspace details."""
    try:
        result = await procurement_read_service.get_procurement_detail_service(procurement_id)
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Procurement workspace with ID '{procurement_id}' was not found.",
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get procurement detail for '%s': %s", procurement_id, exc)
        raise HTTPException(status_code=500, detail="Internal error retrieving procurement workspace detail.")


@router.get(
    "/tenders/{tender_id}",
    response_model=TenderWorkspaceDetailResponse,
    summary="Get Tender Workspace Detail",
    description="Retrieves detailed tender workspace information including specifications, submissions, and requirements.",
)
async def get_tender_detail(tender_id: str) -> TenderWorkspaceDetailResponse:
    """Gets single tender workspace details."""
    try:
        result = await procurement_read_service.get_tender_detail_service(tender_id)
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Tender workspace with ID '{tender_id}' was not found.",
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get tender detail for '%s': %s", tender_id, exc)
        raise HTTPException(status_code=500, detail="Internal error retrieving tender detail.")


@router.get(
    "/tenders/{tender_id}/submissions",
    response_model=List[SubmissionSummaryResponse],
    summary="List Tender Submissions",
    description="Retrieves bidder submissions for a specific tender workspace.",
)
async def list_tender_submissions(tender_id: str) -> List[SubmissionSummaryResponse]:
    """Lists bidder submissions for a tender."""
    try:
        result = await procurement_read_service.get_tender_submissions_service(tender_id)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Tender with ID '{tender_id}' was not found.",
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to list submissions for tender '%s': %s", tender_id, exc)
        raise HTTPException(status_code=500, detail="Internal error retrieving tender submissions.")


@router.get(
    "/submissions/{submission_id}",
    response_model=SubmissionSummaryResponse,
    summary="Get Submission Detail",
    description="Retrieves a specific bidder submission details including bidder profile and document metadata.",
)
async def get_submission_detail(submission_id: str) -> SubmissionSummaryResponse:
    """Gets single submission detail."""
    try:
        result = await procurement_read_service.get_submission_detail_service(submission_id)
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Bid submission with ID '{submission_id}' was not found.",
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get submission detail for '%s': %s", submission_id, exc)
        raise HTTPException(status_code=500, detail="Internal error retrieving submission detail.")


@router.get(
    "/bidders/{bidder_id}",
    response_model=BidderSummaryResponse,
    summary="Get Bidder Detail",
    description="Retrieves legal and registration profile information for a specific bidder.",
)
async def get_bidder_detail(bidder_id: str) -> BidderSummaryResponse:
    """Gets single bidder profile details."""
    try:
        result = await procurement_read_service.get_bidder_detail_service(bidder_id)
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Bidder profile with ID '{bidder_id}' was not found.",
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get bidder detail for '%s': %s", bidder_id, exc)
        raise HTTPException(status_code=500, detail="Internal error retrieving bidder profile.")


@router.post(
    "/procurements/{procurement_id}/process",
    response_model=StartProcessingResponse,
    summary="Start Procurement Processing Lifecycle",
    description="Triggers the automated processing pipeline for an ingested procurement workspace (IMPORTED -> PROCESSING -> READY/FAILED).",
)
async def start_procurement_processing_endpoint(
    procurement_id: str,
    force: bool = Query(False, description="Force re-processing even if status is READY."),
) -> StartProcessingResponse:
    """Triggers processing lifecycle orchestration for a procurement."""
    try:
        return await procurement_processing_service.start_procurement_processing(
            procurement_id=procurement_id, force=force
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to start processing for procurement '%s': %s", procurement_id, exc)
        raise HTTPException(status_code=500, detail="Internal error initiating procurement processing.")


@router.get(
    "/procurements/{procurement_id}/processing-status",
    response_model=ProcurementProcessingStatusResponse,
    summary="Get Procurement Processing Status",
    description="Retrieves active pipeline stage and completed stage results for a procurement workspace.",
)
async def get_procurement_processing_status_endpoint(
    procurement_id: str,
) -> ProcurementProcessingStatusResponse:
    """Retrieves processing lifecycle status for a procurement workspace."""
    try:
        return await procurement_processing_service.get_procurement_processing_status(
            procurement_id=procurement_id
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get processing status for procurement '%s': %s", procurement_id, exc)
        raise HTTPException(status_code=500, detail="Internal error retrieving procurement processing status.")


@router.post(
    "/procurements/{procurement_id}/financial-evaluation",
    response_model=ProcurementFinancialEvaluationResponse,
    summary="Execute Cover 2 Financial / Commercial Evaluation",
    description="Gates technically eligible bidders, unlocks Cover 2, extracts BOQ and commercial quotes, checks parity, normalizes prices in INR, computes L1 ranking, detects anomaly signals, and persists the results.",
)
async def evaluate_procurement_financial_endpoint(
    procurement_id: str,
) -> ProcurementFinancialEvaluationResponse:
    """Executes canonical Cover 2 Financial Evaluation for a procurement."""
    try:
        from app.services.financial_evaluation_service import execute_cover2_financial_evaluation
        return await execute_cover2_financial_evaluation(procurement_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed Cover 2 financial evaluation for '%s': %s", procurement_id, exc)
        raise HTTPException(status_code=500, detail=f"Internal error executing financial evaluation: {str(exc)}")


@router.get(
    "/procurements/{procurement_id}/financial-evaluation",
    response_model=ProcurementFinancialEvaluationResponse,
    summary="Get Cover 2 Financial / Commercial Evaluation",
    description="Retrieves the stored Cover 2 financial evaluation, L1 ranking, BOQ items, findings, and anomaly signals for a procurement.",
)
async def get_procurement_financial_endpoint(
    procurement_id: str,
) -> ProcurementFinancialEvaluationResponse:
    """Gets stored Cover 2 financial evaluation for a procurement."""
    try:
        from app.services.financial_evaluation_service import get_procurement_financial_evaluation_service
        return await get_procurement_financial_evaluation_service(procurement_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch Cover 2 financial evaluation for '%s': %s", procurement_id, exc)
        raise HTTPException(status_code=500, detail=f"Internal error retrieving financial evaluation: {str(exc)}")


# ---------------------------------------------------------------------------
# Technical Freeze Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/procurements/{procurement_id}/submissions/{submission_id}/freeze",
    response_model=TechnicalFreezeResponse,
    summary="Freeze / Lock Technical Bid Submission (Cover 1)",
    description="Applies a formal technical freeze on a submission. Distinguishes NOT_FROZEN, FROZEN, TECHNICAL_REVIEW_REQUIRED, TECHNICALLY_QUALIFIED, TECHNICALLY_DISQUALIFIED.",
)
@router.post(
    "/procurements/{procurement_id}/submissions/{submission_id}/technical-freeze",
    response_model=TechnicalFreezeResponse,
    summary="Freeze / Lock Technical Bid Submission",
)
@router.post(
    "/submissions/{submission_id}/freeze",
    response_model=TechnicalFreezeResponse,
    summary="Freeze / Lock Bid Submission",
)
@router.post(
    "/submissions/{submission_id}/technical-freeze",
    response_model=TechnicalFreezeResponse,
    summary="Freeze / Lock Technical Bid Submission",
)
async def freeze_submission_endpoint(
    submission_id: str,
    payload: TechnicalFreezeRequest = TechnicalFreezeRequest(freeze=True),
    procurement_id: Optional[str] = None,
) -> TechnicalFreezeResponse:
    """Applies or unfreezes technical freeze lock on a submission."""
    try:
        return await clarification_service.freeze_submission_service(
            submission_id=submission_id,
            freeze_request=payload,
            procurement_id=procurement_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to freeze submission '%s': %s", submission_id, exc)
        raise HTTPException(status_code=500, detail=f"Internal error applying technical freeze: {str(exc)}")


@router.post(
    "/procurements/{procurement_id}/submissions/{submission_id}/unfreeze",
    response_model=TechnicalFreezeResponse,
    summary="Unlock Technical Freeze on Submission",
)
@router.post(
    "/submissions/{submission_id}/unfreeze",
    response_model=TechnicalFreezeResponse,
    summary="Unlock Technical Freeze on Submission",
)
async def unfreeze_submission_endpoint(
    submission_id: str,
    payload: Optional[TechnicalFreezeRequest] = None,
    procurement_id: Optional[str] = None,
) -> TechnicalFreezeResponse:
    """Unlocks technical freeze on a submission."""
    try:
        req = payload or TechnicalFreezeRequest(freeze=False, freeze_reason="Officer manual unlock.")
        req.freeze = False
        return await clarification_service.freeze_submission_service(
            submission_id=submission_id,
            freeze_request=req,
            procurement_id=procurement_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to unfreeze submission '%s': %s", submission_id, exc)
        raise HTTPException(status_code=500, detail=f"Internal error unlocking technical freeze: {str(exc)}")


@router.get(
    "/procurements/{procurement_id}/submissions/{submission_id}/freeze",
    response_model=TechnicalFreezeResponse,
    summary="Get Technical Freeze Status for Submission",
)
@router.get(
    "/submissions/{submission_id}/freeze",
    response_model=TechnicalFreezeResponse,
    summary="Get Technical Freeze Status for Submission",
)
async def get_submission_freeze_endpoint(
    submission_id: str,
    procurement_id: Optional[str] = None,
) -> TechnicalFreezeResponse:
    """Gets current technical freeze status for a submission."""
    try:
        return await clarification_service.get_submission_freeze_status_service(submission_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get freeze status for submission '%s': %s", submission_id, exc)
        raise HTTPException(status_code=500, detail=f"Internal error retrieving freeze status: {str(exc)}")


# ---------------------------------------------------------------------------
# Clarification Lifecycle Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/procurements/{procurement_id}/clarifications",
    response_model=ClarificationRecord,
    summary="Create Clarification / Shortfall Request",
    description="Initiates a formal clarification request linked to a specific requirement and originating finding.",
)
@router.post(
    "/clarifications",
    response_model=ClarificationRecord,
    summary="Create Clarification Request",
)
async def create_clarification_endpoint(
    payload: ClarificationCreate,
    procurement_id: Optional[str] = None,
) -> ClarificationRecord:
    """Creates a formal clarification / shortfall request."""
    try:
        return await clarification_service.create_clarification_service(
            payload=payload,
            procurement_id=procurement_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to create clarification: %s", exc)
        raise HTTPException(status_code=500, detail=f"Internal error creating clarification: {str(exc)}")


@router.get(
    "/procurements/{procurement_id}/clarifications",
    response_model=ClarificationListResponse,
    summary="List Clarifications for Procurement",
)
@router.get(
    "/clarifications",
    response_model=ClarificationListResponse,
    summary="List Clarifications",
)
async def list_clarifications_endpoint(
    procurement_id: Optional[str] = None,
    submission_id: Optional[str] = Query(None, description="Filter by submission UUID."),
    bidder_id: Optional[str] = Query(None, description="Filter by bidder UUID."),
    status: Optional[str] = Query(None, description="Filter by status (OPEN, RESPONDED, RESOLVED, etc.)."),
) -> ClarificationListResponse:
    """Lists clarification records with optional filtering."""
    try:
        return await clarification_service.list_clarifications_service(
            procurement_id=procurement_id,
            submission_id=submission_id,
            bidder_id=bidder_id,
            status_filter=status,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to list clarifications: %s", exc)
        raise HTTPException(status_code=500, detail=f"Internal error listing clarifications: {str(exc)}")


@router.get(
    "/procurements/{procurement_id}/clarifications/{clarification_id}",
    response_model=ClarificationRecord,
    summary="Get Clarification Detail",
)
@router.get(
    "/clarifications/{clarification_id}",
    response_model=ClarificationRecord,
    summary="Get Clarification Detail",
)
async def get_clarification_detail_endpoint(
    clarification_id: str,
    procurement_id: Optional[str] = None,
) -> ClarificationRecord:
    """Gets single clarification record by UUID."""
    try:
        return await clarification_service.get_clarification_detail_service(clarification_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get clarification detail '%s': %s", clarification_id, exc)
        raise HTTPException(status_code=500, detail=f"Internal error retrieving clarification: {str(exc)}")


@router.post(
    "/procurements/{procurement_id}/clarifications/{clarification_id}/respond",
    response_model=ClarificationRecord,
    summary="Submit Bidder Clarification Response & Evidence",
    description="Records bidder response text and ingests attached clarification proof documents.",
)
@router.post(
    "/clarifications/{clarification_id}/respond",
    response_model=ClarificationRecord,
    summary="Submit Bidder Clarification Response",
)
async def respond_clarification_endpoint(
    clarification_id: str,
    payload: ClarificationResponseInput,
    procurement_id: Optional[str] = None,
) -> ClarificationRecord:
    """Submits bidder response and attached evidence for an open clarification."""
    try:
        return await clarification_service.respond_to_clarification_service(
            clarification_id=clarification_id,
            response_payload=payload,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to respond to clarification '%s': %s", clarification_id, exc)
        raise HTTPException(status_code=500, detail=f"Internal error responding to clarification: {str(exc)}")


@router.post(
    "/procurements/{procurement_id}/clarifications/{clarification_id}/re-evaluate",
    response_model=ClarificationRecord,
    summary="Execute Targeted Re-Evaluation Post-Clarification",
    description="Re-evaluates the single requirement targeted by the clarification response using newly ingested evidence, updates finding, and preserves audit trail.",
)
@router.post(
    "/clarifications/{clarification_id}/re-evaluate",
    response_model=ClarificationRecord,
    summary="Execute Targeted Re-Evaluation Post-Clarification",
)
async def re_evaluate_clarification_endpoint(
    clarification_id: str,
    procurement_id: Optional[str] = None,
) -> ClarificationRecord:
    """Re-evaluates the single target requirement affected by the clarification response."""
    try:
        return await clarification_service.re_evaluate_clarification_service(clarification_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to re-evaluate clarification '%s': %s", clarification_id, exc)
        raise HTTPException(status_code=500, detail=f"Internal error executing targeted re-evaluation: {str(exc)}")


# ---------------------------------------------------------------------------
# Technical Scrutiny, Technical Review & Cover 2 Gate Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/procurements/{procurement_id}/technical-scrutiny/run",
    response_model=TechnicalScrutinyRunResponse,
    summary="Run Authoritative Technical Scrutiny Pipeline",
    description="Executes the canonical multi-layer verification engine (L1-L7) across all submission evidence.",
)
async def run_technical_scrutiny_endpoint(
    procurement_id: str,
    payload: Optional[TechnicalScrutinyRunRequest] = None,
) -> TechnicalScrutinyRunResponse:
    """Initiates full multi-layer technical scrutiny for the procurement workspace."""
    try:
        actor = payload.actor if payload and payload.actor else "PROCUREMENT_OFFICER"
        force = payload.force if payload else False
        notes = payload.notes if payload else None
        return await procurement_lifecycle_service.run_technical_scrutiny_command(
            procurement_id=procurement_id,
            actor=actor,
            force=force,
            notes=notes,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed executing technical scrutiny for '%s': %s", procurement_id, exc)
        raise HTTPException(status_code=500, detail=f"Internal error running technical scrutiny: {str(exc)}")


@router.get(
    "/procurements/{procurement_id}/technical-review",
    response_model=ProcurementTechnicalReviewResponse,
    summary="Get Officer Technical Review Representation",
    description="Retrieves the structured officer-facing Technical Review representation including bidder summaries, matrix, findings, freeze state, and Cover 2 readiness.",
)
async def get_technical_review_endpoint(
    procurement_id: str,
) -> ProcurementTechnicalReviewResponse:
    """Retrieves the full structured Technical Review representation."""
    try:
        return await procurement_lifecycle_service.get_procurement_technical_review_service(procurement_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed retrieving technical review for '%s': %s", procurement_id, exc)
        raise HTTPException(status_code=500, detail=f"Internal error retrieving technical review: {str(exc)}")


@router.post(
    "/procurements/{procurement_id}/cover2-gate",
    response_model=Cover2ReadinessResponse,
    summary="Evaluate and Advance Cover 2 Readiness Gate",
    description="Checks hard gating blockers (technical freeze enforced, open clarifications resolved, qualified bidders present) and advances state to COVER_2_READY if passed.",
)
@router.post(
    "/procurements/{procurement_id}/cover2-ready",
    response_model=Cover2ReadinessResponse,
    summary="Evaluate and Advance Cover 2 Readiness Gate",
)
@router.get(
    "/procurements/{procurement_id}/cover2-gate",
    response_model=Cover2ReadinessResponse,
    summary="Check Cover 2 Readiness Status",
)
async def evaluate_cover2_gate_endpoint(
    procurement_id: str,
) -> Cover2ReadinessResponse:
    """Evaluates Cover 2 financial opening readiness."""
    try:
        return await procurement_lifecycle_service.evaluate_cover2_gate_service(procurement_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed evaluating Cover 2 gate for '%s': %s", procurement_id, exc)
        raise HTTPException(status_code=500, detail=f"Internal error evaluating Cover 2 readiness: {str(exc)}")




