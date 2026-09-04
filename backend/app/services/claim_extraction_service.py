import json
import logging
import uuid
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from copy import deepcopy

try:
    from backend.app.models.procurement import Document, DocumentType
    from backend.app.models.evidence import BidderClaim, EvidenceObservation
    from backend.app.rules.engine import parse_numeric_value, parse_date_value
    from backend.app.ai.llm_evidence_service import extract_evidence_with_llm
    from backend.app.models.tender_contract import RequirementEvaluationContract
except ImportError:
    from app.models.procurement import Document, DocumentType
    from app.models.evidence import BidderClaim, EvidenceObservation
    from app.rules.engine import parse_numeric_value, parse_date_value
    from app.ai.llm_evidence_service import extract_evidence_with_llm
    from app.models.tender_contract import RequirementEvaluationContract

logger = logging.getLogger(__name__)

GSTIN_PATTERN = re.compile(r'\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b')
PAN_PATTERN = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b')
PERCENTAGE_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*%')


def _build_claim(
    bidder_id: str,
    submission_id: str,
    req_id: str,
    raw_value: str,
    unit: Optional[str],
    doc: Document,
    page: int,
    quote: str,
    confidence: float = 1.0,
    claim_type: str = "BIDDER_DECLARATION"
) -> BidderClaim:
    norm_val, detected_unit = parse_numeric_value(raw_value)
    if norm_val is None:
        norm_val = parse_date_value(raw_value) or raw_value

    return BidderClaim(
        claim_id=f"CLM-{uuid.uuid4().hex[:8]}",
        bidder_id=bidder_id,
        bid_submission_id=submission_id,
        requirement_id=req_id,
        claimed_value=norm_val or raw_value,
        unit=unit or detected_unit,
        source_document=doc.filename,
        page_number=page,
        raw_statement=quote,
        source_type=claim_type,
        confidence=confidence,
        document_id=doc.id
    )

def _build_observation(
    bidder_id: str,
    submission_id: str,
    req_id: str,
    raw_value: str,
    unit: Optional[str],
    doc: Document,
    page: int,
    quote: str,
    is_authoritative: bool = False,
    source_type: str = "SUPPORTING_DOCUMENT",
    confidence: float = 1.0
) -> EvidenceObservation:
    norm_val, detected_unit = parse_numeric_value(raw_value)
    if norm_val is None:
        norm_val = parse_date_value(raw_value) or raw_value
        
    return EvidenceObservation(
        evidence_id=f"EVD-{uuid.uuid4().hex[:8]}",
        bidder_id=bidder_id,
        bid_submission_id=submission_id,
        requirement_id=req_id,
        observed_value=norm_val or raw_value,
        unit=unit or detected_unit,
        is_authoritative=is_authoritative,
        source_document=doc.filename,
        page_number=page,
        source_quote=quote,
        confidence=confidence,
        source_type=source_type,
        document_id=doc.id
    )


TURNOVER_PATTERN = re.compile(
    r'(?:turnover|turn\s*over)[^\d\n\r]*(?:inr|rs\.?|₹)?\s*(\d+(?:\.\d+)?)\s*(crore|cr|lakh|lac|k)?',
    re.IGNORECASE,
)
TURNOVER_ALT_PATTERN = re.compile(
    r'(?:inr|rs\.?|₹)\s*(\d+(?:\.\d+)?)\s*(crore|cr|lakh|lac)\s*(?:average\s*)?(?:annual\s*)?turnover',
    re.IGNORECASE,
)
WARRANTY_PATTERN = re.compile(
    r'(\d+)\s*(?:months?|years?)\s*(?:comprehensive\s*)?(?:onsite\s*)?warranty',
    re.IGNORECASE,
)
EXPERIENCE_COUNT_PATTERN = re.compile(
    r'(\d+)\s*(?:similar\s*)?(?:contracts?|works?|projects?)\s*(?:successfully\s*)?(?:executed|completed)',
    re.IGNORECASE,
)


