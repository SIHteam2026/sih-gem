"""LLM Service for document shortfall evaluation and automated clarification drafting using Groq Multi-Key Router."""

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
    from app.ai.prompts import SHORTFALL_GENERATION_PROMPT
    from app.models.shortfall import ShortfallRequest
    from app.services.ai_router import ai_router
except ImportError:
    try:
        from app.ai.prompts import SHORTFALL_GENERATION_PROMPT
        from app.models.shortfall import ShortfallRequest
        from app.services.ai_router import ai_router
    except ImportError:
        from prompts import SHORTFALL_GENERATION_PROMPT
        from models.shortfall import ShortfallRequest
        from services.ai_router import ai_router

logger = logging.getLogger(__name__)


async def generate_shortfall_notice(compliance_data: dict) -> ShortfallRequest:
    """Evaluates bidder compliance data against mandatory requirements to identify shortfalls
    and draft a formal government clarification notice using Groq LLM.

    Args:
        compliance_data (dict): Compliance findings, missing document records, and bidder details.

    Returns:
        ShortfallRequest: Validated shortfall assessment and formal email draft.

    Raises:
        HTTPException: If API fails or output fails schema validation (500).
    """
    if not compliance_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No compliance data provided for shortfall evaluation.",
        )

    prompt = (
        f"{SHORTFALL_GENERATION_PROMPT}\n\n"
        f"### Bidder Compliance & Scrutiny Dossier:\n"
        f"{json.dumps(compliance_data, indent=2, default=str)}"
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

        parsed_dict["requires_clarification"] = bool(parsed_dict.get("requires_clarification", False))

        items = parsed_dict.get("missing_items", [])
        if isinstance(items, list):
            parsed_dict["missing_items"] = [str(i) for i in items]
        elif isinstance(items, str):
            parsed_dict["missing_items"] = [items]
        else:
            parsed_dict["missing_items"] = []

        if "clarification_email_draft" not in parsed_dict or not parsed_dict["clarification_email_draft"]:
            parsed_dict["clarification_email_draft"] = (
                "Subject: Tender Document Scrutiny Notice\n\nAll submitted documents are in order."
            )

        # Validate against ShortfallRequest Pydantic schema
        try:
            validated_result = ShortfallRequest(**parsed_dict)
            return validated_result
        except ValidationError as val_err:
            logger.error("Pydantic schema validation error on ShortfallRequest: %s", val_err)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Shortfall notice AI output failed schema validation: {str(val_err)}",
            ) from val_err

    except HTTPException:
        raise
    except Exception as err:
        logger.error("Groq AI router error during shortfall generation: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Groq API shortfall notice error: {str(err)}",
        ) from err


if __name__ == "__main__":
    import asyncio

    sample_compliance_data = {
        "tender_id": "GEM/2026/B/88219",
        "bidder_name": "Matrix Technologies Pvt Ltd",
        "compliance_findings": [
            {
                "requirement_id": "REQ-001",
                "category": "GST",
                "state": "VERIFIED",
                "risk_level": "NONE",
            },
            {
                "requirement_id": "REQ-002",
                "category": "OEM_AUTH",
                "state": "NON_COMPLIANT",
                "risk_level": "HIGH",
                "reasoning_trace": "Manufacturer Authorization Form (MAF) was not uploaded or is unreadable.",
            },
            {
                "requirement_id": "REQ-003",
                "category": "LOCAL_CONTENT",
                "state": "REVIEW_REQUIRED",
                "risk_level": "MEDIUM",
                "reasoning_trace": "Local content percentage declared but missing statutory Chartered Accountant (CA) certificate.",
            },
        ],
    }

    print("Testing generate_shortfall_notice...")
    res = asyncio.run(generate_shortfall_notice(sample_compliance_data))
    print("Shortfall Result:")
    print(res.model_dump())
