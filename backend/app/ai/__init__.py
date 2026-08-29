"""AI module initialization for procurement and tender intelligence."""

from .llm_service import analyze_tender_with_llm
from .prompts import TENDER_EXTRACTION_PROMPT

__all__ = ["TENDER_EXTRACTION_PROMPT", "analyze_tender_with_llm"]
