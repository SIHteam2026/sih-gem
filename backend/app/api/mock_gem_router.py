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
    Bidders:
      1. HydroTech Analytics: Fully compliant bidder with valid GST, 27.5% Local Content, ₹14.5 Cr Turnover, and OEM MAF.
      2. AquaPure Systems: Non-compliant / contradictory bidder with 14% Local Content (fails 20% rule) and ₹6.5 Cr Turnover (fails ₹10 Cr rule).
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
            description="Turnkey procurement of online water quality sensors and analyzer units with mandatory GST, >=20% Local Content, >=Rs 10 Cr Turnover, and OEM MAF.",
            estimated_value=45000000.0,
            category="INDUSTRIAL_EQUIPMENT",
            documents=[
                IngestionDocumentInput(
                    filename="RFP_Specification_WQM_2026_017.pdf",
                    document_type=DocumentType.TENDER_SPECIFICATION,
                    mime_type="application/pdf",
                    file_size=3240000,
                    storage_path="mock_storage/tenders/RFP_Specification_WQM_2026_017.pdf",
                    content_text="Chennai Petroleum Corporation Limited (CPCL) - Notice Inviting Tender (NIT)\nClause 1: Bidder must have active GSTIN registration.\nClause 2: Minimum local content under Make in India policy shall be 20.0%.\nClause 3: Average annual financial turnover over past 3 years shall be greater than or equal to Rs. 10.0 Crores.\nClause 4: Bidder must submit valid OEM Manufacturer Authorization Form (MAF).",
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
                        content_text="Government of India - GST Registration Certificate (Form GST REG-06)\nGSTIN: 33AAACH123411Z9\nLegal Name: HydroTech Analytics India Pvt Ltd\nTrade Name: HydroTech Analytics\nStatus: ACTIVE\nDate of Registration: 01/07/2017\nPrincipal Place of Business: Guindy Industrial Estate, Chennai, Tamil Nadu - 600032",
                    ),
                    IngestionDocumentInput(
                        filename="HydroTech_MII_LocalContent_Declaration.pdf",
                        document_type=DocumentType.LOCAL_CONTENT_CERTIFICATE,
                        mime_type="application/pdf",
                        file_size=520000,
                        storage_path="mock_storage/submissions/HTA_MII.pdf",
                        content_text="Make in India (MII) Local Content Declaration & Certificate\nUnder Public Procurement (Preference to Make in India) Order 2017\nWe hereby certify and declare that the Local Content for Model WQ-900 Industrial Online Water Quality Monitoring Units is 27.5%.\nLocation of local value addition: Chennai, Tamil Nadu, India.",
                    ),
                    IngestionDocumentInput(
                        filename="HydroTech_CA_Turnover_Certificate.pdf",
                        document_type=DocumentType.TURNOVER_CERTIFICATE,
                        mime_type="application/pdf",
                        file_size=680000,
                        storage_path="mock_storage/submissions/HTA_Turnover.pdf",
                        content_text="Chartered Accountant Certificate of Annual Financial Turnover\nUDIN: 24089123AAAAAA1001\nThis is to certify that average annual turnover of M/s HydroTech Analytics India Pvt Ltd for the past 3 financial years (FY 2022-23, FY 2023-24, FY 2024-25) is INR 14.50 Crores (INR 145000000).",
                    ),
                    IngestionDocumentInput(
                        filename="HydroTech_OEM_Authorization_WQM.pdf",
                        document_type=DocumentType.OEM_AUTHORIZATION,
                        mime_type="application/pdf",
                        file_size=890000,
                        storage_path="mock_storage/submissions/HTA_OEM.pdf",
                        content_text="Manufacturer Authorization Form (MAF)\nTo: Chennai Petroleum Corporation Limited (CPCL)\nWe, Global Sensors GmbH (OEM), hereby authorize M/s HydroTech Analytics India Pvt Ltd as our authorized distributor and service partner for Model WQ-900 water quality monitoring analyzers with full warranty support.",
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
                        filename="AquaPure_GST_Registration.pdf",
                        document_type=DocumentType.GST_CERTIFICATE,
                        mime_type="application/pdf",
                        file_size=420000,
                        storage_path="mock_storage/submissions/APS_GST.pdf",
                        content_text="Government of India - GST Registration Certificate\nGSTIN: 27BBBCA987622Z4\nLegal Name: AquaPure Monitoring Systems & Instrumentation Ltd\nStatus: ACTIVE",
                    ),
                    IngestionDocumentInput(
                        filename="AquaPure_MII_Declaration.pdf",
                        document_type=DocumentType.LOCAL_CONTENT_CERTIFICATE,
                        mime_type="application/pdf",
                        file_size=510000,
                        storage_path="mock_storage/submissions/APS_MII.pdf",
                        content_text="Make in India Self-Declaration:\nWe hereby declare that our offered sensor units contain 27.0% local content.",
                    ),
                    IngestionDocumentInput(
                        filename="AquaPure_MII_Auditor_Certificate.pdf",
                        document_type=DocumentType.OTHER,
                        mime_type="application/pdf",
                        file_size=510000,
                        storage_path="mock_storage/submissions/APS_MII_Cert.pdf",
                        content_text="CA Auditor Certificate:\nUpon audit, the local content for AquaPure is verified as 14.0%.",
                    ),
                    IngestionDocumentInput(
                        filename="AquaPure_Financial_Turnover_Audited.pdf",
                        document_type=DocumentType.TURNOVER_CERTIFICATE,
                        mime_type="application/pdf",
                        file_size=1560000,
                        storage_path="mock_storage/submissions/APS_Turnover.pdf",
                        content_text="CA Certified Turnover Certificate:\nThe average annual turnover of AquaPure Monitoring Systems over the past 3 financial years is INR 6.50 Crores (INR 65000000).",
                    ),
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
