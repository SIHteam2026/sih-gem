"""Integration tests for multi-format document extraction in the canonical OPAL architecture.

Validates:
1. Multi-format canonical document processing (PDF, CSV, DOCX, XLSX, TXT)
2. Uniform ExtractedDocumentContent contract and serialization to Document.content_text
3. Format-specific provenance retention:
   - PDF: genuine page_number
   - XLSX: sheet_name, row_number, cell location, page_number=None
   - CSV: row_number, column headers, page_number=None
   - DOCX: paragraphs, sections, tables, page_number=None
   - TXT: raw text, encoding fallback, page_number=None
4. Multi-bidder isolation with identical filenames (no ID collisions or cross-contamination)
5. Security guards: max file size and zip bomb protection
6. Graceful malformed / empty file handling
7. Canonical requirement mapping and evidence reconciliation across diverse formats
8. Verification that extraction phase contains zero compliance evaluation logic
"""

import html
import io
import json
import unittest
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from backend.app.models.document import ExtractedDocumentContent
from backend.app.models.evidence import (
    BidderClaim,
    EvidenceObservation,
    ProvenanceRecord,
)
from backend.app.models.procurement import (
    Document,
    DocumentType,
)
from backend.app.models.tender_contract import (
    CanonicalEvaluationField,
    EvaluationMode,
    RequirementCategory,
    RequirementEvaluationContract,
)
from backend.app.services.claim_extraction_service import (
    extract_document_facts,
    process_document_evidence,
)
from backend.app.services.contradiction_service import (
    build_provenance_from_claim,
    build_provenance_from_evidence,
    detect_contradictions,
    reconcile_requirement,
)
from backend.app.services.document_processor import (
    process_canonical_document,
)
from backend.app.models.evaluation import ComplianceState
from backend.app.services.evaluation_service import (
    evaluate_requirement,
    evaluate_requirements,
)
from backend.app.services.multi_format_extractor import (
    MAX_FILE_SIZE,
    _safe_check_zip,
    detect_file_format,
    extract_data_from_file,
)
from backend.app.services.requirement_mapping_service import (
    map_evidence_to_requirements,
)


def _create_sample_docx(paragraphs: List[str], table_rows: Optional[List[List[str]]] = None) -> bytes:
    """Helper to create an in-memory DOCX OOXML package."""
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


def _create_sample_xlsx(sheet_name: str, headers: List[str], rows: List[List[str]]) -> bytes:
    """Helper to create an in-memory XLSX OOXML package."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        # Collect unique shared strings
        all_strings = list(headers)
        for r in rows:
            for val in r:
                if val not in all_strings:
                    all_strings.append(val)

        str_to_idx = {s: idx for idx, s in enumerate(all_strings)}

        si_xml = "".join(f"<si><t>{html.escape(s)}</t></si>" for s in all_strings)
        ss_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{si_xml}</sst>"""
        z.writestr("xl/sharedStrings.xml", ss_xml.encode("utf-8"))

        row_xml_list = []
        # Row 1: Headers
        h_cells = [f'<c t="s"><v>{str_to_idx[h]}</v></c>' for h in headers]
        row_xml_list.append(f'<row r="1">{"".join(h_cells)}</row>')

        # Rows 2+: Data
        for r_idx, row in enumerate(rows, start=2):
            c_cells = [f'<c t="s"><v>{str_to_idx[val]}</v></c>' for val in row]
            row_xml_list.append(f'<row r="{r_idx}">{"".join(c_cells)}</row>')

        sheet_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>{"".join(row_xml_list)}</sheetData>
