"""Integration Tests for OPAL Mock-GeM Adapter Router.

Tests:
1. End-to-end ingestion via Mock-GeM demo endpoint (/api/ingest/mock-gem/demo).
2. Verification of source_system = 'MOCK_GEM' enforcement.
3. Idempotency test (re-submitting DEMO/CPCL/WQM/2026/017 returns existing record with was_created=False).
4. Custom payload ingestion via POST /api/ingest/mock-gem.
5. Error handling and validation error returns (400 Bad Request).
"""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)


def test_mock_gem_demo_ingestion_end_to_end():
    """Test 1: Ingest synthetic CPCL demo package via /api/ingest/mock-gem/demo."""
    response = client.post("/api/ingest/mock-gem/demo")
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}: {response.text}"

    data = response.json()
    assert data["source_system"] == "MOCK_GEM"
    assert data["external_reference"] == "DEMO/CPCL/WQM/2026/017"
    assert data["bidder_count"] == 2
    assert data["document_count"] >= 3
    assert data["status"] == "READY"
    print("[PASS] Test 1: Mock-GeM Demo Ingestion Endpoint (/api/ingest/mock-gem/demo) Validated")


def test_mock_gem_idempotency_end_to_end():
    """Test 2: Re-ingest exact same demo package and verify idempotency (was_created=False)."""
    # First call
    res1 = client.post("/api/ingest/mock-gem/demo")
    assert res1.status_code == 200
    data1 = res1.json()

    # Second call (duplicate payload)
    res2 = client.post("/api/ingest/mock-gem/demo")
    assert res2.status_code == 200
    data2 = res2.json()

    assert data2["procurement_id"] == data1["procurement_id"]
    assert data2["external_reference"] == "DEMO/CPCL/WQM/2026/017"
    assert data2["was_created"] is False
    print("[PASS] Test 2: Mock-GeM Idempotency End-to-End Test Validated (was_created=False on second call)")


def test_custom_mock_gem_payload_ingestion():
    """Test 3: Ingest a custom multi-bidder payload via POST /api/ingest/mock-gem."""
    custom_ref = f"DEMO/TEST/WQM/{uuid.uuid4().hex[:8]}"
    payload = {
        "source_system": "SOME_OTHER_SOURCE",  # Should be overridden to MOCK_GEM
        "external_reference": custom_ref,
        "procurement": {
            "title": "Custom Test Procurement for Sensor Devices",
            "organization": "Test Department of Industrial Development",
        },
        "tender": {
            "tender_reference": "TENDER-TEST-009",
            "title": "Supply of Sensor Arrays",
            "description": "Custom tender scope",
            "estimated_value": 12000000.0,
            "category": "ELECTRONICS",
            "documents": [
                {
                    "filename": "Tender_Specification_Sensors.pdf",
                    "document_type": "TENDER_SPECIFICATION",
                    "mime_type": "application/pdf",
                    "file_size": 1024000,
                    "content_text": "Specification details...",
                }
            ],
        },
        "bidders": [
            {
                "bidder": {
                    "legal_name": "Test Vendor Alpha Pvt Ltd",
                    "gstin": "27AAACT999911Z0",
                    "pan": "AAACT99991",
                    "email": "alpha@testvendor.com",
                },
                "submission": {
                    "external_submission_reference": "SUB-ALPHA-01",
                    "status": "SUBMITTED",
                },
                "documents": [
                    {
                        "filename": "Alpha_GST.pdf",
                        "document_type": "GST_CERTIFICATE",
                        "mime_type": "application/pdf",
                        "file_size": 300000,
                        "content_text": "GST Certificate...",
                    }
                ],
            }
        ],
    }

    response = client.post("/api/ingest/mock-gem", json=payload)
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}: {response.text}"

    data = response.json()
    assert data["source_system"] == "MOCK_GEM"  # Enforced by adapter!
    assert data["external_reference"] == custom_ref
    assert data["bidder_count"] == 1
    assert data["was_created"] is True
    print("[PASS] Test 3: Custom Mock-GeM Payload Ingestion Endpoint Validated (Source System Enforced)")


def test_malformed_mock_gem_payload_rejection():
    """Test 4: Ensure missing metadata returns HTTP 400 Bad Request."""
    bad_payload = {
        "source_system": "MOCK_GEM",
        "external_reference": "",  # Empty reference!
        "procurement": {"title": "Title", "organization": "Org"},
        "tender": {"tender_reference": "Ref", "title": "Title"},
    }

    response = client.post("/api/ingest/mock-gem", json=bad_payload)
    assert response.status_code == 400 or response.status_code == 422, f"Expected 400/422, got {response.status_code}"
    print("[PASS] Test 4: Malformed Package Rejection (400 Bad Request) Validated")


def run_all_mock_gem_tests():
    print("=" * 70)
    print("RUNNING MOCK-GEM ADAPTER SUITE")
    print("=" * 70)
    test_mock_gem_demo_ingestion_end_to_end()
    test_mock_gem_idempotency_end_to_end()
    test_custom_mock_gem_payload_ingestion()
    test_malformed_mock_gem_payload_rejection()
    print("=" * 70)
    print("[ALL PASSED] Mock-GeM Adapter endpoints and idempotency verified!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_mock_gem_tests()
