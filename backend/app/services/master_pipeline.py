"""Master Verification Pipeline Service.

Executes the unified multi-stage intelligence pipeline:
1. Tender PDF text extraction.
2. AI Tender requirement analysis and ambiguity detection.
3. Target requirement selection.
4. Bidder document PDF text extraction.
5. AI Evidence and verbatim proof extraction.
6. AI Contradiction and compliance state evaluation.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure project root and backend paths are available for imports
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent.parent
_root_dir = _backend_dir.parent
for _p in [str(_root_dir), str(_backend_dir), str(_current_file.parent.parent)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import HTTPException, status

try:
    from backend.app.ai.llm_evaluator_service import evaluate_compliance
    from backend.app.ai.llm_evidence_service import extract_evidence_with_llm
    from backend.app.ai.llm_service import analyze_tender_with_llm
    from backend.app.services.pdf_parser import extract_text_from_pdf
except ImportError:
    try:
        from app.ai.llm_evaluator_service import evaluate_compliance
        from app.ai.llm_evidence_service import extract_evidence_with_llm
        from app.ai.llm_service import analyze_tender_with_llm
        from app.services.pdf_parser import extract_text_from_pdf
    except ImportError:
        from ai.llm_evaluator_service import evaluate_compliance
        from ai.llm_evidence_service import extract_evidence_with_llm
        from ai.llm_service import analyze_tender_with_llm
        from services.pdf_parser import extract_text_from_pdf

logger = logging.getLogger(__name__)


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
              extracted evidence, and final compliance finding.

    Raises:
        HTTPException: If document parsing fails, target requirement is not found, or AI pipeline errors.
    """
    logger.info("Starting Master Verification Pipeline for requirement: %s", target_requirement_id)

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

    # 4. Extract text from bidder proof document
    bidder_text = await extract_text_from_pdf(bidder_doc_bytes)

    # 5. Extract evidence for the specific target requirement
    extracted_evidence = await extract_evidence_with_llm(
        document_text=bidder_text,
        requirement_id=matched_req.requirement_id,
        requirement_description=matched_req.description,
    )

    # 6. Evaluate compliance state and contradiction
    req_dict = matched_req.model_dump() if hasattr(matched_req, "model_dump") else matched_req
    evidence_dict = (
        extracted_evidence.model_dump()
        if hasattr(extracted_evidence, "model_dump")
        else extracted_evidence
    )

    compliance_finding = await evaluate_compliance(
        requirement=req_dict,
        evidence=evidence_dict,
    )

    finding_dict = (
        compliance_finding.model_dump()
        if hasattr(compliance_finding, "model_dump")
        else compliance_finding
    )

    # 7. Assemble Unified Verification Dictionary
    unified_report = {
        "tender_id": tender_analysis.tender_id,
        "requirement": req_dict,
        "extracted_evidence": evidence_dict,
        "compliance_finding": finding_dict,
    }

    logger.info(
        "Master Verification completed: %s -> %s (Risk: %s)",
        matched_req.requirement_id,
        finding_dict.get("state"),
        finding_dict.get("risk_level"),
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
