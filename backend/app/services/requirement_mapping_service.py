import logging
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

try:
    from app.models.tender_contract import RequirementEvaluationContract, CanonicalEvaluationField
    from app.models.evidence import BidderClaim, EvidenceObservation
except ImportError:
    from app.models.tender_contract import RequirementEvaluationContract, CanonicalEvaluationField
    from app.models.evidence import BidderClaim, EvidenceObservation

logger = logging.getLogger(__name__)


class RequirementMappingResult(BaseModel):
    """Result of mapping extracted evidence/claim to a canonical tender requirement."""
    requirement_id: Optional[str] = Field(default=None, description="Mapped canonical requirement ID.")
    field_name: Optional[str] = Field(default=None, description="Canonical field name matched.")
    confidence: str = Field(default="UNMAPPED", description="Mapping confidence (HIGH, MEDIUM, LOW, UNMAPPED).")
    method: Optional[str] = Field(default=None, description="Method used for mapping.")
    reason: Optional[str] = Field(default=None, description="Human-readable explanation of the mapping decision.")
    ambiguous: bool = Field(default=False, description="True if multiple plausible requirements exist.")
    candidate_requirement_ids: List[str] = Field(default_factory=list, description="Candidate IDs if ambiguous.")


def _score_requirement_candidates(
    item: Union[BidderClaim, EvidenceObservation],
    requirements: List[RequirementEvaluationContract]
) -> List[Dict[str, Any]]:
    """Scores requirements based on deterministic signals."""
    candidates = []
    item_type = item.source_type or ""
    
    item_value = getattr(item, 'observed_value', getattr(item, 'claimed_value', None))
    req_id_tag = str(getattr(item, 'requirement_id', '') or '').upper()
    is_gst = "GST" in item_type or "GST" in req_id_tag or ("29" in str(item_value) and len(str(item_value)) == 15)
    is_pan = "PAN" in item_type or "PAN" in req_id_tag or (len(str(item_value)) == 10 and str(item_value)[:5].isalpha())
    is_percent = item.unit == "PERCENT" or "%" in str(item_value)
    is_turnover = "CA_TURNOVER" in item_type or "TURNOVER" in item_type or "TURNOVER" in req_id_tag or item.unit in ("INR", "CURRENCY") or ("crore" in str(item_value).lower() or "lakh" in str(item_value).lower())
    is_exp = "EXPERIENCE" in item_type or "EXP" in req_id_tag or item.unit == "COUNT"
    is_warranty = item.unit in ("MONTHS", "YEARS") or "warranty" in item_type.lower() or "warranty" in req_id_tag.lower() or "month" in str(item_value).lower() or "year" in str(item_value).lower()
    
    for req in requirements:
        score = 0
        reasons = []
        field_match = False
        
        # 0. Direct Requirement ID Match
        if getattr(item, 'requirement_id', None) and item.requirement_id == req.requirement_id:
            score += 10
            reasons.append(f"Explicit requirement ID match for `{req.requirement_id}`.")
            field_match = True
            
        # 1. Field match
        req_field = req.evaluation_field
        if req_field:
            if req_field == CanonicalEvaluationField.LOCAL_CONTENT_PERCENTAGE and is_percent:
                score += 5
                reasons.append("Canonical field `local_content_percentage` matches local content percentage unit.")
                field_match = True
            elif req_field == CanonicalEvaluationField.GST_STATUS and is_gst:
                score += 5
                reasons.append("Canonical field `gst_status` matches GSTIN pattern.")
                field_match = True
            elif req_field == CanonicalEvaluationField.PAN_VALIDITY and is_pan:
                score += 5
                reasons.append("Canonical field `pan_validity` matches PAN pattern.")
                field_match = True
            elif req_field == CanonicalEvaluationField.AVERAGE_ANNUAL_TURNOVER and is_turnover:
                score += 5
                reasons.append("Canonical field `average_annual_turnover` matches turnover evidence.")
                field_match = True
            elif req_field == CanonicalEvaluationField.WARRANTY_MONTHS and is_warranty:
                score += 5
                reasons.append("Canonical field `warranty_months` matches warranty duration.")
                field_match = True
            elif req_field == CanonicalEvaluationField.OEM_AUTHORIZATION and ("OEM" in item_type or "OEM" in req_id_tag):
                score += 5
                reasons.append("Canonical field `oem_authorization` matches OEM evidence.")
                field_match = True
            elif req_field == CanonicalEvaluationField.GENERAL_EXPERIENCE and is_exp:
                score += 5
                reasons.append("Canonical field `general_experience` matches experience evidence.")
                field_match = True
            elif req_field == CanonicalEvaluationField.DEBARMENT_STATUS and ("DEBARMENT" in item_type or "DEBAR" in req_id_tag):
                score += 5
                reasons.append("Canonical field `debarment_status` matches debarment evidence.")
                field_match = True
                
        # 2. Evidence Contract match
        if req.evidence_contracts:
            for ec in req.evidence_contracts:
                if ec.document_type and ec.document_type in item_type:
                    score += 3
                    reasons.append(f"Document type `{ec.document_type}` matches evidence.")
                    
        # 3. Keyword Match (Fallback)
        if not field_match and score == 0:
            if "GST" in req.title.upper() and is_gst:
                score += 4
                reasons.append("Requirement title mentions GST.")
            elif "PAN" in req.title.upper() and is_pan:
                score += 4
                reasons.append("Requirement title mentions PAN.")
            elif "LOCAL CONTENT" in req.title.upper() and is_percent:
                score += 4
                reasons.append("Requirement title mentions Local Content.")
                
        if score > 0:
            candidates.append({
                "requirement": req,
                "score": score,
                "reason": " ".join(reasons)
            })
            
    # Sort by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates

