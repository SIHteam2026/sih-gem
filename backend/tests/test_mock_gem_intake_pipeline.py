"""Integration tests for Mock-GeM Intake Pipeline (Master Prompt 7).

Verifies:
1. Real multipart ingestion of tender PDF and multiple bidder ZIP packages.
2. Multiple bidders creation under one tender with classified evidence documents.
3. Procurement persistence in runtime store and automatic discovery by Workspace GET /api/procurements.
4. Second tender ingestion creates a second independent procurement card.
5. Ingested procurement is connected to Command Page with deadline gate passed (ready for scrutiny).
6. Honest rejection of invalid or incomplete uploads (missing tender PDF, empty files, non-zip).
"""

import io
import json
import zipfile
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
import app.db.client as db_client


@pytest.fixture
def mock_gem_test_env(tmp_path, monkeypatch):
    """Isolates runtime store and seed store for Mock-GeM tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    runtime_store = data_dir / "procurement_store.json"
    seed_store = data_dir / "procurement_seed.json"

    real_seed = Path(__file__).resolve().parent.parent / "data" / "procurement_seed.json"
    if real_seed.exists():
        seed_store.write_text(real_seed.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        seed_store.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(db_client, "_DATA_DIR", data_dir)
    monkeypatch.setattr(db_client, "_LOCAL_STORE_PATH", runtime_store)
    monkeypatch.setattr(db_client, "_SEED_STORE_PATH", seed_store)

    db_client._IN_MEMORY_PROCUREMENTS.clear()
    db_client._IN_MEMORY_TENDERS.clear()
    db_client._IN_MEMORY_BIDDERS.clear()
    db_client._IN_MEMORY_SUBMISSIONS.clear()
    db_client._IN_MEMORY_DOCUMENTS.clear()
    db_client._IN_MEMORY_REQUIREMENTS.clear()
    db_client._IN_MEMORY_FINANCIAL_EVALUATIONS.clear()
    db_client._IN_MEMORY_CLARIFICATIONS.clear()
    db_client._IN_MEMORY_AUDIT_LOGS.clear()

    # Initial fresh load creates empty runtime store
    db_client._load_local_store()

    yield {
        "runtime_store": runtime_store,
        "seed_store": seed_store,
    }


import fitz


def _create_dummy_pdf(text: str = "Sample PDF text") -> bytes:
    """Returns a valid PDF byte string containing the specified text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    return doc.write()


def _create_bidder_zip(bidder_name: str, doc_names: list) -> bytes:
    """Creates an in-memory ZIP containing dummy PDF documents for a bidder."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for d_name in doc_names:
            pdf_b = _create_dummy_pdf(f"Document {d_name} for {bidder_name}")
            zf.writestr(d_name, pdf_b)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_mock_gem_multipart_ingestion_and_workspace_discovery(mock_gem_test_env):
    """Verifies that uploading a tender PDF and multiple bidder ZIPs creates a real procurement case
    that is immediately discoverable via GET /api/procurements.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Initial workspace is empty
        list_res0 = await ac.get("/api/procurements")
        assert list_res0.status_code == 200
        assert list_res0.json()["total"] == 0

        # Build multipart payload with 1 tender PDF and 2 bidder ZIPs
        tender_pdf_bytes = _create_dummy_pdf(
            "Notice Inviting Tender for Indian Oil Corporation. Clause 1: Mandatory GST. Clause 2: Local Content 20%."
        )
        bidder1_zip_bytes = _create_bidder_zip("HydroTech", ["GST_Certificate.pdf", "MII_LocalContent.pdf"])
        bidder2_zip_bytes = _create_bidder_zip("CleanFlow", ["GST_Registration.pdf", "Turnover_Audit.pdf"])

        files = [
            ("tender_pdf", ("NIT_IOCL_Tender.pdf", tender_pdf_bytes, "application/pdf")),
            ("bidder_zips", ("Bidder_HydroTech.zip", bidder1_zip_bytes, "application/zip")),
            ("bidder_zips", ("Bidder_CleanFlow.zip", bidder2_zip_bytes, "application/zip")),
        ]
        data = {
            "title": "IOCL High Pressure Sensors Package",
            "organization": "Indian Oil Corporation Limited",
        }

        ingest_res = await ac.post("/api/ingest/mock-gem/upload", files=files, data=data)
        assert ingest_res.status_code == 200, f"Ingestion failed: {ingest_res.text}"
        res_data = ingest_res.json()

        assert res_data["was_created"] is True
        assert res_data["bidder_count"] == 2
        assert res_data["submission_count"] == 2
        assert res_data["document_count"] >= 4
        proc_id = res_data["procurement_id"]
        assert proc_id

        # Check Workspace discovery: GET /api/procurements
        list_res1 = await ac.get("/api/procurements")
        assert list_res1.status_code == 200
        procs = list_res1.json()["procurements"]
        assert len(procs) == 1
        assert procs[0]["id"] == proc_id
        assert procs[0]["title"] == "IOCL High Pressure Sensors Package"
        assert procs[0]["organization"] == "Indian Oil Corporation Limited"


