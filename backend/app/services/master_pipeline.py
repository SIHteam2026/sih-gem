"""Master Verification Pipeline Service.

Executes the unified multi-stage intelligence pipeline:
1. Tender PDF text extraction.
2. AI Tender requirement analysis and ambiguity detection.
3. Target requirement selection.
4. Bidder document PDF text extraction.
5. Deterministic regex, debarment registry, and expiry kill-switch pre-checks.
6. AI Evidence and verbatim proof extraction.
7. AI Contradiction and compliance state evaluation.
"""

import logging
import re
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root and backend paths are available for imports
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent.parent
_root_dir = _backend_dir.parent
for _p in [str(_root_dir), str(_backend_dir), str(_current_file.parent.parent)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import HTTPException, status

try:
    from backend.app.services.evaluation_service import evaluate_requirements
    from backend.app.models.evaluation import ComplianceState, RequirementEvaluationResult
    from backend.app.models.evidence import BidderClaim, EvidenceObservation
    from backend.app.models.tender_contract import RequirementEvaluationContract
    from backend.app.services.claim_extraction_service import map_facts_to_requirements
except ImportError:
    try:
        from app.services.evaluation_service import evaluate_requirements
        from app.models.evaluation import ComplianceState, RequirementEvaluationResult
        from app.models.evidence import BidderClaim, EvidenceObservation
        from app.models.tender_contract import RequirementEvaluationContract
        from app.services.claim_extraction_service import map_facts_to_requirements
    except ImportError:
        from services.evaluation_service import evaluate_requirements
        from models.evaluation import ComplianceState, RequirementEvaluationResult
        from models.evidence import BidderClaim, EvidenceObservation
        from models.tender_contract import RequirementEvaluationContract
        from services.claim_extraction_service import map_facts_to_requirements

logger = logging.getLogger(__name__)


def _load_legacy_dependencies():
    """Import raw-PDF/LLM compatibility dependencies only for the legacy path."""
    try:
        from backend.app.ai.llm_evaluator_service import evaluate_compliance
        from backend.app.ai.llm_evidence_service import extract_evidence_with_llm
        from backend.app.ai.llm_service import analyze_tender_with_llm
        from backend.app.rules.validators import run_deterministic_checks
        from backend.app.services.pdf_parser import extract_text_from_pdf
        from backend.app.services.rag_service import retrieve_relevant_clauses
    except ImportError:
        from app.ai.llm_evaluator_service import evaluate_compliance
        from app.ai.llm_evidence_service import extract_evidence_with_llm
        from app.ai.llm_service import analyze_tender_with_llm
        from app.rules.validators import run_deterministic_checks
        from app.services.pdf_parser import extract_text_from_pdf
        from app.services.rag_service import retrieve_relevant_clauses
    return (evaluate_compliance, extract_evidence_with_llm, analyze_tender_with_llm,
            run_deterministic_checks, extract_text_from_pdf, retrieve_relevant_clauses)


def evaluate_canonical_submission(
    tender_id: str,
    bidder_id: Optional[str],
    submission_id: Optional[str],
    requirement_contracts: List[RequirementEvaluationContract],
    claims: List[BidderClaim],
    observations: List[EvidenceObservation],
    external_verifications: Optional[Dict[str, Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate one canonical submission without making a procurement decision.

    Inputs are already requirement-linked by the ingestion/document layer; this
    function deliberately neither reparses tender PDFs nor concatenates bidder
    documents.  It only groups canonical facts and delegates every requirement
    to the tiered evaluator.
    """
    mapped = map_facts_to_requirements({"claims": claims, "observations": observations}, requirement_contracts)
    claims = mapped["claims"]
    observations = mapped["observations"]
    claim_map: Dict[str, List[BidderClaim]] = {}
    evidence_map: Dict[str, List[EvidenceObservation]] = {}
    for claim in claims:
        claim_map.setdefault(claim.requirement_id, []).append(claim)
    for observation in observations:
        evidence_map.setdefault(observation.requirement_id, []).append(observation)

    req_context = dict(context or {})
    req_context.update({"bidder_id": bidder_id, "submission_id": submission_id})
    results = evaluate_requirements(
        requirements=requirement_contracts,
        claims_by_req=claim_map,
        evidence_by_req=evidence_map,
        verifications_by_req=external_verifications or {},
        context=req_context,
    )
    state_counts = {state.value: 0 for state in (ComplianceState.PASS, ComplianceState.FAIL, ComplianceState.REVIEW, ComplianceState.UNVERIFIED, ComplianceState.NOT_APPLICABLE)}
    for result in results:
        state_counts[result.state.value] = state_counts.get(result.state.value, 0) + 1
    contradictions = sum(len(result.contradiction_findings) for result in results)
    review_count = sum(1 for result in results if result.review_required)
    return {
        "tender_id": tender_id,
        "bidder_id": bidder_id,
        "submission_id": submission_id,
        "requirement_results": results,
        "machine_review_summary": state_counts,
        "review_required": bool(review_count),
        "review_required_count": review_count,
        "unresolved_contradiction_count": contradictions,
        "unverified_count": state_counts.get(ComplianceState.UNVERIFIED.value, 0),
        "unmapped_facts": mapped["unmapped"],
        "evaluation_metadata": {"executed_at": datetime.now(timezone.utc).isoformat(), "decision_authority": "HUMAN_PROCUREMENT_OFFICER"},
    }

# Regex patterns for detecting entity_id and expiry dates
_GSTIN_EXTRACT_REGEX = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b", re.IGNORECASE)
_PAN_EXTRACT_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
_EXPIRY_DATE_REGEX = re.compile(
    r"(?:valid\s+up\s+to|valid\s+thru|valid\s+through|valid\s+till|valid\s+to|expiry\s+date|expires\s+on|validity\s+date|date\s+of\s+expiry)\s*[:\-]?\s*([0-9]{1,2}[/\-.][0-9]{1,2}[/\-.][0-9]{2,4}|[0-9]{4}[/\-.][0-9]{1,2}[/\-.][0-9]{1,2})",
    re.IGNORECASE,
)


def _identify_document_type(matched_req: Any, text: str) -> str:
    """Identifies the expected document type from the requirement and bidder document text."""
    category_str = str(getattr(matched_req, "category", "")).upper()
    desc_str = str(getattr(matched_req, "description", "")).upper()
    evidence_str = str(getattr(matched_req, "evidence_required", "")).upper()
    text_upper = (text or "").upper()

    if "GST" in category_str or "GST" in desc_str or "GST" in evidence_str or "FORM GST" in text_upper:
        return "GST_CERTIFICATE"
    elif "PAN" in desc_str or "PAN" in evidence_str or "PAN" in category_str or "PERMANENT ACCOUNT" in text_upper:
        return "PAN_CARD"
    return "OTHER"


def _extract_entity_id_and_expiry(doc_type: str, text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extracts entity ID (PAN or GSTIN) and expiry date string from document text."""
    if not text:
        return None, None

    entity_id: Optional[str] = None
    expiry_date_str: Optional[str] = None

    # Extract Entity ID based on document type or general text
    if doc_type == "GST_CERTIFICATE":
        gst_matches = _GSTIN_EXTRACT_REGEX.findall(text)
        if gst_matches:
            entity_id = gst_matches[0].upper()
    elif doc_type == "PAN_CARD":
        pan_matches = _PAN_EXTRACT_REGEX.findall(text)
        if pan_matches:
            entity_id = pan_matches[0].upper()
    else:
        gst_matches = _GSTIN_EXTRACT_REGEX.findall(text)
        if gst_matches:
            entity_id = gst_matches[0].upper()
        else:
            pan_matches = _PAN_EXTRACT_REGEX.findall(text)
            if pan_matches:
                entity_id = pan_matches[0].upper()

    # Extract Expiry Date if explicitly present
    expiry_match = _EXPIRY_DATE_REGEX.search(text)
    if expiry_match:
        expiry_date_str = expiry_match.group(1).strip()

    return entity_id, expiry_date_str


async def run_master_verification(
    tender_bytes: bytes,
    bidder_doc_bytes: bytes,
    target_requirement_id: str,
) -> dict:
    """Executes the complete end-to-end tender and bidder document verification pipeline.

    Args:
        tender_bytes (bytes): Raw bytes of the tender PDF document.
        bidder_doc_bytes (bytes): Raw bytes of the bidder-submitted proof document.
        target_requirement_id (str): Unique requirement identifier to verify (e.g. 'REQ-001' or 'REQ-LC-01').

    Returns:
        dict: A unified verification report containing the target requirement,
              extracted evidence, compliance finding, and final recommendation.

    Raises:
        HTTPException: If document parsing fails, target requirement is not found, or AI pipeline errors.
    """
    logger.info("Starting Master Verification Pipeline for requirement: %s", target_requirement_id)
    (evaluate_compliance, extract_evidence_with_llm, analyze_tender_with_llm,
     run_deterministic_checks, extract_text_from_pdf, retrieve_relevant_clauses) = _load_legacy_dependencies()

    # 1. Extract text from tender document
    tender_text = await extract_text_from_pdf(tender_bytes)

    # 2. Extract all tender requirements via LLM
    tender_analysis = await analyze_tender_with_llm(tender_text)

    # 3. Select the requirement matching target_requirement_id
    matched_req = None
    target_clean = (target_requirement_id or "").strip().upper()

    for req in tender_analysis.requirements:
        if req.requirement_id.strip().upper() == target_clean:
            matched_req = req
            break

    # If exact ID not matched, check if ID is contained or fall back to the first requirement
    if not matched_req and tender_analysis.requirements:
        for req in tender_analysis.requirements:
            if target_clean in req.requirement_id.strip().upper() or req.requirement_id.strip().upper() in target_clean:
                matched_req = req
                break
        if not matched_req:
            matched_req = tender_analysis.requirements[0]
            logger.warning(
                "Target requirement ID '%s' not found; defaulted to '%s'",
                target_requirement_id,
                matched_req.requirement_id,
            )

    if not matched_req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target requirement '{target_requirement_id}' was not found in the analyzed tender.",
        )

    # 4. Extract text from bidder proof document, identify document type, entity ID, and expiry date
    bidder_text = await extract_text_from_pdf(bidder_doc_bytes)
    doc_type = _identify_document_type(matched_req, bidder_text)
    extracted_id, extracted_expiry = _extract_entity_id_and_expiry(doc_type, bidder_text)

    # 5. Deterministic Validation (Regex, Debarment & Expiry Kill-Switches)
    if doc_type in ("GST_CERTIFICATE", "PAN_CARD") or extracted_id or extracted_expiry:
        check_result = await run_deterministic_checks(
            document_type=doc_type,
            extracted_text=bidder_text,
            entity_id=extracted_id,
            expiry_date_str=extracted_expiry,
        )
        if not check_result.get("is_valid", False):
            validation_errors = check_result.get("validation_errors", [])
            has_blacklist_error = any("debarment" in err.lower() or "blacklist" in err.lower() for err in validation_errors)
            recommendation = "REJECT"

            logger.info(
                "Deterministic validation failed for %s (%s). Errors: %s. Instantly returning REJECT and skipping LLM.",
                matched_req.requirement_id,
                doc_type,
                validation_errors,
            )
            req_dict = matched_req.model_dump() if hasattr(matched_req, "model_dump") else matched_req
            evidence_dict = {
                "requirement_id": matched_req.requirement_id,
                "is_present": False,
                "extracted_values": {
                    "entity_id": extracted_id or "N/A",
                    "expiry_date": extracted_expiry or "N/A",
                    "validation_errors": validation_errors,
                },
                "source_quote": "; ".join(validation_errors),
                "extraction_confidence": 1.0,
            }
            finding_dict = {
                "requirement_id": matched_req.requirement_id,
                "state": "NON_COMPLIANT",
                "recommendation": recommendation,
                "risk_level": "CRITICAL" if has_blacklist_error else "HIGH",
                "reasoning_trace": f"Deterministic kill-switch triggered: {'; '.join(validation_errors)}",
            }
            return {
                "tender_id": tender_analysis.tender_id,
                "requirement": req_dict,
                "extracted_evidence": evidence_dict,
                "compliance_finding": finding_dict,
                "final_recommendation": recommendation,
            }

    # 6. Extract evidence for the specific target requirement via LLM
    extracted_evidence = await extract_evidence_with_llm(
        document_text=bidder_text,
        requirement_id=matched_req.requirement_id,
        requirement_description=matched_req.description,
    )

    # 7. Retrieve official legal context via ChromaDB RAG
    legal_context = await retrieve_relevant_clauses(
        "MSME exemptions, financial turnover requirements, and document compliance"
    )

    # 8. Evaluate compliance state and contradiction via LLM grounded in official rulebook
    req_dict = matched_req.model_dump() if hasattr(matched_req, "model_dump") else matched_req
    evidence_dict = (
        extracted_evidence.model_dump()
        if hasattr(extracted_evidence, "model_dump")
        else extracted_evidence
    )

    compliance_finding = await evaluate_compliance(
        requirement=req_dict,
        evidence=evidence_dict,
        legal_context=legal_context,
    )

    finding_dict = (
        compliance_finding.model_dump()
        if hasattr(compliance_finding, "model_dump")
        else compliance_finding
    )

    # 9. Assemble Unified Verification Dictionary
    finding_state = str(finding_dict.get("state", "")).upper()
    recommendation = (
        "ACCEPT"
        if ("VERIF" in finding_state or "COMPLIANT" in finding_state) and "NON" not in finding_state
        else "REJECT"
        if "NON" in finding_state
        else "REVIEW"
    )

    finding_dict["recommendation"] = recommendation

    unified_report = {
        "tender_id": tender_analysis.tender_id,
        "requirement": req_dict,
        "extracted_evidence": evidence_dict,
        "compliance_finding": finding_dict,
        "final_recommendation": recommendation,
        "legal_context": legal_context,
    }

    logger.info(
        "Master Verification completed: %s -> %s (Risk: %s, Recommendation: %s)",
        matched_req.requirement_id,
        finding_dict.get("state"),
        finding_dict.get("risk_level"),
        recommendation,
    )

    return unified_report


if __name__ == "__main__":
    import asyncio
    import pymupdf

    # Create synthetic tender PDF
    doc_t = pymupdf.open()
    page_t = doc_t.new_page()
    page_t.insert_text(
        (50, 72),
        "GeM Bid No: GEM/2026/B/99001\n"
        "1. Bidder must have minimum 50% Local Content under Make in India policy.\n"
        "Requirement ID: REQ-LC-01",
    )
    t_bytes = doc_t.tobytes()
    doc_t.close()

    # Create synthetic bidder declaration PDF (with 27% local content -> deficit)
    doc_b = pymupdf.open()
    page_b = doc_b.new_page()
    page_b.insert_text(
        (50, 72),
        "LOCAL CONTENT CERTIFICATE\n"
        "We hereby declare that our product contains 27% Local Content.",
    )
    b_bytes = doc_b.tobytes()
    doc_b.close()

    print("Testing run_master_verification...")
    out = asyncio.run(run_master_verification(t_bytes, b_bytes, "REQ-LC-01"))
    import json
    print("Master Verification Output:")
    print(json.dumps(out, indent=2, default=str))
