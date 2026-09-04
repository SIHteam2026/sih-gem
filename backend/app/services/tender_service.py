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

try:
    from backend.app.models.tender import TenderAnalysisResult
    from backend.app.services.pdf_parser import extract_pages_from_pdf, extract_text_from_pdf
    from backend.app.ai.llm_service import analyze_tender_with_llm
except ImportError:
    try:
        from app.models.tender import TenderAnalysisResult
        from app.services.pdf_parser import extract_pages_from_pdf, extract_text_from_pdf
        from app.ai.llm_service import analyze_tender_with_llm
    except ImportError:
        from models.tender import TenderAnalysisResult
        from services.pdf_parser import extract_pages_from_pdf, extract_text_from_pdf
        from ai.llm_service import analyze_tender_with_llm


async def analyze_tender(file_bytes: bytes) -> TenderAnalysisResult:
    """Analyzes tender document bytes and extracts structured compliance requirements
    using the page-aware PDF extraction and Gemini AI intelligence pipeline.

    Args:
        file_bytes (bytes): Raw bytes of the uploaded tender PDF document.

    Returns:
        TenderAnalysisResult: Validated Pydantic model with structured conditions,
            applicability, evidence specs, provenance, and ambiguity analysis.
    """
    # Step 1: Extract page-aware text chunks from PDF bytes
    pages = await extract_pages_from_pdf(file_bytes)

    # Step 2: Pass extracted pages through Gemini LLM with Ambiguity Radar & Structured Condition extraction
    result = await analyze_tender_with_llm(pages)

    return result

