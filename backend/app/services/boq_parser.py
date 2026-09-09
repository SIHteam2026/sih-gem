"""Bill of Quantities (BoQ) & Financial Table Extraction Service.

Provides asynchronous extraction of structured table grids from financial PDF documents,
BoQ schedules, and price bids using pdfplumber and pandas.
"""

import io
import logging
from typing import Any, Dict, List
try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    import pymupdf  # type: ignore
except Exception:
    try:
        import fitz as pymupdf  # type: ignore
    except Exception:
        pymupdf = None


logger = logging.getLogger(__name__)


def extract_financial_tables_sync(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Synchronously extracts structured financial tables and BoQ schedules from a PDF.

    Opens the PDF bytes in-memory, iterates through all pages, extracts table grids,
    and converts each table into a list of dictionaries where the first row serves
    as header keys. Empty tables and blank rows are safely ignored.

    Tries pdfplumber first (best structured table support), then falls back to
    PyMuPDF/fitz raw text parsing for environments where pdfplumber is unavailable.

    Args:
        file_bytes (bytes): Raw byte content of the financial/BoQ PDF.

    Returns:
        list[dict]: List of row dictionaries extracted from all tables across pages.
    """
    if not file_bytes:
        return []

    # --- Attempt 1: pdfplumber (preferred for structured tables) ---
    if pdfplumber is not None:
        all_table_records: List[Dict[str, Any]] = []
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if not tables:
                        single_table = page.extract_table()
                        tables = [single_table] if single_table else []

                    for table in tables:
                        if not table or len(table) < 2:
                            continue

                        raw_headers = table[0]
                        if not raw_headers or all(h is None or str(h).strip() == "" for h in raw_headers):
                            continue

                        headers: List[str] = []
                        for col_idx, raw_header in enumerate(raw_headers):
                            cleaned_name = (
                                str(raw_header).replace("\n", " ").strip()
                                if raw_header is not None
                                else ""
                            )
                            if not cleaned_name:
                                cleaned_name = f"column_{col_idx + 1}"
                            if cleaned_name in headers:
                                cleaned_name = f"{cleaned_name}_{col_idx + 1}"
                            headers.append(cleaned_name)

                        for row in table[1:]:
                            if not row or all(cell is None or str(cell).strip() == "" for cell in row):
                                continue
                            row_dict: Dict[str, Any] = {}
                            for col_idx, header_key in enumerate(headers):
                                cell_val = row[col_idx] if col_idx < len(row) else None
                                row_dict[header_key] = (
                                    str(cell_val).replace("\n", " ").strip()
                                    if cell_val is not None
                                    else ""
                                )
                            all_table_records.append(row_dict)

            return all_table_records
        except Exception as e:
            logger.error("Failed to extract financial tables via pdfplumber: %s", e)

    # --- Attempt 2: PyMuPDF raw-text table-like row parsing ---
    if pymupdf is not None:
        import re
        all_table_records = []
        try:
            doc_pdf = pymupdf.open(stream=file_bytes, filetype="pdf")
            for page in doc_pdf:
                text = page.get_text()
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    # Detect rows that look like BOQ line items (description | qty | rate | total)
                    parts = [p.strip() for p in re.split(r"\t|\s{2,}", line) if p.strip()]
                    if len(parts) >= 3:
                        # Heuristic: last 1-3 parts are numeric
                        nums = []
                        non_nums = []
                        for p in parts:
                            cleaned = re.sub(r"[,\s]", "", p)
                            if re.fullmatch(r"[\d]+(?:\.\d+)?", cleaned):
                                nums.append(p)
                            else:
                                non_nums.append(p)
                        if 1 <= len(nums) <= 4 and non_nums:
                            row_dict = {"description": " ".join(non_nums)}
                            for i, num in enumerate(nums):
                                key = ["quantity", "unit_rate", "total_price", "taxes"][i] if i < 4 else f"col_{i}"
                                row_dict[key] = num
                            all_table_records.append(row_dict)
            doc_pdf.close()
            return all_table_records
        except Exception as e:
            logger.error("Failed to extract financial tables via PyMuPDF: %s", e)

    logger.warning("No PDF library available for table extraction (pdfplumber and pymupdf both absent/failed).")
    return []


async def extract_financial_tables(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Extracts structured financial tables and BoQ schedules from a PDF (async wrapper)."""
    return extract_financial_tables_sync(file_bytes)

