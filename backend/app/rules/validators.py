"""Deterministic Regex Validators for Indian Identity and Business Documents."""

import re
from typing import Any, Dict, List

# Standard Indian Document Regex Patterns
PAN_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
GSTIN_REGEX = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b", re.IGNORECASE)


async def run_deterministic_checks(document_type: str, extracted_text: str) -> dict:
    """
    Executes deterministic regex checks on extracted document text.

    Args:
        document_type: Type of document (e.g., 'PAN_CARD', 'GST_CERTIFICATE').
        extracted_text: Raw text extracted from document parser/OCR.

    Returns:
        Dict containing:
            - is_valid (bool): True if document passes deterministic regex validation, False otherwise.
            - validation_errors (List[str]): List of error messages if validation fails.
    """
    validation_errors: List[str] = []
    text = str(extracted_text or "").strip()
    doc_type = str(document_type or "").strip().upper()

    if not text:
        return {
            "is_valid": False,
            "validation_errors": ["Extracted text is empty or missing."],
        }

    if doc_type == "PAN_CARD":
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

    else:
        validation_errors.append(
            f"Unsupported document type '{document_type}' for deterministic regex checks. Supported types: 'PAN_CARD', 'GST_CERTIFICATE'."
        )

    is_valid = len(validation_errors) == 0

    return {
        "is_valid": is_valid,
        "validation_errors": validation_errors,
    }
