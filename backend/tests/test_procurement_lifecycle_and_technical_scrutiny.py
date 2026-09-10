"""Tests for Canonical Procurement Case Lifecycle & Authoritative Technical Scrutiny Orchestration.

Verifies:
1. Canonical state machine transitions (IMPORTED -> READY_FOR_TECHNICAL_SCRUTINY -> TECHNICAL_SCRUTINY_RUNNING -> TECHNICAL_REVIEW).
2. Illegal state transition validation and rejection with HTTP 400.
3. Authoritative Technical Scrutiny Execution (POST /api/procurements/{id}/technical-scrutiny/run).
4. Multi-layer verification execution (L1 to L7) with domain results (PASS, FAIL, REVIEW, UNVERIFIED) without HTTP 500.
5. Structured Officer Technical Review representation (GET /api/procurements/{id}/technical-review).
6. State synchronization across Clarification creation, Re-evaluation, and Technical Freeze.
7. Cover 2 Readiness Gate gating checks (POST /api/procurements/{id}/cover2-gate).
8. Audit trail logging across all lifecycle actions.
"""

from datetime import datetime, timezone, timedelta
import json
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.db.client import (
    _IN_MEMORY_AUDIT_LOGS,
    _IN_MEMORY_BIDDERS,
    _IN_MEMORY_CLARIFICATIONS,
    _IN_MEMORY_DOCUMENTS,
    _IN_MEMORY_EVALUATIONS,
    _IN_MEMORY_PROCUREMENTS,
    _IN_MEMORY_SUBMISSIONS,
    _IN_MEMORY_TENDERS,
    get_audit_logs_db,
    insert_document,
)
from app.models.clarification import (
    ClarificationCreate,
    ClarificationResponseInput,
    TechnicalFreezeRequest,
)
from app.models.procurement import (
    DocumentType,
    ProcurementStatus,
    TechnicalFreezeStatus,
)
from app.services.procurement_lifecycle_service import (
    evaluate_cover2_gate_service,
    get_procurement_technical_review_service,
    run_technical_scrutiny_command,
    transition_procurement_state,
    validate_procurement_state_transition,
)


