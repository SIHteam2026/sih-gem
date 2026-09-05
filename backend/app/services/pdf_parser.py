"""PDF Parser Service.

Provides asynchronous utility for extracting raw and page-aware text from PDF document bytes using PyMuPDF
with intelligent OCR fallback for scanned or image-based PDF documents and PII redaction.
"""

import logging
import re
from typing import Any, Dict, List
from fastapi import HTTPException
try:
    import pymupdf
except Exception:
    pymupdf = None

try:
    from app.services.ocr_service import extract_text_with_ocr
    from app.services.redaction_service import redact_sensitive_data
except ImportError:
    from app.services.ocr_service import extract_text_with_ocr
    from app.services.redaction_service import redact_sensitive_data

logger = logging.getLogger(__name__)


async def extract_pages_from_pdf(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Loads PDF bytes into a pymupdf.Document and extracts text on a per-page basis,
    preserving exact 1-indexed page boundaries for audit trail and source provenance.

    Args:
        file_bytes (bytes): The raw byte content of the PDF file.

    Returns:
        List[Dict[str, Any]]: List of page dicts with 1-indexed page number and sanitized text:
            [{"page": 1, "text": "..."}, {"page": 2, "text": "..."}]

    Raises:
        HTTPException: If no readable text is found across all pages.
    """
    pages: List[Dict[str, Any]] = []
    total_text_len = 0

    try:
        with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
            for page_idx, page in enumerate(doc, start=1):
                page_raw = page.get_text() or ""
                # Clean whitespace per page
                cleaned = re.sub(r"[ \t]+", " ", page_raw)
                cleaned = re.sub(r"^[ \t]+|[ \t]+$", "", cleaned, flags=re.MULTILINE)
                cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

                if cleaned:
                    # Redact sensitive PII per page
                    sanitized = await redact_sensitive_data(cleaned)
                else:
                    sanitized = ""

                pages.append({
                    "page": page_idx,
                    "text": sanitized,
                    "char_count": len(sanitized),
                })
                total_text_len += len(sanitized)
    except Exception as parse_err:
        logger.warning("PyMuPDF direct per-page parsing encountered an issue: %s. Attempting OCR fallback.", parse_err)

    # Smart OCR Fallback: If total extracted text is under 50 characters, use OCR
    if total_text_len < 50:
        logger.warning(
            "Extracted per-page text total is under 50 characters (%d chars). Falling back to OCR extraction.",
            total_text_len,
        )
        try:
            ocr_text = await extract_text_with_ocr(file_bytes)
            if ocr_text and ocr_text.strip():
                sanitized_ocr = await redact_sensitive_data(ocr_text.strip())
                pages = [{
                    "page": 1,
                    "text": sanitized_ocr,
                    "char_count": len(sanitized_ocr),
                }]
                total_text_len = len(sanitized_ocr)
        except Exception as ocr_err:
            logger.error("OCR fallback extraction failed: %s", ocr_err)

    if total_text_len == 0 or not pages:
        raise HTTPException(
            status_code=400,
            detail="No readable text found in the PDF. Please upload a searchable document.",
        )

    return pages


async def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Loads PDF bytes, extracts text across all pages, cleans whitespace,
    falls back to OCR if digital text is insufficient, and redacts sensitive PII.
    Maintained for backward compatibility.

    Args:
        file_bytes (bytes): The raw byte content of the PDF file.

    Returns:
        str: Fully sanitized and redacted text extracted across all pages.
    """
    pages = await extract_pages_from_pdf(file_bytes)
    return "\n\n".join(p["text"] for p in pages if p.get("text"))

