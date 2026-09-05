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

try:
    from backend.app.models.document import ExtractedDocumentContent
except ImportError:
    try:
        from app.models.document import ExtractedDocumentContent
    except ImportError:
        from pydantic import BaseModel, Field

        class ExtractedDocumentContent(BaseModel):  # type: ignore
            filename: str
            file_format: str
            raw_text: str = ""
            page_count: int = 1
            pages: List[dict] = Field(default_factory=list)
            sections: List[dict] = Field(default_factory=list)
            tables: List[dict] = Field(default_factory=list)
            source_locations: List[dict] = Field(default_factory=list)
            file_size: int = 0
            metadata: dict = Field(default_factory=dict)

            def __getitem__(self, item: str):
                return getattr(self, item)

            def get(self, item: str, default=None):
                return getattr(self, item, default)

            def __contains__(self, item: str) -> bool:
                return hasattr(self, item)

            def keys(self):
                return self.__dict__.keys()

            def __iter__(self):
                return iter(self.__dict__)

logger = logging.getLogger(__name__)

# XML Namespaces for OOXML
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_SML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _safe_check_zip(z: zipfile.ZipFile, max_entries: int = 1000, max_uncompressed_size: int = 100 * 1024 * 1024) -> None:
    """Protects against zip bombs by limiting entry count and total uncompressed size."""
    entries = z.infolist()
    if len(entries) > max_entries:
        raise ValueError(f"Zip archive contains too many files ({len(entries)} > {max_entries})")
    total_size = sum(e.file_size for e in entries)
    if total_size > max_uncompressed_size:
        raise ValueError(f"Zip archive uncompressed size ({total_size} bytes) exceeds safety limit of {max_uncompressed_size} bytes")


def detect_file_format(filename: str, file_bytes: bytes, mime_type: Optional[str] = None) -> str:
    """Identifies the file format from MIME type, filename extension, and magic bytes."""
    if mime_type:
        mt = mime_type.lower().strip()
        if "pdf" in mt:
            return "pdf"
        if "csv" in mt:
            return "csv"
        if "spreadsheet" in mt or "excel" in mt or "ms-excel" in mt:
            return "xlsx"
        if "wordprocessingml" in mt or "msword" in mt:
            return "docx"
        if "text/plain" in mt:
            return "txt"

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
                _safe_check_zip(z)
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


def _extract_text_from_csv(file_bytes: bytes, filename: str) -> ExtractedDocumentContent:
    """Parses CSV bytes into structured tabular text and table data."""
    text = ""
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if not text:
        text = file_bytes.decode("utf-8", errors="replace")

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
        return ExtractedDocumentContent(
            filename=filename,
            file_format="csv",
            raw_text=f"Empty CSV document: {filename}",
            page_count=1,
            pages=[{"page": 1, "text": ""}],
            sections=[],
            tables=[],
            source_locations=[],
            file_size=len(file_bytes),
            metadata={"row_count": 0, "col_count": 0},
        )

    headers = all_rows[0]
    data_rows = all_rows[1:]

    text_lines = [
        f"=== CSV TABLE: {filename} ===",
        f"Columns ({len(headers)}): {' | '.join(headers)}",
        "--- Data Records ---",
    ]

    source_locations: List[Dict[str, Any]] = []
    for idx, r in enumerate(data_rows, start=1):
        row_fields = []
        for h_idx, val in enumerate(r):
            h_name = headers[h_idx] if h_idx < len(headers) else f"Col_{h_idx+1}"
            row_fields.append(f"{h_name}: {val}")
        text_lines.append(f"Row {idx}: {', '.join(row_fields)}")
        source_locations.append({
            "sheet_name": None,
            "row_number": idx,
            "location_context": f"CSV Row {idx}",
            "headers": headers,
        })

    raw_text = "\n".join(text_lines)

    return ExtractedDocumentContent(
        filename=filename,
        file_format="csv",
        raw_text=raw_text,
        page_count=1,
        pages=[{"page": 1, "text": raw_text}],
        sections=[{"title": "CSV Data Table", "text": raw_text}],
        tables=[{"sheet": None, "headers": headers, "rows": data_rows}],
        source_locations=source_locations,
        file_size=len(file_bytes),
        metadata={
            "row_count": len(all_rows),
            "col_count": len(headers),
            "delimiter": delimiter,
        },
    )


