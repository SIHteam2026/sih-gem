"""Deterministic Regex & Policy Validators for Indian Identity and Business Documents."""

from datetime import date, datetime
import re
from typing import Any, Dict, List, Optional

try:
    from app.rules.debarment import is_entity_blacklisted
except ImportError:
    from rules.debarment import is_entity_blacklisted

# Standard Indian Document Regex Patterns
PAN_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
GSTIN_REGEX = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b", re.IGNORECASE)


def _parse_date(date_str: str) -> Optional[date]:
    """Attempts to parse a date string across various common formats."""
    if not date_str:
        return None
    clean = date_str.strip()
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%Y/%m/%d",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%B %d, %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    return None


def verify_past_performance(turnover: float, required_turnover: float) -> dict:
    """Verifies that a bidder's declared average annual turnover meets the mandatory
    public procurement minimum threshold (at least 40% of the required tender threshold / value).

    Args:
        turnover (float): Bidder's declared annual or average turnover in INR.
        required_turnover (float): Official tender required turnover threshold in INR.

    Returns:
        Dict containing:
            - is_valid (bool): True if turnover >= 40% of required_turnover, False otherwise.
            - actual_turnover (float): Bidder's declared turnover.
            - required_turnover (float): Benchmark required turnover.
            - threshold_amount (float): 40% of required turnover (minimum allowable).
            - shortfall_amount (float): Difference if turnover is below 40% threshold (0.0 if valid).
            - validation_errors (List[str]): List of error descriptions if verification fails.
    """
    validation_errors: List[str] = []
    actual = float(turnover or 0.0)
    required = float(required_turnover or 0.0)
    threshold_min = 0.40 * required

    if required <= 0:
        return {
            "is_valid": True,
            "actual_turnover": actual,
            "required_turnover": required,
            "threshold_amount": 0.0,
            "shortfall_amount": 0.0,
            "validation_errors": [],
        }

    if actual < threshold_min:
        shortfall = threshold_min - actual
        percent_achieved = (actual / required) * 100.0 if required > 0 else 0.0
        validation_errors.append(
            f"Financial Turnover Deficit: Declared turnover (Rs. {actual:,.2f}) is below the mandatory 40% tender threshold "
            f"(Rs. {threshold_min:,.2f} required for baseline eligibility; achieved {percent_achieved:.1f}%)."
        )
        return {
            "is_valid": False,
            "actual_turnover": actual,
            "required_turnover": required,
            "threshold_amount": threshold_min,
            "shortfall_amount": shortfall,
            "validation_errors": validation_errors,
        }

    return {
        "is_valid": True,
        "actual_turnover": actual,
        "required_turnover": required,
        "threshold_amount": threshold_min,
        "shortfall_amount": 0.0,
        "validation_errors": [],
    }


async def run_deterministic_checks(
    document_type: str,
    extracted_text: str,
    entity_id: Optional[str] = None,
    expiry_date_str: Optional[str] = None,
    turnover: Optional[float] = None,
    required_turnover: Optional[float] = None,
) -> dict:
    """Executes deterministic regex, debarment, expiration, and financial threshold checks.

    Args:
        document_type (str): Type of document (e.g., 'PAN_CARD', 'GST_CERTIFICATE').
        extracted_text (str): Raw text extracted from document parser/OCR.
        entity_id (Optional[str]): PAN, GSTIN, or vendor identifier to check against debarment database.
        expiry_date_str (Optional[str]): Document expiry date string to validate against current date.
        turnover (Optional[float]): Bidder's declared annual turnover.
        required_turnover (Optional[float]): Required tender turnover threshold.

    Returns:
        Dict containing:
            - is_valid (bool): True if document passes all deterministic checks, False otherwise.
            - validation_errors (List[str]): List of error messages if validation fails.
            - financial_check (Optional[dict]): Result of past performance financial evaluation.
    """
    validation_errors: List[str] = []
    text = str(extracted_text or "").strip()
    doc_type = str(document_type or "").strip().upper()

    # 1. Debarment / Blacklist Check
    if entity_id:
        if is_entity_blacklisted(entity_id):
            validation_errors.append("CRITICAL: Vendor is on central debarment list")

    # 2. Expiry Date Check
    if expiry_date_str:
        parsed_date = _parse_date(expiry_date_str)
        if parsed_date:
            today = date.today()
            if parsed_date < today:
                validation_errors.append("Document has expired")

    # 3. Financial Past Performance / Turnover Threshold Check
    financial_check_result: Optional[dict] = None
    if turnover is not None and required_turnover is not None:
        financial_check_result = verify_past_performance(turnover, required_turnover)
        if not financial_check_result["is_valid"]:
            validation_errors.extend(financial_check_result["validation_errors"])

    # 4. Document Text & Regex Format Checks
    if not text:
        validation_errors.append("Extracted text is empty or missing.")
    elif doc_type == "PAN_CARD":
        # PAN format: 5 letters, 4 numbers, 1 letter (e.g. ABCDE1234F)
        matches = PAN_REGEX.findall(text)
        if not matches:
            validation_errors.append(
                "No valid PAN found in document text. Expected 10-character format (5 letters, 4 numbers, 1 letter, e.g., ABCDE1234F)."
            )

    elif doc_type == "GST_CERTIFICATE":
        # GSTIN format: 15 characters (2 digit state code + 10 char PAN + 1 entity code + 'Z' + 1 check digit)
        matches = GSTIN_REGEX.findall(text)
        if not matches:
            validation_errors.append(
                "No valid 15-character GSTIN found in document text. Expected format: 2 numbers, 5 letters, 4 numbers, 1 letter, 1 alphanumeric, 'Z', 1 alphanumeric (e.g., 27AABCU9603R1ZN)."
            )

    elif doc_type and doc_type != "TURNOVER_CERTIFICATE":
        validation_errors.append(
            f"Unsupported document type '{document_type}' for deterministic regex checks. Supported types: 'PAN_CARD', 'GST_CERTIFICATE', 'TURNOVER_CERTIFICATE'."
        )

    is_valid = len(validation_errors) == 0

    return {
        "is_valid": is_valid,
        "validation_errors": validation_errors,
        "financial_check": financial_check_result,
    }
