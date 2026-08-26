"""PDF Text Extractor Module.

This module provides functionality to extract and clean text from PDF documents using PyMuPDF.
"""

import os
import re
from pathlib import Path
from typing import Union
import pymupdf


def extract_text_from_pdf(file_path: Union[str, Path]) -> str:
    """Extracts all text from a given PDF file and cleans up excessive whitespace.

    Args:
        file_path (Union[str, Path]): Path to the PDF file to extract text from.

    Returns:
        str: Cleaned raw text extracted from all pages of the PDF.

    Raises:
        FileNotFoundError: If the specified PDF file does not exist.
        ValueError: If the file is not a valid PDF.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found at: {file_path}")

    text_chunks: list[str] = []

    try:
        with pymupdf.open(path) as doc:
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
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


if __name__ == "__main__":
    print("Testing PDF extractor module...")

    # Create a temporary PDF in memory to test extraction & whitespace cleanup
    test_pdf_path = Path("temp_test_extractor.pdf")
    try:
        doc = pymupdf.open()
        page = doc.new_page()
        sample_text = (
            "Smart India Hackathon   -   PDF Extraction Layer\n\n\n\n"
            "This is a    test document with   excessive   whitespace.\n"
            "Second line with   tabs \tand   spaces."
        )
        page.insert_text((50, 72), sample_text, fontsize=12)
        doc.save(test_pdf_path)
        doc.close()

        # Run extraction
        result = extract_text_from_pdf(test_pdf_path)
        print("\n--- Extracted Text Output ---")
        print(result)
        print("-----------------------------\n")

        # Assertions
        assert "Smart India Hackathon - PDF Extraction Layer" in result
        assert "This is a test document with excessive whitespace." in result
        print("Self-test passed without errors!")
    finally:
        if test_pdf_path.exists():
            test_pdf_path.unlink()
