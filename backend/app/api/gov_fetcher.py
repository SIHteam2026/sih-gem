"""External GSP / Government Portal GSTIN Verification Fetcher.

This module provides asynchronous integration with external GSTIN verification
APIs (e.g., Sandbox.co.in / GSP providers) using httpx.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import find_dotenv, load_dotenv
import httpx

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger(__name__)

SANDBOX_BASE_URL = os.getenv(
    "SANDBOX_GSTIN_URL", "https://api.sandbox.co.in/gsp/public/gstin"
)
SANDBOX_API_KEY = os.getenv("SANDBOX_API_KEY", "your-sandbox-api-key")
SANDBOX_API_VERSION = os.getenv("SANDBOX_API_VERSION", "1.0")
SANDBOX_AUTH_TOKEN = os.getenv("SANDBOX_AUTH_TOKEN", "")


async def verify_gstin_external(gstin: str) -> Dict[str, Any]:
    """Verifies a GSTIN against an external GSP / Government verification API.

    Args:
        gstin (str): The 15-character GSTIN string to verify.

    Returns:
        Dict[str, Any]: Parsed JSON containing at least:
            - "gstin": Normalized GSTIN string
            - "legal_name": Legal business name
            - "status": Registration status (e.g., "Active", "Inactive", "Cancelled")
            - "trade_name": Trade name if available
            - "source": "external_api" or "mock_fallback"
            - "raw_data": Complete raw response from API
    """
    clean_gstin = gstin.strip().upper()
    url = f"{SANDBOX_BASE_URL.rstrip('/')}/{clean_gstin}"

    headers = {
        "Accept": "application/json",
        "x-api-key": SANDBOX_API_KEY,
        "x-api-version": SANDBOX_API_VERSION,
    }
    if SANDBOX_AUTH_TOKEN:
        headers["Authorization"] = SANDBOX_AUTH_TOKEN

    logger.info("Initiating external GSTIN verification for %s via %s", clean_gstin, url)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                payload = response.json()
                data = payload.get("data", payload)

                legal_name = (
                    data.get("lgnm")
                    or data.get("legal_name")
                    or data.get("trade_name")
                    or data.get("tradeNam")
                    or "Unknown Legal Name"
                )
                status = data.get("sts") or data.get("status") or "Active"
                trade_name = data.get("tradeNam") or data.get("trade_name") or legal_name

                return {
                    "gstin": clean_gstin,
                    "legal_name": str(legal_name).strip(),
                    "status": str(status).strip(),
                    "trade_name": str(trade_name).strip(),
                    "is_valid": True,
                    "source": "external_api",
                    "raw_data": payload,
                }
            else:
                logger.warning(
                    "External API returned HTTP %s for GSTIN %s: %s",
                    response.status_code,
                    clean_gstin,
                    response.text,
                )
                return {
                    "gstin": clean_gstin,
                    "legal_name": None,
                    "status": "Unknown",
                    "trade_name": None,
                    "is_valid": False,
                    "source": "external_api",
                    "error": f"External API error HTTP {response.status_code}",
                    "raw_data": response.text,
                }

    except Exception as exc:
        logger.error("Failed to query external GSP API for %s: %s", clean_gstin, exc)
        return {
            "gstin": clean_gstin,
            "legal_name": None,
            "status": "Unavailable",
            "trade_name": None,
            "is_valid": False,
            "source": "error_handler",
            "error": str(exc),
            "raw_data": None,
        }


if __name__ == "__main__":
    import asyncio

    async def main():
        test_gstin = "27AABCU9603R1ZN"
        print(f"Testing verify_gstin_external with {test_gstin}...")
        res = await verify_gstin_external(test_gstin)
        print("Result:")
        print(res)

    asyncio.run(main())