def extract_document_facts(
    doc: Document,
    bidder_id: Optional[str] = None,
    submission_id: Optional[str] = None
) -> Dict[str, List[Any]]:
    """Extracts all possible factual claims and observations deterministically from a parsed document."""
    claims: List[BidderClaim] = []
    observations: List[EvidenceObservation] = []

    b_id = bidder_id or (doc.bid_submission_id if hasattr(doc, 'bid_submission_id') else "BID-UNKNOWN")
    s_id = submission_id or (doc.bid_submission_id if hasattr(doc, 'bid_submission_id') else "SUB-UNKNOWN")

    # Extract page_aware_text
    pages = []
    if doc.content_text:
        try:
            pages = json.loads(doc.content_text)
            if not isinstance(pages, list):
                pages = [{"page": 1, "text": doc.content_text}]
        except Exception:
            pages = [{"page": 1, "text": doc.content_text}]
    else:
        pages = [{"page": 1, "text": ""}]

    doc_type_val = (doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type or "")).upper()
    filename_upper = (doc.filename or "").upper()

    for p in pages:
        page_num = p.get("page", 1)
        text = p.get("text", "")
        text_upper = text.upper()

        # 1. GST Extraction
        if doc_type_val == "GST_CERTIFICATE" or "GST" in filename_upper or "GSTIN" in text_upper:
            gst_matches = GSTIN_PATTERN.findall(text)
            for m in gst_matches:
                obs = _build_observation(
                    bidder_id=b_id,
                    submission_id=s_id,
                    req_id="REQ-GST-UNKNOWN",
                    raw_value=m,
                    unit="STATUS",
                    doc=doc,
                    page=page_num,
                    quote=m,
                    is_authoritative=True,
                    source_type="AUTHORITATIVE_REGISTRY"
                )
                observations.append(obs)

        # 2. PAN Extraction
        if "PAN" in doc_type_val or "PAN" in filename_upper or "PERMANENT ACCOUNT" in text_upper:
            pan_matches = PAN_PATTERN.findall(text)
            for m in pan_matches:
                obs = _build_observation(
                    bidder_id=b_id,
                    submission_id=s_id,
                    req_id="REQ-PAN-UNKNOWN",
                    raw_value=m,
                    unit="STATUS",
                    doc=doc,
                    page=page_num,
                    quote=m,
                    is_authoritative=True,
                    source_type="AUTHORITATIVE_REGISTRY"
                )
                observations.append(obs)

        # 3. Local Content (Make in India) Extraction
        if "LOCAL" in filename_upper or "MAKE IN INDIA" in text_upper or "MII" in filename_upper or "LOCAL CONTENT" in text_upper:
            perc_matches = PERCENTAGE_PATTERN.findall(text)
            is_cert = any(w in filename_upper for w in ("CERT", "AUDIT", "CA_")) or any(w in doc_type_val for w in ("CERTIFICATE", "AUDITOR"))
            for m in perc_matches:
                quote_str = f"{m}% local content"
                if is_cert:
                    obs = _build_observation(
                        bidder_id=b_id,
                        submission_id=s_id,
                        req_id="REQ-LC-UNKNOWN",
                        raw_value=f"{m}%",
                        unit="PERCENT",
                        doc=doc,
                        page=page_num,
                        quote=quote_str,
                        is_authoritative=True,
                        source_type="AUTHORITATIVE_CERTIFICATE",
                    )
                    observations.append(obs)
                else:
                    clm = _build_claim(
                        bidder_id=b_id,
                        submission_id=s_id,
                        req_id="REQ-LC-UNKNOWN",
                        raw_value=f"{m}%",
                        unit="PERCENT",
                        doc=doc,
                        page=page_num,
                        quote=quote_str,
                        claim_type="BIDDER_DECLARATION",
                    )
                    claims.append(clm)

        # 4. Financial Turnover Extraction
        if "TURNOVER" in filename_upper or "BALANCE" in filename_upper or "CA_" in filename_upper or "TURNOVER" in text_upper:
            to_match = TURNOVER_ALT_PATTERN.search(text) or TURNOVER_PATTERN.search(text)
            if to_match:
                raw_to = to_match.group(0).strip()
                is_ca = any(w in filename_upper for w in ("CA", "AUDIT", "CERT", "UDIN")) or "CA_" in doc_type_val
                if is_ca:
                    obs = _build_observation(
                        bidder_id=b_id,
                        submission_id=s_id,
                        req_id="REQ-TURNOVER-UNKNOWN",
                        raw_value=raw_to,
                        unit="INR",
                        doc=doc,
                        page=page_num,
                        quote=raw_to,
                        is_authoritative=True,
                        source_type="AUTHORITATIVE_CERTIFICATE",
                    )
                    observations.append(obs)
                else:
                    clm = _build_claim(
                        bidder_id=b_id,
                        submission_id=s_id,
                        req_id="REQ-TURNOVER-UNKNOWN",
                        raw_value=raw_to,
                        unit="INR",
                        doc=doc,
                        page=page_num,
                        quote=raw_to,
                        claim_type="BIDDER_DECLARATION",
                    )
                    claims.append(clm)

        # 5. Warranty Extraction
        if "WARRANTY" in filename_upper or "WARRANTY" in text_upper:
            w_match = WARRANTY_PATTERN.search(text)
            if w_match:
                w_quote = w_match.group(0).strip()
                w_months = w_match.group(1)
                obs = _build_observation(
                    bidder_id=b_id,
                    submission_id=s_id,
                    req_id="REQ-WARRANTY-UNKNOWN",
                    raw_value=f"{w_months} Months",
                    unit="MONTHS",
                    doc=doc,
                    page=page_num,
                    quote=w_quote,
                    is_authoritative=False,
                    source_type="SUPPORTING_DOCUMENT",
                )
                observations.append(obs)

        # 6. Past Experience / Executed Contracts Count Extraction
        if "EXPERIENCE" in filename_upper or "COMPLETION" in filename_upper or "WORK_ORDER" in filename_upper or "CONTRACT" in text_upper:
            exp_match = EXPERIENCE_COUNT_PATTERN.search(text)
            if exp_match:
                cnt_quote = exp_match.group(0).strip()
                cnt_val = exp_match.group(1)
                obs = _build_observation(
                    bidder_id=b_id,
                    submission_id=s_id,
                    req_id="REQ-EXP-UNKNOWN",
                    raw_value=f"{cnt_val} COUNT",
                    unit="COUNT",
                    doc=doc,
                    page=page_num,
                    quote=cnt_quote,
                    is_authoritative=True,
                    source_type="SUPPORTING_DOCUMENT",
                )
                observations.append(obs)

        # 7. Non-Debarment / Blacklisting Undertaking
        if "DEBAR" in filename_upper or "BLACKLIST" in filename_upper or "UNDERTAKING" in filename_upper or "DEBAR" in text_upper:
            if "NOT DEBARRED" in text_upper or "NON-BLACKLIST" in text_upper or "NOT BLACKLISTED" in text_upper or "NO HOLIDAY LISTING" in text_upper:
                obs = _build_observation(
                    bidder_id=b_id,
                    submission_id=s_id,
                    req_id="REQ-DEBAR-UNKNOWN",
                    raw_value="CLEAR",
                    unit="STATUS",
                    doc=doc,
                    page=page_num,
                    quote="Bidder is not debarred, blacklisted, or on holiday listing.",
                    is_authoritative=False,
                    source_type="SUPPORTING_DOCUMENT",
                )
                observations.append(obs)

        # 8. OEM Authorization Form (MAF)
        if "OEM" in filename_upper or "MAF" in filename_upper or "AUTHORIZATION" in filename_upper or "MANUFACTURER AUTHORIZATION" in text_upper:
            obs = _build_observation(
                bidder_id=b_id,
                submission_id=s_id,
                req_id="REQ-OEM-UNKNOWN",
                raw_value="AUTHORIZED",
                unit="STATUS",
                doc=doc,
                page=page_num,
                quote="Valid Manufacturer Authorization Form (MAF) provided.",
                is_authoritative=True,
                source_type="AUTHORITATIVE_CERTIFICATE",
            )
            observations.append(obs)

    return {
        "claims": claims,
        "observations": observations
    }


