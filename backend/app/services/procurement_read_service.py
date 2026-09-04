"""Service layer for OPAL procurement workspace read queries.

This service is strictly a read boundary. It translates raw DB records into typed
Pydantic DTO models for workspace navigation without invoking OCR, LLM extraction,
compliance checks, or fraud evaluation workflows.
"""

import logging
from typing import List, Optional

from app.db import client as db_client
from app.models.procurement import (
    BidderSummaryResponse,
    DocumentMetadataResponse,
    ProcurementDetailResponse,
    ProcurementListResponse,
    ProcurementStatus,
    ProcurementSummaryItem,
    SubmissionSummaryResponse,
    TenderSummaryResponse,
    TenderWorkspaceDetailResponse,
)

logger = logging.getLogger(__name__)


def _map_document(doc_data: dict) -> DocumentMetadataResponse:
    """Helper to convert raw document dict to DocumentMetadataResponse."""
    return DocumentMetadataResponse(
        id=str(doc_data.get("id", "")),
        procurement_id=str(doc_data.get("procurement_id", "")),
        tender_id=str(doc_data["tender_id"]) if doc_data.get("tender_id") else None,
        bid_submission_id=str(doc_data["bid_submission_id"]) if doc_data.get("bid_submission_id") else None,
        filename=str(doc_data.get("filename", "")),
        document_type=doc_data.get("document_type"),
        mime_type=str(doc_data.get("mime_type", "application/pdf")),
        file_size=doc_data.get("file_size"),
        storage_path=doc_data.get("storage_path"),
        processing_status=str(doc_data.get("processing_status", "PENDING")),
        created_at=doc_data.get("created_at"),
        updated_at=doc_data.get("updated_at"),
    )


def _map_bidder(bidder_data: dict) -> BidderSummaryResponse:
    """Helper to convert raw bidder dict to BidderSummaryResponse."""
    return BidderSummaryResponse(
        id=str(bidder_data.get("id", "")),
        legal_name=str(bidder_data.get("legal_name", "")),
        gstin=bidder_data.get("gstin"),
        pan=bidder_data.get("pan"),
        email=bidder_data.get("email"),
        created_at=bidder_data.get("created_at"),
        updated_at=bidder_data.get("updated_at"),
    )


def _map_submission(sub_data: dict) -> SubmissionSummaryResponse:
    """Helper to convert raw submission dict to SubmissionSummaryResponse."""
    bidder_obj = None
    if sub_data.get("bidder") and isinstance(sub_data["bidder"], dict):
        bidder_obj = _map_bidder(sub_data["bidder"])

    raw_docs = sub_data.get("documents", []) or []
    mapped_docs = [_map_document(d) for d in raw_docs]

    return SubmissionSummaryResponse(
        id=str(sub_data.get("id", "")),
        tender_id=str(sub_data.get("tender_id", "")),
        bidder_id=str(sub_data.get("bidder_id", "")),
        external_submission_reference=sub_data.get("external_submission_reference"),
        submitted_at=sub_data.get("submitted_at"),
        status=str(sub_data.get("status", "SUBMITTED")),
        bidder=bidder_obj,
        documents=mapped_docs,
        document_count=sub_data.get("document_count", len(mapped_docs)),
        created_at=sub_data.get("created_at"),
        updated_at=sub_data.get("updated_at"),
    )


def _map_tender(tender_data: dict) -> TenderSummaryResponse:
    """Helper to convert raw tender dict to TenderSummaryResponse."""
    raw_docs = tender_data.get("documents", []) or []
    mapped_docs = [_map_document(d) for d in raw_docs]

    raw_subs = tender_data.get("submissions", []) or []
    mapped_subs = [_map_submission(s) for s in raw_subs]

    return TenderSummaryResponse(
        id=str(tender_data.get("id", "")),
        procurement_id=str(tender_data.get("procurement_id", "")),
        tender_reference=str(tender_data.get("tender_reference", "")),
        title=str(tender_data.get("title", "")),
        description=tender_data.get("description"),
        estimated_value=tender_data.get("estimated_value"),
        category=tender_data.get("category"),
        status=str(tender_data.get("status", "READY")),
        requirement_count=tender_data.get("requirement_count", 0),
        document_count=tender_data.get("document_count", len(mapped_docs)),
        bidder_count=tender_data.get("bidder_count", len(mapped_subs)),
        documents=mapped_docs,
        submissions=mapped_subs,
        created_at=tender_data.get("created_at"),
        updated_at=tender_data.get("updated_at"),
    )


