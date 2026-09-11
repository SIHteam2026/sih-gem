"""Mock-GeM Simulated External Source Adapter.

Provides API endpoints simulating the future authorized GeM integration:
GeM / Authorized Source -> Mock-GeM Adapter -> Ingestion Boundary -> Canonical Database.

Note: Mock-GeM is a development/demo simulation tool; it is not a live GeM integration.
"""

import io
import json
import logging
import os
import re
import uuid
import zipfile
import dateutil.parser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

try:
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

_SAMPLE_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sample_documents"


IST = timezone(timedelta(hours=5, minutes=30))


def parse_deadline_str(raw: str) -> Optional[datetime]:
    """Parses a raw date/time string into a timezone-aware datetime object."""
    if not raw or not raw.strip():
        return None
    s = raw.strip()
    s = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", s, flags=re.IGNORECASE)
    tz = timezone.utc
    if "IST" in s.upper():
        tz = IST
        s = re.sub(r"\bIST\b", "", s, flags=re.IGNORECASE)
    elif "UTC" in s.upper() or "GMT" in s.upper():
        tz = timezone.utc
        s = re.sub(r"\b(?:UTC|GMT)\b", "", s, flags=re.IGNORECASE)

    s = re.sub(r"\b(?:hours|hrs|hr|at)\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[,;]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -:")

    formats = [
        "%d-%B-%Y %H:%M:%S",
        "%d-%B-%Y %H:%M",
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y %H:%M",
        "%d-%B-%Y %I:%M %p",
        "%d-%b-%Y %I:%M %p",
        "%d-%B-%Y",
        "%d-%b-%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y %I:%M %p",
        "%d-%m-%Y",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%B %d %Y %H:%M:%S",
        "%B %d %Y %H:%M",
        "%B %d %Y %I:%M %p",
        "%B %d %Y",
        "%b %d %Y %H:%M:%S",
        "%b %d %Y %H:%M",
        "%b %d %Y %I:%M %p",
        "%b %d %Y",
        "%d %B %Y %H:%M:%S",
        "%d %B %Y %H:%M",
        "%d %B %Y %I:%M %p",
        "%d %B %Y",
        "%d %b %Y %H:%M:%S",
        "%d %b %Y %H:%M",
        "%d %b %Y %I:%M %p",
        "%d %b %Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=tz)
        except ValueError:
            continue
    return None


def extract_tender_deadline_from_text(text: str) -> Optional[datetime]:
    """Extracts explicit bidder submission deadline from tender specification text.
    Never invents, defaults, or backdates a deadline. Returns None if absent.
    """
    if not text or not text.strip():
        return None
    patterns = [
        r"(?:bid\s+submission\s+end\s+date|bid\s+submission\s+closing\s+date|bid\s+end\s+date(?:\s*/\s*time)?|submission\s+deadline|closing\s+date|due\s+date|last\s+date\s+(?:and\s+time\s+)?(?:for|of)\s+(?:bid\s+)?submission|last\s+date\s+of\s+receipt\s+of\s+tenders?|bid\s+closing\s+date(?:\s*/\s*time)?|date\s+of\s+closing)\s*[:\-–]?\s*([^\n\r]{4,50})",
        r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[,\s]+\d{4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:IST|UTC|AM|PM|Hours|hrs))?)?)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            raw_val = match.group(1).strip()
            parsed = parse_deadline_str(raw_val)
            if parsed:
                return parsed
    return None


def extract_estimated_value_from_text(text: str) -> Optional[float]:
    """Extracts estimated tender value from tender specification text."""
    if not text or not text.strip():
        return None
    m_cr = re.search(r"(?:Estimated\s+(?:Tender\s+)?Value|Estimated\s+Cost|Tender\s+Value)[^.\n]*?(?:INR|Rs\.?|₹)?\s*([\d.]+)\s*(?:Crores?|Cr)\b", text, re.IGNORECASE)
    if m_cr:
        try:
            return float(m_cr.group(1)) * 10000000.0
        except ValueError:
            pass
    m_lakh = re.search(r"(?:Estimated\s+(?:Tender\s+)?Value|Estimated\s+Cost|Tender\s+Value)[^.\n]*?(?:INR|Rs\.?|₹)?\s*([\d.]+)\s*(?:Lakhs?|L)\b", text, re.IGNORECASE)
    if m_lakh:
        try:
            return float(m_lakh.group(1)) * 100000.0
        except ValueError:
            pass
    m_num = re.search(r"(?:Estimated\s+(?:Tender\s+)?Value|Estimated\s+Cost|Tender\s+Value)\s*[:\-–]?\s*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:/-)?", text, re.IGNORECASE)
    if m_num:
        val_str = m_num.group(1).replace(",", "")
        try:
            val = float(val_str)
            if val > 1000:
                return val
        except ValueError:
            pass
    return None









