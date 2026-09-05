"""Unit and Integration Tests for Multi-Document and Multi-Format Ingestion & Extraction.

Tests:
1. Format detection across PDF, CSV, DOCX, XLSX, TXT.
2. CSV structured tabular text and table data extraction.
3. DOCX native OOXML paragraph and table extraction.
4. XLSX spreadsheet parsing.
5. TXT encoding fallback.
6. API endpoint `/api/documents/extract` with batch multi-file upload.
7. API endpoint `/api/verify/bid` with multiple bidder documents across varied formats.
8. API endpoint `/api/verify/bid` backward compatibility with single `bidder_file`.
"""

import io
import unittest
import zipfile
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api.main import app
from app.services.multi_format_extractor import (
    detect_file_format,
    extract_data_from_file,
)


def _create_sample_docx(paragraphs, table_rows=None) -> bytes:
    """Helper to synthesize a valid Office Open XML (.docx) package in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        p_xml = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
        tbl_xml = ""
        if table_rows:
            tr_elements = []
            for row in table_rows:
                tc_elements = "".join(f"<w:tc><w:p><w:r><w:t>{cell}</w:t></w:r></w:p></w:tc>" for cell in row)
                tr_elements.append(f"<w:tr>{tc_elements}</w:tr>")
            tbl_xml = f"<w:tbl>{''.join(tr_elements)}</w:tbl>"

        doc_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {p_xml}
    {tbl_xml}
  </w:body>
</w:document>"""
        z.writestr("word/document.xml", doc_xml.encode("utf-8"))
    return buf.getvalue()


def _create_sample_xlsx(shared_strings, rows) -> bytes:
    """Helper to synthesize a minimal OOXML spreadsheet (.xlsx) in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        # 1. sharedStrings.xml
        si_xml = "".join(f"<si><t>{s}</t></si>" for s in shared_strings)
        ss_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{si_xml}</sst>"""
        z.writestr("xl/sharedStrings.xml", ss_xml.encode("utf-8"))

        # 2. sheet1.xml
        row_xml_list = []
        for r_idx, row in enumerate(rows, start=1):
            c_xml_list = []
            for c_idx, s_idx in enumerate(row):
                c_xml_list.append(f'<c t="s"><v>{s_idx}</v></c>')
            row_xml_list.append(f'<row r="{r_idx}">{"".join(c_xml_list)}</row>')

        sheet_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>{"".join(row_xml_list)}</sheetData>
