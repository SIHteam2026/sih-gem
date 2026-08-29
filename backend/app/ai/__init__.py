"""AI module initialization for procurement and tender intelligence."""

from .llm_evaluator_service import evaluate_compliance
from .llm_evidence_service import extract_evidence_with_llm
from .llm_service import analyze_tender_with_llm
from .prompts import (
    CONTRADICTION_ANALYSIS_PROMPT,
    EVIDENCE_EXTRACTION_PROMPT,
    TENDER_EXTRACTION_PROMPT,
)

__all__ = [
    "TENDER_EXTRACTION_PROMPT",
    "EVIDENCE_EXTRACTION_PROMPT",
    "CONTRADICTION_ANALYSIS_PROMPT",
    "analyze_tender_with_llm",
    "extract_evidence_with_llm",
    "evaluate_compliance",
]
