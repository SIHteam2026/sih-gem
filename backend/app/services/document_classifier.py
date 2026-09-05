"""Deterministic Document Classification Service.

Provides fast, rule-based heuristics to classify tender-related documents
(GST, PAN, Udyam, OEM Authorization, Experience Certificates) and extract key identifiers
without invoking an LLM.
"""

import re
from typing import List
from app.models.document import DocumentCategory, DocumentClassificationResult

# Regex patterns for key identifiers
GSTIN_REGEX = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b")
PAN_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b")
UDYAM_REGEX = re.compile(r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b", re.IGNORECASE)


def classify_document(text: str) -> DocumentClassificationResult:
    """Classifies a document deterministically using keyword heuristics and regex extraction.

    Args:
        text (str): Extracted raw text content of the document.

    Returns:
        DocumentClassificationResult: Classification category, confidence score, and detected key identifiers.
    """
    if not text or not text.strip():
        return DocumentClassificationResult(
            category=DocumentCategory.UNKNOWN,
            confidence=0.0,
            key_identifiers=[],
        )

    text_lower = text.lower()
    key_identifiers: List[str] = []

    # 1. GST Certificate Check
    gst_keywords = [
        "form gst reg-06",
        "goods and services tax",
        "registration certificate",
        "gstin",
        "taxpayer type",
    ]
    matched_gst_keywords = [k for k in gst_keywords if k in text_lower]
    gstins_found = list(dict.fromkeys(GSTIN_REGEX.findall(text)))

    if ("form gst reg-06" in text_lower or "goods and services tax" in text_lower) and (gstins_found or len(matched_gst_keywords) >= 2):
        return DocumentClassificationResult(
            category=DocumentCategory.GST_CERTIFICATE,
            confidence=0.95,
            key_identifiers=gstins_found,
        )

    # 2. Udyam Registration Certificate Check
    udyam_keywords = [
        "udyam registration",
        "udyam registration certificate",
        "ministry of micro, small and medium enterprises",
        "msme-dfa",
    ]
    matched_udyam_keywords = [k for k in udyam_keywords if k in text_lower]
    udyam_found = list(dict.fromkeys(UDYAM_REGEX.findall(text)))

    if matched_udyam_keywords or udyam_found:
        return DocumentClassificationResult(
            category=DocumentCategory.UDYAM_CERTIFICATE,
            confidence=0.95,
            key_identifiers=[u.upper() for u in udyam_found],
        )

    # 3. PAN Card Check
    pan_keywords = [
        "permanent account number",
        "income tax department",
        "govt. of india",
    ]
    matched_pan_keywords = [k for k in pan_keywords if k in text_lower]
    pans_found = list(dict.fromkeys(PAN_REGEX.findall(text)))

    if ("permanent account number" in text_lower or "income tax department" in text_lower) and (pans_found or len(matched_pan_keywords) >= 2):
        return DocumentClassificationResult(
            category=DocumentCategory.PAN_CARD,
            confidence=0.95,
            key_identifiers=pans_found,
        )

    # 4. OEM Authorization Check
    oem_keywords = [
        "manufacturer authorization",
        "manufacturer's authorization",
        "oem authorization",
        "authorization certificate",
        "authorized partner",
        "authorized distributor",
        "maf",
    ]
    matched_oem_keywords = [k for k in oem_keywords if k in text_lower]
    if len(matched_oem_keywords) >= 1:
        return DocumentClassificationResult(
            category=DocumentCategory.OEM_AUTHORIZATION,
            confidence=0.90 if len(matched_oem_keywords) > 1 else 0.85,
            key_identifiers=[],
        )

    # 5. Experience / Work Completion Certificate Check
    exp_keywords = [
        "experience certificate",
        "work experience",
        "completion certificate",
        "work completion certificate",
        "satisfactory performance certificate",
        "to whomsoever it may concern",
    ]
    matched_exp_keywords = [k for k in exp_keywords if k in text_lower]
    if len(matched_exp_keywords) >= 1:
        return DocumentClassificationResult(
            category=DocumentCategory.EXPERIENCE_CERTIFICATE,
            confidence=0.90 if len(matched_exp_keywords) > 1 else 0.85,
            key_identifiers=[],
        )

    # Fallback to UNKNOWN
    return DocumentClassificationResult(
        category=DocumentCategory.UNKNOWN,
        confidence=0.0,
        key_identifiers=[],
    )
