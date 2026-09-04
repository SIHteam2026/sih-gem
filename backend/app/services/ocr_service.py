"""OCR Text Extraction Service for Scanned Bidder Documents.

Provides optical character recognition (OCR) capabilities using pdf2image and pytesseract
to extract text from scanned, image-only, or legacy physical PDF submissions.
"""

import asyncio
import io
import logging
import os
import re
try:
    from pdf2image import convert_from_bytes
except Exception:
    convert_from_bytes = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import fitz
except Exception:
    try:
        import pymupdf as fitz
    except Exception:
        fitz = None

try:
    import pytesseract
except Exception:
    pytesseract = None

logger = logging.getLogger(__name__)

# Optional: Auto-detect standard Tesseract binary locations on Windows if not already in PATH
if os.name == "nt":
    possible_tesseract_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for t_path in possible_tesseract_paths:
        if os.path.exists(t_path):
            pytesseract.pytesseract.tesseract_cmd = t_path
            break


def _process_ocr(file_bytes: bytes) -> str:
    """Converts PDF bytes to PIL images and extracts text using Tesseract OCR."""
    if not file_bytes:
        return ""

    images: list[Image.Image] = []

    # Attempt 1: Use pdf2image
    try:
        images = convert_from_bytes(file_bytes)
    except Exception as conv_err:
        logger.warning(
            "pdf2image conversion failed (%s), falling back to PyMuPDF pixmap rendering.",
            conv_err,
        )
        # Attempt 2: PyMuPDF pixmap rendering fallback
        try:
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    pix = page.get_pixmap(dpi=200)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    images.append(img)
        except Exception as fitz_err:
            logger.error("Failed to render PDF pages with PyMuPDF: %s", fitz_err)
            raise

    extracted_pages: list[str] = []
    for page_idx, image in enumerate(images, start=1):
        try:
            page_text = pytesseract.image_to_string(image)
            if page_text and page_text.strip():
                extracted_pages.append(page_text.strip())
        except Exception as ocr_err:
            logger.warning("OCR failed on page %d: %s", page_idx, ocr_err)

    raw_text = "\n\n".join(extracted_pages)
    cleaned_text = re.sub(r"[ \t]+", " ", raw_text)
    cleaned_text = re.sub(r"^[ \t]+|[ \t]+$", "", cleaned_text, flags=re.MULTILINE)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()
    return cleaned_text


async def extract_text_with_ocr(file_bytes: bytes) -> str:
    """Asynchronously extracts text from a PDF document using OCR.

    Converts the PDF into a list of PIL images using pdf2image.convert_from_bytes,
    iterates through each image, extracts text via pytesseract.image_to_string(),
    and concatenates the results into a single cleaned string.

    Args:
        file_bytes (bytes): Raw byte content of the PDF file.

    Returns:
        str: Concatenated, cleaned text extracted across all pages.
    """
    if not file_bytes:
        return ""

    return await asyncio.to_thread(_process_ocr, file_bytes)
