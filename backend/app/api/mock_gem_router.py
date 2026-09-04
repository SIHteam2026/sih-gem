"""Mock-GeM Simulated External Source Adapter.

Provides API endpoints simulating the future authorized GeM integration:
GeM / Authorized Source -> Mock-GeM Adapter -> Ingestion Boundary -> Canonical Database.

Note: Mock-GeM is a development/demo simulation tool; it is not a live GeM integration.
"""

import io
import json
import logging
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

try:
    from backend.app.models.procurement import (
        DocumentType,
        IngestionBidderInfo,
        IngestionBidderPackageInput,
        IngestionDocumentInput,
        IngestionProcurementInfo,
        IngestionSubmissionInfo,
        IngestionTenderInfo,
        ProcurementIngestionPayload,
        ProcurementIngestionResult,
        ProcurementStatus,
    )
    from backend.app.services.ingestion_service import (
        ProcurementIngestionError,
        ingest_procurement,
    )
except ImportError:
    from app.models.procurement import (
        DocumentType,
        IngestionBidderInfo,
        IngestionBidderPackageInput,
        IngestionDocumentInput,
        IngestionProcurementInfo,
        IngestionSubmissionInfo,
        IngestionTenderInfo,
        ProcurementIngestionPayload,
        ProcurementIngestionResult,
        ProcurementStatus,
    )
    from app.services.ingestion_service import (
        ProcurementIngestionError,
        ingest_procurement,
    )

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingest/mock-gem", tags=["Mock-GeM Ingestion"])


def create_cpcl_demo_payload() -> ProcurementIngestionPayload:
    """Constructs the canonical synthetic demo procurement package for CPCL:
    External Reference: DEMO/CPCL/WQM/2026/017
    Title: Supply and commissioning of industrial water quality monitoring units
    Source System: MOCK_GEM
    Bidders: 2 bidders (HydroTech Analytics & AquaPure Systems) with submissions and documents.
    """
    return ProcurementIngestionPayload(
        source_system="MOCK_GEM",
        external_reference="DEMO/CPCL/WQM/2026/017",
        procurement=IngestionProcurementInfo(
            title="Supply and commissioning of industrial water quality monitoring units",
            organization="Chennai Petroleum Corporation Limited (CPCL)",
        ),
        tender=IngestionTenderInfo(
            tender_reference="CPCL/WQM/2026/RFP-017",
            title="RFP for Industrial Water Quality Monitoring Sensor Network",
            description="Turnkey procurement of online water quality sensors and analyzer units.",
            estimated_value=45000000.0,
            category="INDUSTRIAL_EQUIPMENT",
            documents=[
                IngestionDocumentInput(
                    filename="RFP_Specification_WQM_2026_017.pdf",
                    document_type=DocumentType.TENDER_SPECIFICATION,
                    mime_type="application/pdf",
                    file_size=3240000,
                    storage_path="mock_storage/tenders/RFP_Specification_WQM_2026_017.pdf",
                    content_text="Notice Inviting Tender for CPCL Water Quality Sensors...",
                )
            ],
        ),
        bidders=[
            IngestionBidderPackageInput(
                bidder=IngestionBidderInfo(
                    legal_name="HydroTech Analytics India Pvt Ltd",
                    gstin="33AAACH123411Z9",
                    pan="AAACH12341",
                    email="bids@hydrotech.co.in",
                ),
                submission=IngestionSubmissionInfo(
                    external_submission_reference="GEM-SUB-HTA-2026-017",
                    submitted_at=datetime(2026, 9, 1, 10, 30, tzinfo=timezone.utc),
                    status="SUBMITTED",
                ),
                documents=[
                    IngestionDocumentInput(
                        filename="HydroTech_GST_Registration.pdf",
                        document_type=DocumentType.GST_CERTIFICATE,
                        mime_type="application/pdf",
                        file_size=450000,
                        storage_path="mock_storage/submissions/HTA_GST.pdf",
                        content_text="GSTIN: 33AAACH123411Z9 Legal Name: HydroTech Analytics...",
                    ),
                    IngestionDocumentInput(
                        filename="HydroTech_OEM_Authorization_WQM.pdf",
                        document_type=DocumentType.OEM_AUTHORIZATION,
                        mime_type="application/pdf",
                        file_size=890000,
                        storage_path="mock_storage/submissions/HTA_OEM.pdf",
                        content_text="OEM Authorization for WQM Sensors Model WQ-900...",
                    ),
                ],
            ),
            IngestionBidderPackageInput(
                bidder=IngestionBidderInfo(
                    legal_name="AquaPure Monitoring Systems & Instrumentation Ltd",
                    gstin="27BBBCA987622Z4",
                    pan="BBBCA98762",
                    email="tenders@aquapure.in",
                ),
                submission=IngestionSubmissionInfo(
                    external_submission_reference="GEM-SUB-APS-2026-017",
                    submitted_at=datetime(2026, 9, 1, 11, 15, tzinfo=timezone.utc),
                    status="SUBMITTED",
                ),
                documents=[
                    IngestionDocumentInput(
                        filename="AquaPure_Financial_Turnover_Audited.pdf",
                        document_type=DocumentType.TURNOVER_CERTIFICATE,
                        mime_type="application/pdf",
                        file_size=1560000,
                        storage_path="mock_storage/submissions/APS_Turnover.pdf",
                        content_text="CA Certified Turnover Certificate FY 2024-2025...",
                    )
                ],
            ),
        ],
    )


