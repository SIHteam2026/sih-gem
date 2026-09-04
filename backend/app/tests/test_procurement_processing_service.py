"""Unit tests for Procurement Processing Service & Router Endpoints.

Tests lifecycle state transitions, idempotency, retry policy, 404 error isolation,
stage failure boundaries, and API router responses.
"""

import sys
import uuid
import asyncio
from pathlib import Path
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.api.main import app
from app.models.procurement import (
    ProcurementStatus,
    ProcessingStage,
    ProcessingStageResult,
    ProcessingContext,
    IngestionProcurementInfo,
    IngestionTenderInfo,
    IngestionBidderPackageInput,
    IngestionBidderInfo,
    IngestionSubmissionInfo,
    ProcurementIngestionPayload,
)
from app.services.ingestion_service import (
    ingest_procurement,
)
from app.services.procurement_processing_service import (
    ProcurementProcessingStage,
    start_procurement_processing,
    get_procurement_processing_status,
)


async def create_sample_procurement() -> str:
    """Ingests a sample procurement payload and returns its UUID."""
    ref_id = f"GEM-PROC-{uuid.uuid4().hex[:6]}"
    tender_ref = f"GEM/2026/T-{uuid.uuid4().hex[:4]}"
    payload = ProcurementIngestionPayload(
        source_system="MOCK_GEM",
        external_reference=ref_id,
        procurement=IngestionProcurementInfo(
            title="Processing Test Procurement",
            organization="Ministry of IT",
        ),
        tender=IngestionTenderInfo(
            tender_reference=tender_ref,
            title="Tender 1",
            description="Sample Tender Description",
            estimated_value=500000.0,
            category="Goods",
        ),
        bidders=[
            IngestionBidderPackageInput(
                bidder=IngestionBidderInfo(
                    legal_name="Alpha Tech Ltd",
                    gstin="27AAAAA0000A1Z5",
                ),
                submission=IngestionSubmissionInfo(),
            )
        ],
    )
    result = await ingest_procurement(payload)
    return result.procurement_id



def test_start_processing_lifecycle_success():
    """Verifies IMPORTED -> PROCESSING -> READY lifecycle state transition."""
    async def _run():
        proc_id = await create_sample_procurement()

        # Check initial status before processing
        status_before = await get_procurement_processing_status(proc_id)
        assert status_before.status in (
            ProcurementStatus.IMPORTED,
            ProcurementStatus.PROCESSING,
            ProcurementStatus.READY,
        )


        # Start processing with force=True to re-run pipeline explicitly
        response = await start_procurement_processing(proc_id, force=True)
        assert response.procurement_id == proc_id
        assert response.status == ProcurementStatus.READY
        assert response.already_completed is False

        # Check status after processing
        status_after = await get_procurement_processing_status(proc_id)
        assert status_after.status == ProcurementStatus.READY
        assert len(status_after.completed_stages) == 4
        assert status_after.failed_stage is None

    asyncio.run(_run())


def test_processing_idempotency():
    """Verifies calling process on READY procurement returns already_completed=True."""
    async def _run():
        proc_id = await create_sample_procurement()

        # First processing run with force=True to guarantee READY state
        await start_procurement_processing(proc_id, force=True)

        # Second processing run without force
        second_res = await start_procurement_processing(proc_id, force=False)
        assert second_res.status == ProcurementStatus.READY
        assert second_res.already_completed is True

    asyncio.run(_run())


def test_processing_force_reprocessing():
    """Verifies force=True increments retry_count and re-runs processing."""
    async def _run():
        proc_id = await create_sample_procurement()

        # First run
        await start_procurement_processing(proc_id, force=True)

        # Second run with force=True
        force_res = await start_procurement_processing(proc_id, force=True)
        assert force_res.status == ProcurementStatus.READY
        assert force_res.already_completed is False

        status_res = await get_procurement_processing_status(proc_id)
        assert status_res.retry_count > 0

    asyncio.run(_run())


def test_unknown_procurement_404():
    """Verifies non-existent procurement ID raises 404 HTTPException."""
    async def _run():
        fake_id = str(uuid.uuid4())
        with pytest.raises(HTTPException) as exc_info:
            await get_procurement_processing_status(fake_id)
        assert exc_info.value.status_code == 404

        with pytest.raises(HTTPException) as exc_info2:
            await start_procurement_processing(fake_id)
        assert exc_info2.value.status_code == 404

    asyncio.run(_run())


class FailingStage(ProcurementProcessingStage):
    """Mock failing stage for testing failure isolation."""
    @property
    def stage_name(self) -> ProcessingStage:
        return ProcessingStage.DOCUMENT_INTELLIGENCE

    async def execute(self, context: ProcessingContext) -> ProcessingStageResult:
        return ProcessingStageResult(
            stage=self.stage_name,
            success=False,
            error_code="MOCK_OCR_ERROR",
            error_message="OCR processing failed due to missing font stream.",
        )


def test_stage_failure_isolation():
    """Verifies stage failure isolates pipeline, sets status FAILED, and captures error details."""
    async def _run():
        proc_id = await create_sample_procurement()
        pipeline = [FailingStage()]

        res = await start_procurement_processing(proc_id, force=True, custom_pipeline=pipeline)
        assert res.status == ProcurementStatus.FAILED
        assert "MOCK_OCR_ERROR" in res.message or "failed" in res.message

        status_res = await get_procurement_processing_status(proc_id)
        assert status_res.status == ProcurementStatus.FAILED
        assert status_res.failed_stage == ProcessingStage.DOCUMENT_INTELLIGENCE
        assert status_res.last_error_code == "MOCK_OCR_ERROR"
        assert status_res.last_error_message == "OCR processing failed due to missing font stream."

    asyncio.run(_run())


def test_procurement_processing_router_endpoints():
    """Tests POST and GET router endpoints via FastAPI TestClient."""
    async def _run():
        proc_id = await create_sample_procurement()
        client = TestClient(app)

        # Test POST /api/procurements/{id}/process
        post_resp = client.post(f"/api/procurements/{proc_id}/process?force=true")
        assert post_resp.status_code == 200
        post_data = post_resp.json()
        assert post_data["procurement_id"] == proc_id
        assert post_data["status"] == "READY"

        # Test GET /api/procurements/{id}/processing-status
        get_resp = client.get(f"/api/procurements/{proc_id}/processing-status")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["procurement_id"] == proc_id
        assert get_data["status"] == "READY"
        assert len(get_data["completed_stages"]) == 4

        # Test GET 404 for fake ID
        fake_id = str(uuid.uuid4())
        fake_resp = client.get(f"/api/procurements/{fake_id}/processing-status")
        assert fake_resp.status_code == 404

    asyncio.run(_run())
