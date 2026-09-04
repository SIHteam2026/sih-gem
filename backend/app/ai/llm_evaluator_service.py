"""LLM Service for evaluating bidder compliance and contradiction detection using Groq Multi-Key Router."""

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
from pydantic import ValidationError

try:
    from backend.app.ai.prompts import CONTRADICTION_ANALYSIS_PROMPT
    from backend.app.models.evaluation import ComplianceFinding, ComplianceState
    from backend.app.services.ai_router import ai_router
except ImportError:
    try:
        from app.ai.prompts import CONTRADICTION_ANALYSIS_PROMPT
        from app.models.evaluation import ComplianceFinding, ComplianceState
        from app.services.ai_router import ai_router
    except ImportError:
        from prompts import CONTRADICTION_ANALYSIS_PROMPT
        from models.evaluation import ComplianceFinding, ComplianceState
        from services.ai_router import ai_router

logger = logging.getLogger(__name__)


def _normalize_compliance_state(state_str: str) -> ComplianceState:
    """Normalizes string state to a valid ComplianceState enum value."""
    if not state_str:
        return ComplianceState.REVIEW_REQUIRED
    upper = state_str.strip().upper()
    if "NON" in upper or "FAIL" in upper or "REJECT" in upper:
        return ComplianceState.NON_COMPLIANT
    elif "VERIF" in upper or "PASS" in upper or "COMPLIANT" in upper:
        return ComplianceState.VERIFIED
    elif "UNVERIF" in upper or "MISSING" in upper:
        return ComplianceState.UNVERIFIED
    else:
        return ComplianceState.REVIEW_REQUIRED


def _normalize_risk_level(risk_str: str) -> str:
    """Normalizes risk level string to HIGH, MEDIUM, LOW, or NONE."""
    if not risk_str:
        return "MEDIUM"
    upper = risk_str.strip().upper()
    if "HIGH" in upper or "CRITICAL" in upper:
        return "HIGH"
    elif "MED" in upper:
        return "MEDIUM"
    elif "LOW" in upper:
        return "LOW"
    elif "NONE" in upper or "ZERO" in upper:
        return "NONE"
    return "MEDIUM"


async def evaluate_compliance(
    requirement: dict,
    evidence: dict,
    legal_context: str | None = None,
) -> ComplianceFinding:
    """Evaluates whether extracted bidder evidence satisfies a tender requirement using Groq LLM.

    Args:
        requirement (dict): Structured tender requirement object.
        evidence (dict): Extracted bidder evidence object.
        legal_context (str | None): Optional official legal context retrieved from RAG.

    Returns:
        ComplianceFinding: Validated compliance determination model.

    Raises:
        HTTPException: If input is invalid, API fails, or output schema validation fails (500).
    """
    req_id = requirement.get("requirement_id") or evidence.get("requirement_id") or "REQ-UNKNOWN"

    prompt_parts = [CONTRADICTION_ANALYSIS_PROMPT]
    if legal_context and legal_context.strip():
        prompt_parts.append(f"### Government Rulebook & Legal Guidance:\n{legal_context.strip()}")

    prompt_parts.append(
        "### Tender Requirement:\n"
        f"{json.dumps(requirement, indent=2, default=str)}\n\n"
        "### Extracted Bidder Evidence:\n"
        f"{json.dumps(evidence, indent=2, default=str)}"
    )

    prompt = "\n\n".join(prompt_parts)

    try:
        raw_json = await ai_router.generate_json(
            prompt=prompt,
            temperature=0.1,
        )

        if isinstance(raw_json, list) and len(raw_json) > 0:
            parsed_dict = raw_json[0]
        elif isinstance(raw_json, dict):
            parsed_dict = raw_json
        else:
            parsed_dict = {}

        # Ensure requirement_id is consistent
        parsed_dict["requirement_id"] = req_id

        # Normalize state and risk_level
        if "state" in parsed_dict:
            parsed_dict["state"] = _normalize_compliance_state(str(parsed_dict["state"]))
        else:
            parsed_dict["state"] = ComplianceState.REVIEW_REQUIRED

        if "risk_level" in parsed_dict:
            parsed_dict["risk_level"] = _normalize_risk_level(str(parsed_dict["risk_level"]))
        else:
            parsed_dict["risk_level"] = "HIGH" if parsed_dict["state"] == ComplianceState.NON_COMPLIANT else "LOW"

        if "reasoning_trace" not in parsed_dict or not parsed_dict["reasoning_trace"]:
            parsed_dict["reasoning_trace"] = "Automated compliance evaluation completed."

        # Validate against ComplianceFinding Pydantic schema
        try:
            validated_finding = ComplianceFinding(**parsed_dict)
            return validated_finding
        except ValidationError as val_err:
            logger.error("Pydantic schema validation error on compliance finding output: %s", val_err)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Compliance AI output failed schema validation: {str(val_err)}",
            ) from val_err

    except HTTPException:
        raise
    except Exception as err:
        logger.error("Groq AI router error during compliance evaluation: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Groq API compliance evaluation error: {str(err)}",
        ) from err


if __name__ == "__main__":
    import asyncio

    sample_requirement = {
        "requirement_id": "REQ-LC-01",
        "category": "LOCAL_CONTENT",
        "description": "Minimum local content requirement of >=50% under Public Procurement / Make in India policy.",
        "mandatory": True,
        "evidence_required": ["Local Content Self-Declaration"],
    }

    sample_evidence_deficit = {
        "requirement_id": "REQ-LC-01",
        "is_present": True,
        "extracted_values": {"local_content_percentage": "27%"},
        "source_quote": "We certify our product contains 27% local content.",
        "extraction_confidence": 0.95,
    }

    print("Testing evaluate_compliance (deficit case)...")
    res = asyncio.run(evaluate_compliance(sample_requirement, sample_evidence_deficit))
    print("Result:")
    print(res.model_dump())
