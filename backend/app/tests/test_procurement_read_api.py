try:
    import pytest
except ImportError:
    pytest = None
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.api.main import app
from app.models.procurement import ProcurementStatus

client = TestClient(app)


# Mock data fixtures
MOCK_PROCUREMENT_ROW = {
    "id": "11111111-1111-1111-1111-111111111111",
    "external_reference": "MOCK-GEM-PROC-101",
    "title": "Hospital Medical Supplies Procurement 2026",
    "organization": "Ministry of Health & Family Welfare",
    "source_system": "MOCK_GEM",
    "status": "READY",
    "tender_count": 1,
    "bidder_count": 2,
    "document_count": 3,
    "created_at": "2026-09-04T12:00:00Z",
    "updated_at": "2026-09-04T12:00:00Z",
}

MOCK_TENDER_ROW = {
    "id": "22222222-2222-2222-2222-222222222222",
    "procurement_id": "11111111-1111-1111-1111-111111111111",
    "procurement_title": "Hospital Medical Supplies Procurement 2026",
    "procurement_external_reference": "MOCK-GEM-PROC-101",
    "source_system": "MOCK_GEM",
    "tender_reference": "GEM-TENDER-2026-001",
    "title": "Supply of Automated ICU Ventilators",
    "description": "Procurement of 50 units of Class-I ICU Ventilators",
    "estimated_value": 15000000.0,
    "category": "Medical Equipment",
    "status": "READY",
    "requirement_count": 4,
    "document_count": 1,
    "bidder_count": 2,
    "documents": [
        {
            "id": "doc-001",
            "procurement_id": "11111111-1111-1111-1111-111111111111",
            "tender_id": "22222222-2222-2222-2222-222222222222",
            "filename": "Tender_Specification_Ventilators.pdf",
            "document_type": "TECHNICAL_SPECIFICATION",
            "mime_type": "application/pdf",
            "file_size": 2048500,
            "storage_path": "tenders/doc-001.pdf",
            "processing_status": "COMPLETED",
        }
    ],
    "submissions": [
        {
            "id": "sub-001",
            "tender_id": "22222222-2222-2222-2222-222222222222",
            "bidder_id": "33333333-3333-3333-3333-333333333333",
            "external_submission_reference": "BID-SUB-101",
            "status": "SUBMITTED",
            "document_count": 1,
            "bidder": {
                "id": "33333333-3333-3333-3333-333333333333",
                "legal_name": "Apex MedTech Private Limited",
                "gstin": "07AAAAA0000A1Z5",
                "pan": "AAAAA0000A",
                "email": "contact@apexmedtech.in",
            },
            "documents": [
                {
                    "id": "doc-002",
                    "procurement_id": "11111111-1111-1111-1111-111111111111",
                    "bid_submission_id": "sub-001",
                    "filename": "Apex_Technical_Bid.pdf",
                    "document_type": "BIDDER_SUBMISSION",
                    "mime_type": "application/pdf",
                    "file_size": 1500000,
                    "storage_path": "submissions/doc-002.pdf",
                    "processing_status": "COMPLETED",
                }
            ],
        }
    ],
}

MOCK_SUBMISSION_ROW = MOCK_TENDER_ROW["submissions"][0]
MOCK_BIDDER_ROW = MOCK_SUBMISSION_ROW["bidder"]


@patch("app.db.client.list_procurements", new_callable=AsyncMock)
def test_list_procurements_success(mock_list):
    """Test GET /api/procurements lists procurements with pagination."""
    mock_list.return_value = {
        "items": [MOCK_PROCUREMENT_ROW],
        "total": 1,
        "limit": 50,
        "offset": 0,
    }

    response = client.get("/api/procurements?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert len(data["procurements"]) == 1
    item = data["procurements"][0]
    assert item["id"] == MOCK_PROCUREMENT_ROW["id"]
    assert item["external_reference"] == "MOCK-GEM-PROC-101"
    assert item["source_system"] == "MOCK_GEM"
    assert item["status"] == "READY"


@patch("app.db.client.get_procurement_detail_db", new_callable=AsyncMock)
def test_get_procurement_detail_success(mock_get):
    """Test GET /api/procurements/{id} returns detailed procurement workspace."""
    mock_get.return_value = {
        **MOCK_PROCUREMENT_ROW,
        "tenders": [MOCK_TENDER_ROW],
        "documents": [],
    }

    response = client.get(f"/api/procurements/{MOCK_PROCUREMENT_ROW['id']}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == MOCK_PROCUREMENT_ROW["id"]
    assert len(data["tenders"]) == 1
    tender = data["tenders"][0]
    assert tender["tender_reference"] == "GEM-TENDER-2026-001"
    assert tender["bidder_count"] == 1


@patch("app.db.client.get_procurement_detail_db", new_callable=AsyncMock)
def test_get_procurement_detail_not_found(mock_get):
    """Test GET /api/procurements/{id} returns 404 for non-existent ID."""
    mock_get.return_value = None

    response = client.get("/api/procurements/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]


@patch("app.db.client.get_tender_detail_db", new_callable=AsyncMock)
def test_get_tender_detail_success(mock_get):
    """Test GET /api/tenders/{id} returns detailed tender workspace."""
    mock_get.return_value = MOCK_TENDER_ROW

    response = client.get(f"/api/tenders/{MOCK_TENDER_ROW['id']}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == MOCK_TENDER_ROW["id"]
    assert data["procurement_title"] == "Hospital Medical Supplies Procurement 2026"
    assert data["requirement_count"] == 4
    assert len(data["documents"]) == 1
    assert "content_text" not in data["documents"][0]


@patch("app.db.client.get_tender_detail_db", new_callable=AsyncMock)
def test_get_tender_detail_not_found(mock_get):
    """Test GET /api/tenders/{id} returns 404 when tender missing."""
    mock_get.return_value = None

    response = client.get("/api/tenders/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@patch("app.db.client.get_tender_detail_db", new_callable=AsyncMock)
def test_list_tender_submissions_success(mock_get):
    """Test GET /api/tenders/{id}/submissions returns bidder submissions."""
    mock_get.return_value = MOCK_TENDER_ROW

    response = client.get(f"/api/tenders/{MOCK_TENDER_ROW['id']}/submissions")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["bidder"]["legal_name"] == "Apex MedTech Private Limited"


@patch("app.db.client.get_submission_detail_db", new_callable=AsyncMock)
def test_get_submission_detail_success(mock_get):
    """Test GET /api/submissions/{id} returns submission workspace detail."""
    mock_get.return_value = MOCK_SUBMISSION_ROW

    response = client.get(f"/api/submissions/{MOCK_SUBMISSION_ROW['id']}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == MOCK_SUBMISSION_ROW["id"]
    assert data["bidder"]["legal_name"] == "Apex MedTech Private Limited"


@patch("app.db.client.get_bidder_detail_db", new_callable=AsyncMock)
def test_get_bidder_detail_success(mock_get):
    """Test GET /api/bidders/{id} returns legal profile of bidder."""
    mock_get.return_value = MOCK_BIDDER_ROW

    response = client.get(f"/api/bidders/{MOCK_BIDDER_ROW['id']}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == MOCK_BIDDER_ROW["id"]
    assert data["legal_name"] == "Apex MedTech Private Limited"
    assert data["gstin"] == "07AAAAA0000A1Z5"