def _extract_text_from_docx(file_bytes: bytes, filename: str) -> ExtractedDocumentContent:
    """Parses Word .docx (OOXML) bytes into paragraphs, tables, sections, and structured text."""
    paragraphs: List[str] = []
    tables: List[Dict[str, Any]] = []
    sections: List[Dict[str, Any]] = []
    source_locations: List[Dict[str, Any]] = []

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
            _safe_check_zip(z)
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

            current_section_title = "Document Body"
            current_section_lines: List[str] = []

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
                        current_section_lines.append(p_str)
                        # Check for section / heading markers
                        if len(p_str) < 90 and (p_str.isupper() or any(w in p_str.upper() for w in ("UNDERTAKING", "DECLARATION", "SCHEDULE", "CLAUSE", "SECTION", "CERTIFICATE"))):
                            if current_section_lines:
                                sections.append({"title": current_section_title, "text": "\n".join(current_section_lines)})
                                current_section_lines = []
                            current_section_title = p_str
                        source_locations.append({
                            "sheet_name": None,
                            "row_number": None,
                            "location_context": f"Paragraph {len(paragraphs)}",
                            "paragraph_index": len(paragraphs),
                        })

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
                        tables.append({"sheet": None, "headers": tbl_headers, "rows": tbl_data})

                        tbl_text_lines = [f"[Table ({len(tbl_headers)} cols)]: {' | '.join(tbl_headers)}"]
                        for r_idx, r in enumerate(tbl_data, start=1):
                            row_str = " | ".join(r)
                            tbl_text_lines.append(f"  Row {r_idx}: {row_str}")
                            source_locations.append({
                                "sheet_name": None,
                                "row_number": r_idx,
                                "location_context": f"Table {len(tables)}, Row {r_idx}",
                                "headers": tbl_headers,
                            })
                        t_block = "\n".join(tbl_text_lines)
                        paragraphs.append(t_block)
                        current_section_lines.append(t_block)

            if current_section_lines:
                sections.append({"title": current_section_title, "text": "\n".join(current_section_lines)})

    except Exception as e:
        logger.warning("Native DOCX XML parsing error for %s: %s. Attempting fallback text extraction.", filename, e)
        strings = re.findall(rb"[\x20-\x7E]{4,}", file_bytes)
        fallback_text = "\n".join(s.decode("latin-1", errors="ignore") for s in strings if len(s) > 8)
        if fallback_text:
            paragraphs.append(fallback_text)
            sections.append({"title": "Recovered Content", "text": fallback_text})
        else:
            paragraphs.append(f"Document content from {filename}")

    raw_text = "\n\n".join(paragraphs)
    estimated_pages = max(1, (len(raw_text) // 2500) + 1)
    pages = [{"page": i + 1, "text": chunk} for i, chunk in enumerate(paragraphs[:estimated_pages])]
    if not pages:
        pages = [{"page": 1, "text": raw_text}]

    return ExtractedDocumentContent(
        filename=filename,
        file_format="docx",
        raw_text=raw_text,
        page_count=estimated_pages,
        pages=pages,
        sections=sections,
        tables=tables,
        source_locations=source_locations,
        file_size=len(file_bytes),
        metadata={"paragraph_count": len(paragraphs), "table_count": len(tables), "section_count": len(sections)},
    )


def _extract_text_from_xlsx(file_bytes: bytes, filename: str) -> ExtractedDocumentContent:
    """Parses Excel (.xlsx) bytes into structured table data and text."""
    all_tables: List[Dict[str, Any]] = []
    all_source_locations: List[Dict[str, Any]] = []
    text_parts: List[str] = [f"=== EXCEL SPREADSHEET: {filename} ==="]
    sheet_names: List[str] = []

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
            _safe_check_zip(z)
    except Exception as ze:
        logger.debug("Zip check in xlsx for %s: %s", filename, ze)

    try:
        import pandas as pd
        excel_file = io.BytesIO(file_bytes)
        xls = pd.ExcelFile(excel_file)
        sheet_names = list(xls.sheet_names)

        for sheet_name in sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            df = df.dropna(how="all")
            if df.empty:
                continue
            headers = [str(c) for c in df.columns]
            rows = [[str(v) if v is not None and not pd.isna(v) else "" for v in r] for r in df.values]
            all_tables.append({"sheet": sheet_name, "headers": headers, "rows": rows})

            text_parts.append(f"\n--- Sheet: {sheet_name} ({len(rows)} rows) ---")
            text_parts.append(f"Columns: {' | '.join(headers)}")
            for idx, r in enumerate(rows, start=1):
                all_source_locations.append({
                    "sheet_name": sheet_name,
                    "row_number": idx,
                    "location_context": f"Sheet '{sheet_name}', Row {idx}",
                    "headers": headers,
                })
                if idx <= 50:
                    text_parts.append(f"Row {idx}: {', '.join(f'{h}: {val}' for h, val in zip(headers, r) if val)}")

        raw_text = "\n".join(text_parts)
        pages = []
        for s_idx, t in enumerate(all_tables, start=1):
            s_name = t.get("sheet", f"Sheet{s_idx}")
            s_text = f"Sheet: {s_name}\nColumns: {' | '.join(t.get('headers', []))}\n" + "\n".join(
                f"Row {r_idx}: {', '.join(r)}" for r_idx, r in enumerate(t.get("rows", [])[:50], start=1)
            )
            pages.append({"page": s_idx, "text": s_text})
        if not pages:
            pages = [{"page": 1, "text": raw_text}]

        return ExtractedDocumentContent(
            filename=filename,
            file_format="xlsx",
            raw_text=raw_text,
            page_count=max(1, len(sheet_names)),
            pages=pages,
            sections=[{"title": f"Sheet: {t['sheet']}", "text": f"Columns: {', '.join(t['headers'])}"} for t in all_tables],
            tables=all_tables,
            source_locations=all_source_locations,
            file_size=len(file_bytes),
            metadata={"sheet_names": sheet_names, "sheet_count": len(sheet_names)},
        )
    except Exception as pd_err:
        logger.warning("Pandas excel parse skipped/failed for %s: %s. Using native XML parser.", filename, pd_err)

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
            _safe_check_zip(z)
            shared_strings: List[str] = []
            if "xl/sharedStrings.xml" in z.namelist():
                ss_root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                for si in ss_root:
                    t_elems = [e.text for e in si.iter() if e.tag.endswith("t") and e.text]
                    shared_strings.append("".join(t_elems))

            sheet_files = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
            text_lines = [f"=== EXCEL SPREADSHEET: {filename} ==="]
            
            for s_idx, s_name in enumerate(sheet_files, start=1):
                s_title = f"Sheet{s_idx}"
                sheet_names.append(s_title)
                s_root = ET.fromstring(z.read(s_name))
                sheet_rows: List[List[str]] = []
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
                                cell_vals.append(val)
                        if any(cell_vals):
                            sheet_rows.append(cell_vals)
                            text_lines.append(" | ".join(cell_vals))

                if sheet_rows:
                    headers = sheet_rows[0]
                    data_rows = sheet_rows[1:]
                    all_tables.append({"sheet": s_title, "headers": headers, "rows": data_rows})
                    for r_idx, r in enumerate(data_rows, start=1):
                        all_source_locations.append({
                            "sheet_name": s_title,
                            "row_number": r_idx,
                            "location_context": f"Sheet '{s_title}', Row {r_idx}",
                            "headers": headers,
                        })

            raw_text = "\n".join(text_lines)
            pages = []
            for s_idx, t in enumerate(all_tables, start=1):
                s_name = t.get("sheet", f"Sheet{s_idx}")
                s_text = f"Sheet: {s_name}\nColumns: {' | '.join(t.get('headers', []))}\n" + "\n".join(
                    f"Row {r_idx}: {', '.join(r)}" for r_idx, r in enumerate(t.get("rows", [])[:50], start=1)
                )
                pages.append({"page": s_idx, "text": s_text})
            if not pages:
                pages = [{"page": 1, "text": raw_text}]

            return ExtractedDocumentContent(
                filename=filename,
                file_format="xlsx",
                raw_text=raw_text,
                page_count=max(1, len(sheet_files)),
                pages=pages,
                sections=[{"title": f"Sheet: {t['sheet']}", "text": f"Columns: {', '.join(t['headers'])}"} for t in all_tables],
                tables=all_tables,
                source_locations=all_source_locations,
                file_size=len(file_bytes),
                metadata={"sheet_count": len(sheet_files), "sheet_names": sheet_names},
            )
    except Exception as e:
        logger.error("Failed native XLSX extraction for %s: %s", filename, e)
        return ExtractedDocumentContent(
            filename=filename,
            file_format="xlsx",
            raw_text=f"Could not parse Excel document: {filename}",
            page_count=1,
            pages=[{"page": 1, "text": ""}],
            sections=[],
            tables=[],
            source_locations=[],
            file_size=len(file_bytes),
            metadata={"error": str(e)},
        )


def _extract_text_from_txt(file_bytes: bytes, filename: str) -> ExtractedDocumentContent:
    """Parses plain text bytes with automatic encoding fallback."""
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = file_bytes.decode("utf-8", errors="replace")

    clean_text = text.strip()
    return ExtractedDocumentContent(
        filename=filename,
        file_format="txt",
        raw_text=clean_text,
        page_count=1,
        pages=[{"page": 1, "text": clean_text}],
        sections=[{"title": "Plain Text Content", "text": clean_text}],
        tables=[],
        source_locations=[{
            "sheet_name": None,
            "row_number": None,
            "location_context": "Plain text document",
            "source_format": "txt",
        }],
        file_size=len(file_bytes),
        metadata={"character_count": len(clean_text)},
    )


async def _extract_text_from_pdf(file_bytes: bytes, filename: str) -> ExtractedDocumentContent:
    """Extracts text and pages from a PDF document using PyMuPDF / pdf_parser."""
    pages = []
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
        except Exception as pe:
            logger.warning("extract_pages_from_pdf failed for %s: %s. Using PyMuPDF fallback.", filename, pe)

    if not pages:
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
                for i, page in enumerate(doc, start=1):
                    p_text = page.get_text()
                    pages.append({"page": i, "text": p_text})
                doc.close()
            except Exception as fitz_err:
                logger.error("PyMuPDF fallback failed for %s: %s", filename, fitz_err)

    if not pages:
        try:
            decoded_text = file_bytes.decode("utf-8").strip()
            if decoded_text:
                pages = [{"page": 1, "text": decoded_text}]
        except Exception:
            pass

    if not pages:
        pages = [{"page": 1, "text": f"PDF document: {filename} ({len(file_bytes)} bytes)"}]

    raw_text = "\n\n".join(p.get("text", "") for p in pages if p.get("text"))
    source_locations = [
        {
            "page_number": p.get("page", 1),
            "location_context": f"Page {p.get('page', 1)}",
            "source_format": "pdf",
        }
        for p in pages
    ]

    return ExtractedDocumentContent(
        filename=filename,
        file_format="pdf",
        raw_text=raw_text,
        page_count=len(pages),
        pages=pages,
        sections=[{"title": f"Page {p.get('page', 1)}", "text": p.get("text", "")} for p in pages],
        tables=[],
        source_locations=source_locations,
        file_size=len(file_bytes),
        metadata={"page_count": len(pages)},
    )


async def extract_data_from_file(
    file_bytes: bytes,
    filename: str,
    mime_type: Optional[str] = None
) -> ExtractedDocumentContent:
    """Universal multi-format data extractor for procurement documents.

    Supports: PDF, CSV, DOCX, DOC, XLSX, XLS, TXT.
    Returns typed ExtractedDocumentContent conforming to OPAL extraction contract.
    """
    if not file_bytes:
        return ExtractedDocumentContent(
            filename=filename,
            file_format="empty",
            raw_text="",
            page_count=0,
            pages=[],
            sections=[],
            tables=[],
            source_locations=[],
            file_size=0,
            metadata={"empty": True},
        )

    if len(file_bytes) > MAX_FILE_SIZE:
        return ExtractedDocumentContent(
            filename=filename,
            file_format="oversized",
            raw_text=f"File exceeds maximum allowed size of {MAX_FILE_SIZE} bytes: {filename}",
            page_count=0,
            pages=[],
            sections=[],
            tables=[],
            source_locations=[],
            file_size=len(file_bytes),
            metadata={"error": "FILE_TOO_LARGE", "max_size": MAX_FILE_SIZE},
        )

    fmt = detect_file_format(filename, file_bytes, mime_type=mime_type)

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
            return ExtractedDocumentContent(
                filename=filename,
                file_format=fmt,
                raw_text=f"Binary document: {filename} ({len(file_bytes)} bytes)",
                page_count=1,
                pages=[{"page": 1, "text": ""}],
                sections=[],
                tables=[],
                source_locations=[],
                file_size=len(file_bytes),
                metadata={"unknown_format": True},
            )
