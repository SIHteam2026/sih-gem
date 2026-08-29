"""LLM Service for tender requirement extraction and intelligence analysis."""

import json
import logging
import os
from typing import Any, Dict
from dotenv import find_dotenv, load_dotenv
import google.generativeai as genai

try:
    from backend.app.ai.prompts import TENDER_EXTRACTION_PROMPT
except ImportError:
    try:
        from app.ai.prompts import TENDER_EXTRACTION_PROMPT
    except ImportError:
        from prompts import TENDER_EXTRACTION_PROMPT

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger(__name__)

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)


async def analyze_tender_with_llm(text: str) -> dict:
    """Analyzes raw tender document text using Gemini LLM and extracts structured requirements.

    Args:
        text (str): Raw extracted text from the tender document.

    Returns:
        dict: A dictionary containing the extracted requirements list and status metadata.
    """
    if not text or not text.strip():
        return {
            "status": "EMPTY_INPUT",
            "requirements": [],
            "error": "Input tender text is empty.",
        }

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

    # Attempt with requested model, with automatic fallback for deprecated models
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

            parsed_data = json.loads(response.text.strip())

            # Normalize to dictionary output
            if isinstance(parsed_data, list):
                return {
                    "status": "SUCCESS",
                    "model_used": model_name,
                    "count": len(parsed_data),
                    "requirements": parsed_data,
                }
            elif isinstance(parsed_data, dict):
                if "requirements" not in parsed_data:
                    parsed_data["status"] = "SUCCESS"
                    parsed_data["model_used"] = model_name
                return parsed_data
            else:
                return {
                    "status": "SUCCESS",
                    "model_used": model_name,
                    "requirements": [parsed_data],
                }

        except Exception as err:
            last_error = err
            err_str = str(err)
            # If model is deprecated or not found, try the next candidate model
            if "not found" in err_str.lower() or "no longer available" in err_str.lower() or "404" in err_str:
                logger.warning(
                    "Model %s unavailable (%s). Trying fallback candidate...",
                    model_name,
                    err_str,
                )
                continue
            else:
                logger.error("Gemini API error during tender analysis: %s", err)
                return {
                    "status": "ERROR",
                    "requirements": [],
                    "error": str(err),
                }

    logger.error("All Gemini candidate models failed: %s", last_error)
    return {
        "status": "ERROR",
        "requirements": [],
        "error": f"Failed to extract tender requirements: {str(last_error)}",
    }


if __name__ == "__main__":
    import asyncio

    sample_tender_text = """
    TENDER NOTICE: SUPPLY OF NETWORKING HARDWARE (GeM Bid No: GEM/2026/B/88219)
    1. The bidder must possess a valid GST Registration Certificate. Submit GSTIN and latest 3 months GSTR-3B filings.
    2. OEM Authorization (MAF): The bidder must be an authorized partner of the OEM and submit OEM Authorization Form.
    3. Minimum 50% Local Content is required under Make in India (Class-I Local Supplier). Submit self-declaration.
    4. Average annual turnover of the bidder during the last 3 financial years must be at least Rs. 50 Lakhs (CA Certificate required).
    """

    print("Testing analyze_tender_with_llm...")
    result = asyncio.run(analyze_tender_with_llm(sample_tender_text))
    print("Result:")
    print(json.dumps(result, indent=2))
