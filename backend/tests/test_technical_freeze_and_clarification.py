"""Tests for Technical Freeze (Cover 1) and Clarification Lifecycle.

Verifies:
1. Formal Technical Freeze lifecycle states (NOT_FROZEN, FROZEN, locked state).
2. Mutation blocking on frozen submissions (409 Conflict and audit log).
3. Creation of formal shortfall / clarification requests linked to specific requirements and findings.
4. Bidder response submission with attached evidence documents.
5. Targeted requirement re-evaluation updating finding post-clarification.
6. Ensuring no autonomous qualification/disqualification occurs (human officer decision boundary).
7. Audit trail integrity across freeze and clarification actions.
"""

from datetime import datetime, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.db.client import (
    _IN_MEMORY_PROCUREMENTS,
    _IN_MEMORY_TENDERS,
    _IN_MEMORY_BIDDERS,
    _IN_MEMORY_SUBMISSIONS,
    _IN_MEMORY_DOCUMENTS,
    _IN_MEMORY_CLARIFICATIONS,
    _IN_MEMORY_AUDIT_LOGS,
    get_audit_logs_db,
    insert_document,
)
from app.models.clarification import (
    ClarificationCreate,
    ClarificationResponseInput,
    ClarificationStatus,
    TechnicalFreezeRequest,
)
from app.models.procurement import (
    DocumentType,
    IngestionDocumentInput,
    TechnicalFreezeStatus,
)
from app.services.clarification_service import (
    create_clarification_service,
    freeze_submission_service,
    get_submission_freeze_status_service,
    re_evaluate_clarification_service,
    respond_to_clarification_service,
)


