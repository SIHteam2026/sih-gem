"""Multi-Format Document Extractor Service.

Provides format-aware parsing and structured text/table extraction for:
- PDF (.pdf) via PyMuPDF / OCR
- CSV (.csv) via delimiter detection, structured tabular text, and record arrays
- Word (.docx) via native OOXML XML parsing (paragraphs and tables)
- Excel (.xlsx, .xls) via pandas / openpyxl or native OOXML sheet parsing
- Plain Text (.txt) via auto-encoding detection

Returns a standardized document extraction contract:
{
    "filename": str,
    "file_format": str,
    "raw_text": str,
    "page_count": int,
    "pages": [{"page": int, "text": str}],
    "tables": [{"headers": list, "rows": list}],
    "file_size": int,
    "metadata": dict
}
"""

import csv
import io
import json
import logging
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# XML Namespaces for OOXML
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_SML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def detect_file_format(filename: str, file_bytes: bytes) -> str:
    """Identifies the file format from filename extension and magic bytes."""
    ext = Path(filename).suffix.lower().lstrip(".") if filename else ""

    # Magic byte signatures
    if file_bytes.startswith(b"%PDF"):
        return "pdf"
    if file_bytes.startswith(b"PK\x03\x04"):
        # ZIP-based container: could be docx, xlsx, or zip
        if ext in ("docx", "doc"):
            return "docx"
        if ext in ("xlsx", "xls"):
            return "xlsx"
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
                names = z.namelist()
                if any(n.startswith("word/") for n in names):
                    return "docx"
                if any(n.startswith("xl/") for n in names):
                    return "xlsx"
        except Exception:
            pass
        return ext if ext in ("docx", "xlsx", "zip") else "zip"

    if ext in ("csv", "tsv"):
        return "csv"
    if ext in ("xlsx", "xls"):
        return "xlsx"
    if ext in ("docx", "doc"):
        return "docx"
    if ext in ("txt", "log", "json", "md"):
        return "txt"
    if ext == "pdf":
        return "pdf"

    # Fallback inspection: if mostly valid text, treat as txt/csv
    try:
        sample = file_bytes[:1024].decode("utf-8")
        if "\n" in sample and ("," in sample or "\t" in sample):
            return "csv"
        return "txt"
    except Exception:
        return "unknown"