@router.post("", response_model=ProcurementIngestionResult)
async def ingest_mock_gem_package(payload: ProcurementIngestionPayload):
    """Ingests a structured simulated GeM procurement package.

    Enforces source_system = 'MOCK_GEM' and calls the canonical ingestion service.
    """
    try:
        # Enforce source system label
        payload.source_system = "MOCK_GEM"

        result = await ingest_procurement(payload)
        logger.info(
            "Mock-GeM package ingested successfully: %s (Created: %s, Bidders: %d)",
            result.external_reference,
            result.was_created,
            result.bidder_count,
        )
        return result
    except ProcurementIngestionError as pie:
        logger.error("Mock-GeM ingestion validation error: %s", pie)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(pie),
        )
    except Exception as err:
        logger.error("Mock-GeM ingestion unexpected error: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mock-GeM ingestion failed: {str(err)}",
        )


@router.post("/demo", response_model=ProcurementIngestionResult)
async def ingest_mock_gem_demo():
    """Ingests the pre-packaged synthetic CPCL Water Quality Monitoring procurement (DEMO/CPCL/WQM/2026/017).

    Demonstrates multi-bidder ingestion and idempotency verification.
    """
    try:
        demo_payload = create_cpcl_demo_payload()
        result = await ingest_procurement(demo_payload)
        logger.info(
            "Mock-GeM demo package ingested successfully: %s (Created: %s)",
            result.external_reference,
            result.was_created,
        )
        return result
    except Exception as err:
        logger.error("Mock-GeM demo ingestion failed: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mock-GeM demo ingestion failed: {str(err)}",
        )


@router.post("/zip", response_model=ProcurementIngestionResult)
async def ingest_mock_gem_zip(file: UploadFile = File(...)):
    """Ingests a ZIP archive package containing metadata.json and procurement documents."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only .zip archives are supported.",
        )

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded ZIP file: {str(e)}",
        )

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zip_ref:
            file_list = zip_ref.namelist()

            # Find metadata.json or package.json
            meta_filename = next(
                (f for f in file_list if f.endswith("metadata.json") or f.endswith("package.json")),
                None,
            )

            if not meta_filename:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ZIP package must contain a 'metadata.json' or 'package.json' file describing the procurement package.",
                )

            with zip_ref.open(meta_filename) as meta_file:
                raw_json = meta_file.read().decode("utf-8")
                payload_dict = json.loads(raw_json)

            # Enforce MOCK_GEM source system
            payload_dict["source_system"] = "MOCK_GEM"

            # Parse payload
            payload = ProcurementIngestionPayload.model_validate(payload_dict)

            # Process ingestion via canonical service
            result = await ingest_procurement(payload)
            return result

    except json.JSONDecodeError as jde:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed metadata.json in ZIP archive: {str(jde)}",
        )
    except ProcurementIngestionError as pie:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(pie),
        )
    except HTTPException:
        raise
    except Exception as err:
        logger.error("Failed to process Mock-GeM ZIP archive: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process Mock-GeM ZIP package: {str(err)}",
        )
