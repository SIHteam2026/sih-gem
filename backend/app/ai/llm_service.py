"""LLM Service for tender requirement extraction and intelligence analysis."""

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
    from backend.app.ai.prompts import TENDER_EXTRACTION_PROMPT
    from backend.app.models.tender import TenderAnalysisResult
except ImportError:
    try:
        from app.ai.prompts import TENDER_EXTRACTION_PROMPT
        from app.models.tender import TenderAnalysisResult
    except ImportError:
        from prompts import TENDER_EXTRACTION_PROMPT
        from models.tender import TenderAnalysisResult

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger(__name__)

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)


def _normalize_category(cat: str) -> str:
    """Normalizes extracted category strings to valid TenderRequirement categories."""
    if not cat:
        return "EXPERIENCE"
    cat_upper = cat.strip().upper()
    if "GST" in cat_upper:
        return "GST"
    elif "OEM" in cat_upper or "AUTH" in cat_upper or "MANUFACTURER" in cat_upper:
        return "OEM_AUTH"
    elif "LOCAL" in cat_upper or "CONTENT" in cat_upper or "MII" in cat_upper:
        return "LOCAL_CONTENT"
    else:
        return "EXPERIENCE"


async def analyze_tender_with_llm(text: str) -> TenderAnalysisResult:
    """Analyzes raw tender document text using Gemini LLM and returns a validated TenderAnalysisResult.

    Args:
        text (str): Raw extracted text from the tender document.

    Returns:
        TenderAnalysisResult: A validated Pydantic model representing the extracted requirements.

    Raises:
        HTTPException: If AI output fails schema validation (500) or if generation fails.
    """
    if not text or not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Input tender text is empty.",
        )

    # Ensure API key is configured
    current_key = os.getenv("GEMINI_API_KEY")
    if current_key:
        genai.configure(api_key=current_key)

    prompt = (
        f"{TENDER_EXTRACTION_PROMPT}\n\n"
        "### Raw Tender Document Content:\n"
        f"{text}"
    )

    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.1,
    }

    # Candidate models with automatic fallback
    candidate_models = ["gemini-1.5-flash", "gemini-3.6-flash", "gemini-2.5-flash"]
    last_error = None
    parsed_dict: Dict[str, Any] = {}

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

            # Prepare dictionary for TenderAnalysisResult validation
            if isinstance(raw_json, list):
                parsed_dict = {
                    "tender_id": "TENDER-AUTO-001",
                    "requirements": raw_json,
                }
            elif isinstance(raw_json, dict):
                parsed_dict = raw_json
                if "tender_id" not in parsed_dict or not parsed_dict["tender_id"]:
                    parsed_dict["tender_id"] = "TENDER-AUTO-001"
                if "requirements" not in parsed_dict:
                    if "data" in parsed_dict and isinstance(parsed_dict["data"], list):
                        parsed_dict["requirements"] = parsed_dict.pop("data")
                    else:
                        parsed_dict["requirements"] = []
            else:
                parsed_dict = {
                    "tender_id": "TENDER-AUTO-001",
                    "requirements": [],
                }

            # Normalize categories within requirements
            if "requirements" in parsed_dict and isinstance(parsed_dict["requirements"], list):
                for req in parsed_dict["requirements"]:
                    if isinstance(req, dict) and "category" in req:
                        req["category"] = _normalize_category(str(req["category"]))

            # Validate against TenderAnalysisResult Pydantic schema
            try:
                validated_result = TenderAnalysisResult(**parsed_dict)
                return validated_result
            except ValidationError as val_err:
                logger.error("Pydantic schema validation error on AI output: %s", val_err)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="AI output failed schema validation",
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
                logger.error("Gemini API error during tender analysis: %s", err)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Gemini API generation error: {str(err)}",
                ) from err

    logger.error("All Gemini candidate models failed: %s", last_error)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Failed to analyze tender with AI: {str(last_error)}",
    )


if __name__ == "__main__":
    import asyncio

    sample_tender_text = """
    TENDER NOTICE: SUPPLY OF NETWORKING HARDWARE (GeM Bid No: GEM/2026/B/88219)
    1. The bidder must possess a valid GST Registration Certificate. Submit GSTIN and latest 3 months GSTR-3B filings.
    2. OEM Authorization (MAF): The bidder must be an authorized partner of the OEM and submit OEM Authorization Form.
    3. Minimum 50% Local Content is required under Make in India (Class-I Local Supplier). Submit self-declaration.
    4. Past Experience: Bidder must have successfully executed 3 similar contracts in the last 3 financial years.
    """

    print("Testing analyze_tender_with_llm returning validated TenderAnalysisResult...")
    result = asyncio.run(analyze_tender_with_llm(sample_tender_text))
    print(f"Validated Model Type: {type(result)}")
    print(f"Tender ID: {result.tender_id}")
    print(f"Extracted Requirements Count: {len(result.requirements)}")
    for r in result.requirements:
        print(f" - [{r.requirement_id}] {r.category}: {r.description} (Mandatory: {r.mandatory})")
