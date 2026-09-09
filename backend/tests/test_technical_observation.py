import pytest
from fastapi.testclient import TestClient
from app.api.main import app
from app.db.client import _load_local_store, _IN_MEMORY_PROCUREMENTS, _IN_MEMORY_OBSERVATIONS

client = TestClient(app)

def test_officer_observation_lifecycle():
    procurement_id = "test-obs-proc-001"
    _IN_MEMORY_PROCUREMENTS[procurement_id] = {
        "id": procurement_id,
        "external_reference": "DEMO/CPCL/WQM/2026/OBS",
        "title": "Observation Test Proc",
        "status": "TECHNICAL_REVIEW"
    }
    
    # 1. Create observation
    payload = {
        "layer": "ADMINISTRATIVE_AND_IDENTITY",
        "observation": "GST certificates look valid but require manual cross-check."
    }
    
    resp = client.post(f"/api/procurements/{procurement_id}/observations", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["observation_id"] is not None
    assert data["layer"] == "ADMINISTRATIVE_AND_IDENTITY"
    assert data["actor"] == "HUMAN_PROCUREMENT_OFFICER"
    assert data["observation"] == payload["observation"]
    
    # 2. Duplicate submission test (idempotency)
    resp_dup = client.post(f"/api/procurements/{procurement_id}/observations", json=payload)
    assert resp_dup.status_code == 200
    data_dup = resp_dup.json()
    assert data_dup["observation_id"] == data["observation_id"]  # Should return existing
    
    # 3. Fetch technical review to see it included
    rev_resp = client.get(f"/api/procurements/{procurement_id}/technical-review")
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    
    observations = rev_data.get("observations", [])
    assert len(observations) >= 1
    matched = [o for o in observations if o["observation_id"] == data["observation_id"]]
    assert len(matched) == 1
    
    # 4. Assert six technical layers exist in finding grouping or presentation
    assert "key_findings" in rev_data
    assert "requirements" in rev_data

