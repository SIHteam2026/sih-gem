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


def extract_document_facts(
    doc: Document,
    bidder_id: Optional[str] = None,
    submission_id: Optional[str] = None
) -> Dict[str, List[Any]]:
    """
    Extracts all possible factual claims and observations deterministically from a parsed document.
    """
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

    for p in pages:
        page_num = p.get("page", 1)
        text = p.get("text", "")
        
        # Determine source type
        src_type = "SUPPORTING_DOCUMENT"
        is_auth = False
        doc_type_val = doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type)
        if doc_type_val == "GST_CERTIFICATE":
            src_type = "AUTHORITATIVE_REGISTRY"
            is_auth = True
            
            # Deterministic GST extraction
            gst_matches = GSTIN_PATTERN.findall(text)
            for m in gst_matches:
                obs = _build_observation(
                    bidder_id=b_id,
                    submission_id=s_id,
                    req_id="REQ-GST-UNKNOWN",  # Requirement mapper should update this later
                    raw_value=m,
                    unit=None,
                    doc=doc,
                    page=page_num,
                    quote=m,
                    is_authoritative=is_auth,
                    source_type=src_type
                )
                observations.append(obs)
                
            pan_matches = PAN_PATTERN.findall(text)
            for m in pan_matches:
                obs = _build_observation(
                    bidder_id=b_id,
                    submission_id=s_id,
                    req_id="REQ-PAN-UNKNOWN",
                    raw_value=m,
                    unit=None,
                    doc=doc,
                    page=page_num,
                    quote=m,
                    is_authoritative=is_auth,
                    source_type=src_type
                )
                observations.append(obs)
                
        elif "PAN" in doc_type_val or "PAN" in doc.filename.upper():
            src_type = "AUTHORITATIVE_REGISTRY"
            is_auth = True
            pan_matches = PAN_PATTERN.findall(text)
            for m in pan_matches:
                obs = _build_observation(
                    bidder_id=b_id,
                    submission_id=s_id,
                    req_id="REQ-PAN-UNKNOWN",
                    raw_value=m,
                    unit=None,
                    doc=doc,
                    page=page_num,
                    quote=m,
                    is_authoritative=is_auth,
                    source_type=src_type
                )
                observations.append(obs)

        elif "LOCAL" in doc.filename.upper() or "MAKE IN INDIA" in text.upper():
            src_type = "BIDDER_DECLARATION"
            perc_matches = PERCENTAGE_PATTERN.findall(text)
            if perc_matches:
                for m in perc_matches:
                    clm = _build_claim(
                        bidder_id=b_id,
                        submission_id=s_id,
                        req_id="REQ-LC-UNKNOWN",
                        raw_value=m,
                        unit="PERCENT",
                        doc=doc,
                        page=page_num,
                        quote=f"{m}% local content",
                        claim_type=src_type
                    )
                    claims.append(clm)
                    
        # Future-proof for LLM based extraction for semantic facts (omitted here to avoid huge calls unless explicitly requested via context)
                    
    return {
        "claims": claims,
        "observations": observations
    }

def process_document_evidence(doc: Document, tender_context: Optional[Dict[str, Any]] = None) -> Dict[str, List[Any]]:
    """
    Main entry point for claim/evidence extraction pipeline.
    """
    bidder_id = None
    submission_id = None
    
    if tender_context:
        bidder_id = tender_context.get("bidder_id")
        submission_id = tender_context.get("bid_submission_id")
        
    return extract_document_facts(doc, bidder_id, submission_id)


def map_facts_to_requirements(
    facts: Dict[str, List[Any]], requirements: List[RequirementEvaluationContract]
) -> Dict[str, List[Any]]:
    """Map placeholder facts to a canonical requirement without guessing.

    Mapping uses an explicit existing ID first, then the contract's canonical
    field and requirement language.  A non-unique or unsupported match remains
    unmapped and is returned separately for officer review.
    """
    mapped_claims, mapped_observations, unmapped = [], [], []
    field_signals = {
        "LC": ("local_content", "LOCAL CONTENT", "MAKE IN INDIA"),
        "GST": ("gst_status", "GST"),
        "PAN": ("pan_validity", "PAN"),
    }
    for kind in ("claims", "observations"):
        for fact in facts.get(kind, []):
            placeholder = "UNKNOWN" in fact.requirement_id.upper() or "UNMAPPED" in fact.requirement_id.upper()
            matches = []
            if not placeholder:
                matches = [r for r in requirements if r.requirement_id == fact.requirement_id]
            else:
                key = next((key for key in field_signals if key in fact.requirement_id.upper()), None)
                if key:
                    field, *terms = field_signals[key]
                    matches = [r for r in requirements if str(r.evaluation_field.value if hasattr(r.evaluation_field, 'value') else r.evaluation_field) == field or any(term in r.description.upper() for term in terms)]
            if len(matches) == 1:
                updated = fact.model_copy(update={"requirement_id": matches[0].requirement_id})
                (mapped_claims if kind == "claims" else mapped_observations).append(updated)
            else:
                unmapped.append({"fact_id": getattr(fact, "claim_id", None) or getattr(fact, "evidence_id", None), "reason": "No unique canonical requirement match", "candidate_requirement_ids": [r.requirement_id for r in matches]})
    return {"claims": mapped_claims, "observations": mapped_observations, "unmapped": unmapped}
