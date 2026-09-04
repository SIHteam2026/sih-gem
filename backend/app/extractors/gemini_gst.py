import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, Field

# Ensure project root and backend paths are available for imports
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent.parent
_root_dir = _backend_dir.parent
for _p in [str(_root_dir), str(_backend_dir), str(_current_file.parent.parent)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from backend.app.services.ai_router import ai_router
except ImportError:
    try:
        from app.services.ai_router import ai_router
    except ImportError:
        from services.ai_router import ai_router

# Load environment variables from nearest .env file
load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger(__name__)


class GSTClaim(BaseModel):
    gstin: Optional[str] = Field(
        default=None,
        description="Goods and Services Tax Identification Number (GSTIN).",
    )
    legal_name: Optional[str] = Field(
        default=None,
        description="Legal business name or trade name of the taxpayer.",
    )
    status: Optional[str] = Field(
        default=None,
        description="Status of the GST registration or claim (e.g. Active, Inactive, Cancelled).",
    )
    total_amount: Optional[str] = Field(
        default=None,
        description="Total invoice or claim amount in rupees if present (e.g. 118000.00).",
    )


async def extract_gst_fields_async(raw_text: str) -> dict:
    """Extracts GST fields from raw text using Groq AI router and enforces the GSTClaim response schema."""
    prompt = (
        "Extract the GST identification number (gstin), legal business name (legal_name), "
        "status (status), and total invoice/claim amount (total_amount) from the following text in JSON format:\n\n"
        f"{raw_text}"
    )

    try:
        parsed_dict = await ai_router.generate_json(prompt=prompt, temperature=0.1)
        if isinstance(parsed_dict, list) and len(parsed_dict) > 0:
            parsed_dict = parsed_dict[0]
        elif not isinstance(parsed_dict, dict):
            parsed_dict = {}

        validated = GSTClaim(**parsed_dict)
        return validated.model_dump()
    except Exception as e:
        logger.error("Error in extract_gst_fields_async: %s", e)
        return GSTClaim().model_dump()


def extract_gst_fields(raw_text: str, model: Optional[str] = None) -> dict:
    """Extracts GST fields from raw text using Groq AI router synchronously and enforces the GSTClaim response schema.

    Args:
        raw_text: Unstructured raw text containing GST details.
        model: Model identifier override (optional).

    Returns:
        A dictionary containing the extracted fields: 'gstin', 'legal_name', 'status', and 'total_amount'.
    """
    prompt = (
        "Extract the GST identification number (gstin), legal business name (legal_name), "
        "status (status), and total invoice/claim amount (total_amount) from the following text in JSON format:\n\n"
        f"{raw_text}"
    )

    try:
        parsed_dict = ai_router.generate_json_sync(prompt=prompt, temperature=0.1)
        if isinstance(parsed_dict, list) and len(parsed_dict) > 0:
            parsed_dict = parsed_dict[0]
        elif not isinstance(parsed_dict, dict):
            parsed_dict = {}

        validated = GSTClaim(**parsed_dict)
        return validated.model_dump()
    except Exception as e:
        logger.error("Error in extract_gst_fields: %s", e)
        return GSTClaim().model_dump()


if __name__ == "__main__":
    sample_text = """
    Taxpayer Details Verification:
    GSTIN / UIN: 27AABCU9603R1ZN
    Legal Name of Business: TATA CONSULTANCY SERVICES LIMITED
    Trade Name: TATA CONSULTANCY SERVICES
    Registration Date: 01/07/2017
    Status: Active
    Taxpayer Type: Regular
    """
    print("Testing extract_gst_fields with sample input...")
    result = extract_gst_fields(sample_text)
    print("Extracted dictionary:")
    print(result)
