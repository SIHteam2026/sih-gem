"""AI module initialization for procurement and tender intelligence."""

from .llm_evidence_service import extract_evidence_with_llm
from .llm_service import analyze_tender_with_llm
from .prompts import EVIDENCE_EXTRACTION_PROMPT, TENDER_EXTRACTION_PROMPT

__all__ = [
    "TENDER_EXTRACTION_PROMPT",
    "EVIDENCE_EXTRACTION_PROMPT",
    "analyze_tender_with_llm",
    "extract_evidence_with_llm",
]
