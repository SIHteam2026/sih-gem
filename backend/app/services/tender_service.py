"""Tender Intelligence Service Module.

Provides services for analyzing tender documents, parsing compliance criteria,
and generating structured tender requirement models via the live AI extraction pipeline.
"""

import sys
from pathlib import Path

# Ensure project root and backend paths are available for imports
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent.parent
_root_dir = _backend_dir.parent
for _p in [str(_root_dir), str(_backend_dir), str(_current_file.parent.parent)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from typing import Any, Dict, List, Optional

try:
    from backend.app.models.tender import TenderAnalysisResult, TenderRequirement
    from backend.app.services.pdf_parser import extract_pages_from_pdf, extract_text_from_pdf
    from backend.app.ai.llm_service import analyze_tender_with_llm
    from backend.app.db.client import save_tender_requirements, get_tender_requirements
except ImportError:
    try:
        from app.models.tender import TenderAnalysisResult, TenderRequirement
        from app.services.pdf_parser import extract_pages_from_pdf, extract_text_from_pdf
        from app.ai.llm_service import analyze_tender_with_llm
        from app.db.client import save_tender_requirements, get_tender_requirements
    except ImportError:
        from models.tender import TenderAnalysisResult, TenderRequirement
        from services.pdf_parser import extract_pages_from_pdf, extract_text_from_pdf
        from ai.llm_service import analyze_tender_with_llm
        from db.client import save_tender_requirements, get_tender_requirements


async def analyze_tender(
    file_bytes: bytes,
    tender_id: Optional[str] = None,
    filename: Optional[str] = "tender.pdf",
) -> TenderAnalysisResult:
    """Analyzes tender document bytes and extracts structured compliance requirements
    using the multi-format extraction and Gemini AI intelligence pipeline.

    Args:
        file_bytes (bytes): Raw bytes of the uploaded tender document.
        tender_id (Optional[str]): Optional explicit canonical tender ID or reference.
        filename (Optional[str]): Filename for format detection (PDF, DOCX, TXT).

    Returns:
        TenderAnalysisResult: Validated Pydantic model with structured conditions,
            applicability, evidence specs, provenance, and ambiguity analysis.
    """
    try:
        from backend.app.services.multi_format_extractor import extract_data_from_file
    except ImportError:
        try:
            from app.services.multi_format_extractor import extract_data_from_file
        except ImportError:
            from services.multi_format_extractor import extract_data_from_file

    # Step 1: Extract page-aware text chunks (supports PDF, DOCX, TXT)
    extracted = await extract_data_from_file(file_bytes, filename or "tender.pdf")
    pages = extracted.get("pages")
    if not pages:
        pages = await extract_pages_from_pdf(file_bytes)

    # Step 2: Pass extracted pages through Gemini LLM with Ambiguity Radar & Structured Condition extraction
    result = await analyze_tender_with_llm(pages)

    if tender_id:
        result.tender_id = tender_id

    return result


async def persist_tender_requirements(
    tender_id: str,
    analysis_result: TenderAnalysisResult,
) -> List[TenderRequirement]:
    """Persists structured requirements from an analysis result against a canonical tender.
    
    Guarantees idempotency by replacing existing requirement definitions for the tender.
    """
    req_dicts = [req.model_dump() for req in analysis_result.requirements]
    saved_rows = await save_tender_requirements(tender_id, req_dicts)
    
    # Parse back into typed TenderRequirement objects
    persisted_reqs: List[TenderRequirement] = []
    for row in saved_rows:
        try:
            persisted_reqs.append(TenderRequirement.model_validate(row))
        except Exception:
            pass

    return persisted_reqs if persisted_reqs else analysis_result.requirements


async def get_requirements_for_tender(tender_id: str) -> List[TenderRequirement]:
    """Retrieves structured requirements for a canonical tender or snapshot."""
    raw_rows = await get_tender_requirements(tender_id)
    typed_reqs: List[TenderRequirement] = []
    for row in raw_rows:
        try:
            typed_reqs.append(TenderRequirement.model_validate(row))
        except Exception:
            pass
    return typed_reqs