@pytest.fixture(autouse=True)
def setup_lifecycle_test_workspace():
    """Sets up an isolated, complete procurement test workspace."""
    proc_id = "test-proc-lifecycle-001"
    tender_id = "test-tender-lifecycle-001"
    bidder_1 = "test-bidder-life-001"
    bidder_2 = "test-bidder-life-002"
    sub_1 = "test-sub-life-001"
    sub_2 = "test-sub-life-002"

    _IN_MEMORY_PROCUREMENTS[proc_id] = {
        "id": proc_id,
        "external_reference": "GEM/2026/LIFECYCLE/01",
        "title": "Online Continuous Effluent Monitoring System",
        "organization": "Chennai Petroleum Corporation Limited",
        "source_system": "MOCK_GEM",
        "status": ProcurementStatus.IMPORTED.value,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    _IN_MEMORY_TENDERS[tender_id] = {
        "id": tender_id,
        "procurement_id": proc_id,
        "tender_reference": "GEM/2026/B/882190",
        "title": "OCEMS Turbidity & pH Analyzer Package",
        "estimated_value": 7500000.0,
        "category": "GOODS",
        "status": "READY",
        "submission_deadline": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    _IN_MEMORY_BIDDERS[bidder_1] = {
        "id": bidder_1,
        "legal_name": "Apex Environmental Systems Ltd",
        "gstin": "33AABCU9603R1ZM",
        "pan": "AABCU9603R",
        "email": "tenders@apexenv.com",
    }

    _IN_MEMORY_BIDDERS[bidder_2] = {
        "id": bidder_2,
        "legal_name": "Zenith Analytics India Pvt Ltd",
        "gstin": "27AAACZ1234F1Z5",
        "pan": "AAACZ1234F",
        "email": "gov@zenithanalytics.com",
    }

    _IN_MEMORY_SUBMISSIONS[sub_1] = {
        "id": sub_1,
        "procurement_id": proc_id,
        "tender_id": tender_id,
        "bidder_id": bidder_1,
        "external_submission_reference": "SUB-APEX-8821",
        "status": "SUBMITTED",
        "technical_freeze_status": TechnicalFreezeStatus.NOT_FROZEN.value,
        "is_locked": False,
        "frozen_at": None,
        "frozen_by": None,
        "freeze_reason": None,
        "bidder": _IN_MEMORY_BIDDERS[bidder_1],
        "documents": [],
    }

    _IN_MEMORY_SUBMISSIONS[sub_2] = {
        "id": sub_2,
        "procurement_id": proc_id,
        "tender_id": tender_id,
        "bidder_id": bidder_2,
        "external_submission_reference": "SUB-ZENITH-8821",
        "status": "SUBMITTED",
        "technical_freeze_status": TechnicalFreezeStatus.NOT_FROZEN.value,
        "is_locked": False,
        "frozen_at": None,
        "frozen_by": None,
        "freeze_reason": None,
        "bidder": _IN_MEMORY_BIDDERS[bidder_2],
        "documents": [],
    }

    # Add tender spec document
    _IN_MEMORY_DOCUMENTS["doc-spec-001"] = {
        "id": "doc-spec-001",
        "procurement_id": proc_id,
        "tender_id": tender_id,
        "filename": "Tender_Specification_OCEMS.pdf",
        "document_type": DocumentType.TENDER_SPECIFICATION.value,
        "mime_type": "application/pdf",
        "content_text": json.dumps([{"page": 1, "text": "Clause 1.1: The bidder must have valid GST registration in Tamil Nadu (State code 33). Clause 2.1: OEM Authorization Certificate required. Clause 3.1: Minimum 3 years experience in supply of continuous effluent water monitoring systems. Clause 4.1: Average annual turnover of minimum INR 50 Lakhs for last 3 financial years. Clause 5.1: Minimum local content 50% under Make in India."}]),
        "processing_status": "COMPLETED",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Add bidder 1 documents
    _IN_MEMORY_DOCUMENTS["doc-apex-gst"] = {
        "id": "doc-apex-gst",
        "procurement_id": proc_id,
        "tender_id": tender_id,
        "bid_submission_id": sub_1,
        "filename": "Apex_GST_Registration.pdf",
        "document_type": DocumentType.GST_CERTIFICATE.value,
        "mime_type": "application/pdf",
        "content_text": json.dumps([{"page": 1, "text": "Government of India - GST Registration Certificate. Legal Name: Apex Environmental Systems Ltd. GSTIN: 33AABCU9603R1ZM. State: Tamil Nadu. Status: ACTIVE."}]),
        "processing_status": "COMPLETED",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    _IN_MEMORY_DOCUMENTS["doc-apex-turnover"] = {
        "id": "doc-apex-turnover",
        "procurement_id": proc_id,
        "tender_id": tender_id,
        "bid_submission_id": sub_1,
        "filename": "Apex_CA_Turnover_Certificate.pdf",
        "document_type": DocumentType.TURNOVER_CERTIFICATE.value,
        "mime_type": "application/pdf",
        "content_text": json.dumps([{"page": 1, "text": "Chartered Accountant Certificate: Annual Turnover of Apex Environmental Systems Ltd for FY 2022-23: INR 120 Lakhs, FY 2023-24: INR 140 Lakhs, FY 2024-25: INR 160 Lakhs. Average turnover: INR 140 Lakhs. UDIN: 24123456AAAAAA1234."}]),
        "processing_status": "COMPLETED",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Add bidder 2 documents
    _IN_MEMORY_DOCUMENTS["doc-zenith-gst"] = {
        "id": "doc-zenith-gst",
        "procurement_id": proc_id,
        "tender_id": tender_id,
        "bid_submission_id": sub_2,
        "filename": "Zenith_GST_Certificate.pdf",
        "document_type": DocumentType.GST_CERTIFICATE.value,
        "mime_type": "application/pdf",
        "content_text": json.dumps([{"page": 1, "text": "GST Registration Certificate. Legal Name: Zenith Analytics India Pvt Ltd. GSTIN: 27AAACZ1234F1Z5. State: Maharashtra. Status: ACTIVE."}]),
        "processing_status": "COMPLETED",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    yield {
        "procurement_id": proc_id,
        "tender_id": tender_id,
        "bidder_1": bidder_1,
        "bidder_2": bidder_2,
        "sub_1": sub_1,
        "sub_2": sub_2,
    }


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_canonical_state_transitions_and_rejection():
    """Tests legal and illegal state transitions in procurement state machine."""
    proc_id = "test-proc-lifecycle-001"

    # Legal: IMPORTED -> READY_FOR_TECHNICAL_SCRUTINY
    updated = await transition_procurement_state(
        procurement_id=proc_id,
        target_status=ProcurementStatus.READY_FOR_TECHNICAL_SCRUTINY,
        actor="OFFICER_CHETAN",
        reason="Initial ingestion and requirement decomposition verified.",
    )
    assert updated["status"] == ProcurementStatus.READY_FOR_TECHNICAL_SCRUTINY.value

    # Illegal: READY_FOR_TECHNICAL_SCRUTINY -> COVER_2_READY (cannot skip technical scrutiny & freeze)
    with pytest.raises(Exception) as exc_info:
        await transition_procurement_state(
            procurement_id=proc_id,
            target_status=ProcurementStatus.COVER_2_READY,
            actor="OFFICER_CHETAN",
        )
    assert "Illegal state transition" in str(exc_info.value)


@pytest.mark.asyncio
async def test_run_technical_scrutiny_orchestration():
    """Tests authoritative execution of Technical Scrutiny (L1-L7) and transition to TECHNICAL_REVIEW."""
    proc_id = "test-proc-lifecycle-001"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/procurements/{proc_id}/technical-scrutiny/run",
            json={"force": True, "actor": "OFFICER_CHETAN", "notes": "Auditing OCEMS package"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["procurement_id"] == proc_id
        assert data["status"] == ProcurementStatus.TECHNICAL_REVIEW.value
        assert data["bidders_evaluated"] == 2
        assert len(data["executed_layers"]) >= 5
        assert data["execution_time_ms"] > 0

    # Verify state in storage
    assert _IN_MEMORY_PROCUREMENTS[proc_id]["status"] == ProcurementStatus.TECHNICAL_REVIEW.value

    # Verify audit logs generated
    logs = await get_audit_logs_db(procurement_id=proc_id)
    event_types = [l["event_type"] for l in logs]
    assert "TECHNICAL_SCRUTINY_STARTED" in event_types
    assert "TECHNICAL_SCRUTINY_COMPLETED" in event_types


@pytest.mark.asyncio
async def test_get_procurement_technical_review_representation():
    """Tests GET /api/procurements/{id}/technical-review representation."""
    proc_id = "test-proc-lifecycle-001"

    # Run scrutiny first
    await run_technical_scrutiny_command(proc_id, actor="OFFICER_CHETAN")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/procurements/{proc_id}/technical-review")
        assert response.status_code == 200, response.text
        data = response.json()

        assert data["procurement_id"] == proc_id
        assert data["total_bidders"] == 2
        assert len(data["bidders"]) == 2
        assert data["decision_authority"] == "HUMAN_PROCUREMENT_OFFICER"

        # Check bidder summaries
        b_names = [b["legal_name"] for b in data["bidders"]]
        assert "Apex Environmental Systems Ltd" in b_names
        assert "Zenith Analytics India Pvt Ltd" in b_names

        for b_sum in data["bidders"]:
            assert b_sum["compliance_status"] in ("PASS", "FAIL", "REVIEW", "UNVERIFIED")
            assert "passed_requirements_count" in b_sum

        # Check freeze summary and Cover 2 readiness
        assert "freeze_status" in data
        assert data["freeze_status"]["is_frozen"] is False  # Not yet frozen
        assert "cover2_readiness" in data
        assert data["cover2_readiness"]["is_ready"] is False  # Blocked because not frozen


@pytest.mark.asyncio
async def test_clarification_lifecycle_state_sync():
    """Tests that creating a clarification moves status to CLARIFICATION_OPEN and re-evaluation restores TECHNICAL_REVIEW."""
    proc_id = "test-proc-lifecycle-001"
    sub_1 = "test-sub-life-001"
    tender_id = "test-tender-lifecycle-001"
    bidder_1 = "test-bidder-life-001"

    # Run technical scrutiny first to bring procurement into TECHNICAL_REVIEW
    await run_technical_scrutiny_command(proc_id, actor="OFFICER_CHETAN")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create clarification
        create_resp = await client.post(
            f"/api/procurements/{proc_id}/clarifications",
            json={
                "submission_id": sub_1,
                "requirement_id": "REQ-OEM-01",
                "question": "Please submit OEM Authorization for Turbidity Sensors.",
                "created_by": "OFFICER_CHETAN",
            },
        )
        assert create_resp.status_code == 200, create_resp.text
        c_data = create_resp.json()
        c_id = c_data["id"]

        # Check procurement status moved to CLARIFICATION_OPEN
        assert _IN_MEMORY_PROCUREMENTS[proc_id]["status"] == ProcurementStatus.CLARIFICATION_OPEN.value

        # Bidder responds
        resp_res = await client.post(
            f"/api/clarifications/{c_id}/respond",
            json={
                "response_text": "Attached OEM certificate from SensorCorp.",
                "responded_by": "BIDDER_APEX",
                "documents": [
                    {
                        "filename": "SensorCorp_OEM_Auth.pdf",
                        "document_type": "OEM_AUTHORIZATION",
                        "content_text": json.dumps([{"page": 1, "text": "OEM Authorization: SensorCorp authorizes Apex Environmental Systems Ltd."}]),
                    }
                ],
            },
        )
        assert resp_res.status_code == 200

        # Execute targeted re-evaluation
        re_eval_res = await client.post(f"/api/clarifications/{c_id}/re-evaluate")
        assert re_eval_res.status_code == 200

        # Check procurement status moved back to TECHNICAL_REVIEW
        assert _IN_MEMORY_PROCUREMENTS[proc_id]["status"] == ProcurementStatus.TECHNICAL_REVIEW.value


@pytest.mark.asyncio
async def test_technical_freeze_and_cover2_readiness_gate():
    """Tests technical freeze gating and advancing to COVER_2_READY."""
    proc_id = "test-proc-lifecycle-001"
    sub_1 = "test-sub-life-001"
    sub_2 = "test-sub-life-002"

    # Scrutiny run
    await run_technical_scrutiny_command(proc_id, actor="OFFICER_CHETAN")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Attempt Cover 2 gate before freezing -> BLOCKED
        gate_res = await client.post(f"/api/procurements/{proc_id}/cover2-gate")
        assert gate_res.status_code == 200
        gate_data = gate_res.json()
        assert gate_data["cover2_readiness"]["is_ready"] is False
        assert any("Technical Freeze" in b for b in gate_data["cover2_readiness"]["blockers"])

        # 2. Freeze submission 1
        f1_res = await client.post(
            f"/api/submissions/{sub_1}/technical-freeze",
            json={"freeze": True, "freeze_reason": "Technical evaluation completed", "officer_id": "OFFICER_CHETAN"},
        )
        assert f1_res.status_code == 200

        # 3. Freeze submission 2
        f2_res = await client.post(
            f"/api/submissions/{sub_2}/technical-freeze",
            json={"freeze": True, "freeze_reason": "Technical evaluation completed", "officer_id": "OFFICER_CHETAN"},
        )
        assert f2_res.status_code == 200

        # Procurement status should now be TECHNICAL_FREEZE
        assert _IN_MEMORY_PROCUREMENTS[proc_id]["status"] == ProcurementStatus.TECHNICAL_FREEZE.value

        # 4. Now evaluate Cover 2 Readiness Gate
        gate_res2 = await client.post(f"/api/procurements/{proc_id}/cover2-gate")
        assert gate_res2.status_code == 200
        gate_data2 = gate_res2.json()
        assert gate_data2["decision_authority"] == "HUMAN_PROCUREMENT_OFFICER"
        assert gate_data2["cover2_readiness"]["technical_freeze_enforced"] is True

        # Check audit trail for gate evaluation
        logs = await get_audit_logs_db(procurement_id=proc_id)
        events = [l["event_type"] for l in logs]
        assert "COVER_2_GATE_BLOCKED" in events or "COVER_2_GATE_PASSED" in events
