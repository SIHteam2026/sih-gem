"""PDF Parser Service.

Provides asynchronous utility for extracting raw text from PDF document bytes using PyMuPDF (fitz).
"""

import re
from fastapi import HTTPException
import fitz  # PyMuPDF


async def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Loads PDF bytes into a fitz.Document, iterates through all pages,
    cleans whitespace, and validates readable text presence.

    Args:
        file_bytes (bytes): The raw byte content of the PDF file.

    Returns:
        str: Cleaned text extracted across all pages.

    Raises:
        HTTPException: If no readable text is found in the PDF (400 Bad Request).
    """
    text_chunks: list[str] = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            page_text = page.get_text()
            if page_text:
                text_chunks.append(page_text)

    raw_text = "\n".join(text_chunks)
    cleaned_text = re.sub(r"\n+", "\n", raw_text).strip()

    if not cleaned_text:
        raise HTTPException(
            status_code=400,
            detail="No readable text found in the PDF. Please upload a searchable document.",
        )

    return cleaned_text
