"""LLM Service for audit explainability, transparency reporting, and decision justifications using Groq Multi-Key Router."""

import json
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
    from app.ai.prompts import AUDIT_EXPLAINABILITY_PROMPT
    from app.services.ai_router import ai_router
except ImportError:
    try:
        from app.ai.prompts import AUDIT_EXPLAINABILITY_PROMPT
        from app.services.ai_router import ai_router
    except ImportError:
        from prompts import AUDIT_EXPLAINABILITY_PROMPT
        from services.ai_router import ai_router

logger = logging.getLogger(__name__)


async def generate_audit_explainability(evaluation_result: dict) -> str:
    """Generates a plain-English, non-technical justification explaining why a bidder
    passed, failed, or was flagged for review, citing specific RAG rules and fraud scores using Groq LLM.

    Args:
        evaluation_result (dict): Complete evaluation dossier or MasterEvaluationResponse dict.

    Returns:
        str: Cohesive, plain-English justification narrative.

    Raises:
        HTTPException: If the AI generation fails.
    """
    if not evaluation_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No evaluation result provided for explainability analysis.",
        )

    prompt = (
        f"{AUDIT_EXPLAINABILITY_PROMPT}\n\n"
        f"### Master Evaluation Dossier:\n"
        f"{json.dumps(evaluation_result, indent=2, default=str)}"
    )

    try:
        justification = await ai_router.generate_text(
            prompt=prompt,
            temperature=0.2,
        )
        return justification.strip()

    except HTTPException:
        raise
    except Exception as err:
        logger.error("Groq AI router error during explainability generation: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate audit explainability narrative: {str(err)}",
        ) from err


if __name__ == "__main__":
    import asyncio

    sample_eval = {
        "tender_id": "GEM/2026/B/88219",
        "bidder_name": "Apex Infotech Pvt Ltd",
        "deterministic_checks": {"gst_verified": True, "gstin": "27AABCU9603R1ZN", "entity_match_score": 100.0},
        "fraud_analysis": {"trust_score": 92.0, "is_suspicious": False, "red_flags": [], "collusion_risk_level": "NONE"},
        "legal_citations": [{"rule_source": "GFR 2017 Rule 144(xi)", "clause_title": "Land Border Verification"}],
        "financial_evaluation": {"total_bid_value": 1200000.0, "math_errors_found": False, "abnormally_low_bid": False},
        "final_report": {"final_recommendation": "ACCEPT", "executive_summary": "Bidder is fully verified."},
    }

    print("Testing generate_audit_explainability...")
    try:
        res = asyncio.run(generate_audit_explainability(sample_eval))
        print("\nExplainability Justification:\n")
        print(res)
    except Exception as e:
        print("Test execution finished (handled):", e)
