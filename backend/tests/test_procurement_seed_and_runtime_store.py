"""Tests for canonical seed data separation and mutable local runtime store initialization.

Verifies:
1. Fresh runtime store creation from static canonical seed when runtime store is absent.
2. Existing runtime store is preserved without being overwritten by seed.
3. Static seed (procurement_seed.json) is never mutated by runtime store writes.
4. Canonical demo CPCL procurement exists and is queryable upon fresh initialization.
5. Normal CRUD operations persist correctly to the runtime store.
6. Supabase fallback functions gracefully operate with seed/runtime store separation.
"""

import json
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
import app.db.client as db_client


@pytest.fixture
def seed_store_isolation(tmp_path, monkeypatch):
    """Provides isolated temporary directories and mock store paths to test store loading and seeding without mutating repo files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    runtime_store = data_dir / "procurement_store.json"
    seed_store = data_dir / "procurement_seed.json"

    # Copy real static seed to isolated test seed path
    real_seed = Path(__file__).resolve().parent.parent / "data" / "procurement_seed.json"
    assert real_seed.exists(), "Real procurement_seed.json must exist in backend/data/"
    seed_store.write_text(real_seed.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(db_client, "_DATA_DIR", data_dir)
    monkeypatch.setattr(db_client, "_LOCAL_STORE_PATH", runtime_store)
    monkeypatch.setattr(db_client, "_SEED_STORE_PATH", seed_store)

    # Clear in-memory state
    db_client._IN_MEMORY_PROCUREMENTS.clear()
    db_client._IN_MEMORY_TENDERS.clear()
    db_client._IN_MEMORY_BIDDERS.clear()
    db_client._IN_MEMORY_SUBMISSIONS.clear()
    db_client._IN_MEMORY_DOCUMENTS.clear()
    db_client._IN_MEMORY_REQUIREMENTS.clear()
    db_client._IN_MEMORY_FINANCIAL_EVALUATIONS.clear()
    db_client._IN_MEMORY_CLARIFICATIONS.clear()
    db_client._IN_MEMORY_AUDIT_LOGS.clear()

    yield {
        "data_dir": data_dir,
        "runtime_store": runtime_store,
        "seed_store": seed_store,
    }


def test_fresh_runtime_store_initialization_from_seed(seed_store_isolation):
    """Verifies that when runtime store is absent, _load_local_store() initializes from seed and creates the runtime store."""
    paths = seed_store_isolation
    runtime_store = paths["runtime_store"]
    seed_store = paths["seed_store"]

    assert not runtime_store.exists()
    assert seed_store.exists()

    seed_content_before = seed_store.read_text(encoding="utf-8")

    # Trigger store load
    db_client._load_local_store()

    # 1. In-memory state is populated with canonical demo
    assert len(db_client._IN_MEMORY_PROCUREMENTS) == 1
    cpcl_proc = next(iter(db_client._IN_MEMORY_PROCUREMENTS.values()))
    assert cpcl_proc["external_reference"] == "DEMO/CPCL/WQM/2026/017"
    assert len(db_client._IN_MEMORY_BIDDERS) == 3
    assert len(db_client._IN_MEMORY_SUBMISSIONS) == 3
    assert len(db_client._IN_MEMORY_DOCUMENTS) == 16

    # 2. Runtime store file was created
    assert runtime_store.exists()

    # 3. Seed file was NOT modified
    seed_content_after = seed_store.read_text(encoding="utf-8")
    assert seed_content_before == seed_content_after


def test_existing_runtime_store_is_preserved(seed_store_isolation):
    """Verifies that if runtime store already exists, its contents are preserved and seed is not reloaded."""
    paths = seed_store_isolation
    runtime_store = paths["runtime_store"]

    # Create pre-existing runtime store with custom local data
    custom_runtime_data = {
        "procurements": {
            "custom-proc-99": {
                "id": "custom-proc-99",
                "external_reference": "CUSTOM/REF/001",
                "title": "Custom Local Engineering Workspace",
                "organization": "Local PSU",
                "status": "READY",
            }
        },
        "tenders": {},
        "bidders": {},
        "submissions": {},
        "documents": {},
        "requirements": {},
        "financial_evaluations": {},
        "clarifications": {},
        "audit_logs": [],
    }
    with open(runtime_store, "w", encoding="utf-8") as f:
        json.dump(custom_runtime_data, f, indent=2)

    assert runtime_store.exists()

    # Trigger store load
    db_client._load_local_store()

    # Local custom data must be loaded, not the seed data
    assert len(db_client._IN_MEMORY_PROCUREMENTS) == 1
    assert "custom-proc-99" in db_client._IN_MEMORY_PROCUREMENTS
    assert db_client._IN_MEMORY_PROCUREMENTS["custom-proc-99"]["title"] == "Custom Local Engineering Workspace"


@pytest.mark.asyncio
async def test_seed_is_never_mutated_by_runtime_writes(seed_store_isolation):
    """Verifies that runtime CRUD modifications write to procurement_store.json and never to procurement_seed.json."""
    paths = seed_store_isolation
    runtime_store = paths["runtime_store"]
    seed_store = paths["seed_store"]

    seed_content_before = seed_store.read_text(encoding="utf-8")

    # Initial load from seed
    db_client._load_local_store()

    # Perform a runtime insertion
    new_bidder = {
        "id": "bidder-runtime-test-999",
        "legal_name": "New Dynamic Bidder Ltd",
        "gstin": "33AABCR1234F1Z0",
    }
    await db_client.insert_bidder(new_bidder)

    # 1. Runtime store contains the new record
    assert runtime_store.exists()
    runtime_data = json.loads(runtime_store.read_text(encoding="utf-8"))
    assert "bidder-runtime-test-999" in runtime_data["bidders"]

    # 2. Seed file remains completely untouched
    seed_content_after = seed_store.read_text(encoding="utf-8")
    assert seed_content_before == seed_content_after
    seed_data = json.loads(seed_content_after)
    assert "bidder-runtime-test-999" not in seed_data["bidders"]


@pytest.mark.asyncio
async def test_demo_procurement_queryable_via_rest_api(seed_store_isolation):
    """Verifies that on a fresh setup with only the seed file, the canonical CPCL demo is queryable via REST API."""
    paths = seed_store_isolation
    assert not paths["runtime_store"].exists()

    # Fresh initialization
    db_client._load_local_store()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/procurements")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1
        cpcl = next((p for p in data["procurements"] if p["external_reference"] == "DEMO/CPCL/WQM/2026/017"), None)
        assert cpcl is not None
        assert cpcl["title"] == "Supply and commissioning of industrial water quality monitoring units"
        assert cpcl["organization"] == "Chennai Petroleum Corporation Limited (CPCL)"
        assert cpcl["bidder_count"] == 3
        assert cpcl["document_count"] == 16
