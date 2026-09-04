"""API router for OPAL Procurement Workspace read endpoints.

Provides read-only query access for navigating procurements, tenders, bidder submissions,
and bidder profiles. Thin route handlers delegate business logic to procurement_read_service.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Query

try:
    from backend.app.models.procurement import (
        BidderSummaryResponse,
        ProcurementDetailResponse,
        ProcurementListResponse,
        ProcurementProcessingStatusResponse,
        StartProcessingResponse,
        SubmissionSummaryResponse,
        TenderWorkspaceDetailResponse,
    )
    from backend.app.services import procurement_processing_service, procurement_read_service
except ImportError:
    from app.models.procurement import (
        BidderSummaryResponse,
        ProcurementDetailResponse,
        ProcurementListResponse,
        ProcurementProcessingStatusResponse,
        StartProcessingResponse,
        SubmissionSummaryResponse,
        TenderWorkspaceDetailResponse,
    )
    from app.services import procurement_processing_service, procurement_read_service

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