</worksheet>"""
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml.encode("utf-8"))
    return buf.getvalue()


def _make_dummy_doc(
    doc_id: str,
    filename: str,
    doc_type: Optional[DocumentType] = None,
    content_text: Optional[str] = None,
    bidder_id: str = "BID-001",
    submission_id: str = "SUB-001",
    mime_type: str = "application/octet-stream",
) -> Document:
    """Helper to build a canonical Document model instance for testing."""
    return Document(
        id=doc_id,
        procurement_id="PROC-001",
        tender_id="TND-001",
        bid_submission_id=submission_id,
        filename=filename,
        document_type=doc_type,
        mime_type=mime_type,
        file_size=len(content_text or ""),
        content_text=content_text,
        processing_status="PROCESSED" if content_text else "PENDING",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestMultiFormatCanonicalDocuments(unittest.IsolatedAsyncioTestCase):
    """Integration test suite for multi-format document extraction in canonical OPAL."""

    # -----------------------------------------------------------------------
    # 1. Format-Aware Extraction Contract
    # -----------------------------------------------------------------------
    async def test_csv_extraction_contract(self):
        """CSV extractor returns ExtractedDocumentContent with structured tables and row locations."""
        csv_bytes = (
            "Year,Turnover_INR,UDIN_Reference\n"
            "2022-2023,55000000,23049182UDIN001\n"
            "2023-2024,62000000,24049182UDIN002\n"
        ).encode("utf-8")

        res = await extract_data_from_file(csv_bytes, "financials.csv")
        self.assertIsInstance(res, ExtractedDocumentContent)
        self.assertEqual(res.file_format, "csv")
        self.assertEqual(len(res.tables), 1)
        self.assertEqual(res.tables[0]["headers"], ["Year", "Turnover_INR", "UDIN_Reference"])
        self.assertEqual(len(res.tables[0]["rows"]), 2)
        self.assertIn("62000000", res.raw_text)
        self.assertEqual(len(res.source_locations), 2)
        self.assertEqual(res.source_locations[0]["row_number"], 1)
        self.assertEqual(res.source_locations[1]["row_number"], 2)

    async def test_docx_extraction_contract(self):
        """DOCX extractor returns ExtractedDocumentContent with sections, paragraphs, and tables."""
        paragraphs = [
            "TECHNICAL COMPLIANCE DECLARATION",
            "Make in India local content declared is 72% for this proposal.",
            "Standard 36 Months comprehensive warranty will be provided.",
        ]
        tables = [
            ["Contract_Ref", "Client", "Value_INR"],
            ["PO-2023-01", "CPCL Refineries", "15000000"],
            ["PO-2023-02", "IOCL Pipelines", "22000000"],
        ]
        docx_bytes = _create_sample_docx(paragraphs, tables)

        res = await extract_data_from_file(docx_bytes, "technical_bid.docx")
        self.assertIsInstance(res, ExtractedDocumentContent)
        self.assertEqual(res.file_format, "docx")
        self.assertIn("72%", res.raw_text)
        self.assertIn("36 Months", res.raw_text)
        self.assertEqual(len(res.tables), 1)
        self.assertEqual(res.tables[0]["headers"], ["Contract_Ref", "Client", "Value_INR"])
        self.assertEqual(len(res.tables[0]["rows"]), 2)
        self.assertTrue(len(res.sections) >= 1)

    async def test_xlsx_extraction_contract(self):
        """XLSX extractor returns ExtractedDocumentContent with sheet-aware tables and rows."""
        headers = ["FY", "Annual_Turnover", "Auditor_CA"]
        rows = [
            ["2022-23", "48000000", "Sharma & Co CA"],
            ["2023-24", "56000000", "Sharma & Co CA"],
        ]
        xlsx_bytes = _create_sample_xlsx("Turnover_Details", headers, rows)

        res = await extract_data_from_file(xlsx_bytes, "ca_turnover.xlsx")
        self.assertIsInstance(res, ExtractedDocumentContent)
        self.assertEqual(res.file_format, "xlsx")
        self.assertIn("48000000", res.raw_text)
        self.assertIn("56000000", res.raw_text)
        self.assertEqual(len(res.tables), 1)
        self.assertEqual(res.tables[0]["headers"], headers)
        self.assertEqual(len(res.tables[0]["rows"]), 2)
        self.assertTrue(any(loc.get("row_number") == 1 for loc in res.source_locations))

    async def test_txt_extraction_contract(self):
        """TXT extractor returns ExtractedDocumentContent with auto-encoding."""
        txt_content = "Manufacturer Authorization Form: We authorize Apex Ltd to supply CPCL sensors."
        txt_bytes = txt_content.encode("utf-8")

        res = await extract_data_from_file(txt_bytes, "oem_maf.txt")
        self.assertIsInstance(res, ExtractedDocumentContent)
        self.assertEqual(res.file_format, "txt")
        self.assertIn("Manufacturer Authorization Form", res.raw_text)
        self.assertEqual(res.page_count, 1)

    # -----------------------------------------------------------------------
    # 2. Canonical Document Processor Serialization
    # -----------------------------------------------------------------------
    @patch("backend.app.services.document_processor.get_supabase_client")
    async def test_canonical_document_processor_serializes_normalized_content(self, mock_get_client):
        """process_canonical_document serializes ExtractedDocumentContent to Document.content_text."""
        mock_db = MagicMock()
        mock_get_client.return_value = mock_db

        doc_id = "DOC-UUID-1234"
        doc_record = {
            "id": doc_id,
            "procurement_id": "PROC-001",
            "tender_id": "TND-001",
            "bid_submission_id": "SUB-001",
            "filename": "ca_turnover_schedule.csv",
            "mime_type": "text/csv",
            "processing_status": "PENDING",
            "content_text": None,
        }

        # Mock select query
        mock_db.table().select().eq().execute.return_value = MagicMock(data=[doc_record])

        # Capture update call
        update_calls = []

        def fake_update(data):
            update_calls.append(data)
            return MagicMock(eq=lambda col, val: MagicMock(execute=lambda: MagicMock(data=[{**doc_record, **data}])))

        mock_db.table().update.side_effect = fake_update

        csv_bytes = "Year,Turnover,UDIN\n2023-24,52000000,24049182UDIN001\n".encode("utf-8")
        updated_doc = await process_canonical_document(doc_id, csv_bytes)

        self.assertIsNotNone(updated_doc.content_text)
        payload = json.loads(updated_doc.content_text)
        self.assertEqual(payload["file_format"], "csv")
        self.assertEqual(payload["filename"], "ca_turnover_schedule.csv")
        self.assertEqual(len(payload["tables"]), 1)
        self.assertEqual(updated_doc.processing_status, "PROCESSED")
        self.assertEqual(updated_doc.document_type, DocumentType.TURNOVER_CERTIFICATE)

    # -----------------------------------------------------------------------
    # 3. Provenance Retention Across Formats
    # -----------------------------------------------------------------------
    def test_pdf_provenance_retention(self):
        """PDF extraction preserves true 1-indexed page_number."""
        pdf_doc = _make_dummy_doc(
            doc_id="DOC-PDF-01",
            filename="audited_financials.pdf",
            doc_type=DocumentType.TURNOVER_CERTIFICATE,
            content_text=json.dumps({
                "file_format": "pdf",
                "filename": "audited_financials.pdf",
                "pages": [
                    {"page": 1, "text": "Cover page and table of contents"},
                    {"page": 2, "text": "Audited Annual Turnover is INR 65 Crore for FY 2024. UDIN: 24049182UDIN"},
                ],
                "tables": [],
            }),
        )

        facts = extract_document_facts(pdf_doc, bidder_id="BIDDER-A", submission_id="SUB-A")
        self.assertEqual(len(facts["observations"]), 1)
        obs = facts["observations"][0]
        self.assertEqual(obs.page_number, 2)
        self.assertIsNone(obs.sheet_name)
        self.assertIsNone(obs.row_number)
        self.assertEqual(obs.source_format, "pdf")

        # ProvenanceRecord conversion
        prov = build_provenance_from_evidence(obs)[0]
        self.assertEqual(prov.page_number, 2)
        self.assertEqual(prov.source_format, "pdf")

    def test_csv_provenance_retention(self):
        """CSV extraction retains row_number and location_context, with page_number=None."""
        csv_doc = _make_dummy_doc(
            doc_id="DOC-CSV-01",
            filename="turnover_sheet.csv",
            doc_type=DocumentType.TURNOVER_CERTIFICATE,
            content_text=json.dumps({
                "file_format": "csv",
                "filename": "turnover_sheet.csv",
                "tables": [{
                    "sheet": None,
                    "headers": ["Financial_Year", "Turnover_INR", "UDIN"],
                    "rows": [
                        ["2022-2023", "45000000", "23049182UDIN001"],
                        ["2023-2024", "52000000", "24049182UDIN002"],
                    ],
                }],
                "pages": [{"page": 1, "text": "CSV Content"}],
            }),
        )

        facts = extract_document_facts(csv_doc, bidder_id="BIDDER-A", submission_id="SUB-A")
        self.assertEqual(len(facts["observations"]), 2)

        obs1 = facts["observations"][0]
        self.assertIsNone(obs1.page_number)  # MUST NOT fabricate fake PDF page
        self.assertEqual(obs1.row_number, 1)
        self.assertEqual(obs1.source_format, "csv")
        self.assertIn("Row: 1", obs1.location_context)

        prov1 = build_provenance_from_evidence(obs1)[0]
        self.assertIsNone(prov1.page_number)
        self.assertEqual(prov1.row_number, 1)
        self.assertEqual(prov1.source_format, "csv")

    def test_xlsx_provenance_retention(self):
        """XLSX extraction retains sheet_name and row_number, with page_number=None."""
        xlsx_doc = _make_dummy_doc(
            doc_id="DOC-XLSX-01",
            filename="commercial_financials.xlsx",
            doc_type=DocumentType.TURNOVER_CERTIFICATE,
            content_text=json.dumps({
                "file_format": "xlsx",
                "filename": "commercial_financials.xlsx",
                "tables": [{
                    "sheet": "Turnover_Schedule",
                    "headers": ["Year", "Annual_Turnover", "UDIN_Number"],
                    "rows": [
                        ["2023-24", "58000000", "24049182UDIN999"],
                    ],
                }],
                "pages": [{"page": 1, "text": "Sheet: Turnover_Schedule"}],
            }),
        )

        facts = extract_document_facts(xlsx_doc, bidder_id="BIDDER-A", submission_id="SUB-A")
        self.assertEqual(len(facts["observations"]), 1)

        obs = facts["observations"][0]
        self.assertIsNone(obs.page_number)
        self.assertEqual(obs.sheet_name, "Turnover_Schedule")
        self.assertEqual(obs.row_number, 1)
        self.assertEqual(obs.source_format, "xlsx")
        self.assertIn("Sheet: Turnover_Schedule", obs.location_context)

        prov = build_provenance_from_evidence(obs)[0]
        self.assertIsNone(prov.page_number)
        self.assertEqual(prov.sheet_name, "Turnover_Schedule")
        self.assertEqual(prov.row_number, 1)
        self.assertEqual(prov.source_format, "xlsx")

    def test_docx_provenance_retention(self):
        """DOCX extraction retains location_context and source_format without fake page numbers."""
        docx_doc = _make_dummy_doc(
            doc_id="DOC-DOCX-01",
            filename="undertaking.docx",
            doc_type=DocumentType.OTHER,
            content_text=json.dumps({
                "file_format": "docx",
                "filename": "undertaking.docx",
                "pages": [{
                    "page": 1,
                    "text": "UNDERTAKING: We confirm that our company is not blacklisted or debarred by any PSU.",
                }],
                "tables": [],
            }),
        )

        facts = extract_document_facts(docx_doc, bidder_id="BIDDER-A", submission_id="SUB-A")
        self.assertEqual(len(facts["observations"]), 1)
        obs = facts["observations"][0]
        self.assertIsNone(obs.page_number)
        self.assertEqual(obs.source_format, "docx")
        self.assertEqual(obs.observed_value, "CLEAR")

    def test_txt_provenance_retention(self):
        """TXT extraction tags source_format='txt'."""
        txt_doc = _make_dummy_doc(
            doc_id="DOC-TXT-01",
            filename="oem_maf.txt",
            doc_type=DocumentType.OEM_AUTHORIZATION,
            content_text=json.dumps({
                "file_format": "txt",
                "filename": "oem_maf.txt",
                "pages": [{
                    "page": 1,
                    "text": "Manufacturer Authorization Form: Authorized partner for CPCL project.",
                }],
                "tables": [],
            }),
        )

        facts = extract_document_facts(txt_doc, bidder_id="BIDDER-A", submission_id="SUB-A")
        self.assertEqual(len(facts["observations"]), 1)
        obs = facts["observations"][0]
        self.assertEqual(obs.source_format, "txt")
        self.assertEqual(obs.observed_value, "AUTHORIZED")

    # -----------------------------------------------------------------------
    # 4. Multi-Bidder Isolation with Identical Filenames
    # -----------------------------------------------------------------------
    def test_multi_bidder_isolation_with_identical_filenames(self):
        """Documents with identical filenames across different bidders maintain distinct canonical identity."""
        # Bidder 1 document
        doc_b1 = _make_dummy_doc(
            doc_id="DOC-B1-001",
            filename="turnover_certificate.csv",
            doc_type=DocumentType.TURNOVER_CERTIFICATE,
            bidder_id="BIDDER-ALPHA",
            submission_id="SUB-ALPHA",
            content_text=json.dumps({
                "file_format": "csv",
                "filename": "turnover_certificate.csv",
                "tables": [{
                    "headers": ["Year", "Turnover", "UDIN"],
                    "rows": [["2023-24", "45000000", "UDIN-ALPHA-01"]],
                }],
            }),
        )

        # Bidder 2 document with same filename
        doc_b2 = _make_dummy_doc(
            doc_id="DOC-B2-001",
            filename="turnover_certificate.csv",
            doc_type=DocumentType.TURNOVER_CERTIFICATE,
            bidder_id="BIDDER-BETA",
            submission_id="SUB-BETA",
            content_text=json.dumps({
                "file_format": "csv",
                "filename": "turnover_certificate.csv",
                "tables": [{
                    "headers": ["Year", "Turnover", "UDIN"],
                    "rows": [["2023-24", "85000000", "UDIN-BETA-01"]],
                }],
            }),
        )

        facts_b1 = extract_document_facts(doc_b1, bidder_id="BIDDER-ALPHA", submission_id="SUB-ALPHA")
        facts_b2 = extract_document_facts(doc_b2, bidder_id="BIDDER-BETA", submission_id="SUB-BETA")

        # Verify Bidder 1 claims/observations
        obs_b1 = facts_b1["observations"][0]
        self.assertEqual(obs_b1.bidder_id, "BIDDER-ALPHA")
        self.assertEqual(obs_b1.bid_submission_id, "SUB-ALPHA")
        self.assertEqual(obs_b1.document_id, "DOC-B1-001")
        self.assertEqual(obs_b1.observed_value, 45000000.0)

        # Verify Bidder 2 claims/observations
        obs_b2 = facts_b2["observations"][0]
        self.assertEqual(obs_b2.bidder_id, "BIDDER-BETA")
        self.assertEqual(obs_b2.bid_submission_id, "SUB-BETA")
        self.assertEqual(obs_b2.document_id, "DOC-B2-001")
        self.assertEqual(obs_b2.observed_value, 85000000.0)

        # Confirm no cross-contamination
        self.assertNotEqual(obs_b1.document_id, obs_b2.document_id)
        self.assertNotEqual(obs_b1.bidder_id, obs_b2.bidder_id)

    # -----------------------------------------------------------------------
    # 5. Security & Edge Case Handling
    # -----------------------------------------------------------------------
    async def test_oversized_file_handling(self):
        """Oversized file returns ExtractedDocumentContent with oversized status without memory explosion."""
        large_bytes = b"0" * (MAX_FILE_SIZE + 1024)
        res = await extract_data_from_file(large_bytes, "huge_file.csv")

        self.assertIsInstance(res, ExtractedDocumentContent)
        self.assertEqual(res.file_format, "oversized")
        self.assertEqual(res.metadata.get("error"), "FILE_TOO_LARGE")

    def test_zip_bomb_protection(self):
        """Zip archive with excessive uncompressed size is rejected."""
        mock_zip = MagicMock()
        mock_info = MagicMock()
        mock_info.file_size = 200 * 1024 * 1024  # 200MB > 100MB limit
        mock_zip.infolist.return_value = [mock_info]

        with self.assertRaises(ValueError) as ctx:
            _safe_check_zip(mock_zip)
        self.assertIn("exceeds safety limit", str(ctx.exception))

    async def test_corrupted_binary_handling(self):
        """Corrupted/unknown binary file is handled gracefully without crashing."""
        garbage_bytes = b"\x00\x01\x02\x03\xff\xfe\x00\x00\x12\x34\x56"
        res = await extract_data_from_file(garbage_bytes, "corrupt.dat")

        self.assertIsInstance(res, ExtractedDocumentContent)
        self.assertIn(res.file_format, ("unknown", "txt"))
        self.assertIsNotNone(res.raw_text)

    async def test_empty_file_handling(self):
        """Empty byte payload returns clean empty extraction."""
        res = await extract_data_from_file(b"", "empty_document.pdf")
        self.assertEqual(res.file_format, "empty")
        self.assertEqual(res.raw_text, "")
        self.assertEqual(res.page_count, 0)

    # -----------------------------------------------------------------------
    # 6. Synthetic CPCL Benchmark End-to-End Multi-Format Pipeline
    # -----------------------------------------------------------------------
    def test_cpcl_multi_format_end_to_end_reconciliation(self):
        """Multi-format submission for CPCL tender is mapped and evaluated format-agnostically."""
        # 1. Tender Requirements for CPCL Water Quality Sensors
        req_turnover = RequirementEvaluationContract(
            requirement_id="REQ-TURNOVER",
            category=RequirementCategory.FINANCIAL_TURNOVER,
            title="Annual Turnover",
            description="Minimum average annual turnover of INR 50,000,000 required.",
            evaluation_mode=EvaluationMode.DETERMINISTIC,
            evaluation_field=CanonicalEvaluationField.AVERAGE_ANNUAL_TURNOVER,
            operator=">=",
            threshold_value=50000000.0,
            threshold_unit="INR",
            mandatory=True,
        )
        req_lc = RequirementEvaluationContract(
            requirement_id="REQ-LOCAL-CONTENT",
            category=RequirementCategory.LOCAL_CONTENT_MII,
            title="Make in India Local Content",
            description="Minimum 50% local content required under MII policy.",
            evaluation_mode=EvaluationMode.DETERMINISTIC,
            evaluation_field=CanonicalEvaluationField.LOCAL_CONTENT_PERCENTAGE,
            operator=">=",
            threshold_value=50.0,
            threshold_unit="PERCENT",
            mandatory=True,
        )
        req_warranty = RequirementEvaluationContract(
            requirement_id="REQ-WARRANTY",
            category=RequirementCategory.DELIVERY_AND_SLA,
            title="Comprehensive Warranty",
            description="Minimum 24 months comprehensive onsite warranty required.",
            evaluation_mode=EvaluationMode.DETERMINISTIC,
            evaluation_field=CanonicalEvaluationField.WARRANTY_MONTHS,
            operator=">=",
            threshold_value=24.0,
            threshold_unit="MONTHS",
            mandatory=True,
        )
        requirements = [req_turnover, req_lc, req_warranty]

        # 2. Multi-Format Submissions from Bidder
        # Doc 1: Turnover in CSV
        doc_csv = _make_dummy_doc(
            doc_id="DOC-CPCL-CSV",
            filename="ca_audited_turnover.csv",
            doc_type=DocumentType.TURNOVER_CERTIFICATE,
            content_text=json.dumps({
                "file_format": "csv",
                "filename": "ca_audited_turnover.csv",
                "tables": [{
                    "headers": ["Financial_Year", "Turnover_INR", "UDIN"],
                    "rows": [["2023-24", "65000000", "24049182UDIN001"]],
                }],
            }),
        )

        # Doc 2: Local Content in DOCX
        doc_docx = _make_dummy_doc(
            doc_id="DOC-CPCL-DOCX",
            filename="ca_local_content_cert.docx",
            doc_type=DocumentType.OTHER,
            content_text=json.dumps({
                "file_format": "docx",
                "filename": "ca_local_content_cert.docx",
                "pages": [{
                    "page": 1,
                    "text": "Make in India Certificate: We certify 68% local content for CPCL sensors.",
                }],
            }),
        )

        # Doc 3: Warranty in TXT
        doc_txt = _make_dummy_doc(
            doc_id="DOC-CPCL-TXT",
            filename="warranty_commitment.txt",
            doc_type=DocumentType.TECHNICAL_BID,
            content_text=json.dumps({
                "file_format": "txt",
                "filename": "warranty_commitment.txt",
                "pages": [{
                    "page": 1,
                    "text": "Warranty Undertaking: 36 Months comprehensive onsite warranty provided.",
                }],
            }),
        )

        # 3. Extract facts from each document
        all_claims = []
        all_observations = []

        for d in [doc_csv, doc_docx, doc_txt]:
            f = extract_document_facts(d, bidder_id="BID-HYDROTECH", submission_id="SUB-HYDROTECH")
            all_claims.extend(f["claims"])
            all_observations.extend(f["observations"])

        # Verification: No compliance logic executed during extraction!
        for c in all_claims:
            self.assertFalse(hasattr(c, "status"))
        for o in all_observations:
            self.assertFalse(hasattr(o, "status"))

        # 4. Map facts format-agnostically to canonical requirements
        mapped_claims = map_evidence_to_requirements(all_claims, requirements)
        mapped_obs = map_evidence_to_requirements(all_observations, requirements)

        # Turnover mapped to REQ-TURNOVER
        turnover_obs = [o for o in mapped_obs if o.requirement_id == "REQ-TURNOVER"]
        self.assertEqual(len(turnover_obs), 1)
        self.assertEqual(turnover_obs[0].observed_value, 65000000.0)
        self.assertEqual(turnover_obs[0].source_format, "csv")
        self.assertEqual(turnover_obs[0].row_number, 1)

        # Local content mapped to REQ-LOCAL-CONTENT
        lc_obs = [o for o in mapped_obs if o.requirement_id == "REQ-LOCAL-CONTENT"]
        self.assertEqual(len(lc_obs), 1)
        self.assertEqual(lc_obs[0].observed_value, 68.0)
        self.assertEqual(lc_obs[0].source_format, "docx")

        # Warranty mapped to REQ-WARRANTY
        war_obs = [o for o in mapped_obs if o.requirement_id == "REQ-WARRANTY"]
        self.assertEqual(len(war_obs), 1)
        self.assertEqual(war_obs[0].observed_value, 36.0)
        self.assertEqual(war_obs[0].source_format, "txt")

        # 5. Run reconciliation and evaluation
        claims_by_req = {}
        for c in mapped_claims:
            claims_by_req.setdefault(c.requirement_id, []).append(c)
        evidence_by_req = {}
        for o in mapped_obs:
            evidence_by_req.setdefault(o.requirement_id, []).append(o)

        eval_results = evaluate_requirements(
            requirements=requirements,
            claims_by_req=claims_by_req,
            evidence_by_req=evidence_by_req,
            context={"bidder_id": "BID-HYDROTECH", "submission_id": "SUB-HYDROTECH"},
        )

        self.assertEqual(len(eval_results), 3)
        passed = [r for r in eval_results if r.state == ComplianceState.PASS]
        self.assertEqual(len(passed), 3)

        # Check that provenance records carry multi-format location context
        for r in eval_results:
            self.assertTrue(len(r.provenance) >= 1)
            p = r.provenance[0]
            self.assertIsNotNone(p.source_format)
            self.assertIn(p.source_format, ("csv", "docx", "txt"))


if __name__ == "__main__":
    unittest.main()
