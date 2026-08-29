"""Bill of Quantities (BoQ) & Financial Table Extraction Service.

Provides asynchronous extraction of structured table grids from financial PDF documents,
BoQ schedules, and price bids using pdfplumber and pandas.
"""

import io
import logging
from typing import Any, Dict, List
import pdfplumber

logger = logging.getLogger(__name__)


async def extract_financial_tables(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Extracts structured financial tables and BoQ schedules from a PDF.

    Opens the PDF bytes in-memory, iterates through all pages, extracts table grids,
    and converts each table into a list of dictionaries where the first row serves
    as header keys. Empty tables and blank rows are safely ignored.

    Args:
        file_bytes (bytes): Raw byte content of the financial/BoQ PDF.

    Returns:
        list[dict]: List of row dictionaries extracted from all tables across pages.
    """
    if not file_bytes:
        return []

    all_table_records: List[Dict[str, Any]] = []

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                # Extract tables on current page
                tables = page.extract_tables()
                if not tables:
                    single_table = page.extract_table()
                    tables = [single_table] if single_table else []

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    # First row acts as the header keys
                    raw_headers = table[0]
                    if not raw_headers or all(h is None or str(h).strip() == "" for h in raw_headers):
                        continue

                    # Clean header strings
                    headers: List[str] = []
                    for col_idx, raw_header in enumerate(raw_headers):
                        cleaned_name = (
                            str(raw_header).replace("\n", " ").strip()
                            if raw_header is not None
                            else ""
                        )
                        if not cleaned_name:
                            cleaned_name = f"column_{col_idx + 1}"
                        # Ensure unique header keys
                        if cleaned_name in headers:
                            cleaned_name = f"{cleaned_name}_{col_idx + 1}"
                        headers.append(cleaned_name)

                    # Iterate over data rows
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
        logger.error("Failed to extract financial tables from PDF bytes: %s", e)
        return []
