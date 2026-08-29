"""LLM Service for financial bid and Bill of Quantities (BOQ) arithmetic audit."""

import json
import logging
import os
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

from dotenv import find_dotenv, load_dotenv
from fastapi import HTTPException, status
import google.generativeai as genai
from pydantic import ValidationError

try:
    from backend.app.ai.prompts import FINANCIAL_BOQ_PROMPT
    from backend.app.models.financial import FinancialEvaluationResult
except ImportError:
    try:
        from app.ai.prompts import FINANCIAL_BOQ_PROMPT
        from app.models.financial import FinancialEvaluationResult
    except ImportError:
        from prompts import FINANCIAL_BOQ_PROMPT
        from models.financial import FinancialEvaluationResult

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger(__name__)

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)


async def analyze_financial_bid(
    boq_tables: list[dict],
    estimated_tender_value: float,
) -> FinancialEvaluationResult:
    """Performs deep arithmetic audits, unit rate checks, and abnormally low bid detection on BOQ tables.

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

    # Ensure API key is configured
    current_key = os.getenv("GEMINI_API_KEY")
    if current_key:
        genai.configure(api_key=current_key)

    prompt = (
        f"{FINANCIAL_BOQ_PROMPT}\n\n"
        f"### Estimated Tender Value:\n"
        f"{estimated_tender_value}\n\n"
        f"### Bill of Quantities (BOQ) Line Items:\n"
        f"{json.dumps(boq_tables, indent=2, default=str)}"
    )

    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.1,
    }

    # Candidate models with automatic fallback
    candidate_models = ["gemini-1.5-flash", "gemini-3.6-flash", "gemini-2.5-flash"]
    last_error = None

    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
            )

            response = await model.generate_content_async(prompt)

            if not response or not response.text:
                raise ValueError("Received empty response from Gemini API.")

            raw_json = json.loads(response.text.strip())

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

            # Ensure booleans
            parsed_dict["math_errors_found"] = bool(parsed_dict.get("math_errors_found", False))
            parsed_dict["abnormally_low_bid"] = bool(parsed_dict.get("abnormally_low_bid", False))

            # Ensure audit_notes is a list of strings
            notes = parsed_dict.get("audit_notes", [])
            if isinstance(notes, list):
                parsed_dict["audit_notes"] = [str(n) for n in notes]
            elif isinstance(notes, str):
                parsed_dict["audit_notes"] = [notes]
            else:
                parsed_dict["audit_notes"] = []

            # Validate against FinancialEvaluationResult Pydantic schema
            try:
                validated_result = FinancialEvaluationResult(**parsed_dict)
                return validated_result
            except ValidationError as val_err:
                logger.error("Pydantic schema validation error on financial evaluation: %s", val_err)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Financial AI output failed schema validation: {str(val_err)}",
                ) from val_err

        except HTTPException:
            raise
        except Exception as err:
            last_error = err
            err_str = str(err)
            if "not found" in err_str.lower() or "no longer available" in err_str.lower() or "404" in err_str:
                logger.warning(
                    "Model %s unavailable (%s). Trying fallback candidate...",
                    model_name,
                    err_str,
                )
                continue
            else:
                logger.error("Gemini API error during financial evaluation: %s", err)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Gemini API financial evaluation error: {str(err)}",
                ) from err

    logger.error("All Gemini candidate models failed: %s", last_error)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Failed to evaluate financial bid with AI: {str(last_error)}",
    )


if __name__ == "__main__":
    import asyncio

    sample_boq = [
        {"item": "High Speed Router", "quantity": 10, "unit_rate": 50000, "row_total": 500000},
        {"item": "Core Switch 48-Port", "quantity": 5, "unit_rate": 80000, "row_total": 400000},
        {"item": "Installation & Cabling", "quantity": 1, "unit_rate": 100000, "row_total": 100000},
    ]

    print("Testing analyze_financial_bid...")
    # Estimated tender value: 1,500,000. Total bid: 1,000,000 (33.3% below estimate -> abnormally low bid)
    res = asyncio.run(analyze_financial_bid(sample_boq, estimated_tender_value=1500000.0))
    print("Result:")
    print(res.model_dump())