def map_evidence_to_requirements(
    evidence_items: List[Union[BidderClaim, EvidenceObservation]],
    requirements: List[RequirementEvaluationContract]
) -> List[Union[BidderClaim, EvidenceObservation]]:
    """
    Maps a list of extracted evidence items to canonical requirements.
    Updates the requirement_id field in place.
    """
    mapped_items = []
    
    for item in evidence_items:
        res = map_single_item(item, requirements)
        if res.requirement_id:
            item.requirement_id = res.requirement_id
        else:
            item.requirement_id = "UNMAPPED"
        mapped_items.append(item)
        
    return mapped_items

def map_single_item(
    item: Union[BidderClaim, EvidenceObservation],
    requirements: List[RequirementEvaluationContract]
) -> RequirementMappingResult:
    """Maps a single item to a canonical requirement."""
    candidates = _score_requirement_candidates(item, requirements)
    
    if not candidates:
        return RequirementMappingResult(
            requirement_id=None,
            confidence="UNMAPPED",
            method="DETERMINISTIC",
            reason="No deterministic signals matched any requirement.",
            ambiguous=False
        )
        
    top_score = candidates[0]["score"]
    top_candidates = [c for c in candidates if c["score"] == top_score]
    
    if len(top_candidates) == 1:
        req = top_candidates[0]["requirement"]
        return RequirementMappingResult(
            requirement_id=req.requirement_id,
            field_name=req.evaluation_field,
            confidence="HIGH" if top_score >= 5 else "MEDIUM",
            method="DETERMINISTIC",
            reason=top_candidates[0]["reason"],
            ambiguous=False
        )
    else:
        # Ambiguous
        c_ids = [c["requirement"].requirement_id for c in top_candidates]
        return RequirementMappingResult(
            requirement_id=None,
            confidence="LOW",
            method="DETERMINISTIC",
            reason=f"Evidence could refer to {', '.join(c_ids)}; deterministic signals are insufficient.",
            ambiguous=True,
            candidate_requirement_ids=c_ids
        )