@pytest.mark.asyncio
async def test_second_tender_creates_second_independent_procurement_card(mock_gem_test_env):
    """Verifies that ingesting a second tender package creates a second independent procurement card."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Tender 1
        files1 = [
            ("tender_pdf", ("Tender_Water_Sensors.pdf", _create_dummy_pdf("Tender for CPCL"), "application/pdf")),
            ("bidder_zips", ("Bidder_Alpha.zip", _create_bidder_zip("Alpha", ["GST_Doc.pdf"]), "application/zip")),
        ]
        res1 = await ac.post("/api/ingest/mock-gem/upload", files=files1, data={"title": "CPCL Water Project"})
        assert res1.status_code == 200
        id1 = res1.json()["procurement_id"]

        # Tender 2
        files2 = [
            ("tender_pdf", ("Tender_Solar_Panels.pdf", _create_dummy_pdf("Tender for NTPC"), "application/pdf")),
            ("bidder_zips", ("Bidder_Beta.zip", _create_bidder_zip("Beta", ["GST_Doc.pdf"]), "application/zip")),
            ("bidder_zips", ("Bidder_Gamma.zip", _create_bidder_zip("Gamma", ["GST_Doc.pdf"]), "application/zip")),
        ]
        res2 = await ac.post("/api/ingest/mock-gem/upload", files=files2, data={"title": "NTPC Solar Project"})
        assert res2.status_code == 200
        id2 = res2.json()["procurement_id"]

        assert id1 != id2

        # Verify Workspace returns both independent cards
        list_res = await ac.get("/api/procurements")
        assert list_res.status_code == 200
        items = list_res.json()["procurements"]
        assert len(items) == 2
        found_ids = {p["id"] for p in items}
        assert id1 in found_ids
        assert id2 in found_ids


@pytest.mark.asyncio
async def test_procurement_with_extracted_deadline_and_explicit_bidder_names(mock_gem_test_env):
    """Verifies that tender with explicit deadline text extracts submission_deadline and applies explicit bidder names."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        tender_text = (
            "NOTICE INVITING TENDER\n"
            "Tender Ref: CPCL/WQM/2026/017\n"
            "Closing Date: 15-September-2026 15:00 IST\n"
            "Estimated Value: Rs. 4,50,00,000\n"
            "Clause 1: Valid GST Registration required.\n"
        )
        files = [
            ("tender_pdf", ("Tender_Spec.pdf", _create_dummy_pdf(tender_text), "application/pdf")),
            ("bidder_zips", ("Bidder_1.zip", _create_bidder_zip("Bidder1", ["GST.pdf", "MII.pdf"]), "application/zip")),
        ]
        data = {
            "bidder_names": ["HydroTech Environmental Solutions Pvt Ltd"],
        }
        res = await ac.post("/api/ingest/mock-gem/upload", files=files, data=data)
        assert res.status_code == 200
        proc_id = res.json()["procurement_id"]

        # Detail endpoint (Command Page data source)
        detail_res = await ac.get(f"/api/procurements/{proc_id}")
        assert detail_res.status_code == 200
        detail = detail_res.json()

        assert detail["id"] == proc_id
        assert len(detail["tenders"]) == 1
        tender = detail["tenders"][0]
        assert tender["submission_deadline"] is not None
        assert "2026-09-15" in tender["submission_deadline"]
        # Verify explicit bidder legal name
        assert len(tender["submissions"]) == 1
        assert tender["submissions"][0]["bidder"]["legal_name"] == "HydroTech Environmental Solutions Pvt Ltd"


@pytest.mark.asyncio
async def test_procurement_without_deadline_locks_technical_scrutiny(mock_gem_test_env):
    """Verifies that a tender without any deadline text results in submission_deadline=None,
    and attempting technical scrutiny is rejected with 400.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        tender_text = "Notice Inviting Tender without any closing date or deadline mentioned."
        files = [
            ("tender_pdf", ("Tender_No_Deadline.pdf", _create_dummy_pdf(tender_text), "application/pdf")),
            ("bidder_zips", ("Bidder_A.zip", _create_bidder_zip("BidderA", ["GST.pdf"]), "application/zip")),
        ]
        res = await ac.post("/api/ingest/mock-gem/upload", files=files)
        assert res.status_code == 200
        proc_id = res.json()["procurement_id"]

        # Detail endpoint
        detail_res = await ac.get(f"/api/procurements/{proc_id}")
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["tenders"][0]["submission_deadline"] is None

        # Attempt to run technical scrutiny must be rejected with 400
        scrutiny_res = await ac.post(f"/api/procurements/{proc_id}/technical-scrutiny/run")
        assert scrutiny_res.status_code == 400
        assert "deadline" in scrutiny_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_incomplete_or_invalid_uploads_rejected_honestly(mock_gem_test_env):
    """Verifies that invalid uploads (missing files, non-pdf tender, invalid zip) are rejected with 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Non-PDF tender file
        files_bad_tender = [
            ("tender_pdf", ("tender.docx", b"not a pdf", "application/octet-stream")),
            ("bidder_zips", ("bidder.zip", _create_bidder_zip("B1", ["gst.pdf"]), "application/zip")),
        ]
        res1 = await ac.post("/api/ingest/mock-gem/upload", files=files_bad_tender)
        assert res1.status_code == 400
        assert "Only .pdf files are accepted" in res1.json()["detail"]

        # Non-ZIP bidder file
        files_bad_bidder = [
            ("tender_pdf", ("tender.pdf", _create_dummy_pdf(), "application/pdf")),
            ("bidder_zips", ("bidder.txt", b"not a zip", "text/plain")),
        ]
        res2 = await ac.post("/api/ingest/mock-gem/upload", files=files_bad_bidder)
        assert res2.status_code == 400
        assert "Only .zip archives are accepted" in res2.json()["detail"]
