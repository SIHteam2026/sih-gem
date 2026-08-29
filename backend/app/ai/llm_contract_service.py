"""LLM Service for automated Letter of Award (LoA) legal drafting and contract generation."""

import datetime
import json
import logging
import os
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

from dotenv import find_dotenv, load_dotenv
from fastapi import HTTPException, status
import google.generativeai as genai
from pydantic import ValidationError

try:
    from backend.app.ai.prompts import CONTRACT_GENERATION_PROMPT
    from backend.app.models.contract import LetterOfAward
except ImportError:
    try:
        from app.ai.prompts import CONTRACT_GENERATION_PROMPT
        from app.models.contract import LetterOfAward
    except ImportError:
        from prompts import CONTRACT_GENERATION_PROMPT
        from models.contract import LetterOfAward

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger(__name__)

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)


async def generate_award_contract(tender_data: dict, winner_data: dict) -> LetterOfAward:
    """Generates an official, legally binding Letter of Award (LoA) contract note
    for the selected winning bidder using Gemini AI legal reasoning.

    Args:
        tender_data (dict): Tender details, scope of work, technical requirements, and delivery expectations.
        winner_data (dict): Winning bidder's corporate identity, BOQ financials, unit rates, and compliance proofs.

    Returns:
        LetterOfAward: Validated contract award object containing clauses and full legal text.

    Raises:
        HTTPException: If API fails or output fails schema validation (500).
    """
    if not tender_data and not winner_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tender data and winner data are required for contract generation.",
        )

    # Ensure API key is configured
    current_key = os.getenv("GEMINI_API_KEY")
    if current_key:
        genai.configure(api_key=current_key)

    payload = {
        "tender_data": tender_data or {},
        "winner_data": winner_data or {},
    }

    prompt = (
        f"{CONTRACT_GENERATION_PROMPT}\n\n"
        f"### Contract Input Dossier:\n"
        f"{json.dumps(payload, indent=2, default=str)}"
    )

    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.2,
    }

    # Candidate models prioritized with gemini-1.5-pro for deep legal drafting
    candidate_models = ["gemini-1.5-pro", "gemini-3.6-flash", "gemini-2.5-pro", "gemini-1.5-flash"]
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

            # Sanitize fallback values if missing
            today_str = datetime.date.today().isoformat()
            if "date_of_issue" not in parsed_dict or not parsed_dict["date_of_issue"]:
                parsed_dict["date_of_issue"] = today_str

            if "contract_reference_number" not in parsed_dict or not parsed_dict["contract_reference_number"]:
                tender_id = tender_data.get("tender_id", "TENDER") if isinstance(tender_data, dict) else "TENDER"
                parsed_dict["contract_reference_number"] = f"LOA/GEM/{datetime.date.today().year}/{tender_id}"

            if "vendor_name" not in parsed_dict or not parsed_dict["vendor_name"]:
                vendor = (
                    winner_data.get("company_name") or winner_data.get("vendor_name")
                    if isinstance(winner_data, dict)
                    else "Awarded Bidder"
                )
                parsed_dict["vendor_name"] = str(vendor or "Awarded Bidder")

            if "total_award_value" in parsed_dict:
                try:
                    parsed_dict["total_award_value"] = float(parsed_dict["total_award_value"])
                except (ValueError, TypeError):
                    parsed_dict["total_award_value"] = 0.0
            else:
                parsed_dict["total_award_value"] = 0.0

            clauses = parsed_dict.get("legal_clauses", [])
            if isinstance(clauses, list):
                parsed_dict["legal_clauses"] = [str(c) for c in clauses]
            elif isinstance(clauses, str):
                parsed_dict["legal_clauses"] = [clauses]
            else:
                parsed_dict["legal_clauses"] = []

            if "full_contract_text" not in parsed_dict or not parsed_dict["full_contract_text"]:
                parsed_dict["full_contract_text"] = "LETTER OF AWARD (LOA)\nContract text generated."

            # Validate against LetterOfAward Pydantic schema
            try:
                validated_result = LetterOfAward(**parsed_dict)
                return validated_result
            except ValidationError as val_err:
                logger.error("Pydantic schema validation error on LetterOfAward: %s", val_err)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Contract generation AI output failed schema validation: {str(val_err)}",
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
                logger.error("Gemini API error during contract generation: %s", err)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Gemini API contract generation error: {str(err)}",
                ) from err

    logger.error("All Gemini candidate models failed: %s", last_error)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Failed to generate contract award with AI: {str(last_error)}",
    )


if __name__ == "__main__":
    import asyncio

    sample_tender = {
        "tender_id": "GEM/2026/B/77102",
        "description": "Procurement of 500 High-Performance Workstations for Central Data Centre",
        "delivery_period_days": 45,
        "warranty_years": 3,
        "jurisdiction": "New Delhi",
    }

    sample_winner = {
        "company_name": "Zenith Infotech Solutions Ltd",
        "gstin": "07AAAAZ0000A1Z5",
        "pan": "AAAAZ0000A",
        "address": "Block B, Tech Park, Okhla Phase III, New Delhi 110020",
        "financial_quote": 24500000.0,
        "line_items": [
            {"item": "Workstations Intel Xeon 64GB RAM", "qty": 500, "unit_rate": 49000, "total": 24500000.0}
        ],
    }

    print("Testing generate_award_contract...")
    res = asyncio.run(generate_award_contract(sample_tender, sample_winner))
    print("Contract Result:")
    print(res.model_dump())