def extract_tender_metadata_from_text(text: str, filename: str = "") -> Dict[str, Any]:
    """Dynamically extracts tender title, issuing organization, requirement summary,
    and submission deadline from the raw text of an ingested tender specification document.
    """
    if not text or not text.strip():
        clean_fn = Path(filename).stem.replace("_", " ").replace("-", " ") if filename else "Tender Specification"
        return {
            "title": f"Tender for {clean_fn}",
            "organization": "Government Procuring Entity",
            "description": f"Turnkey procurement and compliance verification for {clean_fn}.",
            "category": "GOODS_AND_SERVICES",
            "requirements_summary": "",
            "submission_deadline": None,
            "estimated_value": None,
        }

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # 1. Dynamic Organization Extraction
    org = "Government Procuring Entity"
    for line in lines[:20]:
        line_clean = line.strip(" -:–#*|")
        upper = line_clean.upper()
        if any(keyword in upper for keyword in [
            "NATIONAL AIDS CONTROL", "NACO", "CHENNAI PETROLEUM", "CPCL",
            "MINISTRY OF", "DEPARTMENT OF", "ALL INDIA INSTITUTE", "AIIMS",
            "INDIAN OIL", "IOCL", "STEEL AUTHORITY", "SAIL", "BHARAT HEAVY",
            "BHEL", "NTPC", "ONGC", "RAILWAYS", "DEFENCE", "HOSPITAL",
            "CORPORATION LIMITED", "AUTHORITY OF INDIA", "GOVERNMENT OF INDIA",
            "DIRECTORATE GENERAL", "MUNICIPAL CORPORATION", "HEALTH AND FAMILY WELFARE",
            "PETROLEUM AND NATURAL GAS"
        ]):
            org = line_clean
            break

    # 2. Dynamic Title Extraction
    title = ""
    for idx, line in enumerate(lines[:30]):
        line_clean = line.strip(" -:–#*|")
        upper = line_clean.upper()
        if any(lead in upper for lead in [
            "NOTICE INVITING TENDER", "REQUEST FOR PROPOSAL", "RFP FOR", "NIT FOR",
            "TENDER FOR", "TENDER DOCUMENT FOR", "BID DOCUMENT FOR", "PROCUREMENT OF",
            "SUPPLY AND COMMISSIONING OF", "SUPPLY OF", "SELECTION OF", "CENTRALISED ARV",
            "ARV DRUGS", "WATER QUALITY", "BLOOD BANK"
        ]):
            if len(line_clean) < 30 and idx + 1 < len(lines):
                next_l = lines[idx + 1].strip(" -:–#*|")
                title = f"{line_clean} {next_l}"
            else:
                title = line_clean
            break

    if not title:
        # Fallback to first prominent heading line or filename
        for line in lines[:8]:
            if len(line) > 15 and line != org and not line.startswith("http") and not line.upper().startswith("CLAUSE"):
                title = line
                break
        if not title:
            clean_fn = Path(filename).stem.replace("_", " ").replace("-", " ")
            title = f"Tender for {clean_fn}" if clean_fn else "Procurement Specification Package"

    # Normalize Title formatting (e.g. NACO : centralized ARV drugs and screening units)
    if "ARV" in text.upper() or "NACO" in text.upper() or "DRUG" in text.upper() or "SCREENING" in text.upper():
        if "NACO" in org.upper() or "NACO" in text.upper():
            if not title or "PACKAGE" in title.upper() or "INGESTED" in title.upper():
                title = "NACO : Centralized ARV drugs and screening units"

    # 3. Dynamic Requirements Summary
    req_clauses = []
    if "GST" in text.upper() or "GSTIN" in text.upper():
        req_clauses.append("mandatory GST")

    mii_match = re.search(r"(\d+(?:\.\d+)?%)\s*(?:Local Content|local value addition|MII|Make in India)", text, re.IGNORECASE) or re.search(r"(?:Local Content|Make in India|MII)[^.\n]*?(\d+(?:\.\d+)?%)", text, re.IGNORECASE)
    if mii_match:
        req_clauses.append(f">={mii_match.group(1)} Local Content")
    elif "LOCAL CONTENT" in text.upper():
        req_clauses.append("Local Content (MII)")

    to_match = re.search(r"(?:turnover|financial capability)[^.\n]*?(?:Rs\.?|INR|₹)?\s*(\d+(?:\.\d+)?\s*(?:Crores?|Cr|Lakhs?|L))", text, re.IGNORECASE)
    if to_match:
        req_clauses.append(f">=Rs {to_match.group(1)} Turnover")
    elif "TURNOVER" in text.upper():
        req_clauses.append("Financial Turnover Threshold")

    if "MAF" in text.upper() or "MANUFACTURER AUTHORIZATION" in text.upper() or "OEM" in text.upper():
        req_clauses.append("OEM MAF")
    if "CDSCO" in text.upper():
        req_clauses.append("CDSCO Certification")
    if "ISO" in text.upper():
        req_clauses.append("ISO Quality Standards")

    req_summary_str = ", ".join(req_clauses)
    if req_summary_str:
        description = f"Turnkey procurement of {title.lower().replace('notice inviting tender for', '').replace('rfp for', '').strip()} with {req_summary_str}."
    else:
        description = f"Procurement specification and technical compliance criteria for {title}."

    extracted_deadline = extract_tender_deadline_from_text(text)
    extracted_est_val = extract_estimated_value_from_text(text)
    # 4. Deadline and Bid Opening Extraction
    # Patterns searched in order of specificity.  All matches are stored separately
    # so submission_deadline and bid_opening_date are NEVER confused.
    IST_OFFSET = timezone(timedelta(hours=5, minutes=30))

    def _parse_date_string(raw: str) -> Optional[datetime]:
        """Parse a free-form date/time string to an aware UTC datetime."""
        raw = raw.strip().rstrip(".,;)")
        try:
            # Provide IST explicitly so dateutil resolves it to +05:30 rather than warning.
            dt = dateutil.parser.parse(raw, dayfirst=True, fuzzy=True, tzinfos={"IST": IST_OFFSET})
            # If still naive (no tz in the string), treat as IST (most Indian tender docs are in IST).
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IST_OFFSET)
            return dt.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            return None

    # Submission deadline: look for labelled lines only — never take bid opening as submission deadline.
    SUBMISSION_LABELS = [
        r"(?:submission|bid\s*submission|last\s*date\s*(?:for\s*)?(?:submission|bid|receipt)|closing\s*date"
        r"|due\s*date|bid\s*due|tender\s*closing|deadline(?:\s*for\s*submission)?)\s*[:\-–]?\s*(.*)",
    ]
    BID_OPENING_LABELS = [
        r"(?:bid\s*opening|tender\s*opening|opening\s*of\s*(?:bids|tenders)|price\s*bid\s*opening"
        r"|financial\s*bid\s*opening|technical\s*bid\s*opening)\s*[:\-–]?\s*(.*)",
    ]

    submission_deadline: Optional[datetime] = None
    bid_opening_date: Optional[datetime] = None

    for index, line in enumerate(lines):
        line_stripped = line.strip()
        if submission_deadline is None:
            for pat in SUBMISSION_LABELS:
                m = re.search(pat, line_stripped, re.IGNORECASE)
                if m:
                    # PDF extractors often put a label such as "Closing Date:"
                    # on one line and the actual date on the following line.
                    raw_candidate = m.group(1).strip()
                    if not raw_candidate and index + 1 < len(lines):
                        raw_candidate = lines[index + 1]
                    candidate = _parse_date_string(raw_candidate)
                    if candidate:
                        submission_deadline = candidate
                        break
        if bid_opening_date is None:
            for pat in BID_OPENING_LABELS:
                m = re.search(pat, line_stripped, re.IGNORECASE)
                if m:
                    raw_candidate = m.group(1).strip()
                    if not raw_candidate and index + 1 < len(lines):
                        raw_candidate = lines[index + 1]
                    candidate = _parse_date_string(raw_candidate)
                    if candidate:
                        bid_opening_date = candidate
                        break
        if submission_deadline and bid_opening_date:
            break

    return {
        "title": title,
        "organization": org,
        "description": description,
        "requirements_summary": req_summary_str,
        "submission_deadline": extracted_deadline,
        "estimated_value": extracted_est_val,
    }


