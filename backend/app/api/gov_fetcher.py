"""External GSP / Government Portal GSTIN Verification via Sandbox API."""

import logging
import os
from typing import Any, Dict, Optional
from dotenv import find_dotenv, load_dotenv

from app.services.government_provider import SandboxGovProvider
from app.config.sandbox_settings import SandboxSettings

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger(__name__)

async def verify_gstin_external(gstin: Optional[str]) -> Dict[str, Any]:
    """Verifies a GSTIN against the official Sandbox GST public verification API.

    This legacy function is maintained for compatibility but now delegates to the
    centralized SandboxGovProvider.

    Args:
        gstin (str): The 15-character GST identification number.

    Returns:
        dict: Legacy normalized GST details containing legal_name, status, gstin, and raw_data.
    """
    cleaned_gstin = (gstin or "").strip().upper()
    if not cleaned_gstin:
        return {
            "gstin": None,
            "legal_name": None,
            "status": "INVALID_INPUT",
            "error": "GSTIN is missing or empty",
        }

    # Use the provider
    try:
        provider = SandboxGovProvider()
        result = await provider.verify_gstin(cleaned_gstin)

        if result.outcome == "NOT_CONFIGURED":
            # For backward compatibility
            return {
                "gstin": cleaned_gstin,
                "legal_name": None,
                "status": "ERROR",
                "error": "Sandbox API key not configured",
            }
        
        if result.outcome == "VERIFIED" or result.outcome == "INVALID":
            # Success response parsing
            raw_data = result.raw_data or {}
            legal_name = (
                raw_data.get("legalName")
                or raw_data.get("legal_name")
                or raw_data.get("lgnm")
                or raw_data.get("tradeName")
            )
            return {
                "gstin": cleaned_gstin,
                "legal_name": legal_name,
                "status": result.status.capitalize() if result.status else "Unknown",
                "trade_name": raw_data.get("tradeName") or raw_data.get("trade_name"),
                "raw_data": raw_data,
            }
        
        # Error outcomes
        if result.outcome == "NOT_FOUND":
            return {
                "gstin": cleaned_gstin,
                "legal_name": None,
                "status": "NOT_FOUND",
                "error": result.reason,
            }
        
        return {
            "gstin": cleaned_gstin,
            "legal_name": None,
            "status": "ERROR",
            "error": result.reason,
        }

    except Exception as exc:
        logger.error("Unexpected error delegating to Sandbox provider: %s", exc)
        return {
            "gstin": cleaned_gstin,
            "legal_name": None,
            "status": "ERROR",
            "error": str(exc),
        }

async def verify_pan_external(pan: Optional[str], name_as_per_pan: Optional[str] = None, date_of_birth: Optional[str] = None) -> Dict[str, Any]:
    """Verifies a PAN against the official Sandbox PAN public verification API.

    This function delegates to the centralized SandboxGovProvider.

    Args:
        pan (str): The 10-character PAN.
        name_as_per_pan (str): The name as per PAN document.
        date_of_birth (str): The date of birth or incorporation (DD/MM/YYYY).

    Returns:
        dict: Normalized PAN details containing pan, status, and raw_data.
    """
    cleaned_pan = (pan or "").strip().upper()
    if not cleaned_pan:
        return {
            "pan": None,
            "status": "INVALID_INPUT",
            "error": "PAN is missing or empty",
        }

    # Use the provider
    try:
        provider = SandboxGovProvider()
        result = await provider.verify_pan(cleaned_pan, name_as_per_pan=name_as_per_pan, date_of_birth=date_of_birth)

        if result.outcome == "NOT_CONFIGURED":
            return {
                "pan": cleaned_pan,
                "status": "ERROR",
                "error": "Sandbox API key not configured",
            }
        
        if result.outcome == "VERIFIED" or result.outcome == "INVALID":
            # Success response parsing
            return {
                "pan": cleaned_pan,
                "status": result.status.capitalize() if result.status else "Unknown",
                "raw_data": result.raw_data or {},
            }
        
        # Error outcomes
        if result.outcome == "NOT_FOUND":
            return {
                "pan": cleaned_pan,
                "status": "NOT_FOUND",
                "error": result.reason,
            }
        
        return {
            "pan": cleaned_pan,
            "status": "ERROR",
            "error": result.reason,
        }

    except Exception as exc:
        logger.error("Unexpected error delegating to Sandbox provider for PAN: %s", exc)
        return {
            "pan": cleaned_pan,
            "status": "ERROR",
            "error": str(exc),
        }

if __name__ == "__main__":
    import asyncio

    test_gstin = "27AABCU9603R1ZN"
    print(f"Testing Sandbox GST verification for GSTIN: {test_gstin}...")
    # Need to set SANDBOX_BASE_URL to test locally without env
    os.environ.setdefault("SANDBOX_BASE_URL", "https://api.sandbox.co.in")
    res = asyncio.run(verify_gstin_external(test_gstin))
    print(f"Result: {res}")
