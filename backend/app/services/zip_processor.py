"""ZIP Processing Service for Multi-Document Bidder Submissions.

Provides asynchronous in-memory extraction, parsing, and classification
of all PDF documents bundled within a bidder'\''s ZIP archive.
"""

import io
import logging
from pathlib import Path
from typing import Any, Dict, List
import zipfile
from fastapi import HTTPException, status

try:
    from backend.app.services.pdf_parser import extract_text_from_pdf
    from backend.app.services.document_classifier import classify_document
    from backend.app.models.document import DocumentClassificationResult
except ImportError:
    from app.services.pdf_parser import extract_text_from_pdf
    from app.services.document_classifier import classify_document
    from app.models.document import DocumentClassificationResult

logger = logging.getLogger(__name__)


async def process_bidder_zip(zip_bytes: bytes) -> List[Dict[str, Any]]:
    """Opens an in-memory ZIP file, iterates through all PDF files,
    extracts text, and classifies each document.

    Args:
        zip_bytes (bytes): The raw byte content of the uploaded ZIP file.

    Returns:
        list[dict]: A list of dictionaries containing:
            - "filename" (str): Name of the PDF file.
            - "classification_result" (DocumentClassificationResult): Document classification result.
            - "extracted_text_preview" (str): Preview snippet of extracted text.

    Raises:
        HTTPException: If the ZIP file is corrupted, empty, or contains no PDF files.
    """
    if not zip_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded ZIP file is empty.",
        )

    try:
        zip_buffer = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(zip_buffer, "r") as archive:
            pdf_entries = [
                name for name in archive.namelist()
                if name.lower().endswith(".pdf") and not name.startswith("__MACOSX/") and not Path(name).name.startswith("._")
            ]

            if not pdf_entries:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No PDF documents found in the uploaded ZIP archive.",
                )

            results: List[Dict[str, Any]] = []

            for entry in pdf_entries:
                clean_filename = Path(entry).name
                try:
                    file_bytes = archive.read(entry)
                    extracted_text = await extract_text_from_pdf(file_bytes)
                    classification = classify_document(extracted_text)
                    preview = (
                        extracted_text[:300] + ("..." if len(extracted_text) > 300 else "")
                        if extracted_text
                        else ""
                    )

                    results.append({
                        "filename": clean_filename,
                        "classification_result": classification,
                        "extracted_text_preview": preview,
                    })
                except HTTPException as http_err:
                    logger.warning("HTTP error parsing %s in ZIP: %s", clean_filename, http_err.detail)
                    results.append({
                        "filename": clean_filename,
                        "classification_result": classify_document(""),
                        "extracted_text_preview": f"Error: {http_err.detail}",
                    })
                except Exception as doc_err:
                    logger.error("Failed to process %s in ZIP: %s", clean_filename, doc_err)
                    results.append({
                        "filename": clean_filename,
                        "classification_result": classify_document(""),
                        "extracted_text_preview": f"Processing error: {str(doc_err)}",
                    })

            return results

    except zipfile.BadZipFile as e:
        logger.error("Corrupted ZIP file uploaded: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrupted or invalid ZIP archive. Please upload a valid .zip file.",
        ) from e
    except HTTPException:
        raise
    except Exception as general_err:
        logger.error("Unexpected error processing ZIP archive: %s", general_err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process ZIP archive: {str(general_err)}",
        ) from general_err
