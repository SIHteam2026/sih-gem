from pathlib import Path
import os
from typing import Optional
from dotenv import find_dotenv, load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Load environment variables from nearest .env file
load_dotenv(find_dotenv(usecwd=True))


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


def extract_gst_fields(raw_text: str, model: str = "gemini-3.6-flash") -> dict:
    """
    Extracts GST fields from raw text using the Gemini model
    and enforces the GSTClaim response schema.

    Args:
        raw_text: Unstructured raw text containing GST details.
        model: Gemini model identifier (defaults to "gemini-3.6-flash").

    Returns:
        A dictionary containing the extracted fields: 'gstin', 'legal_name', and 'status'.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key) if api_key else genai.Client()

    prompt = (
        "Extract the GST identification number (gstin), legal business name (legal_name), "
        "and status (status) from the following text:\n\n"
        f"{raw_text}"
    )

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=GSTClaim,
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
    except Exception as e:
        # Fallback to gemini-3.6-flash if deprecated model like gemini-2.5-flash is passed
        if model != "gemini-3.6-flash" and ("no longer available" in str(e) or "404" in str(e)):
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=config,
            )
        else:
            raise e

    if response.parsed:
        if isinstance(response.parsed, GSTClaim):
            return response.parsed.model_dump()
        if isinstance(response.parsed, dict):
            return response.parsed

    if response.text:
        validated = GSTClaim.model_validate_json(response.text)
        return validated.model_dump()

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

