"""AI module initialization for procurement and tender intelligence."""

from .chat_service import answer_procurement_question
from .llm_contract_service import generate_award_contract
from .llm_evaluator_service import evaluate_compliance
from .llm_evidence_service import extract_evidence_with_llm
from .llm_financial_service import analyze_financial_bid
from .llm_fraud_service import analyze_vendor_risk
from .llm_report_service import generate_final_report
from .llm_service import analyze_tender_with_llm
from .llm_translation_service import normalize_document_language
from .prompts import (
    CONTRACT_GENERATION_PROMPT,
    CONTRADICTION_ANALYSIS_PROMPT,
    EVIDENCE_EXTRACTION_PROMPT,
    EXECUTIVE_REPORT_PROMPT,
    FINANCIAL_BOQ_PROMPT,
    FRAUD_DETECTION_PROMPT,
    LEGAL_TRANSLATION_PROMPT,
    PROCUREMENT_QA_PROMPT,
    TENDER_EXTRACTION_PROMPT,
)

__all__ = [
    "TENDER_EXTRACTION_PROMPT",
    "EVIDENCE_EXTRACTION_PROMPT",
    "CONTRADICTION_ANALYSIS_PROMPT",
    "PROCUREMENT_QA_PROMPT",
    "FINANCIAL_BOQ_PROMPT",
    "EXECUTIVE_REPORT_PROMPT",
    "FRAUD_DETECTION_PROMPT",
    "LEGAL_TRANSLATION_PROMPT",
    "CONTRACT_GENERATION_PROMPT",
    "analyze_tender_with_llm",
    "extract_evidence_with_llm",
    "evaluate_compliance",
    "answer_procurement_question",
    "analyze_financial_bid",
    "generate_final_report",
    "analyze_vendor_risk",
    "normalize_document_language",
    "generate_award_contract",
]
