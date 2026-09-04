"""PDF Text Extractor Module.

This module provides functionality to extract text, compute cryptographic hashes,
detect scanned documents, and locate text coordinates from PDF documents using PyMuPDF.
"""

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Union
try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None


def compute_file_hash(file_bytes: bytes) -> str:
    """Generates a SHA-256 checksum for audit and tamper detection.

    Args:
        file_bytes (bytes): The raw bytes of the file.

    Returns:
        str: The hexadecimal SHA-256 checksum.
    """
    return hashlib.sha256(file_bytes).hexdigest()


def extract_text_from_pdf(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Extracts structured text data, page count, SHA-256 hash, and scanned status from a PDF.

    Args:
        file_path (Union[str, Path]): Path to the PDF file to extract text from.

    Returns:
        dict: A dictionary containing:
            - "raw_text" (str): Cleaned text across all pages.
            - "page_count" (int): Total number of pages.
            - "sha256" (str): SHA-256 checksum of the file.
            - "is_scanned" (bool): True if extracted text length is under 30 characters.

    Raises:
        FileNotFoundError: If the specified PDF file does not exist.
        ValueError: If the file is not a valid PDF or fails to parse.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found at: {file_path}")

    file_bytes = path.read_bytes()
    sha256_hash = compute_file_hash(file_bytes)

    text_chunks: List[str] = []

    try:
        with pymupdf.open(path) as doc:
            page_count = len(doc)
            for page in doc:
                page_text = page.get_text()
                if page_text:
                    text_chunks.append(page_text)
    except Exception as e:
        raise ValueError(f"Failed to open or parse PDF '{file_path}': {e}") from e

    raw_text = "\n".join(text_chunks)

    # Clean excessive whitespace:
    # 1. Replace tabs and multiple horizontal spaces with a single space
    cleaned = re.sub(r"[ \t]+", " ", raw_text)
    # 2. Strip leading/trailing horizontal whitespace on each line
    cleaned = re.sub(r"^[ \t]+|[ \t]+$", "", cleaned, flags=re.MULTILINE)
    # 3. Collapse 3+ consecutive newlines down to 2
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    # Determine if document is scanned (under 30 characters of extracted text)
    is_scanned = len(cleaned) < 30

    return {
        "raw_text": cleaned,
        "page_count": page_count,
        "sha256": sha256_hash,
        "is_scanned": is_scanned,
    }


def locate_text_coordinates(file_path: Union[str, Path], keyword: str) -> List[Dict[str, Any]]:
    """Locates occurrences of a keyword within a PDF and returns page numbers and bounding boxes.

    Args:
        file_path (Union[str, Path]): Path to the PDF file.
        keyword (str): The keyword or phrase to search for.

    Returns:
        list[dict]: List of matches, each containing:
            - "page" (int): 1-indexed page number where the keyword was found.
            - "bbox" (list[float]): Bounding box rectangle [x0, y0, x1, y1].

    Raises:
        FileNotFoundError: If the specified PDF file does not exist.
        ValueError: If searching the PDF fails.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found at: {file_path}")

    results: List[Dict[str, Any]] = []

    try:
        with pymupdf.open(path) as doc:
            for page_index, page in enumerate(doc, start=1):
                rects = page.search_for(keyword)
                for rect in rects:
                    results.append({
                        "page": page_index,
                        "bbox": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
                    })
    except Exception as e:
        raise ValueError(f"Failed to search text in PDF '{file_path}': {e}") from e

    return results


if __name__ == "__main__":
    print("Testing PDF extractor module with enterprise validation features...")

    # 1. Test hash computation
    sample_bytes = b"SIH 2026 Test Sample Content"
    calculated_hash = compute_file_hash(sample_bytes)
    assert len(calculated_hash) == 64
    print(f"[PASSED] compute_file_hash: {calculated_hash}")

    # 2. Test extraction & coordinate location on text-rich PDF
    test_pdf_path = Path("temp_test_enterprise.pdf")
    try:
        doc = pymupdf.open()
        page = doc.new_page()
        sample_text = (
            "Smart India Hackathon   -   PDF Extraction Layer\n\n\n\n"
            "This is an enterprise test document with   excessive   whitespace.\n"
            "Keyword Target: INVOICE-9921 for visual verification."
        )
        page.insert_text((50, 72), sample_text, fontsize=12)
        doc.save(test_pdf_path)
        doc.close()

        # Run extraction
        extracted_data = extract_text_from_pdf(test_pdf_path)
        print("\n--- Structured Extraction Result ---")
        print(f"Page Count: {extracted_data['page_count']}")
        print(f"SHA-256: {extracted_data['sha256']}")
        print(f"Is Scanned: {extracted_data['is_scanned']}")
        print(f"Raw Text:\n{extracted_data['raw_text']}")
        print("------------------------------------\n")

        assert extracted_data["page_count"] == 1
        assert len(extracted_data["sha256"]) == 64
        assert extracted_data["is_scanned"] is False
        assert "Smart India Hackathon - PDF Extraction Layer" in extracted_data["raw_text"]
        print("[PASSED] extract_text_from_pdf (text document)")

        # Run coordinate search
        coords = locate_text_coordinates(test_pdf_path, "INVOICE-9921")
        print(f"\nCoordinates for 'INVOICE-9921': {coords}")
        assert len(coords) >= 1
        assert coords[0]["page"] == 1
        assert len(coords[0]["bbox"]) == 4
        print("[PASSED] locate_text_coordinates")

    finally:
        if test_pdf_path.exists():
            test_pdf_path.unlink()

    # 3. Test scanned detection on short/empty text PDF
    scanned_test_path = Path("temp_scanned_test.pdf")
    try:
        doc = pymupdf.open()
        doc.new_page()  # blank page without text
        doc.save(scanned_test_path)
        doc.close()

        scanned_data = extract_text_from_pdf(scanned_test_path)
        assert scanned_data["is_scanned"] is True
        print("[PASSED] extract_text_from_pdf (scanned document detection)")
    finally:
        if scanned_test_path.exists():
            scanned_test_path.unlink()

    print("\nAll enterprise validation tests passed successfully!")
