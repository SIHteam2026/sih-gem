"""External GSP / Government Portal GSTIN Verification via Sandbox API."""

import logging
import os
from typing import Any, Dict, Optional
from dotenv import find_dotenv, load_dotenv
import httpx

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger(__name__)

SANDBOX_GST_VERIFY_URL = "https://api.sandbox.co.in/gst/compliance/public/gstin/verify"


async def verify_gstin_external(gstin: Optional[str]) -> Dict[str, Any]:
    """Verifies a GSTIN against the official Sandbox GST public verification API.

    Args:
        gstin (str): The 15-character GST identification number.

    Returns:
        dict: Normalized GST details containing legal_name, status, gstin, and raw_data.
    """
    cleaned_gstin = (gstin or "").strip().upper()
    if not cleaned_gstin:
        return {
            "gstin": None,
            "legal_name": None,
            "status": "INVALID_INPUT",
            "error": "GSTIN is missing or empty",
        }

    api_key = os.getenv("SANDBOX_API_KEY", "").strip()

    headers = {
        "x-api-key": api_key,
        "x-api-version": "1.0.0",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {"gstin": cleaned_gstin}

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(
                SANDBOX_GST_VERIFY_URL,
                json=payload,
                headers=headers,
            )

            # If response is non-2xx, handle status code
            if response.is_error:
                logger.error(
                    "Sandbox GST verification returned error %d: %s",
                    response.status_code,
                    response.text,
                )
                return {
                    "gstin": cleaned_gstin,
                    "legal_name": None,
                    "status": "NOT_FOUND" if response.status_code == 404 else "ERROR",
                    "error": f"Sandbox API HTTP {response.status_code}: {response.text}",
                }

            res_json = response.json()

            # Drill down into nested data.data schema
            outer_data = res_json.get("data", {})
            if isinstance(outer_data, dict):
                inner_data = outer_data.get("data", {})
                if not isinstance(inner_data, dict):
                    inner_data = outer_data
            else:
                inner_data = {}

            # Extract and normalize fields
            legal_name = (
                inner_data.get("legalName")
                or inner_data.get("legal_name")
                or inner_data.get("lgnm")
                or inner_data.get("tradeName")
            )
            raw_status = (
                inner_data.get("status")
                or inner_data.get("sts")
                or inner_data.get("gstin_status")
            )

            normalized_status = str(raw_status).strip().capitalize() if raw_status else "Unknown"

            return {
                "gstin": cleaned_gstin,
                "legal_name": legal_name,
                "status": normalized_status,
                "trade_name": inner_data.get("tradeName") or inner_data.get("trade_name"),
                "raw_data": inner_data,
            }

        except httpx.RequestError as req_err:
            logger.error("Network error communicating with Sandbox API: %s", req_err)
            raise req_err
        except Exception as exc:
            logger.error("Unexpected error during Sandbox GST verification: %s", exc)
            return {
                "gstin": cleaned_gstin,
                "legal_name": None,
                "status": "ERROR",
                "error": str(exc),
            }


if __name__ == "__main__":
    import asyncio

    test_gstin = "27AABCU9603R1ZN"
    print(f"Testing Sandbox GST verification for GSTIN: {test_gstin}...")
    res = asyncio.run(verify_gstin_external(test_gstin))
    print(f"Result: {res}")