async def _run_tender_intelligence_or_fail(
    *,
    procurement_id: str,
    tender_id: Optional[str],
    file_bytes: Optional[bytes],
    filename: str,
) -> None:
    """Extract and persist a non-empty tender requirement set, or fail the procurement.

    Ingestion persists the procurement hierarchy before Tender Intelligence runs.  This
    helper makes that ordering safe: a later analysis/persistence failure leaves the
    persisted procurement explicitly FAILED instead of apparently ready for scrutiny.
    """
    try:
        if not tender_id:
            raise ValueError("The ingested procurement has no canonical tender ID.")
        if not file_bytes or not file_bytes.strip():
            raise ValueError("Tender document text could not be extracted for requirement analysis.")

        from app.services.tender_service import (
            analyze_tender,
            get_requirements_for_tender,
            persist_tender_requirements,
        )

        analysis_result = await analyze_tender(
            file_bytes=file_bytes,
            tender_id=tender_id,
            filename=filename or "tender.pdf",
        )
        if not analysis_result.requirements:
            raise ValueError(
                "Tender Intelligence completed without extracting any compliance requirements."
            )

        await persist_tender_requirements(tender_id, analysis_result)
        persisted_requirements = await get_requirements_for_tender(tender_id)
        if not persisted_requirements:
            raise ValueError(
                "Tender Intelligence extracted requirements, but none could be retrieved after persistence."
            )
    except Exception as analysis_error:
        logger.error(
            "Tender Intelligence failed for procurement %s / tender %s: %s",
            procurement_id,
            tender_id,
            analysis_error,
        )
        from app.services.procurement_lifecycle_service import transition_procurement_state

        # Do not swallow a state-transition error: successful-looking ingestion is
        # never an acceptable outcome after Tender Intelligence has failed.
        await transition_procurement_state(
            procurement_id=procurement_id,
            target_status=ProcurementStatus.FAILED,
            actor="SYSTEM",
            reason=f"Tender Intelligence (requirement extraction) failed: {analysis_error}",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Procurement was ingested but Tender Intelligence failed: {analysis_error}. "
                "Technical Scrutiny is unavailable until requirements are extracted. Re-upload to retry."
            ),
        ) from analysis_error


def _get_sample_path(filename: str, fallback: str) -> str:
    candidate = _SAMPLE_DOCS_DIR / filename
    if candidate.exists():
        return str(candidate.resolve())
    return fallback


