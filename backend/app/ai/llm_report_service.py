"""LLM Service for generating final executive audit reports and procurement decisions using Groq Multi-Key Router."""

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
    from app.ai.prompts import EXECUTIVE_REPORT_PROMPT
    from app.models.report import FinalAuditReport
    from app.services.ai_router import ai_router
except ImportError:
    try:
        from app.ai.prompts import EXECUTIVE_REPORT_PROMPT
        from app.models.report import FinalAuditReport
        from app.services.ai_router import ai_router
    except ImportError:
        from prompts import EXECUTIVE_REPORT_PROMPT
        from models.report import FinalAuditReport
        from services.ai_router import ai_router

logger = logging.getLogger(__name__)


def _normalize_recommendation(rec_str: str) -> str:
    """Normalizes recommendation string to ACCEPT, REJECT, or MANUAL_REVIEW."""
    if not rec_str:
        return "MANUAL_REVIEW"
    upper = rec_str.strip().upper()
    if "REJECT" in upper or "DISQUALIF" in upper or "NON" in upper:
        return "REJECT"
    elif "ACCEPT" in upper or "PASS" in upper or "QUALIF" in upper:
        return "ACCEPT"
    elif "REVIEW" in upper or "MANUAL" in upper or "COMMITTEE" in upper:
        return "MANUAL_REVIEW"
    return "MANUAL_REVIEW"


async def generate_final_report(audit_data: dict) -> FinalAuditReport:
    """Synthesizes compliance findings, financial BOQ audits, and entity match results
    into an executive procurement audit report using Groq LLM.

    Args:
        audit_data (dict): Aggregate dictionary of compliance findings, BOQ audits, and entity scores.

    Returns:
        FinalAuditReport: Validated executive audit report with decision recommendation.

    Raises:
        HTTPException: If API fails or output fails schema validation (500).
    """
    if not audit_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audit data provided for executive report synthesis.",
        )

    prompt = (
        f"{EXECUTIVE_REPORT_PROMPT}\n\n"
        f"### Aggregate Procurement Audit Dossier:\n"
        f"{json.dumps(audit_data, indent=2, default=str)}"
    )

    try:
        raw_json = await ai_router.generate_json(
            prompt=prompt,
            temperature=0.2,
        )

        if isinstance(raw_json, list) and len(raw_json) > 0:
            parsed_dict = raw_json[0]
        elif isinstance(raw_json, dict):
            parsed_dict = raw_json
        else:
            parsed_dict = {}

        # Ensure executive_summary is a string
        if "executive_summary" not in parsed_dict or not parsed_dict["executive_summary"]:
            parsed_dict["executive_summary"] = "Procurement audit evaluation synthesis completed."

        # Ensure key_violations is a list of strings
        violations = parsed_dict.get("key_violations", [])
        if isinstance(violations, list):
            parsed_dict["key_violations"] = [str(v) for v in violations]
        elif isinstance(violations, str):
            parsed_dict["key_violations"] = [violations]
        else:
            parsed_dict["key_violations"] = []

        # Ensure financial_assessment is a string
        if "financial_assessment" not in parsed_dict or not parsed_dict["financial_assessment"]:
            parsed_dict["financial_assessment"] = "Commercial evaluation completed."

        # Normalize final_recommendation
        parsed_dict["final_recommendation"] = _normalize_recommendation(
            str(parsed_dict.get("final_recommendation", "MANUAL_REVIEW"))
        )

        # Validate against FinalAuditReport Pydantic schema
        try:
            validated_report = FinalAuditReport(**parsed_dict)
            return validated_report
        except ValidationError as val_err:
            logger.error("Pydantic schema validation error on executive report output: %s", val_err)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Executive report AI output failed schema validation: {str(val_err)}",
            ) from val_err

    except HTTPException:
        raise
    except Exception as err:
        logger.error("Groq AI router error during report generation: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Groq API report generation error: {str(err)}",
        ) from err


if __name__ == "__main__":
    import asyncio

    sample_dossier = {
        "tender_id": "GEM/2026/B/99001",
        "bidder_name": "Apex Infotech Pvt Ltd",
        "compliance_findings": [
            {
                "requirement_id": "REQ-LC-01",
                "state": "NON_COMPLIANT",
                "risk_level": "HIGH",
                "reasoning_trace": "Claimed local content is 27.0%, falling short of mandatory 50% threshold.",
            },
            {
                "requirement_id": "REQ-GST-01",
                "state": "VERIFIED",
                "risk_level": "LOW",
                "reasoning_trace": "Active GSTIN verified against government registry.",
            },
        ],
        "financial_audit": {
            "total_bid_value": 1000000.0,
            "math_errors_found": False,
            "abnormally_low_bid": True,
            "audit_notes": [
                "Grand total matches line items.",
                "Bid value is 33.3% below estimated tender value (Rs. 15,00,000).",
            ],
        },
        "entity_match": {
            "name_match_score": 1.0,
            "pan_verified": True,
            "gstin_verified": True,
        },
    }

    print("Testing generate_final_report...")
    report = asyncio.run(generate_final_report(sample_dossier))
    print("Executive Report Result:")
    print(report.model_dump())
