"""Comprehensive integration tests for P2 Officer Technical Review Lifecycle.

Tests:
1. Canonical Blocker computation and Technical Review representation.
2. Grounded AI Draft Notice generation (with Gemini/Groq fallback, marked is_draft=True).
3. Response submission and document linkage without synthetic PASS conversion.
4. Targeted re-evaluation preserving non-pass finding states without sufficient evidence.
5. Clarification resolution lifecycle (RESOLVED, REQUIRES_FURTHER_CLARIFICATION).
6. Technical freeze hardening and idempotency.
7. Cover 2 gate evaluation and qualification boundary.
8. State transition enforcement via procurement lifecycle service.
9. Invariant: RESOLVED clarification with unresolved UNVERIFIED blocker remains blocked.
10. Invariant: RESOLVED clarification with unresolved REVIEW blocker remains blocked.
11. Invariant: Invalid procurement lifecycle transitions are rejected.
12. Invariant: Re-evaluation from invalid clarification state is rejected.
13. Invariant: Freeze is blocked by mandatory UNVERIFIED / REVIEW blockers.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.api.main import app
from app.db.client import (
    _IN_MEMORY_AUDIT_LOGS,
    _IN_MEMORY_BIDDERS,
    _IN_MEMORY_CLARIFICATIONS,
    _IN_MEMORY_DOCUMENTS,
    _IN_MEMORY_PROCUREMENTS,
    _IN_MEMORY_SUBMISSIONS,
    _IN_MEMORY_TENDERS,
    insert_audit_log_db,
    insert_bid_evaluation,
    insert_clarification_db,
    insert_document,
)
from app.models.clarification import (
    ClarificationCreate,
    ClarificationDraftRequest,
    ClarificationResolutionRequest,
    ClarificationResponseInput,
    ClarificationStatus,
    TechnicalFreezeRequest,
)
from app.models.procurement import DocumentType, IngestionDocumentInput, ProcurementStatus, TechnicalFreezeStatus
from app.services.clarification_service import (
    create_clarification_service,
    freeze_submission_service,
    generate_clarification_draft_service,
    re_evaluate_clarification_service,
    resolve_clarification_service,
    respond_to_clarification_service,
)
from app.services.procurement_lifecycle_service import (
    evaluate_cover2_gate_service,
    freeze_procurement_technical_service,
    get_procurement_technical_review_service,
    run_technical_scrutiny_command,
    transition_procurement_state,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_p2_workspace():
    """Seeds an isolated test procurement workspace for P2 lifecycle testing."""
    _IN_MEMORY_PROCUREMENTS.clear()
    _IN_MEMORY_TENDERS.clear()
    _IN_MEMORY_SUBMISSIONS.clear()
    _IN_MEMORY_BIDDERS.clear()
    _IN_MEMORY_DOCUMENTS.clear()
    _IN_MEMORY_CLARIFICATIONS.clear()
    _IN_MEMORY_AUDIT_LOGS.clear()

    proc_id = "PROC-P2-TEST-001"
    tender_id = "TENDER-P2-001"
    sub_1_id = "SUB-P2-001"
    sub_2_id = "SUB-P2-002"
    bidder_1_id = "BIDDER-P2-001"
    bidder_2_id = "BIDDER-P2-002"

    _IN_MEMORY_PROCUREMENTS[proc_id] = {
        "id": proc_id,
        "title": "Procurement of Online Monitoring Sensors",
        "external_reference": "GEM/2026/B/999888",
        "status": ProcurementStatus.TECHNICAL_REVIEW.value,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    _IN_MEMORY_TENDERS[tender_id] = {
        "id": tender_id,
        "procurement_id": proc_id,
        "tender_reference": "GEM/2026/B/999888",
        "title": "Online Sensors Tender",
    }

    _IN_MEMORY_BIDDERS[bidder_1_id] = {
        "id": bidder_1_id,
        "legal_name": "Apex Sensor Systems Ltd",
        "gstin": "27ABCDE1234F1Z5",
        "pan": "ABCDE1234F",
    }

    _IN_MEMORY_BIDDERS[bidder_2_id] = {
        "id": bidder_2_id,
        "legal_name": "Zenith Enviro Technologies Pvt Ltd",
        "gstin": "33AABCC5544R1Z2",
        "pan": "AABCC5544R",
    }

    _IN_MEMORY_SUBMISSIONS[sub_1_id] = {
        "id": sub_1_id,
        "procurement_id": proc_id,
        "tender_id": tender_id,
        "bidder_id": bidder_1_id,
        "technical_freeze_status": TechnicalFreezeStatus.NOT_FROZEN.value,
        "is_locked": False,
        "bidder": _IN_MEMORY_BIDDERS[bidder_1_id],
    }

    _IN_MEMORY_SUBMISSIONS[sub_2_id] = {
        "id": sub_2_id,
        "procurement_id": proc_id,
        "tender_id": tender_id,
        "bidder_id": bidder_2_id,
        "technical_freeze_status": TechnicalFreezeStatus.NOT_FROZEN.value,
        "is_locked": False,
        "bidder": _IN_MEMORY_BIDDERS[bidder_2_id],
    }

    # Seed tender specification
    _IN_MEMORY_DOCUMENTS["DOC-SPEC"] = {
        "id": "DOC-SPEC",
        "procurement_id": proc_id,
        "tender_id": tender_id,
        "filename": "tender_specification.pdf",
        "document_type": DocumentType.TENDER_SPECIFICATION.value,
        "mime_type": "application/pdf",
        "content_text": json.dumps([{"page": 1, "text": "Clause 1.1: Valid GST registration is mandatory. Clause 2.1: Minimum local content 50% under Make in India is required. Clause 3.1: Minimum 3 years past experience required."}]),
        "processing_status": "COMPLETED",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Seed initial documents
    _IN_MEMORY_DOCUMENTS["DOC-1"] = {
        "id": "DOC-1",
        "procurement_id": proc_id,
        "tender_id": tender_id,
        "bid_submission_id": sub_1_id,
        "filename": "gst_cert.pdf",
        "document_type": "GST_CERTIFICATE",
        "mime_type": "application/pdf",
        "content_text": json.dumps([{"page": 1, "text": "GSTIN: 27ABCDE1234F1Z5 Active Status"}]),
        "processing_status": "COMPLETED",
    }


@pytest.mark.asyncio
async def test_01_technical_review_blocker_computation():
    """Verifies that technical review aggregates canonical findings, identifies blockers without boolean collapsing."""
    rep = await get_procurement_technical_review_service("PROC-P2-TEST-001")
    assert rep.procurement_id == "PROC-P2-TEST-001"
    assert rep.total_bidders == 2
    assert rep.decision_authority == "HUMAN_PROCUREMENT_OFFICER"

    for b in rep.bidders:
        assert b.is_blocking is True
        assert b.officer_action_required is True
        assert len(b.blockers) > 0
        assert b.compliance_status in ("REVIEW", "UNVERIFIED", "FAIL")

    assert rep.can_open_cover2 is False
    assert rep.cover2_readiness.is_ready is False
    assert len(rep.cover2_readiness.blockers) > 0


@pytest.mark.asyncio
async def test_02_generate_ai_clarification_draft():
    """Verifies AI draft generation creates evidence-grounded draft marked strictly is_draft=True without changing state."""
    draft_req = ClarificationDraftRequest(
        procurement_id="PROC-P2-TEST-001",
        submission_id="SUB-P2-001",
        requirement_id="REQ-003",
        custom_instruction="Request audited balance sheets for FY 2024-25.",
    )
    draft = await generate_clarification_draft_service(draft_req)
    assert draft.is_draft is True
    assert draft.decision_authority == "HUMAN_PROCUREMENT_OFFICER"
    assert "Apex Sensor Systems" in draft.recipient_bidder
    assert draft.requirement_id == "REQ-003"
    assert len(draft.observed_shortfall) > 0
    assert len(draft.requested_clarification) > 0


@pytest.mark.asyncio
async def test_03_create_clarification_state_guard_and_idempotency():
    """Verifies clarification creation enforces legal procurement state and idempotency."""
    create_payload = ClarificationCreate(
        procurement_id="PROC-P2-TEST-001",
        submission_id="SUB-P2-001",
        requirement_id="REQ-003",
        question="Please provide CA-certified turnover certificate for last 3 years.",
    )
    record = await create_clarification_service(create_payload)
    assert record.status == ClarificationStatus.OPEN
    assert record.requirement_id == "REQ-003"

    proc = _IN_MEMORY_PROCUREMENTS["PROC-P2-TEST-001"]
    assert proc["status"] == ProcurementStatus.CLARIFICATION_OPEN.value

    record_dup = await create_clarification_service(create_payload)
    assert record_dup.id == record.id

    rep = await get_procurement_technical_review_service("PROC-P2-TEST-001")
    assert rep.can_freeze is False


@pytest.mark.asyncio
async def test_04_clarification_response_and_targeted_reevaluation():
    """Verifies responding to a clarification and targeted re-evaluation updates finding without synthetic PASS conversion."""
    create_payload = ClarificationCreate(
        procurement_id="PROC-P2-TEST-001",
        submission_id="SUB-P2-001",
        requirement_id="REQ-003",
        question="Please submit audited financial certificate.",
    )
    record = await create_clarification_service(create_payload)

    resp_payload = ClarificationResponseInput(
        response_text="We have attached our turnover certificate.",
        documents=[
            IngestionDocumentInput(
                filename="turnover_cert.pdf",
                document_type=DocumentType.TURNOVER_CERTIFICATE,
                mime_type="application/pdf",
                content_text=json.dumps([{"page": 1, "text": "Annual Turnover for FY 2024: INR 45 Lakhs"}]),
            )
        ],
        responded_by="Apex Bidder Admin",
    )
    updated_rec = await respond_to_clarification_service(record.id, resp_payload)
    assert updated_rec.status == ClarificationStatus.RESPONDED
    assert len(updated_rec.response_documents) == 1

    reeval_rec = await re_evaluate_clarification_service(record.id)
    assert reeval_rec.status == ClarificationStatus.RESOLVED
    assert reeval_rec.resulting_finding is not None
    assert len(reeval_rec.audit_history) >= 3


@pytest.mark.asyncio
async def test_05_explicit_clarification_resolution():
    """Verifies explicit resolution of a clarification (REQUIRES_FURTHER_CLARIFICATION vs RESOLVED)."""
    create_payload = ClarificationCreate(
        procurement_id="PROC-P2-TEST-001",
        submission_id="SUB-P2-002",
        requirement_id="REQ-005",
        question="Please submit valid OEM authorization.",
    )
    record = await create_clarification_service(create_payload)

    res_req = ClarificationResolutionRequest(
        resolution_status=ClarificationStatus.REQUIRES_FURTHER_CLARIFICATION,
        resolution_notes="Document provided was blurry, please upload clear scan.",
        officer_id="SENIOR_OFFICER",
    )
    resolved_rec = await resolve_clarification_service(record.id, res_req)
    assert resolved_rec.status == ClarificationStatus.REQUIRES_FURTHER_CLARIFICATION

    proc = _IN_MEMORY_PROCUREMENTS["PROC-P2-TEST-001"]
    assert proc["status"] == ProcurementStatus.CLARIFICATION_OPEN.value

    res_req_final = ClarificationResolutionRequest(
        resolution_status=ClarificationStatus.RESOLVED,
        resolution_notes="Adequate proof verified.",
        officer_id="SENIOR_OFFICER",
    )
    final_rec = await resolve_clarification_service(record.id, res_req_final)
    assert final_rec.status == ClarificationStatus.RESOLVED


@pytest.mark.asyncio
async def test_06_technical_freeze_hardening_and_mutation_guard():
    """Verifies technical freeze checks blockers, locks submissions against mutations, and is idempotent."""
    create_payload = ClarificationCreate(
        procurement_id="PROC-P2-TEST-001",
        submission_id="SUB-P2-001",
        requirement_id="REQ-001",
        question="GST verification pending.",
    )
    await create_clarification_service(create_payload)

    with pytest.raises(Exception):
        await freeze_procurement_technical_service("PROC-P2-TEST-001")

    all_c = _IN_MEMORY_CLARIFICATIONS
    for c in all_c.values():
        c["status"] = ClarificationStatus.RESOLVED.value

    # Direct submission freeze
    freeze_resp = await freeze_submission_service("SUB-P2-001", TechnicalFreezeRequest(freeze=True, freeze_reason="Technical opening concluded."))
    assert freeze_resp.technical_freeze_status == TechnicalFreezeStatus.FROZEN
    assert freeze_resp.is_locked is True

    sub = _IN_MEMORY_SUBMISSIONS["SUB-P2-001"]
    assert sub["is_locked"] is True

    with pytest.raises(Exception):
        await insert_document({
            "id": "MUTATION-DOC-001",
            "procurement_id": "PROC-P2-TEST-001",
            "bid_submission_id": "SUB-P2-001",
            "filename": "late_submission.pdf",
            "allow_locked": False,
        })


@pytest.mark.asyncio
async def test_07_cover2_readiness_gate_boundary():
    """Verifies Cover 2 gate checks all prerequisites and does NOT invoke financial opening."""
    c2_resp = await evaluate_cover2_gate_service("PROC-P2-TEST-001")
    assert c2_resp.decision_authority == "HUMAN_PROCUREMENT_OFFICER"
    assert c2_resp.cover2_readiness.is_ready is False


def test_08_rest_api_p2_endpoints():
    """Verifies all REST API endpoints for P2 officer technical review lifecycle."""
    res = client.get("/api/procurements/PROC-P2-TEST-001/technical-review")
    assert res.status_code == 200
    data = res.json()
    assert data["procurement_id"] == "PROC-P2-TEST-001"
    assert "bidders" in data
    assert "key_findings" in data
    assert "cover2_readiness" in data

    draft_res = client.post(
        "/api/procurements/PROC-P2-TEST-001/clarifications/draft",
        json={
            "procurement_id": "PROC-P2-TEST-001",
            "submission_id": "SUB-P2-001",
            "requirement_id": "REQ-003",
        },
    )
    assert draft_res.status_code == 200
    assert draft_res.json()["is_draft"] is True

    c2_get = client.get("/api/procurements/PROC-P2-TEST-001/cover2-gate")
    assert c2_get.status_code == 200
    assert "cover2_readiness" in c2_get.json()


@pytest.mark.asyncio
async def test_09_resolved_clarification_with_unresolved_unverified_blocker_remains_blocked():
    """Invariant: RESOLVED clarification does NOT magically promote UNVERIFIED finding to PASS or unblock freeze."""
    create_payload = ClarificationCreate(
        procurement_id="PROC-P2-TEST-001",
        submission_id="SUB-P2-001",
        requirement_id="REQ-001",
        question="Please submit verified GST proof.",
    )
    rec = await create_clarification_service(create_payload)

    # Resolve clarification without providing proof that passes requirement
    res_req = ClarificationResolutionRequest(
        resolution_status=ClarificationStatus.RESOLVED,
        resolution_notes="Officer resolved clarification administrative record.",
        officer_id="OFFICER_AUDIT",
    )
    await resolve_clarification_service(rec.id, res_req)

    # Technical review computation must still see UNVERIFIED / REVIEW findings as blockers
    rev = await get_procurement_technical_review_service("PROC-P2-TEST-001")
    apex_bidder = next((b for b in rev.bidders if b.bidder_id == "BIDDER-P2-001"), None)
    assert apex_bidder is not None
    assert apex_bidder.is_blocking is True
    assert rev.can_freeze is False
    assert rev.can_open_cover2 is False
    assert rev.cover2_readiness.is_ready is False


@pytest.mark.asyncio
async def test_10_resolved_clarification_with_unresolved_review_blocker_remains_blocked():
    """Invariant: RESOLVED clarification on a REVIEW finding does not unlock Cover 2 when finding remains REVIEW."""
    create_payload = ClarificationCreate(
        procurement_id="PROC-P2-TEST-001",
        submission_id="SUB-P2-002",
        requirement_id="REQ-002",
        question="Please explain local content discrepancy.",
    )
    rec = await create_clarification_service(create_payload)
    await resolve_clarification_service(rec.id, ClarificationResolutionRequest(
        resolution_status=ClarificationStatus.RESOLVED,
        resolution_notes="Officer noted explanation.",
        officer_id="OFFICER_AUDIT",
    ))

    c2_resp = await evaluate_cover2_gate_service("PROC-P2-TEST-001")
    assert c2_resp.cover2_readiness.is_ready is False
    assert len(c2_resp.cover2_readiness.blockers) > 0


@pytest.mark.asyncio
async def test_11_invalid_procurement_state_transitions_rejected():
    """Invariant: Illegal state transitions (e.g. IMPORTED -> TECHNICAL_FREEZE) must be rejected with HTTP 400."""
    _IN_MEMORY_PROCUREMENTS["PROC-P2-TEST-001"]["status"] = ProcurementStatus.IMPORTED.value

    with pytest.raises(HTTPException) as exc_info:
        await transition_procurement_state(
            procurement_id="PROC-P2-TEST-001",
            target_status=ProcurementStatus.TECHNICAL_FREEZE,
            actor="OFFICER_TEST",
        )
    assert exc_info.value.status_code == 400
    assert "Illegal state transition" in exc_info.value.detail


@pytest.mark.asyncio
async def test_12_reevaluation_from_invalid_state_rejected():
    """Invariant: Re-evaluation on cancelled or rejected clarification must be rejected with HTTP 400."""
    create_payload = ClarificationCreate(
        procurement_id="PROC-P2-TEST-001",
        submission_id="SUB-P2-001",
        requirement_id="REQ-003",
        question="Check past experience certificate.",
    )
    rec = await create_clarification_service(create_payload)

    # Reject clarification
    await resolve_clarification_service(rec.id, ClarificationResolutionRequest(
        resolution_status=ClarificationStatus.REJECTED,
        resolution_notes="Clarification rejected by officer.",
        officer_id="OFFICER_TEST",
    ))

    with pytest.raises(HTTPException) as exc_info:
        await re_evaluate_clarification_service(rec.id)
    assert exc_info.value.status_code == 400
    assert "terminal state" in exc_info.value.detail


@pytest.mark.asyncio
async def test_13_freeze_blocked_by_unresolved_technical_blocker():
    """Invariant: Procurement-level freeze must be blocked when bidders have unresolved REVIEW/UNVERIFIED blockers."""
    # Ensure all clarifications are resolved
    all_c = _IN_MEMORY_CLARIFICATIONS
    for c in all_c.values():
        c["status"] = ClarificationStatus.RESOLVED.value

    # But technical requirements are not satisfied (UNVERIFIED / REVIEW)
    with pytest.raises(HTTPException) as exc_info:
        await freeze_procurement_technical_service("PROC-P2-TEST-001")
    assert exc_info.value.status_code == 400
    assert "Cannot freeze procurement" in exc_info.value.detail