</worksheet>"""
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml.encode("utf-8"))
    return buf.getvalue()


class TestMultiFormatExtraction(unittest.IsolatedAsyncioTestCase):
    """Unit tests for multi_format_extractor service."""

    def test_detect_file_format(self):
        self.assertEqual(detect_file_format("tender.pdf", b"%PDF-1.4"), "pdf")
        self.assertEqual(detect_file_format("data.csv", b"a,b,c\n1,2,3"), "csv")
        self.assertEqual(detect_file_format("notes.txt", b"simple plain text"), "txt")

        # Test DOCX detection from zip content
        docx_bytes = _create_sample_docx(["Test"])
        self.assertEqual(detect_file_format("file.docx", docx_bytes), "docx")

        # Test XLSX detection from zip content
        xlsx_bytes = _create_sample_xlsx(["Header"], [[0]])
        self.assertEqual(detect_file_format("file.xlsx", xlsx_bytes), "xlsx")

    async def test_csv_extraction(self):
        csv_content = (
            "Financial_Year,Annual_Turnover_INR,UDIN_Reference,Auditor_Remarks\n"
            "2022-2023,45000000,23049182UDIN001,Statutory Audit Completed\n"
            "2023-2024,52000000,24049182UDIN002,Statutory Audit Completed\n"
        ).encode("utf-8")

        result = await extract_data_from_file(csv_content, "turnover_schedule.csv")

        self.assertEqual(result["file_format"], "csv")
        self.assertIn("45000000", result["raw_text"])
        self.assertIn("52000000", result["raw_text"])
        self.assertIn("UDIN_Reference", result["raw_text"])
        self.assertEqual(len(result["tables"]), 1)
        self.assertEqual(result["tables"][0]["headers"], ["Financial_Year", "Annual_Turnover_INR", "UDIN_Reference", "Auditor_Remarks"])
        self.assertEqual(len(result["tables"][0]["rows"]), 2)

    async def test_docx_extraction(self):
        paragraphs = [
            "UNDERTAKING OF NON-BLACKLISTING",
            "We hereby certify that M/s Alpha Tech has not been debarred by any Central or State Govt department.",
            "Make in India Local Content: 68% declared for the current tender.",
        ]
        table_rows = [
            ["Contract_Ref", "Client_Name", "Value_INR"],
            ["PO-2023-01", "Ministry of Power", "12000000"],
            ["PO-2023-02", "Indian Oil Corp", "18000000"],
        ]
        docx_bytes = _create_sample_docx(paragraphs, table_rows)

        result = await extract_data_from_file(docx_bytes, "non_blacklisting_undertaking.docx")

        self.assertEqual(result["file_format"], "docx")
        self.assertIn("UNDERTAKING OF NON-BLACKLISTING", result["raw_text"])
        self.assertIn("68% declared", result["raw_text"])
        self.assertIn("Ministry of Power", result["raw_text"])
        self.assertEqual(len(result["tables"]), 1)
        self.assertEqual(result["tables"][0]["headers"], ["Contract_Ref", "Client_Name", "Value_INR"])

    async def test_xlsx_extraction(self):
        shared_strings = ["Item_Name", "Quantity", "Unit_Price_INR", "Total_INR", "BoQ Item 1", "50", "2000", "100000"]
        rows = [
            [0, 1, 2, 3],  # Headers
            [4, 5, 6, 7],  # Row 1
        ]
        xlsx_bytes = _create_sample_xlsx(shared_strings, rows)

        result = await extract_data_from_file(xlsx_bytes, "commercial_schedule.xlsx")

        self.assertEqual(result["file_format"], "xlsx")
        self.assertIn("Item_Name", result["raw_text"])
        self.assertIn("BoQ Item 1", result["raw_text"])

    async def test_txt_extraction(self):
        txt_bytes = "Manufacturer Authorization Form: We hereby authorize Beta Traders to supply our OEM equipment.".encode("utf-8")
        result = await extract_data_from_file(txt_bytes, "oem_maf.txt")

        self.assertEqual(result["file_format"], "txt")
        self.assertIn("Manufacturer Authorization Form", result["raw_text"])
        self.assertEqual(result["page_count"], 1)

    async def test_empty_file(self):
        result = await extract_data_from_file(b"", "empty.csv")
        self.assertEqual(result["file_format"], "empty")
        self.assertEqual(result["raw_text"], "")


class TestMultiFormatApiIntegration(unittest.TestCase):
    """Integration tests for FastAPI endpoints with multi-file and multi-format payloads."""

    def setUp(self):
        self.client = TestClient(app)

    def test_extract_documents_endpoint(self):
        """Tests POST /api/documents/extract with CSV, DOCX, and TXT files."""
        csv_bytes = b"ColA,ColB\nVal1,Val2\n"
        docx_bytes = _create_sample_docx(["Sample Docx Paragraph"])
        txt_bytes = b"Sample text declaration."

        files = [
            ("files", ("schedule.csv", csv_bytes, "text/csv")),
            ("files", ("declaration.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("undertaking.txt", txt_bytes, "text/plain")),
        ]

        response = self.client.post("/api/documents/extract", files=files)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 3)
        self.assertEqual(len(data["documents"]), 3)

        doc_formats = [d["file_format"] for d in data["documents"]]
        self.assertIn("csv", doc_formats)
        self.assertIn("docx", doc_formats)
        self.assertIn("txt", doc_formats)

    @patch("app.api.main.run_master_verification", new_callable=AsyncMock)
    def test_verify_bid_multi_files(self, mock_run_verification):
        """Tests POST /api/verify/bid with multiple bidder files (PDF + CSV + DOCX)."""
        mock_run_verification.return_value = {
            "tender_id": "TENDER-2026-MULTI",
            "requirement": {"requirement_id": "REQ-TURNOVER"},
            "extracted_evidence": {"is_present": True, "source_quote": "Annual Turnover INR 4.5 Cr"},
            "compliance_finding": {"state": "COMPLIANT", "recommendation": "ACCEPT"},
            "final_recommendation": "ACCEPT",
        }

        tender_bytes = b"%PDF-1.4 dummy tender bytes"
        bidder_csv = b"Year,Turnover\n2023,45000000\n"
        bidder_docx = _create_sample_docx(["Turnover CA Certificate: Certified turnover is 4.5 Crore."])

        files = [
            ("tender_file", ("tender.pdf", tender_bytes, "application/pdf")),
            ("bidder_files", ("turnover.csv", bidder_csv, "text/csv")),
            ("bidder_files", ("ca_audit.docx", bidder_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
        ]
        data = {"requirement_id": "REQ-TURNOVER"}

        response = self.client.post("/api/verify/bid", files=files, data=data)
        self.assertEqual(response.status_code, 200)
        json_resp = response.json()
        self.assertEqual(json_resp["final_recommendation"], "ACCEPT")

        # Verify mock received multiple bidder documents
        mock_run_verification.assert_called_once()
        call_kwargs = mock_run_verification.call_args.kwargs
        bidder_doc_bytes = call_kwargs["bidder_doc_bytes"]
        self.assertIsInstance(bidder_doc_bytes, list)
        self.assertEqual(len(bidder_doc_bytes), 2)
        filenames = [item[0] for item in bidder_doc_bytes]
        self.assertIn("turnover.csv", filenames)
        self.assertIn("ca_audit.docx", filenames)

    @patch("app.api.main.run_master_verification", new_callable=AsyncMock)
    def test_verify_bid_legacy_single_file(self, mock_run_verification):
        """Tests POST /api/verify/bid backward compatibility with single bidder_file."""
        mock_run_verification.return_value = {
            "tender_id": "TENDER-LEGACY-01",
            "requirement": {"requirement_id": "REQ-GST"},
            "extracted_evidence": {"is_present": True},
            "compliance_finding": {"state": "COMPLIANT", "recommendation": "ACCEPT"},
            "final_recommendation": "ACCEPT",
        }

        tender_bytes = b"%PDF-1.4 dummy tender"
        bidder_bytes = b"%PDF-1.4 dummy single bidder"

        files = {
            "tender_file": ("tender.pdf", tender_bytes, "application/pdf"),
            "bidder_file": ("bidder_gst.pdf", bidder_bytes, "application/pdf"),
        }
        data = {"requirement_id": "REQ-GST"}

        response = self.client.post("/api/verify/bid", files=files, data=data)
        self.assertEqual(response.status_code, 200)
        mock_run_verification.assert_called_once()


if __name__ == "__main__":
    unittest.main()
