"""Regression coverage for the no-requirements Technical Scrutiny safety gate."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api import mock_gem_router
from app.models.procurement import ProcurementStatus
from app.models.tender import TenderAnalysisResult
from app.services import procurement_lifecycle_service as lifecycle


def test_scrutiny_blocks_zero_requirement_procurement_and_marks_it_failed():
    """An empty tender contract must never yield a successful empty scrutiny run."""

    procurement = {
        "id": "procurement-without-requirements",
        "status": ProcurementStatus.READY.value,
        "tenders": [{
            "id": "tender-without-requirements",
            "submission_deadline": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "submissions": [],
            "documents": [],
        }],
        "documents": [],
    }
    transition = AsyncMock()
    audit_log = AsyncMock()

    async def exercise_guard():
        with patch.object(lifecycle, "get_procurement_detail_db", AsyncMock(return_value=procurement)), \
             patch.object(lifecycle, "get_tender_evaluation_contract", AsyncMock(return_value=None)), \
             patch.object(lifecycle, "transition_procurement_state", transition), \
             patch.object(lifecycle, "insert_audit_log_db", audit_log):
            with pytest.raises(HTTPException) as raised:
                await lifecycle.run_technical_scrutiny_command(
                    procurement_id=procurement["id"],
                    actor="TEST_OFFICER",
                )

        assert raised.value.status_code == 422
        assert "0 compliance requirements" in raised.value.detail

    asyncio.run(exercise_guard())

    failed_transitions = [
        call for call in transition.await_args_list
        if call.kwargs.get("target_status") == ProcurementStatus.FAILED
    ]
    assert len(failed_transitions) == 1
    assert audit_log.await_count == 2  # start event and no-requirements abort event


def test_ingestion_analysis_with_zero_requirements_marks_procurement_failed():
    """Every Mock-GeM route uses the shared helper, so empty analysis is a hard failure."""

    transition = AsyncMock()
    empty_analysis = TenderAnalysisResult(
        tender_id="tender-empty",
        requirements=[],
        raw_text="Tender text without extractable requirements",
        page_count=1,
    )

    async def exercise_empty_analysis():
        with patch("app.services.tender_service.analyze_tender", AsyncMock(return_value=empty_analysis)), \
             patch("app.services.procurement_lifecycle_service.transition_procurement_state", transition):
            with pytest.raises(HTTPException) as raised:
                await mock_gem_router._run_tender_intelligence_or_fail(
                    procurement_id="procurement-empty",
                    tender_id="tender-empty",
                    file_bytes=b"Tender text without extractable requirements",
                    filename="tender.txt",
                )

        assert raised.value.status_code == 422
        assert "without extracting any compliance requirements" in raised.value.detail

    asyncio.run(exercise_empty_analysis())

    transition.assert_awaited_once()
    assert transition.await_args.kwargs["target_status"] == ProcurementStatus.FAILED


def test_metadata_extracts_deadline_when_pdf_text_uses_a_following_line():
    metadata = mock_gem_router.extract_tender_metadata_from_text(
        "Closing Date:\n15-September-2026 15:00 IST",
        "tender.pdf",
    )

    assert metadata["submission_deadline"] == datetime(2026, 9, 15, 9, 30, tzinfo=timezone.utc)