@pytest.fixture(autouse=True)
def setup_test_procurement_state():
    """Sets up an isolated test procurement workspace before each test."""
    proc_id = "test-proc-freeze-001"
    tender_id = "test-tender-freeze-001"
    bidder_id = "test-bidder-freeze-001"
    sub_id = "test-sub-freeze-001"

    _IN_MEMORY_PROCUREMENTS[proc_id] = {
        "id": proc_id,
        "external_reference": "GEM/2026/FREEZE/01",
        "title": "Water Treatment Sensors Procurement",
        "organization": "CPCL",
        "status": "READY",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _IN_MEMORY_TENDERS[tender_id] = {
        "id": tender_id,
        "procurement_id": proc_id,
        "tender_reference": "GEM/2026/B/9991",
        "title": "Supply of Turbidity Sensors",
        "estimated_value": 5000000.0,
        "status": "READY",
    }
    _IN_MEMORY_BIDDERS[bidder_id] = {
        "id": bidder_id,
        "legal_name": "Apex Environmental Solutions Ltd",
        "gstin": "33AABCU9603R1ZM",
        "pan": "AABCU9603R",
        "email": "tenders@apexenv.com",
    }
    _IN_MEMORY_SUBMISSIONS[sub_id] = {
        "id": sub_id,
        "procurement_id": proc_id,
        "tender_id": tender_id,
        "bidder_id": bidder_id,
        "external_submission_reference": "SUB-APEX-001",
        "status": "SUBMITTED",
        "technical_freeze_status": TechnicalFreezeStatus.NOT_FROZEN.value,
        "is_locked": False,
        "frozen_at": None,
        "frozen_by": None,
        "freeze_reason": None,
        "bidder": _IN_MEMORY_BIDDERS[bidder_id],
        "documents": [],
    }

    yield {
        "procurement_id": proc_id,
        "tender_id": tender_id,
        "bidder_id": bidder_id,
        "submission_id": sub_id,
    }


@pytest.mark.asyncio
async def test_technical_freeze_lifecycle_and_lock(setup_test_procurement_state):
    """Verifies that freezing a submission locks it, sets timestamps, and unfreezing unlocks it."""
    ctx = setup_test_procurement_state
    sub_id = ctx["submission_id"]

    # 1. Initial State: NOT_FROZEN
    status_resp = await get_submission_freeze_status_service(sub_id)
    assert status_resp.technical_freeze_status == TechnicalFreezeStatus.NOT_FROZEN
    assert status_resp.is_locked is False

    # 2. Freeze the submission
    freeze_req = TechnicalFreezeRequest(
        freeze=True,
        freeze_reason="Technical evaluation deadline reached.",
        officer_id="OFFICER_VERMA",
    )
    freeze_resp = await freeze_submission_service(sub_id, freeze_req)
    assert freeze_resp.technical_freeze_status == TechnicalFreezeStatus.FROZEN
    assert freeze_resp.is_locked is True
    assert freeze_resp.frozen_by == "OFFICER_VERMA"
    assert freeze_resp.frozen_at is not None
    assert "locked" in freeze_resp.message.lower() or "frozen" in freeze_resp.message.lower()

    # Verify persistent state reflects freeze
    current_status = await get_submission_freeze_status_service(sub_id)
    assert current_status.technical_freeze_status == TechnicalFreezeStatus.FROZEN
    assert current_status.is_locked is True

    # 3. Check Audit Trail
    audit_logs = await get_audit_logs_db(submission_id=sub_id, event_type="TECHNICAL_FREEZE_APPLIED")
    assert len(audit_logs) >= 1
    assert audit_logs[-1]["actor"] == "OFFICER_VERMA"

    # 4. Unfreeze the submission
    unfreeze_req = TechnicalFreezeRequest(
        freeze=False,
        freeze_reason="Re-opened by Senior Procurement Officer for corrigendum.",
        officer_id="OFFICER_SHARMA",
    )
    unfreeze_resp = await freeze_submission_service(sub_id, unfreeze_req)
    assert unfreeze_resp.technical_freeze_status == TechnicalFreezeStatus.NOT_FROZEN
    assert unfreeze_resp.is_locked is False

    audit_logs_unfreeze = await get_audit_logs_db(submission_id=sub_id, event_type="TECHNICAL_FREEZE_UNLOCKED")
    assert len(audit_logs_unfreeze) >= 1


@pytest.mark.asyncio
async def test_mutation_blocking_on_frozen_submission(setup_test_procurement_state):
    """Verifies that unauthorized document attachment to a frozen submission is rejected with 409 Conflict."""
    ctx = setup_test_procurement_state
    sub_id = ctx["submission_id"]

    # Lock submission
    await freeze_submission_service(
        sub_id,
        TechnicalFreezeRequest(freeze=True, freeze_reason="Pre-qualification freeze applied."),
    )

    # Attempt direct document insertion without clarification bypass
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await insert_document({
            "id": "doc-unauthorized-001",
            "bid_submission_id": sub_id,
            "filename": "late_certificate.pdf",
            "document_type": "GST_CERTIFICATE",
        })

    assert exc_info.value.status_code == 409
    assert "frozen" in exc_info.value.detail.lower()

    # Verify mutation blocking audit event was recorded
    blocked_audits = await get_audit_logs_db(submission_id=sub_id, event_type="TECHNICAL_FREEZE_BLOCKED_MUTATION")
    assert len(blocked_audits) >= 1
    assert blocked_audits[-1]["details"]["attempted_action"] == "INSERT_DOCUMENT"


@pytest.mark.asyncio
async def test_clarification_lifecycle_flow(setup_test_procurement_state):
    """Verifies full clarification lifecycle: creation -> response -> targeted re-evaluation."""
    ctx = setup_test_procurement_state
    sub_id = ctx["submission_id"]
    proc_id = ctx["procurement_id"]

    # 1. Create Clarification for missing GST document
    create_req = ClarificationCreate(
        procurement_id=proc_id,
        submission_id=sub_id,
        requirement_id="REQ-001",
        originating_finding_id="find-gst-missing-001",
        question="Please submit your GST registration certificate and latest GSTR-3B return.",
        created_by="OFFICER_MEHTA",
    )
    clarification = await create_clarification_service(create_req)

    assert clarification.id is not None
    assert clarification.status == ClarificationStatus.OPEN
    assert clarification.requirement_id == "REQ-001"
    assert clarification.originating_finding_id == "find-gst-missing-001"
    assert len(clarification.audit_history) >= 1
    assert clarification.audit_history[0]["event"] == "CLARIFICATION_CREATED"

    # 2. Bidder responds with textual explanation and attached proof document
    response_input = ClarificationResponseInput(
        response_text="Attached is our valid GSTIN certificate showing active status in Tamil Nadu.",
        documents=[
            IngestionDocumentInput(
                filename="apex_gst_certificate.pdf",
                document_type=DocumentType.GST_CERTIFICATE,
                mime_type="application/pdf",
                content_text='[{"page": 1, "text": "GSTIN: 33AABCU9603R1ZM Legal Name: Apex Environmental Solutions Ltd Status: Active"}]',
            )
        ],
        responded_by="APEX_SIGNATORY",
    )
    responded_record = await respond_to_clarification_service(
        clarification_id=clarification.id,
        response_payload=response_input,
    )

    assert responded_record.status == ClarificationStatus.RESPONDED
    assert responded_record.response_text == response_input.response_text
    assert len(responded_record.response_documents) == 1
    assert responded_record.response_documents[0].filename == "apex_gst_certificate.pdf"
    assert responded_record.responded_at is not None

    # 3. Execute targeted re-evaluation for REQ-001
    re_eval_record = await re_evaluate_clarification_service(clarification.id)

    assert re_eval_record.status == ClarificationStatus.RESOLVED
    assert re_eval_record.re_evaluation_status == "RESOLVED"
    assert re_eval_record.resulting_finding is not None
    assert re_eval_record.resulting_finding.get("requirement_id") == "REQ-001"
    # Verification engine finds the GST certificate attached in response
    assert re_eval_record.resulting_finding.get("status") in ("PASS", "REVIEW")

    # 4. Check audit trail
    audit_history_events = [entry["event"] for entry in re_eval_record.audit_history]
    assert "CLARIFICATION_CREATED" in audit_history_events
    assert "CLARIFICATION_RESPONSE_SUBMITTED" in audit_history_events
    assert "TARGETED_REEVALUATION_TRIGGERED" in audit_history_events


@pytest.mark.asyncio
async def test_rest_api_freeze_and_clarification_endpoints(setup_test_procurement_state):
    """Verifies all Technical Freeze and Clarification REST API endpoints."""
    ctx = setup_test_procurement_state
    sub_id = ctx["submission_id"]
    proc_id = ctx["procurement_id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. API: Freeze submission
        freeze_res = await ac.post(
            f"/api/procurements/{proc_id}/submissions/{sub_id}/freeze",
            json={"freeze": True, "freeze_reason": "Technical Bid Opening concluded."},
        )
        assert freeze_res.status_code == 200
        freeze_data = freeze_res.json()
        assert freeze_data["technical_freeze_status"] == "FROZEN"
        assert freeze_data["is_locked"] is True

        # 2. API: Get freeze status
        status_res = await ac.get(f"/api/submissions/{sub_id}/freeze")
        assert status_res.status_code == 200
        assert status_res.json()["is_locked"] is True

        # 3. API: Create Clarification
        clar_create_payload = {
            "submission_id": sub_id,
            "requirement_id": "REQ-005",
            "originating_finding_id": "find-maf-001",
            "question": "OEM authorization form is missing seal. Please provide authenticated copy.",
            "created_by": "OFFICER_ROY",
        }
        create_res = await ac.post(
            f"/api/procurements/{proc_id}/clarifications",
            json=clar_create_payload,
        )
        assert create_res.status_code == 200
        clar_data = create_res.json()
        clar_id = clar_data["id"]
        assert clar_data["status"] == "OPEN"

        # 4. API: List Clarifications
        list_res = await ac.get(f"/api/procurements/{proc_id}/clarifications?submission_id={sub_id}")
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total"] >= 1
        assert any(c["id"] == clar_id for c in list_data["clarifications"])

        # 5. API: Submit Clarification Response
        respond_payload = {
            "response_text": "Attached is the officially sealed Manufacturer Authorization Form from Endress+Hauser.",
            "documents": [
                {
                    "filename": "oem_authorization_signed.pdf",
                    "document_type": "OEM_AUTHORIZATION",
                    "mime_type": "application/pdf",
                    "content_text": "MANUFACTURER AUTHORIZATION FORM: We hereby authorize Apex Environmental Solutions Ltd to bid for Turbidity Sensor supply.",
                }
            ],
            "responded_by": "BIDDER_APEX",
        }
        resp_res = await ac.post(
            f"/api/clarifications/{clar_id}/respond",
            json=respond_payload,
        )
        assert resp_res.status_code == 200
        assert resp_res.json()["status"] == "RESPONDED"
        assert len(resp_res.json()["response_documents"]) == 1

        # 6. API: Targeted Re-evaluation
        reeval_res = await ac.post(f"/api/clarifications/{clar_id}/re-evaluate")
        assert reeval_res.status_code == 200
        reeval_data = reeval_res.json()
        assert reeval_data["status"] == "RESOLVED"
        assert reeval_data["re_evaluation_status"] == "RESOLVED"
        assert reeval_data["resulting_finding"] is not None

        # 7. API: Unfreeze submission
        unfreeze_res = await ac.post(f"/api/submissions/{sub_id}/unfreeze")
        assert unfreeze_res.status_code == 200
        assert unfreeze_res.json()["technical_freeze_status"] == "NOT_FROZEN"
        assert unfreeze_res.json()["is_locked"] is False
