"""Deterministic Regex & Policy Validators for Indian Identity and Business Documents."""

from datetime import date, datetime
import re
from typing import Any, Dict, List, Optional

try:
    from backend.app.rules.debarment import is_entity_blacklisted
except ImportError:
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


async def run_deterministic_checks(
    document_type: str,
    extracted_text: str,
    entity_id: Optional[str] = None,
    expiry_date_str: Optional[str] = None,
) -> dict:
    """Executes deterministic regex, debarment, and expiration checks on document data.

    Args:
        document_type (str): Type of document (e.g., 'PAN_CARD', 'GST_CERTIFICATE').
        extracted_text (str): Raw text extracted from document parser/OCR.
        entity_id (Optional[str]): PAN, GSTIN, or vendor identifier to check against debarment database.
        expiry_date_str (Optional[str]): Document expiry date string to validate against current date.

    Returns:
        Dict containing:
            - is_valid (bool): True if document passes all deterministic checks, False otherwise.
            - validation_errors (List[str]): List of error messages if validation fails.
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

    # 3. Document Text & Regex Format Checks
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

    elif doc_type:
        validation_errors.append(
            f"Unsupported document type '{document_type}' for deterministic regex checks. Supported types: 'PAN_CARD', 'GST_CERTIFICATE'."
        )

    is_valid = len(validation_errors) == 0

    return {
        "is_valid": is_valid,
        "validation_errors": validation_errors,
    }