def process_document_evidence(doc: Document, tender_context: Optional[Dict[str, Any]] = None) -> Dict[str, List[Any]]:
    """Main entry point for claim/evidence extraction pipeline."""
    bidder_id = None
    submission_id = None
    requirements = []
    
    if tender_context:
        bidder_id = tender_context.get("bidder_id")
        submission_id = tender_context.get("bid_submission_id")
        requirements = tender_context.get("requirements", [])
        
    facts = extract_document_facts(doc, bidder_id, submission_id)
    
    if requirements:
        try:
            from backend.app.services.requirement_mapping_service import map_evidence_to_requirements
        except ImportError:
            from app.services.requirement_mapping_service import map_evidence_to_requirements
            
        facts["claims"] = map_evidence_to_requirements(facts["claims"], requirements)
        facts["observations"] = map_evidence_to_requirements(facts["observations"], requirements)
        
    return facts


def map_facts_to_requirements(
    facts: Dict[str, List[Any]], requirements: List[RequirementEvaluationContract]
) -> Dict[str, List[Any]]:
    """Map placeholder facts to a canonical requirement without guessing.

    Mapping uses an explicit existing ID first, then canonical evaluation field,
    category, keywords, document types, and unit compatibility. A non-unique or
    unsupported match remains unmapped and is returned separately for officer review.
    """
    mapped_claims, mapped_observations, unmapped = [], [], []

    domain_signals = {
        "LC": {
            "fields": {"local_content_percentage", "local_content", "mii_percentage"},
            "terms": {"LOCAL CONTENT", "MAKE IN INDIA", "MII", "LOCAL_CONTENT"},
            "categories": {"LOCAL_CONTENT_MII"},
            "units": {"PERCENT", "%"},
        },
        "GST": {
            "fields": {"gst_status", "gstin_active", "gst_registration"},
            "terms": {"GST", "GSTIN", "GSTR-3B", "GOODS AND SERVICES TAX"},
            "categories": {"GST_AND_TAX", "GST"},
            "units": {"STATUS"},
        },
        "PAN": {
            "fields": {"pan_validity", "pan_valid", "corporate_registration"},
            "terms": {"PAN", "PERMANENT ACCOUNT NUMBER", "INCORPORATION"},
            "categories": {"PAN_IDENTITY", "CORPORATE_IDENTITY"},
            "units": {"STATUS"},
        },
        "TURNOVER": {
            "fields": {"average_annual_turnover", "annual_turnover", "financial_turnover"},
            "terms": {"TURNOVER", "ANNUAL TURNOVER", "BALANCE SHEET", "UDIN"},
            "categories": {"FINANCIAL_TURNOVER", "FINANCIAL"},
            "units": {"INR", "CURRENCY"},
        },
        "EXPERIENCE": {
            "fields": {"executed_contracts_count", "similar_contract_count", "general_experience"},
            "terms": {"PAST SIMILAR WORK", "EXPERIENCE", "COMPLETED CONTRACTS", "WORK ORDER", "COMPLETION CERTIFICATE"},
            "categories": {"PAST_EXPERIENCE", "TECHNICAL_EXPERIENCE"},
            "units": {"COUNT"},
        },
        "OEM": {
            "fields": {"oem_authorization", "maf_status"},
            "terms": {"MANUFACTURER AUTHORIZATION", "OEM AUTHORIZATION", "MAF"},
            "categories": {"OEM_AUTHORIZATION"},
            "units": {"STATUS"},
        },
        "DEBAR": {
            "fields": {"debarment_status", "non_blacklisting"},
            "terms": {"NON-BLACKLISTING", "DEBARMENT", "HOLIDAY LISTING", "NON-DEBARMENT"},
            "categories": {"LEGAL_AND_DEBARMENT"},
            "units": {"STATUS"},
        },
        "WARRANTY": {
            "fields": {"warranty_period_months", "warranty_months"},
            "terms": {"WARRANTY", "ONSITE WARRANTY", "COMPREHENSIVE WARRANTY"},
            "categories": {"DELIVERY_AND_SLA", "WARRANTY"},
            "units": {"MONTHS", "YEARS"},
        },
    }

    for kind in ("claims", "observations"):
        for fact in facts.get(kind, []):
            req_id_str = str(getattr(fact, "requirement_id", "") or "").upper()
            placeholder = any(w in req_id_str for w in ("UNKNOWN", "UNMAPPED", "PLACEHOLDER", "NONE", "UNDEF"))
            matches = []

            if not placeholder:
                matches = [r for r in requirements if r.requirement_id.upper() == req_id_str]

            if not matches:
                # 1. Check if an explicit requirement_id is embedded in the fact's requirement_id
                embedded = [r for r in requirements if r.requirement_id.upper() in req_id_str]
                if len(embedded) == 1:
                    matches = embedded

            if not matches:
                # 2. Domain-based matching using signals
                fact_doc = str(getattr(fact, "source_document", "") or "").upper()
                fact_quote = str(getattr(fact, "source_quote", None) or getattr(fact, "raw_statement", None) or "").upper()
                fact_unit = str(getattr(fact, "unit", "") or "").upper()

                # Identify which domain(s) the fact belongs to
                matched_domains = []
                for d_key, d_meta in domain_signals.items():
                    key_in_id = d_key in req_id_str
                    key_in_doc = any(t in fact_doc for t in d_meta["terms"]) or d_key in fact_doc
                    unit_match = fact_unit in d_meta["units"] if fact_unit else False
                    quote_match = any(t in fact_quote for t in d_meta["terms"])
                    if key_in_id or (unit_match and (key_in_doc or quote_match)) or (key_in_doc and quote_match):
                        matched_domains.append(d_key)

                candidates = []
                for d_key in matched_domains:
                    d_meta = domain_signals[d_key]
                    for r in requirements:
                        r_field = str(r.evaluation_field.value if hasattr(r.evaluation_field, "value") else r.evaluation_field or "").lower()
                        r_cat = str(r.category.value if hasattr(r.category, "value") else r.category or "").upper()
                        r_desc = str(r.description or "").upper()
                        r_title = str(r.title or "").upper()

                        if r_field in d_meta["fields"] or r_cat in d_meta["categories"] or any(t in r_desc or t in r_title for t in d_meta["terms"]):
                            if r not in candidates:
                                candidates.append(r)

                # Filter candidates by unit compatibility if fact has a specific unit
                if len(candidates) > 1 and fact_unit:
                    unit_filtered = [c for c in candidates if str(c.threshold_unit or "").upper() == fact_unit]
                    if len(unit_filtered) == 1:
                        candidates = unit_filtered

                matches = candidates

            if len(matches) == 1:
                updated = fact.model_copy(update={"requirement_id": matches[0].requirement_id})
                (mapped_claims if kind == "claims" else mapped_observations).append(updated)
            else:
                unmapped.append({
                    "fact_id": getattr(fact, "claim_id", None) or getattr(fact, "evidence_id", None),
                    "fact_type": "claim" if kind == "claims" else "observation",
                    "requirement_id": getattr(fact, "requirement_id", None),
                    "source_document": getattr(fact, "source_document", None),
                    "reason": "Ambiguous match between candidate requirements" if len(matches) > 1 else "No unique canonical requirement match",
                    "candidate_requirement_ids": [r.requirement_id for r in matches],
                })

    return {"claims": mapped_claims, "observations": mapped_observations, "unmapped": unmapped}

