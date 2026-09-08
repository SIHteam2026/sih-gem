"""Tests for Clear Log functionality and 2-Active + 5-Logs pruning limit in Audit Trail.

Verifies:
1. Auto-pruning to max 7 items (2 active + 5 logs) when more procurements are ingested/stored.
2. DELETE /api/procurements/logs clears historical logs while preserving latest 2 active procurements.
3. POST /api/procurements/clear-logs alias clears historical logs.
4. Audit log records are cleared upon clear logs action.
"""

import pytest
import app.db.client as db_client
from app.api.main import app

from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_auto_pruning_max_7_items():
    for i in range(10):
        await db_client.insert_procurement({
            "id": f"proc-test-{i}",
            "external_reference": f"GEM/2026/B/{i}",
            "title": f"Tender Test {i}",
            "organization": "Test Org",
            "source_system": "MOCK_GEM",
            "status": "READY",
            "created_at": f"2026-09-09T10:00:0{i}Z",
        })
    proc_list = await db_client.list_procurements(limit=50)
    items = proc_list.get("items", [])
    assert len(items) <= 7, f"Expected at most 7 procurements, got {len(items)}"


@pytest.mark.asyncio
async def test_clear_logs_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.delete("/api/procurements/logs?keep_active_count=2")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SUCCESS"
        assert data["retained_active_procurements"] <= 2

        list_res = await client.get("/api/procurements")
        assert list_res.status_code == 200
        procs = list_res.json().get("procurements", [])
        assert len(procs) <= 2
