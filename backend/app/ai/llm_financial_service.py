"""LLM Service for financial bid and Bill of Quantities (BOQ) arithmetic audit using Groq Multi-Key Router."""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

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
    from backend.app.ai.prompts import FINANCIAL_BOQ_PROMPT
    from backend.app.models.financial import FinancialEvaluationResult
    from backend.app.services.ai_router import ai_router
except ImportError:
    try:
        from app.ai.prompts import FINANCIAL_BOQ_PROMPT
        from app.models.financial import FinancialEvaluationResult
        from app.services.ai_router import ai_router
    except ImportError:
        from prompts import FINANCIAL_BOQ_PROMPT
        from models.financial import FinancialEvaluationResult
        from services.ai_router import ai_router

logger = logging.getLogger(__name__)


async def analyze_financial_bid(
    boq_tables: list[dict],
    estimated_tender_value: float,
) -> FinancialEvaluationResult:
    """Performs deep arithmetic audits, unit rate checks, and abnormally low bid detection on BOQ tables using Groq LLM.

    Args:
        boq_tables (list[dict]): List of extracted Bill of Quantities line item dictionaries.
        estimated_tender_value (float): Benchmark/baseline estimated tender value.

    Returns:
        FinancialEvaluationResult: Validated financial audit and evaluation result.

    Raises:
        HTTPException: If API fails or output fails schema validation (500).
    """
    if not boq_tables:
        return FinancialEvaluationResult(
            total_bid_value=0.0,
            math_errors_found=False,
            abnormally_low_bid=False,
            audit_notes=["No Bill of Quantities line items provided for analysis."],
        )

    prompt = (
        f"{FINANCIAL_BOQ_PROMPT}\n\n"
        f"### Estimated Tender Value:\n"
        f"{estimated_tender_value}\n\n"
        f"### Bill of Quantities (BOQ) Line Items:\n"
        f"{json.dumps(boq_tables, indent=2, default=str)}"
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

        # Ensure total_bid_value is float
        if "total_bid_value" in parsed_dict:
            try:
                parsed_dict["total_bid_value"] = float(parsed_dict["total_bid_value"])
            except (ValueError, TypeError):
                parsed_dict["total_bid_value"] = 0.0
        else:
            parsed_dict["total_bid_value"] = 0.0

        # Ensure boq_item_count is int
        if "boq_item_count" in parsed_dict:
            try:
                parsed_dict["boq_item_count"] = int(parsed_dict["boq_item_count"])
            except (ValueError, TypeError):
                parsed_dict["boq_item_count"] = len(boq_tables)
        else:
            parsed_dict["boq_item_count"] = len(boq_tables)

        # Ensure boq_item_count is non-negative
        if parsed_dict["boq_item_count"] < 0:
            parsed_dict["boq_item_count"] = len(boq_tables)

        # Ensure math_errors_found is boolean
        parsed_dict["math_errors_found"] = bool(parsed_dict.get("math_errors_found", False))

        # Ensure abnormally_low_bid is boolean
        parsed_dict["abnormally_low_bid"] = bool(parsed_dict.get("abnormally_low_bid", False))

        # Ensure audit_notes is a list of strings
        notes = parsed_dict.get("audit_notes", [])
        if isinstance(notes, list):
            parsed_dict["audit_notes"] = [str(n) for n in notes]
        elif isinstance(notes, str):
            parsed_dict["audit_notes"] = [notes]
        else:
            parsed_dict["audit_notes"] = ["Financial audit completed."]

        # Validate against FinancialEvaluationResult Pydantic schema
        try:
            validated_result = FinancialEvaluationResult(**parsed_dict)
            return validated_result
        except ValidationError as val_err:
            logger.error("Pydantic schema validation error on financial evaluation: %s", val_err)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Financial evaluation AI output failed schema validation: {str(val_err)}",
            ) from val_err

    except HTTPException:
        raise
    except Exception as err:
        logger.error("Groq AI router error during financial evaluation: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Groq API financial evaluation error: {str(err)}",
        ) from err


if __name__ == "__main__":
    import asyncio

    sample_boq = [
        {"item_description": "Core Switch 48-Port PoE+", "quantity": 10, "unit_price": 50000.0, "total_price": 500000.0},
        {"item_description": "Edge Switch 24-Port", "quantity": 20, "unit_price": 25000.0, "total_price": 400000.0},
        {"item_description": "Installation and Commissioning", "quantity": 1, "unit_price": 50000.0, "total_price": 50000.0},
    ]

    print("Testing analyze_financial_bid...")
    res = asyncio.run(analyze_financial_bid(sample_boq, estimated_tender_value=1200000.0))
    print("Financial Audit Result:")
    print(res.model_dump())
