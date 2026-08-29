"""PDF Parser Service.

Provides asynchronous utility for extracting raw text from PDF document bytes using PyMuPDF (fitz)
with intelligent OCR fallback for scanned or image-based PDF documents.
"""

import logging
import re
from fastapi import HTTPException
import fitz  # PyMuPDF

try:
    from backend.app.services.ocr_service import extract_text_with_ocr
except ImportError:
    from app.services.ocr_service import extract_text_with_ocr

logger = logging.getLogger(__name__)


async def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Loads PDF bytes into a fitz.Document, iterates through all pages,
    cleans whitespace, and automatically falls back to OCR if digital text is insufficient.

    Args:
        file_bytes (bytes): The raw byte content of the PDF file.

    Returns:
        str: Cleaned text extracted across all pages.

    Raises:
        HTTPException: If no readable text is found in the PDF via both direct extraction and OCR (400 Bad Request).
    """
    text_chunks: list[str] = []
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                page_text = page.get_text()
                if page_text:
                    text_chunks.append(page_text)
    except Exception as parse_err:
        logger.warning("PyMuPDF direct parsing encountered an issue: %s. Attempting OCR fallback.", parse_err)

    raw_text = "\n".join(text_chunks)
    cleaned_text = re.sub(r"\n+", "\n", raw_text).strip()

    # Smart OCR Fallback: If cleaned text length is under 50 characters
    if len(cleaned_text) < 50:
        logger.warning(
            "Extracted text length is under 50 characters (%d chars). Falling back to OCR extraction.",
            len(cleaned_text),
        )
        try:
            ocr_text = await extract_text_with_ocr(file_bytes)
            if ocr_text and ocr_text.strip():
                cleaned_text = ocr_text.strip()
        except Exception as ocr_err:
            logger.error("OCR fallback extraction failed: %s", ocr_err)

    if not cleaned_text:
        raise HTTPException(
            status_code=400,
            detail="No readable text found in the PDF. Please upload a searchable document.",
        )

    return cleaned_text