def _extract_text_from_csv(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Parses CSV bytes into structured tabular text and table data."""
    # Decode with fallback encodings
    text = ""
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if not text:
        text = file_bytes.decode("utf-8", errors="replace")

    # Detect delimiter
    delimiter = ","
    try:
        sample = text[:2048]
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except Exception:
        if "\t" in text[:500]:
            delimiter = "\t"
        elif ";" in text[:500]:
            delimiter = ";"

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    all_rows: List[List[str]] = []
    for row in reader:
        cleaned_row = [str(c).strip() for c in row]
        if any(cleaned_row):
            all_rows.append(cleaned_row)

    if not all_rows:
        return {
            "filename": filename,
            "file_format": "csv",
            "raw_text": f"Empty CSV document: {filename}",
            "page_count": 1,
            "pages": [{"page": 1, "text": ""}],
            "tables": [],
            "file_size": len(file_bytes),
            "metadata": {"row_count": 0, "col_count": 0},
        }

    headers = all_rows[0]
    data_rows = all_rows[1:]

    # Build readable formatted text
    text_lines = [
        f"=== CSV TABLE: {filename} ===",
        f"Columns ({len(headers)}): {' | '.join(headers)}",
        "--- Data Records ---",
    ]

    for idx, r in enumerate(data_rows, start=1):
        row_fields = []
        for h_idx, val in enumerate(r):
            h_name = headers[h_idx] if h_idx < len(headers) else f"Col_{h_idx+1}"
            row_fields.append(f"{h_name}: {val}")
        text_lines.append(f"Row {idx}: {', '.join(row_fields)}")

    raw_text = "\n".join(text_lines)

    return {
        "filename": filename,
        "file_format": "csv",
        "raw_text": raw_text,
        "page_count": 1,
        "pages": [{"page": 1, "text": raw_text}],
        "tables": [{"headers": headers, "rows": data_rows}],
        "file_size": len(file_bytes),
        "metadata": {
            "row_count": len(all_rows),
            "col_count": len(headers),
            "delimiter": delimiter,
        },
    }


def _extract_text_from_docx(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Parses Word .docx (OOXML) bytes into paragraphs, tables, and structured text."""
    paragraphs: List[str] = []
    tables: List[Dict[str, Any]] = []

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
            doc_xml_name = "word/document.xml"
            if doc_xml_name not in z.namelist():
                matches = [n for n in z.namelist() if n.endswith("document.xml")]
                if matches:
                    doc_xml_name = matches[0]
                else:
                    raise ValueError(f"document.xml not found in DOCX package {filename}")

            xml_content = z.read(doc_xml_name)
            root = ET.fromstring(xml_content)

            def _local_tag(elem) -> str:
                t = elem.tag
                return t.split("}")[-1] if "}" in t else t

            body = None
            for child in root:
                if _local_tag(child) == "body":
                    body = child
                    break
            if body is None:
                body = root

            for elem in body:
                tag = _local_tag(elem)

                if tag == "p":
                    p_texts = [
                        t_elem.text
                        for t_elem in elem.iter()
                        if _local_tag(t_elem) == "t" and t_elem.text
                    ]
                    p_str = "".join(p_texts).strip()
                    if p_str:
                        paragraphs.append(p_str)

                elif tag == "tbl":
                    table_rows: List[List[str]] = []
                    for row_elem in elem:
                        if _local_tag(row_elem) != "tr":
                            continue
                        row_cells: List[str] = []
                        for cell_elem in row_elem:
                            if _local_tag(cell_elem) != "tc":
                                continue
                            cell_texts = [
                                t_elem.text
                                for t_elem in cell_elem.iter()
                                if _local_tag(t_elem) == "t" and t_elem.text
                            ]
                            cell_str = " ".join("".join(cell_texts).split()).strip()
                            row_cells.append(cell_str)
                        if any(row_cells):
                            table_rows.append(row_cells)

                    if table_rows:
                        tbl_headers = table_rows[0]
                        tbl_data = table_rows[1:]
                        tables.append({"headers": tbl_headers, "rows": tbl_data})

                        tbl_text_lines = [f"[Table ({len(tbl_headers)} cols)]: {' | '.join(tbl_headers)}"]
                        for r_idx, r in enumerate(tbl_data, start=1):
                            row_str = " | ".join(r)
                            tbl_text_lines.append(f"  Row {r_idx}: {row_str}")
                        paragraphs.append("\n".join(tbl_text_lines))

    except Exception as e:
        logger.warning("Native DOCX XML parsing error for %s: %s. Attempting fallback text extraction.", filename, e)
        strings = re.findall(rb"[\x20-\x7E]{4,}", file_bytes)
        fallback_text = "\n".join(s.decode("latin-1", errors="ignore") for s in strings if len(s) > 8)
        if fallback_text:
            paragraphs.append(fallback_text)
        else:
            paragraphs.append(f"Document content from {filename}")

    raw_text = "\n\n".join(paragraphs)
    estimated_pages = max(1, (len(raw_text) // 2500) + 1)
    pages = [{"page": i + 1, "text": chunk} for i, chunk in enumerate(paragraphs[:estimated_pages])]
    if not pages:
        pages = [{"page": 1, "text": raw_text}]

    return {
        "filename": filename,
        "file_format": "docx",
        "raw_text": raw_text,
        "page_count": estimated_pages,
        "pages": pages,
        "tables": tables,
        "file_size": len(file_bytes),
        "metadata": {"paragraph_count": len(paragraphs), "table_count": len(tables)},
    }


def _extract_text_from_xlsx(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Parses Excel (.xlsx) bytes into structured table data and text."""
    try:
        import pandas as pd
        excel_file = io.BytesIO(file_bytes)
        xls = pd.ExcelFile(excel_file)
        all_tables: List[Dict[str, Any]] = []
        text_parts: List[str] = [f"=== EXCEL SPREADSHEET: {filename} ==="]

        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            df = df.dropna(how="all")
            if df.empty:
                continue
            headers = [str(c) for c in df.columns]
            rows = [[str(v) if v is not None and not pd.isna(v) else "" for v in r] for r in df.values]
            all_tables.append({"sheet": sheet_name, "headers": headers, "rows": rows})

            text_parts.append(f"\n--- Sheet: {sheet_name} ({len(rows)} rows) ---")
            text_parts.append(f"Columns: {' | '.join(headers)}")
            for idx, r in enumerate(rows[:50], start=1):
                text_parts.append(f"Row {idx}: {', '.join(f'{h}: {val}' for h, val in zip(headers, r) if val)}")

        raw_text = "\n".join(text_parts)
        return {
            "filename": filename,
            "file_format": "xlsx",
            "raw_text": raw_text,
            "page_count": len(xls.sheet_names),
            "pages": [{"page": i + 1, "text": f"Sheet: {s}"} for i, s in enumerate(xls.sheet_names)],
            "tables": all_tables,
            "file_size": len(file_bytes),
            "metadata": {"sheet_names": xls.sheet_names},
        }
    except Exception as pd_err:
        logger.warning("Pandas excel parse skipped/failed for %s: %s. Using native XML parser.", filename, pd_err)

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
            shared_strings: List[str] = []
            if "xl/sharedStrings.xml" in z.namelist():
                ss_root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                for si in ss_root:
                    t_elems = [e.text for e in si.iter() if e.tag.endswith("t") and e.text]
                    shared_strings.append("".join(t_elems))

            sheet_names = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
            text_lines = [f"=== EXCEL SPREADSHEET: {filename} ==="]
            for s_name in sheet_names:
                s_root = ET.fromstring(z.read(s_name))
                for row_elem in s_root.iter():
                    if row_elem.tag.endswith("row"):
                        cell_vals = []
                        for c in row_elem:
                            if c.tag.endswith("c"):
                                c_type = c.attrib.get("t", "")
                                v_elem = c.find("{*}v")
                                val = v_elem.text if v_elem is not None else ""
                                if c_type == "s" and val.isdigit() and int(val) < len(shared_strings):
                                    val = shared_strings[int(val)]
                                if val:
                                    cell_vals.append(val)
                        if cell_vals:
                            text_lines.append(" | ".join(cell_vals))

            raw_text = "\n".join(text_lines)
            return {
                "filename": filename,
                "file_format": "xlsx",
                "raw_text": raw_text,
                "page_count": max(1, len(sheet_names)),
                "pages": [{"page": 1, "text": raw_text}],
                "tables": [],
                "file_size": len(file_bytes),
                "metadata": {"sheet_count": len(sheet_names)},
            }
    except Exception as e:
        logger.error("Failed native XLSX extraction for %s: %s", filename, e)
        return {
            "filename": filename,
            "file_format": "xlsx",
            "raw_text": f"Could not parse Excel document: {filename}",
            "page_count": 1,
            "pages": [{"page": 1, "text": ""}],
            "tables": [],
            "file_size": len(file_bytes),
            "metadata": {"error": str(e)},
        }


def _extract_text_from_txt(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Parses plain text bytes."""
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = file_bytes.decode("utf-8", errors="replace")

    return {
        "filename": filename,
        "file_format": "txt",
        "raw_text": text.strip(),
        "page_count": 1,
        "pages": [{"page": 1, "text": text.strip()}],
        "tables": [],
        "file_size": len(file_bytes),
        "metadata": {"character_count": len(text)},
    }


async def _extract_text_from_pdf(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Extracts text and pages from a PDF document using PyMuPDF / pdf_parser."""
    try:
        from backend.app.services.pdf_parser import extract_pages_from_pdf
    except ImportError:
        try:
            from app.services.pdf_parser import extract_pages_from_pdf
        except ImportError:
            extract_pages_from_pdf = None

    if extract_pages_from_pdf:
        try:
            pages = await extract_pages_from_pdf(file_bytes)
            raw_text = "\n\n".join(p["text"] for p in pages if p.get("text"))
            return {
                "filename": filename,
                "file_format": "pdf",
                "raw_text": raw_text,
                "page_count": len(pages),
                "pages": pages,
                "tables": [],
                "file_size": len(file_bytes),
                "metadata": {"page_count": len(pages)},
            }
        except Exception as pe:
            logger.warning("extract_pages_from_pdf failed for %s: %s. Using PyMuPDF fallback.", filename, pe)

    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError:
            pymupdf = None

    if pymupdf:
        try:
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            pages = []
            for i, page in enumerate(doc, start=1):
                p_text = page.get_text()
                pages.append({"page": i, "text": p_text})
            doc.close()
            raw_text = "\n\n".join(p["text"] for p in pages if p.get("text"))
            return {
                "filename": filename,
                "file_format": "pdf",
                "raw_text": raw_text,
                "page_count": len(pages),
                "pages": pages,
                "tables": [],
                "file_size": len(file_bytes),
                "metadata": {"page_count": len(pages)},
            }
        except Exception as fitz_err:
            logger.error("PyMuPDF fallback failed for %s: %s", filename, fitz_err)

    return {
        "filename": filename,
        "file_format": "pdf",
        "raw_text": f"PDF document: {filename} ({len(file_bytes)} bytes)",
        "page_count": 1,
        "pages": [{"page": 1, "text": ""}],
        "tables": [],
        "file_size": len(file_bytes),
        "metadata": {},
    }


async def extract_data_from_file(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Universal multi-format data extractor for procurement documents.

    Supports: PDF, CSV, DOCX, DOC, XLSX, XLS, TXT.
    Returns standard extraction payload with raw_text, pages, tables, and metadata.
    """
    if not file_bytes:
        return {
            "filename": filename,
            "file_format": "empty",
            "raw_text": "",
            "page_count": 0,
            "pages": [],
            "tables": [],
            "file_size": 0,
            "metadata": {"empty": True},
        }

    fmt = detect_file_format(filename, file_bytes)

    if fmt == "pdf":
        return await _extract_text_from_pdf(file_bytes, filename)
    elif fmt == "csv":
        return _extract_text_from_csv(file_bytes, filename)
    elif fmt == "docx":
        return _extract_text_from_docx(file_bytes, filename)
    elif fmt == "xlsx":
        return _extract_text_from_xlsx(file_bytes, filename)
    elif fmt == "txt":
        return _extract_text_from_txt(file_bytes, filename)
    else:
        try:
            return _extract_text_from_txt(file_bytes, filename)
        except Exception:
            return {
                "filename": filename,
                "file_format": fmt,
                "raw_text": f"Binary document: {filename} ({len(file_bytes)} bytes)",
                "page_count": 1,
                "pages": [{"page": 1, "text": ""}],
                "tables": [],
                "file_size": len(file_bytes),
                "metadata": {"unknown_format": True},
            }