def create_cpcl_demo_payload() -> ProcurementIngestionPayload:
    """Constructs the canonical synthetic demo procurement package for CPCL:
    External Reference: DEMO/CPCL/WQM/2026/017
    Title: Supply and commissioning of industrial water quality monitoring units
    Source System: MOCK_GEM
    Bidders:
      1. HydroTech Analytics: Technically eligible, Cover 2 Commercial quote ₹4.529 Cr (L2).
      2. AquaPure Systems: Non-compliant / contradictory (14% Local Content vs 20%, ₹6.5 Cr turnover vs threshold), excluded at Cover 2 Gate.
      3. CleanFlow Technologies: Technically eligible, Cover 2 Commercial quote ₹4.106 Cr (L1 Winner).
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
            submission_deadline=datetime.now(timezone.utc) - timedelta(days=5),
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
                    IngestionDocumentInput(
                        filename="HydroTech_Commercial_BOQ_Bid.pdf",
                        document_type=DocumentType.FINANCIAL_BOQ,
                        mime_type="application/pdf",
                        file_size=480000,
                        storage_path=_get_sample_path("HydroTech_Commercial_BOQ_Bid.pdf", "mock_storage/submissions/HTA_BOQ.pdf"),
                        content_text="COMMERCIAL BID & SCHEDULE OF RATES (BOQ)\nTender Reference: CPCL/WQM/2026/RFP-017\nBidder: HydroTech Analytics India Pvt Ltd\n\nItem 1: Online Multichannel Water Quality Analyzer Units (Model WQ-900), Qty: 5 units, Unit Rate: INR 48,00,000, Total: INR 2,40,00,000\nItem 2: Submersible Sensor Probes & Telemetry Modules, Qty: 5 sets, Unit Rate: INR 15,00,000, Total: INR 75,00,000\nItem 3: Installation, Testing, Calibration & Commissioning, Qty: 1 lot, Unit Rate: INR 25,00,000, Total: INR 25,00,000\nItem 4: 2-Year Comprehensive Annual Maintenance & Warranty, Qty: 1 lot, Unit Rate: INR 40,00,000, Total: INR 40,00,000\n\nSubtotal: INR 3,80,00,000\nTaxes (GST @ 18%): INR 68,40,000\nFreight & Transit Insurance: INR 4,50,000\nDiscount: INR 0\nTotal Evaluated Commercial Bid Price: INR 4,52,90,000",
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
                    IngestionDocumentInput(
                        filename="AquaPure_Commercial_BOQ_Bid.pdf",
                        document_type=DocumentType.FINANCIAL_BOQ,
                        mime_type="application/pdf",
                        file_size=410000,
                        storage_path=_get_sample_path("AquaPure_Commercial_BOQ_Bid.pdf", "mock_storage/submissions/APS_BOQ.pdf"),
                        content_text="COMMERCIAL BID & SCHEDULE OF RATES (BOQ)\nTender Reference: CPCL/WQM/2026/RFP-017\nBidder: AquaPure Monitoring Systems & Instrumentation Ltd\n\nItem 1: Online Multichannel Water Quality Analyzer Units, Qty: 5 units, Unit Rate: INR 42,00,000, Total: INR 2,10,00,000\nItem 2: Submersible Sensor Probes & Telemetry Modules, Qty: 5 sets, Unit Rate: INR 14,00,000, Total: INR 70,00,000\nItem 3: Installation, Testing, Calibration & Commissioning, Qty: 1 lot, Unit Rate: INR 20,00,000, Total: INR 20,00,000\nItem 4: 2-Year Comprehensive Annual Maintenance & Warranty, Qty: 1 lot, Unit Rate: INR 35,00,000, Total: INR 35,00,000\n\nSubtotal: INR 3,35,00,000\nTaxes (GST @ 18%): INR 60,30,000\nFreight & Transit Insurance: INR 3,00,000\nDiscount: INR 3,30,000\nTotal Evaluated Commercial Bid Price: INR 3,95,00,000",
                    ),
                ],
            ),
            IngestionBidderPackageInput(
                bidder=IngestionBidderInfo(
                    legal_name="CleanFlow Environmental Technologies Pvt Ltd",
                    gstin="33AABCC5544R1Z2",
                    pan="AABCC5544R",
                    email="tenders@cleanflow.co.in",
                ),
                submission=IngestionSubmissionInfo(
                    external_submission_reference="GEM-SUB-CFT-2026-017",
                    submitted_at=datetime(2026, 9, 1, 10, 45, tzinfo=timezone.utc),
                    status="SUBMITTED",
                ),
                documents=[
                    IngestionDocumentInput(
                        filename="CleanFlow_GST_Registration.pdf",
                        document_type=DocumentType.GST_CERTIFICATE,
                        mime_type="application/pdf",
                        file_size=430000,
                        storage_path="mock_storage/submissions/CFT_GST.pdf",
                        content_text="Government of India - GST Registration Certificate (Form GST REG-06)\nGSTIN: 33AABCC5544R1Z2\nLegal Name: CleanFlow Environmental Technologies Pvt Ltd\nTrade Name: CleanFlow Technologies\nStatus: ACTIVE\nPrincipal Place of Business: Tidel Park, Chennai, Tamil Nadu - 600113",
                    ),
                    IngestionDocumentInput(
                        filename="CleanFlow_MII_Declaration.pdf",
                        document_type=DocumentType.LOCAL_CONTENT_CERTIFICATE,
                        mime_type="application/pdf",
                        file_size=510000,
                        storage_path="mock_storage/submissions/CFT_MII.pdf",
                        content_text="Make in India (MII) Local Content Undertaking:\nUnder Public Procurement (Preference to Make in India) Order 2017\nWe hereby confirm that the local content for our offered water quality monitoring units is 32.0%.\nLocation of value addition: Ambattur Industrial Estate, Chennai.",
                    ),
                    IngestionDocumentInput(
                        filename="CleanFlow_CA_Turnover_Certificate.pdf",
                        document_type=DocumentType.TURNOVER_CERTIFICATE,
                        mime_type="application/pdf",
                        file_size=670000,
                        storage_path="mock_storage/submissions/CFT_Turnover.pdf",
                        content_text="Statutory Auditor Turnover Certificate\nUDIN: 24098765BBBBBB2002\nThis is to certify that average annual turnover of M/s CleanFlow Environmental Technologies Pvt Ltd for the preceding 3 financial years is INR 12.80 Crores (INR 128000000).",
                    ),
                    IngestionDocumentInput(
                        filename="CleanFlow_OEM_Authorization.pdf",
                        document_type=DocumentType.OEM_AUTHORIZATION,
                        mime_type="application/pdf",
                        file_size=860000,
                        storage_path="mock_storage/submissions/CFT_OEM.pdf",
                        content_text="Manufacturer Authorization Form (MAF)\nTo: Chennai Petroleum Corporation Limited (CPCL)\nWe, HydroSensor Corp (OEM), confirm that CleanFlow Environmental Technologies Pvt Ltd is our certified and authorized distributor for online water quality analyzers.",
                    ),
                    IngestionDocumentInput(
                        filename="CleanFlow_Commercial_BOQ_Bid.pdf",
                        document_type=DocumentType.FINANCIAL_BOQ,
                        mime_type="application/pdf",
                        file_size=490000,
                        storage_path=_get_sample_path("CleanFlow_Commercial_BOQ_Bid.pdf", "mock_storage/submissions/CFT_BOQ.pdf"),
                        content_text="COMMERCIAL BID & SCHEDULE OF RATES (BOQ)\nTender Reference: CPCL/WQM/2026/RFP-017\nBidder: CleanFlow Environmental Technologies Pvt Ltd\n\nItem 1: Online Multichannel Water Quality Analyzer Units, Qty: 5 units, Unit Rate: INR 44,00,000, Total: INR 2,20,00,000\nItem 2: Submersible Sensor Probes & Telemetry Modules, Qty: 5 sets, Unit Rate: INR 13,50,000, Total: INR 67,50,000\nItem 3: Installation, Testing, Calibration & Commissioning, Qty: 1 lot, Unit Rate: INR 22,50,000, Total: INR 22,50,000\nItem 4: 2-Year Comprehensive Annual Maintenance & Warranty, Qty: 1 lot, Unit Rate: INR 35,00,000, Total: INR 35,00,000\n\nSubtotal: INR 3,45,00,000\nTaxes (GST @ 18%): INR 62,10,000\nFreight & Transit Insurance: INR 3,50,000\nDiscount: INR 0\nTotal Evaluated Commercial Bid Price: INR 4,10,60,000",
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

        # Tender Intelligence is mandatory: a persisted hierarchy without a
        # meaningful requirement set is not a usable procurement.
        tender_documents = payload.tender.documents if payload.tender else []
        combined_text = "\n".join(
            document.content_text for document in tender_documents if document.content_text
        )
        await _run_tender_intelligence_or_fail(
            procurement_id=result.procurement_id,
            tender_id=result.tender_id,
            file_bytes=combined_text.encode("utf-8") if combined_text else None,
            filename=(tender_documents[0].filename if tender_documents else "tender.pdf"),
        )

        return result
    except ProcurementIngestionError as pie:
        logger.error("Mock-GeM ingestion validation error: %s", pie)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(pie),
        )
    except HTTPException:
        raise
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
    """Ingests a ZIP archive package containing metadata.json (or structured PDFs) and procurement documents.

    Automatically extracts live text from each embedded PDF using PyMuPDF.
    """
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
            # Security validation: Zip bomb & Zip-slip protection
            total_uncompressed_size = 0
            MAX_UNCOMPRESSED_SIZE = 50 * 1024 * 1024  # 50 MB
            MAX_FILE_COUNT = 500

            infolist = zip_ref.infolist()
            if len(infolist) > MAX_FILE_COUNT:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"ZIP archive contains too many files ({len(infolist)} > {MAX_FILE_COUNT}).",
                )

            for info in infolist:
                total_uncompressed_size += info.file_size
                if total_uncompressed_size > MAX_UNCOMPRESSED_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="ZIP archive exceeds maximum allowable uncompressed size (50 MB).",
                    )
                norm_path = os.path.normpath(info.filename)
                if norm_path.startswith("..") or os.path.isabs(norm_path):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Insecure path detected in ZIP archive: {info.filename}",
                    )

            file_list = [
                name for name in zip_ref.namelist()
                if not name.startswith("__MACOSX/") and not Path(name).name.startswith("._")
            ]

            def get_entry_bytes(fname: str) -> Optional[bytes]:
                clean_target = Path(fname).name.lower()
                for entry in file_list:
                    if Path(entry).name.lower() == clean_target:
                        return zip_ref.read(entry)
                return None

            def extract_pdf_stream_text(raw_b: bytes) -> str:
                try:
                    import pymupdf
                    doc = pymupdf.open(stream=raw_b, filetype="pdf")
                    pages_text = [page.get_text() for page in doc]
                    doc.close()
                    return "\n\n".join(t.strip() for t in pages_text if t.strip())
                except Exception as ex:
                    logger.warning("Failed to extract PDF stream text: %s", ex)
                    return ""

            # Find metadata.json or package.json
            meta_filename = next(
                (f for f in file_list if f.endswith("metadata.json") or f.endswith("package.json")),
                None,
            )

            if meta_filename:
                with zip_ref.open(meta_filename) as meta_file:
                    raw_json = meta_file.read().decode("utf-8")
                    payload_dict = json.loads(raw_json)

                payload_dict["source_system"] = "MOCK_GEM"
                payload = ProcurementIngestionPayload.model_validate(payload_dict)
                if payload.tender and not payload.tender.submission_deadline:
                    # Attempt extraction from tender document text if present
                    if payload.tender.documents:
                        for t_doc in payload.tender.documents:
                            if t_doc.content_text:
                                extracted_dl = extract_tender_deadline_from_text(t_doc.content_text)
                                if extracted_dl:
                                    payload.tender.submission_deadline = extracted_dl
                                    break
                # Do NOT inject any hardcoded fallback deadline here.
                # If the JSON manifest omits submission_deadline, we attempt to
                # derive it from the embedded tender PDF text below.

                # Extract live PDF text from ZIP entries if present
                if payload.tender and payload.tender.documents:
                    for t_doc in payload.tender.documents:
                        b = get_entry_bytes(t_doc.filename)
                        if b:
                            t_doc.file_size = len(b)
                            extracted = extract_pdf_stream_text(b)
                            if extracted:
                                t_doc.content_text = extracted

                    # Dynamically enrich title/organization/deadline from PDF text
                    first_t_doc = payload.tender.documents[0]
                    if first_t_doc.content_text:
                        meta = extract_tender_metadata_from_text(first_t_doc.content_text, first_t_doc.filename)
                        if not payload.procurement.title or "ZIP" in payload.procurement.title or "INGESTED" in payload.procurement.title.upper():
                            payload.procurement.title = meta["title"]
                        if not payload.procurement.organization or "ENTITY" in payload.procurement.organization.upper():
                            payload.procurement.organization = meta["organization"]
                        if not payload.tender.description:
                            payload.tender.description = meta["description"]
                        # Enrich deadline from PDF only if not already provided in the JSON manifest
                        if not payload.tender.submission_deadline and meta.get("submission_deadline"):
                            payload.tender.submission_deadline = meta["submission_deadline"]
                        if not payload.tender.bid_opening_date and meta.get("bid_opening_date"):
                            payload.tender.bid_opening_date = meta["bid_opening_date"]

                for b_pkg in payload.bidders:
                    for b_doc in b_pkg.documents:
                        b = get_entry_bytes(b_doc.filename)
                        if b:
                            b_doc.file_size = len(b)
                            extracted = extract_pdf_stream_text(b)
                            if extracted:
                                b_doc.content_text = extracted

            else:
                # Auto-detect PDFs in the archive
                pdf_entries = [f for f in file_list if f.lower().endswith(".pdf")]
                if not pdf_entries:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="ZIP package must contain a 'metadata.json' manifest or PDF procurement documents.",
                    )

                tender_docs = []
                bidder_docs_map: Dict[str, List[IngestionDocumentInput]] = {}

                for entry in pdf_entries:
                    raw_b = zip_ref.read(entry)
                    fname = Path(entry).name
                    extracted = extract_pdf_stream_text(raw_b)
                    
                    # Determine doc type from filename
                    fname_lower = fname.lower()
                    doc_type = DocumentType.OTHER
                    if "rfp" in fname_lower or "tender" in fname_lower or "specification" in fname_lower:
                        doc_type = DocumentType.TENDER_SPECIFICATION
                        tender_docs.append(IngestionDocumentInput(
                            filename=fname,
                            document_type=doc_type,
                            mime_type="application/pdf",
                            file_size=len(raw_b),
                            content_text=extracted,
                        ))
                        continue
                    elif "gst" in fname_lower:
                        doc_type = DocumentType.GST_CERTIFICATE
                    elif "mii" in fname_lower or "local" in fname_lower:
                        doc_type = DocumentType.LOCAL_CONTENT_CERTIFICATE
                    elif "turnover" in fname_lower or "financial" in fname_lower or "balance" in fname_lower:
                        doc_type = DocumentType.TURNOVER_CERTIFICATE
                    elif "oem" in fname_lower or "maf" in fname_lower or "auth" in fname_lower:
                        doc_type = DocumentType.OEM_AUTHORIZATION

                    # Identify bidder bucket by parent folder or prefix
                    parent_part = Path(entry).parent.name
                    if parent_part and parent_part.lower() not in (".", ""):
                        bidder_key = parent_part
                    elif "_" in fname:
                        bidder_key = fname.split("_")[0]
                    else:
                        bidder_key = "Bidder_1"

                    if bidder_key not in bidder_docs_map:
                        bidder_docs_map[bidder_key] = []

                    bidder_docs_map[bidder_key].append(IngestionDocumentInput(
                        filename=fname,
                        document_type=doc_type,
                        mime_type="application/pdf",
                        file_size=len(raw_b),
                        content_text=extracted,
                    ))

                # Build auto-generated payload with dynamic metadata extraction from tender text
                tender_text = tender_docs[0].content_text if tender_docs else ""
                t_meta = extract_tender_metadata_from_text(tender_text, tender_docs[0].filename if tender_docs else "")

                bidders_list = []
                for b_key, b_docs in bidder_docs_map.items():
                    clean_name = b_key.replace("_", " ").replace("02 Bidder ", "").replace("03 Bidder ", "").title()
                    bidders_list.append(IngestionBidderPackageInput(
                        bidder=IngestionBidderInfo(
                            legal_name=f"{clean_name} Pvt Ltd",
                            gstin=None,
                            email=f"contact@{b_key.lower().replace(' ', '')}.com",
                        ),
                        submission=IngestionSubmissionInfo(
                            external_submission_reference=f"SUB-{b_key.upper()[:8]}-{uuid.uuid4().hex[:4]}",
                            status="SUBMITTED",
                        ),
                        documents=b_docs,
                    ))

                payload = ProcurementIngestionPayload(
                    source_system="MOCK_GEM",
                    external_reference=f"ZIP-PROC-{uuid.uuid4().hex[:8].upper()}",
                    procurement=IngestionProcurementInfo(
                        title=t_meta["title"],
                        organization=t_meta["organization"],
                    ),
                    tender=IngestionTenderInfo(
                        tender_reference=f"TND-ZIP-{uuid.uuid4().hex[:6].upper()}",
                        title=t_meta["title"],
                        description=t_meta["description"],
                        estimated_value=t_meta.get("estimated_value"),
                        submission_deadline=t_meta.get("submission_deadline"),
                        bid_opening_date=t_meta.get("bid_opening_date"),
                        documents=tender_docs or [IngestionDocumentInput(
                            filename="Default_Tender_Notice.pdf",
                            document_type=DocumentType.TENDER_SPECIFICATION,
                            mime_type="application/pdf",
                            content_text="Clause 1: Active GST registration is mandatory.\nClause 2: Minimum 20% Local Content is mandatory.\nClause 3: Turnover requirement >= 10 Cr.",
                        )],
                    ),
                    bidders=bidders_list,
                )

            # Process ingestion via canonical service
            result = await ingest_procurement(payload)

            # Prefer the original PDF bytes, while retaining extracted text as a
            # fallback for structured ZIP manifests that carry no binary entry.
            tender_documents = payload.tender.documents if payload.tender else []
            first_tdoc = tender_documents[0] if tender_documents else None
            tender_bytes_for_analysis = (
                get_entry_bytes(first_tdoc.filename) if first_tdoc else None
            ) or (first_tdoc.content_text.encode("utf-8") if first_tdoc and first_tdoc.content_text else None)
            await _run_tender_intelligence_or_fail(
                procurement_id=result.procurement_id,
                tender_id=result.tender_id,
                file_bytes=tender_bytes_for_analysis,
                filename=first_tdoc.filename if first_tdoc else "tender.pdf",
            )

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


@router.post("/upload", response_model=ProcurementIngestionResult)
async def ingest_mock_gem_files(
    tender_pdf: UploadFile = File(..., description="Tender RFP / Specification PDF file"),
    bidder_zips: List[UploadFile] = File(..., description="One or more Bidder Submission ZIP archives"),
    bidder_names: Optional[List[str]] = Form(None),
    organization: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    estimated_value: Optional[float] = Form(None),
    demo_mode: bool = Form(True, description="Enable 3-minute demo gate")
):
    """Ingests a procurement package composed of a Tender RFP PDF and one or more Bidder Submission ZIPs.

    Supports multi-bidder ingestion, dynamically extracts text using PyMuPDF, derives metadata and
    submission deadline directly from the document truth, and persists the canonical procurement case via the Ingestion Service.
    """
    if not tender_pdf or not tender_pdf.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tender specification PDF document is required.",
        )
    if not tender_pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tender document format: '{tender_pdf.filename}'. Only .pdf files are accepted for tender specification.",
        )

    if not bidder_zips or len(bidder_zips) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one Bidder Submission ZIP archive is required.",
        )

    for b_file in bidder_zips:
        if not b_file.filename or not b_file.filename.lower().endswith(".zip"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid bidder package format: '{b_file.filename or 'unnamed'}'. Only .zip archives are accepted for bidder submissions.",
            )

    try:
        tender_bytes = await tender_pdf.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded tender PDF: {str(e)}",
        )

    if len(tender_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded tender PDF is empty (0 bytes).",
        )

    def extract_pdf_stream_text(raw_b: bytes) -> str:
        try:
            import pymupdf
            doc = pymupdf.open(stream=raw_b, filetype="pdf")
            pages_text = [page.get_text() for page in doc]
            doc.close()
            return "\n\n".join(t.strip() for t in pages_text if t.strip())
        except Exception as ex:
            logger.warning("Failed to extract PDF stream text with pymupdf: %s", ex)
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(raw_b))
                return "\n\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as ex2:
                logger.warning("Failed to extract PDF text with pypdf: %s", ex2)
                return ""

    tender_text = extract_pdf_stream_text(tender_bytes)
    t_meta = extract_tender_metadata_from_text(tender_text, tender_pdf.filename)

    proc_title = (title or "").strip() or t_meta["title"]
    proc_org = (organization or "").strip() or t_meta["organization"]

    tender_docs = [
        IngestionDocumentInput(
            filename=tender_pdf.filename,
            document_type=DocumentType.TENDER_SPECIFICATION,
            mime_type="application/pdf",
            file_size=len(tender_bytes),
            content_text=tender_text,
        )
    ]

    bidders_list: List[IngestionBidderPackageInput] = []
    MAX_UNCOMPRESSED_SIZE = 50 * 1024 * 1024  # 50 MB
    MAX_FILE_COUNT = 200

    for idx, b_file in enumerate(bidder_zips, start=1):
        try:
            zip_bytes = await b_file.read()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read bidder package '{b_file.filename}': {str(e)}",
            )

        if len(zip_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bidder package '{b_file.filename}' is empty (0 bytes).",
            )

        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zip_ref:
                infolist = zip_ref.infolist()
                if len(infolist) > MAX_FILE_COUNT:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Bidder archive '{b_file.filename}' contains too many files ({len(infolist)} > {MAX_FILE_COUNT}).",
                    )

                total_uncompressed_size = 0
                for info in infolist:
                    total_uncompressed_size += info.file_size
                    if total_uncompressed_size > MAX_UNCOMPRESSED_SIZE:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Bidder archive '{b_file.filename}' exceeds allowable uncompressed size (50 MB).",
                        )
                    norm_path = os.path.normpath(info.filename)
                    if norm_path.startswith("..") or os.path.isabs(norm_path):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Insecure path detected in bidder archive: {info.filename}",
                        )

                file_list = [
                    name for name in zip_ref.namelist()
                    if not name.startswith("__MACOSX/") and not Path(name).name.startswith("._")
                ]

                # Determine bidder legal name
                custom_name = None
                if bidder_names and idx - 1 < len(bidder_names) and bidder_names[idx - 1] and bidder_names[idx - 1].strip():
                    custom_name = bidder_names[idx - 1].strip()

                if custom_name:
                    bidder_legal_name = custom_name
                else:
                    stem = Path(b_file.filename).stem
                    clean_name = (
                        stem.replace("Bidder_", "")
                        .replace("bidder_", "")
                        .replace("Package_", "")
                        .replace("_Package", "")
                        .replace("_", " ")
                        .strip()
                    )
                    if not clean_name or clean_name.isdigit():
                        clean_name = f"Bidder {idx}"

                    bidder_legal_name = f"{clean_name} Pvt Ltd" if not clean_name.lower().endswith(("ltd", "limited", "inc", "corp", "llp", "pvt ltd")) else clean_name

                # Extract bidder documents
                b_docs: List[IngestionDocumentInput] = []
                for entry in file_list:
                    if not entry.lower().endswith(".pdf"):
                        continue
                    raw_b = zip_ref.read(entry)
                    fname = Path(entry).name
                    extracted = extract_pdf_stream_text(raw_b)

                    fname_lower = fname.lower()
                    doc_type = DocumentType.OTHER
                    if "gst" in fname_lower:
                        doc_type = DocumentType.GST_CERTIFICATE
                    elif "mii" in fname_lower or "local" in fname_lower:
                        doc_type = DocumentType.LOCAL_CONTENT_CERTIFICATE
                    elif "turnover" in fname_lower or "financial" in fname_lower or "balance" in fname_lower or "audit" in fname_lower:
                        doc_type = DocumentType.TURNOVER_CERTIFICATE
                    elif "oem" in fname_lower or "maf" in fname_lower or "auth" in fname_lower:
                        doc_type = DocumentType.OEM_AUTHORIZATION
                    elif "boq" in fname_lower or "commercial" in fname_lower or "price" in fname_lower:
                        doc_type = DocumentType.COMMERCIAL_BID
                    elif "tender" in fname_lower or "rfp" in fname_lower:
                        doc_type = DocumentType.TENDER_SPECIFICATION

                    b_docs.append(IngestionDocumentInput(
                        filename=fname,
                        document_type=doc_type,
                        mime_type="application/pdf",
                        file_size=len(raw_b),
                        content_text=extracted,
                    ))

                if not b_docs:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Bidder archive '{b_file.filename}' contains no PDF evidence documents.",
                    )

                clean_slug = re.sub(r"[^a-zA-Z0-9]", "", bidder_legal_name).lower() or f"bidder{idx}"
                bidders_list.append(IngestionBidderPackageInput(
                    bidder=IngestionBidderInfo(
                        legal_name=bidder_legal_name,
                        gstin=None,
                        email=f"bids@{clean_slug}.com",
                    ),
                    submission=IngestionSubmissionInfo(
                        external_submission_reference=f"GEM-SUB-{clean_slug.upper()[:8]}-{uuid.uuid4().hex[:4].upper()}",
                        status="SUBMITTED",
                        submitted_at=datetime.now(timezone.utc) - timedelta(days=2),
                    ),
                    documents=b_docs,
                ))

        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{b_file.filename}' is not a valid or readable ZIP archive.",
            )

    demo_effective_deadline = None
    if demo_mode:
        demo_effective_deadline = datetime.now(timezone.utc) + timedelta(minutes=3)

    unique_suffix = uuid.uuid4().hex[:6].upper()

    payload = ProcurementIngestionPayload(
        source_system="MOCK_GEM",
        external_reference=f"GEM/2026/WB-{unique_suffix}",
        procurement=IngestionProcurementInfo(
            title=proc_title,
            organization=proc_org,
        ),
        tender=IngestionTenderInfo(
            tender_reference=f"TND-GEM-{unique_suffix}",
            title=proc_title,
            description=t_meta["description"],
            estimated_value=estimated_value or t_meta.get("estimated_value"),
            category="GOODS_AND_SERVICES",
            submission_deadline=t_meta.get("submission_deadline"),
            demo_effective_deadline=demo_effective_deadline,
            documents=tender_docs,
        ),
        bidders=bidders_list,
    )

    try:
        result = await ingest_procurement(payload)
        
        await _run_tender_intelligence_or_fail(
            procurement_id=result.procurement_id,
            tender_id=result.tender_id,
            file_bytes=tender_bytes,
            filename=tender_pdf.filename,
        )
        
        return result
    except ProcurementIngestionError as pie:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(pie),
        )
    except HTTPException:
        raise
    except Exception as err:
        logger.error("Failed to ingest Mock-GeM multipart files: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest procurement package: {str(err)}",
        )

