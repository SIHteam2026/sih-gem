"""Procurement Ingestion Service.

Provides a reusable, source-agnostic ingestion pipeline for converting external
procurement packages into OPAL canonical domain entities:
Procurement -> Tender -> Bidder -> BidSubmission -> Documents.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from app.db.client import (
    get_procurement_by_source_and_ref,
    get_procurement_hierarchy,
    insert_bid_submission,
    insert_bidder,
    insert_document,
    insert_procurement,
    insert_tender,
)
from app.models.procurement import (
    Bidder,
    BidSubmission,
    BidSubmissionWithDetails,
    Document,
    DocumentType,
    Procurement,
    ProcurementHierarchy,
    ProcurementIngestionPayload,
    ProcurementIngestionResult,
    ProcurementStatus,
    Tender,
    TenderWithDetails,
)

logger = logging.getLogger(__name__)


class ProcurementIngestionError(Exception):
    """Custom exception raised when procurement ingestion fails."""
    pass


async def ingest_procurement(
    payload: Union[ProcurementIngestionPayload, Dict[str, Any]]
) -> ProcurementIngestionResult:
    """Ingests an external procurement package into OPAL canonical entities.

    Operations:
    1. Validates and parses the typed input payload contract.
    2. Enforces database-level idempotency via source_system + external_reference uniqueness.
    3. Creates canonical Procurement workspace (staged: PROCESSING -> READY / FAILED).
    4. Creates associated Tender entity.
    5. Resolves/creates Bidders and BidSubmissions for multiple bidders.
    6. Registers Tender and Bidder-Submission Documents with correct context references.
    7. Returns a structured ProcurementIngestionResult summary.
    """
    # 1. Validate payload using Pydantic contract
    if isinstance(payload, dict):
        try:
            validated_payload = ProcurementIngestionPayload.model_validate(payload)
        except Exception as ve:
            raise ProcurementIngestionError(f"Invalid procurement ingestion payload: {str(ve)}")
    elif isinstance(payload, ProcurementIngestionPayload):
        validated_payload = payload
    else:
        raise ProcurementIngestionError("Payload must be a dict or ProcurementIngestionPayload instance.")

    source_system = validated_payload.source_system.strip()
    external_reference = validated_payload.external_reference.strip()

    if not source_system or not external_reference:
        raise ProcurementIngestionError("Both source_system and external_reference must be non-empty strings.")

    # 2. Database-level Idempotency Check
    existing_proc = await get_procurement_by_source_and_ref(source_system, external_reference)
    if existing_proc:
        proc_id = existing_proc["id"]
        logger.info(
            "Idempotency match: Procurement (%s, %s) already exists with ID %s.",
            source_system,
            external_reference,
            proc_id,
        )
        try:
            hierarchy_dict = await get_procurement_hierarchy(proc_id)
            hierarchy = ProcurementHierarchy.model_validate(hierarchy_dict)
            tender_id = hierarchy.tenders[0].id if hierarchy.tenders else proc_id
            b_count = sum(len(t.submissions) for t in hierarchy.tenders)
            d_count = sum(len(t.documents) + sum(len(s.documents) for s in t.submissions) for t in hierarchy.tenders)
        except Exception:
            hierarchy = None
            tender_id = proc_id
            b_count = 0
            d_count = 0

        return ProcurementIngestionResult(
            procurement_id=proc_id,
            source_system=source_system,
            external_reference=external_reference,
            tender_id=tender_id,
            bidder_count=b_count,
            submission_count=b_count,
            document_count=d_count,
            status=ProcurementStatus(existing_proc.get("status", "READY")),
            was_created=False,
            message=f"Procurement package already exists (Idempotent match for {external_reference}).",
            hierarchy=hierarchy,
        )

    # 3. Create Procurement Workspace (Staged Processing)
    proc_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    proc_record = {
        "id": proc_id,
        "source_system": source_system,
        "external_reference": external_reference,
        "title": validated_payload.procurement.title,
        "organization": validated_payload.procurement.organization,
        "status": ProcurementStatus.PROCESSING.value,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    try:
        created_proc = await insert_procurement(proc_record)
    except Exception as db_err:
        logger.error("Failed to insert procurement record: %s", db_err)
        raise ProcurementIngestionError(f"Database failure creating procurement: {str(db_err)}")

    document_count = 0
    bidder_count = 0
    submission_count = 0

    try:
        # 4. Create Tender Entity
        tender_id = str(uuid.uuid4())
        tender_record = {
            "id": tender_id,
            "procurement_id": proc_id,
            "tender_reference": validated_payload.tender.tender_reference,
            "title": validated_payload.tender.title,
            "description": validated_payload.tender.description,
            "estimated_value": validated_payload.tender.estimated_value,
            "category": validated_payload.tender.category,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        await insert_tender(tender_record)

        # 5. Register Tender Specification Documents
        for t_doc in validated_payload.tender.documents:
            doc_id = str(uuid.uuid4())
            doc_record = {
                "id": doc_id,
                "procurement_id": proc_id,
                "tender_id": tender_id,
                "bid_submission_id": None,
                "filename": t_doc.filename,
                "document_type": t_doc.document_type.value if hasattr(t_doc.document_type, "value") else (t_doc.document_type or "TENDER_SPECIFICATION"),
                "mime_type": t_doc.mime_type or "application/pdf",
                "file_size": t_doc.file_size,
                "storage_path": t_doc.storage_path,
                "content_text": t_doc.content_text,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            await insert_document(doc_record)
            document_count += 1

        # 6. Process Multiple Bidders & Submissions
        for pkg in validated_payload.bidders:
            # Create Bidder
            bidder_id = str(uuid.uuid4())
            bidder_record = {
                "id": bidder_id,
                "legal_name": pkg.bidder.legal_name,
                "gstin": pkg.bidder.gstin,
                "pan": pkg.bidder.pan,
                "email": pkg.bidder.email,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            await insert_bidder(bidder_record)
            bidder_count += 1

            # Create Bid Submission
            sub_id = str(uuid.uuid4())
            sub_info = pkg.submission
            sub_record = {
                "id": sub_id,
                "tender_id": tender_id,
                "bidder_id": bidder_id,
                "external_submission_reference": sub_info.external_submission_reference if sub_info else None,
                "submitted_at": sub_info.submitted_at.isoformat() if (sub_info and sub_info.submitted_at) else now_iso,
                "status": sub_info.status if sub_info else "SUBMITTED",
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            await insert_bid_submission(sub_record)
            submission_count += 1

            # Register Bidder Submission Documents
            for b_doc in pkg.documents:
                b_doc_id = str(uuid.uuid4())
                b_doc_record = {
                    "id": b_doc_id,
                    "procurement_id": proc_id,
                    "tender_id": tender_id,
                    "bid_submission_id": sub_id,
                    "filename": b_doc.filename,
                    "document_type": b_doc.document_type.value if hasattr(b_doc.document_type, "value") else (b_doc.document_type or "OTHER"),
                    "mime_type": b_doc.mime_type or "application/pdf",
                    "file_size": b_doc.file_size,
                    "storage_path": b_doc.storage_path,
                    "content_text": b_doc.content_text,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }
                await insert_document(b_doc_record)
                document_count += 1

        # 7. Finalize Procurement Status to READY
        try:
            from app.db.client import get_supabase_client
            db_client = get_supabase_client()
            await asyncio.to_thread(
                lambda: db_client.table("procurements").update({"status": ProcurementStatus.READY.value}).eq("id", proc_id).execute()
            )
        except Exception as st_err:
            logger.warning("Non-blocking status update error: %s", st_err)

        # 8. Retrieve and Return Final Hierarchy
        hierarchy = None
        try:
            h_dict = await get_procurement_hierarchy(proc_id)
            hierarchy = ProcurementHierarchy.model_validate(h_dict)
        except Exception as h_err:
            logger.warning("Could not assemble full hierarchy model: %s", h_err)

        return ProcurementIngestionResult(
            procurement_id=proc_id,
            source_system=source_system,
            external_reference=external_reference,
            tender_id=tender_id,
            bidder_count=bidder_count,
            submission_count=submission_count,
            document_count=document_count,
            status=ProcurementStatus.READY,
            was_created=True,
            message=f"Successfully ingested procurement package '{external_reference}' with {bidder_count} bidders and {document_count} documents.",
            hierarchy=hierarchy,
        )

    except Exception as exc:
        logger.error("Ingestion failed for procurement %s: %s", external_reference, exc)
        # Mark procurement state as FAILED
        try:
            from app.db.client import get_supabase_client
            db_client = get_supabase_client()
            await asyncio.to_thread(
                lambda: db_client.table("procurements").update({"status": ProcurementStatus.FAILED.value}).eq("id", proc_id).execute()
            )
        except Exception:
            pass
        raise ProcurementIngestionError(f"Ingestion failed for procurement '{external_reference}': {str(exc)}")
