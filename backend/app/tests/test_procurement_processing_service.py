"""Unit tests for Procurement Processing Service & Router Endpoints.

Tests lifecycle state transitions, idempotency, retry policy, 404 error isolation,
stage failure boundaries, and API router responses.
"""

import sys
import uuid
import asyncio
import unittest
from pathlib import Path
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
    tender_ref = f"DEMO/CPCL/WQM/2026/{uuid.uuid4().hex[:4]}"
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


class ProcurementProcessingServiceTests(unittest.IsolatedAsyncioTestCase):
    """Test suite for procurement processing lifecycle and stage isolation."""

    async def test_start_processing_lifecycle_success(self):
        """Verifies IMPORTED -> PROCESSING -> READY lifecycle state transition."""
        proc_id = await create_sample_procurement()

        # Check initial status before processing
        status_before = await get_procurement_processing_status(proc_id)
        self.assertIn(
            status_before.status,
            (
                ProcurementStatus.IMPORTED,
                ProcurementStatus.PROCESSING,
                ProcurementStatus.READY,
            ),
        )

        # Start processing with force=True to re-run pipeline explicitly
        response = await start_procurement_processing(proc_id, force=True)
        self.assertEqual(response.procurement_id, proc_id)
        self.assertEqual(response.status, ProcurementStatus.READY)
        self.assertFalse(response.already_completed)

        # Check status after processing
        status_after = await get_procurement_processing_status(proc_id)
        self.assertEqual(status_after.status, ProcurementStatus.READY)
        self.assertEqual(len(status_after.completed_stages), 4)
        self.assertIsNone(status_after.failed_stage)

    async def test_processing_idempotency(self):
        """Verifies calling process on READY procurement returns already_completed=True."""
        proc_id = await create_sample_procurement()

        # First processing run with force=True to guarantee READY state
        await start_procurement_processing(proc_id, force=True)

        # Second processing run without force
        second_res = await start_procurement_processing(proc_id, force=False)
        self.assertEqual(second_res.status, ProcurementStatus.READY)
        self.assertTrue(second_res.already_completed)

    async def test_processing_force_reprocessing(self):
        """Verifies force=True increments retry_count and re-runs processing."""
        proc_id = await create_sample_procurement()

        # First run
        await start_procurement_processing(proc_id, force=True)

        # Second run with force=True
        force_res = await start_procurement_processing(proc_id, force=True)
        self.assertEqual(force_res.status, ProcurementStatus.READY)
        self.assertFalse(force_res.already_completed)

        status_res = await get_procurement_processing_status(proc_id)
        self.assertGreater(status_res.retry_count, 0)

    async def test_unknown_procurement_404(self):
        """Verifies non-existent procurement ID raises 404 HTTPException."""
        fake_id = str(uuid.uuid4())
        with self.assertRaises(HTTPException) as ctx:
            await get_procurement_processing_status(fake_id)
        self.assertEqual(ctx.exception.status_code, 404)

        with self.assertRaises(HTTPException) as ctx2:
            await start_procurement_processing(fake_id)
        self.assertEqual(ctx2.exception.status_code, 404)

    async def test_stage_failure_isolation(self):
        """Verifies stage failure isolates pipeline, sets status FAILED, and captures error details."""
        proc_id = await create_sample_procurement()
        pipeline = [FailingStage()]

        res = await start_procurement_processing(proc_id, force=True, custom_pipeline=pipeline)
        self.assertEqual(res.status, ProcurementStatus.FAILED)
        self.assertTrue("MOCK_OCR_ERROR" in res.message or "failed" in res.message)

        status_res = await get_procurement_processing_status(proc_id)
        self.assertEqual(status_res.status, ProcurementStatus.FAILED)
        self.assertEqual(status_res.failed_stage, ProcessingStage.DOCUMENT_INTELLIGENCE)
        self.assertEqual(status_res.last_error_code, "MOCK_OCR_ERROR")
        self.assertEqual(status_res.last_error_message, "OCR processing failed due to missing font stream.")

    async def test_procurement_processing_router_endpoints(self):
        """Tests POST and GET router endpoints via FastAPI TestClient."""
        proc_id = await create_sample_procurement()
        client = TestClient(app)

        # Test POST /api/procurements/{id}/process
        post_resp = client.post(f"/api/procurements/{proc_id}/process?force=true")
        self.assertEqual(post_resp.status_code, 200)
        post_data = post_resp.json()
        self.assertEqual(post_data["procurement_id"], proc_id)
        self.assertEqual(post_data["status"], "READY")

        # Test GET /api/procurements/{id}/processing-status
        get_resp = client.get(f"/api/procurements/{proc_id}/processing-status")
        self.assertEqual(get_resp.status_code, 200)
        get_data = get_resp.json()
        self.assertEqual(get_data["procurement_id"], proc_id)
        self.assertEqual(get_data["status"], "READY")
        self.assertEqual(len(get_data["completed_stages"]), 4)

        # Test GET 404 for fake ID
        fake_id = str(uuid.uuid4())
        fake_resp = client.get(f"/api/procurements/{fake_id}/processing-status")
        self.assertEqual(fake_resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