async def list_procurements_service(limit: int = 50, offset: int = 0) -> ProcurementListResponse:
    """Retrieves paginated list of procurement summary items."""
    db_result = await db_client.list_procurements(limit=limit, offset=offset)
    items = db_result.get("items", [])
    total = db_result.get("total", len(items))

    procurement_items: List[ProcurementSummaryItem] = []
    for raw in items:
        status_val = raw.get("status", ProcurementStatus.IMPORTED)
        if isinstance(status_val, str):
            try:
                status_enum = ProcurementStatus(status_val)
            except ValueError:
                status_enum = ProcurementStatus.IMPORTED
        else:
            status_enum = status_val

        p_id = str(raw.get("id", ""))
        procurement_items.append(
            ProcurementSummaryItem(
                procurement_id=p_id,
                id=p_id,
                external_reference=str(raw.get("external_reference", "")),
                title=str(raw.get("title", "")),
                organization=str(raw.get("organization", "")),
                source_system=str(raw.get("source_system", "MOCK_GEM")),
                status=status_enum,
                tender_count=raw.get("tender_count", 0),
                bidder_count=raw.get("bidder_count", 0),
                document_count=raw.get("document_count", 0),
                created_at=raw.get("created_at"),
                updated_at=raw.get("updated_at"),
            )
        )

    return ProcurementListResponse(
        total=total,
        limit=limit,
        offset=offset,
        procurements=procurement_items,
    )


async def get_procurement_detail_service(procurement_id: str) -> Optional[ProcurementDetailResponse]:
    """Retrieves detailed procurement workspace data by ID."""
    raw = await db_client.get_procurement_detail_db(procurement_id)
    if not raw:
        return None

    status_val = raw.get("status", ProcurementStatus.IMPORTED)
    if isinstance(status_val, str):
        try:
            status_enum = ProcurementStatus(status_val)
        except ValueError:
            status_enum = ProcurementStatus.IMPORTED
    else:
        status_enum = status_val

    top_docs = [_map_document(d) for d in raw.get("documents", []) or []]
    tenders = [_map_tender(t) for t in raw.get("tenders", []) or []]

    return ProcurementDetailResponse(
        id=str(raw.get("id", "")),
        external_reference=str(raw.get("external_reference", "")),
        title=str(raw.get("title", "")),
        organization=str(raw.get("organization", "")),
        source_system=str(raw.get("source_system", "MOCK_GEM")),
        status=status_enum,
        tenders=tenders,
        documents=top_docs,
        created_at=raw.get("created_at"),
        updated_at=raw.get("updated_at"),
    )


async def get_tender_detail_service(tender_id: str) -> Optional[TenderWorkspaceDetailResponse]:
    """Retrieves detailed workspace response for a specific tender."""
    raw = await db_client.get_tender_detail_db(tender_id)
    if not raw:
        return None

    mapped_docs = [_map_document(d) for d in raw.get("documents", []) or []]
    mapped_subs = [_map_submission(s) for s in raw.get("submissions", []) or []]

    return TenderWorkspaceDetailResponse(
        id=str(raw.get("id", "")),
        procurement_id=str(raw.get("procurement_id", "")),
        procurement_title=raw.get("procurement_title"),
        procurement_external_reference=raw.get("procurement_external_reference"),
        source_system=raw.get("source_system"),
        tender_reference=str(raw.get("tender_reference", "")),
        title=str(raw.get("title", "")),
        description=raw.get("description"),
        estimated_value=raw.get("estimated_value"),
        category=raw.get("category"),
        status=str(raw.get("status", "READY")),
        requirement_count=raw.get("requirement_count", 0),
        document_count=raw.get("document_count", len(mapped_docs)),
        bidder_count=raw.get("bidder_count", len(mapped_subs)),
        documents=mapped_docs,
        submissions=mapped_subs,
        created_at=raw.get("created_at"),
        updated_at=raw.get("updated_at"),
    )


async def get_tender_submissions_service(tender_id: str) -> Optional[List[SubmissionSummaryResponse]]:
    """Retrieves submissions list for a specific tender."""
    raw_tender = await db_client.get_tender_detail_db(tender_id)
    if not raw_tender:
        return None

    mapped_subs = [_map_submission(s) for s in raw_tender.get("submissions", []) or []]
    return mapped_subs


async def get_submission_detail_service(submission_id: str) -> Optional[SubmissionSummaryResponse]:
    """Retrieves submission detail by submission ID."""
    raw_sub = await db_client.get_submission_detail_db(submission_id)
    if not raw_sub:
        return None

    return _map_submission(raw_sub)


async def get_bidder_detail_service(bidder_id: str) -> Optional[BidderSummaryResponse]:
    """Retrieves bidder profile details by bidder ID."""
    raw_bidder = await db_client.get_bidder_detail_db(bidder_id)
    if not raw_bidder:
        return None

    return _map_bidder(raw_bidder)
