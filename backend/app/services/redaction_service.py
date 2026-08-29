"""Sensitive PII Redaction Service.

Provides asynchronous regex-based sanitization and redaction for sensitive
Indian identification numbers (Aadhaar, PAN) and contact phone numbers.
"""

import re
from typing import Optional

# Regex patterns for sensitive identifiers
AADHAAR_PATTERN = re.compile(r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b")
PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b")


async def redact_sensitive_data(text: str) -> str:
    """Sanitizes text by masking Aadhaar numbers, PAN card numbers, and 10-digit phone numbers.

    Args:
        text (str): The raw text to sanitize.

    Returns:
        str: The sanitized text with sensitive PII replaced by '[REDACTED]'.
    """
    if not text:
        return ""

    sanitized = text

    # 1. Redact Aadhaar numbers (12 digits, with optional spaces/hyphens)
    sanitized = AADHAAR_PATTERN.sub("[REDACTED]", sanitized)

    # 2. Redact PAN card numbers ([A-Z]{5}[0-9]{4}[A-Z]{1})
    sanitized = PAN_PATTERN.sub("[REDACTED]", sanitized)

    # 3. Redact 10-digit phone numbers (with optional +91 prefix)
    sanitized = PHONE_PATTERN.sub("[REDACTED]", sanitized)

    return sanitized
