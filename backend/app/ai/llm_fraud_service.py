"""LLM Service for forensic fraud detection, document consistency audit, and vendor trust scoring using Groq Multi-Key Router."""

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
    from backend.app.ai.prompts import FRAUD_DETECTION_PROMPT
    from backend.app.models.fraud import FraudAnalysisResult
    from backend.app.services.ai_router import ai_router
except ImportError:
    try:
        from app.ai.prompts import FRAUD_DETECTION_PROMPT
        from app.models.fraud import FraudAnalysisResult
        from app.services.ai_router import ai_router
    except ImportError:
        from prompts import FRAUD_DETECTION_PROMPT
        from models.fraud import FraudAnalysisResult
        from services.ai_router import ai_router

logger = logging.getLogger(__name__)


def _normalize_risk_level(risk_str: str) -> str:
    """Normalizes risk level string to HIGH, MEDIUM, LOW, or NONE."""
    if not risk_str:
        return "LOW"
    upper = risk_str.strip().upper()
    if "HIGH" in upper or "CRITICAL" in upper or "SEVERE" in upper:
        return "HIGH"
    elif "MED" in upper:
        return "MEDIUM"
    elif "NONE" in upper or "ZERO" in upper:
        return "NONE"
    return "LOW"


async def analyze_vendor_risk(bidder_data: dict) -> FraudAnalysisResult:
    """Performs deep forensic audit and cross-document verification using Groq LLM to calculate
    a vendor trust score and detect fraud/collusion signals.

    Args:
        bidder_data (dict): Unified payload containing bidder documents, metadata, entity data, and BOQ details.

    Returns:
        FraudAnalysisResult: Validated forensic risk assessment and trust score.

    Raises:
        HTTPException: If API fails or output fails schema validation (500).
    """
    if not bidder_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No bidder data provided for fraud and risk analysis.",
        )

    prompt = (
        f"{FRAUD_DETECTION_PROMPT}\n\n"
        f"### Bidder Submission & Forensic Data Dossier:\n"
        f"{json.dumps(bidder_data, indent=2, default=str)}"
    )

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

        # Ensure trust_score is float bounded between 0 and 100
        if "trust_score" in parsed_dict:
            try:
                score = float(parsed_dict["trust_score"])
                parsed_dict["trust_score"] = max(0.0, min(100.0, score))
            except (ValueError, TypeError):
                parsed_dict["trust_score"] = 50.0
        else:
            parsed_dict["trust_score"] = 50.0

        # Ensure is_suspicious is bool
        parsed_dict["is_suspicious"] = bool(parsed_dict.get("is_suspicious", False))

        # Ensure red_flags is a list of strings
        flags = parsed_dict.get("red_flags", [])
        if isinstance(flags, list):
            parsed_dict["red_flags"] = [str(f) for f in flags]
        elif isinstance(flags, str):
            parsed_dict["red_flags"] = [flags]
        else:
            parsed_dict["red_flags"] = []

        # Normalize collusion_risk_level
        parsed_dict["collusion_risk_level"] = _normalize_risk_level(
            str(parsed_dict.get("collusion_risk_level", "LOW"))
        )

        # Validate against FraudAnalysisResult Pydantic schema
        try:
            validated_result = FraudAnalysisResult(**parsed_dict)
            return validated_result
        except ValidationError as val_err:
            logger.error("Pydantic schema validation error on fraud analysis: %s", val_err)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Fraud analysis AI output failed schema validation: {str(val_err)}",
            ) from val_err

    except HTTPException:
        raise
    except Exception as err:
        logger.error("Groq AI router error during fraud analysis: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Groq API fraud analysis error: {str(err)}",
        ) from err


if __name__ == "__main__":
    import asyncio

    sample_bidder_data = {
        "company_name": "QuickShell Enterprises LLP",
        "gst_registration_date": "2026-07-15",
        "tender_bid_date": "2026-08-01",
        "experience_certificate_date": "2023-01-10",
        "experience_certificate_issuer": "Global Tech Corp",
        "pan_number": "AAACQ1234F",
        "financial_bid_value": 450000.0,
        "estimated_tender_value": 1500000.0,
        "documents": [
            {"filename": "gst_cert.pdf", "text": "GSTIN 27AAACQ1234F1Z5 registered on 15-July-2026"},
            {"filename": "exp_cert.pdf", "text": "Successfully completed contract in Jan 2023"},
        ],
    }

    print("Testing analyze_vendor_risk...")
    res = asyncio.run(analyze_vendor_risk(sample_bidder_data))
    print("Fraud Analysis Result:")
    print(res.model_dump())
