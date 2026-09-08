"""Focused Backend Action Studio Integration Test Suite.

Verifies:
1. Action context correctly consumes canonical technical results.
2. Action context correctly consumes canonical financial results when available.
3. Draft generation is evidence-grounded.
4. AI draft never changes procurement/evaluation state.
5. Deterministic fallback works if AI fails.
6. Note for File draft creation.
7. Evaluation Committee Report draft creation.
8. LoA generation blocked when no legitimate L1 exists.
9. Rejection/regret draft uses actual exclusion reason.
10. Draft editing does not mutate procurement.
11. Version history works.
12. Approval requires appropriate actor.
13. Approval does not dispatch.
14. Audit events are generated.
15. End-to-end API integration and workflow safety.
"""

import asyncio
import os
import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

try:
    from app.api.main import app
    from app.models.action_studio import (
        ActionDocumentStatus,
        ActionDocumentType,
        ActionStudioDocument,
        ApproveDraftRequest,
        CreateDraftRequest,
        UpdateDraftRequest,
    )
    from app.services.action_studio_ai_service import ActionStudioAiDraftingService
    from app.services.action_studio_context_service import ActionStudioContextService
    from app.services.action_studio_service import (
        _ACTION_STUDIO_AUDIT_LOGS,
        _ACTION_STUDIO_DRAFTS,
        _ACTION_STUDIO_VERSIONS,
        ActionStudioService,
    )
    from app.db import client as db_client
except ImportError:
    from api.main import app
    from models.action_studio import (
        ActionDocumentStatus,
        ActionDocumentType,
        ActionStudioDocument,
        ApproveDraftRequest,
        CreateDraftRequest,
        UpdateDraftRequest,
    )
    from services.action_studio_ai_service import ActionStudioAiDraftingService
    from services.action_studio_context_service import ActionStudioContextService
    from services.action_studio_service import (
        _ACTION_STUDIO_AUDIT_LOGS,
        _ACTION_STUDIO_DRAFTS,
        _ACTION_STUDIO_VERSIONS,
        ActionStudioService,
    )
    from db import client as db_client


class TestActionStudioFoundation(unittest.TestCase):
    """Test suite covering the 15 Action Studio requirements."""

    def setUp(self):
        """Seed synthetic test fixtures without altering canonical seed files."""
        self.client = TestClient(app)
        self.procurement_id = f"PROC-TEST-{uuid.uuid4().hex[:8]}"
        self.tender_id = f"TENDER-TEST-{uuid.uuid4().hex[:8]}"

        # Seed synthetic procurement record
        self.proc_record = {
            "id": self.procurement_id,
            "external_reference": f"GEM/2026/TEST/{self.procurement_id}",
            "title": "Synthetic Test Water Supply Procurement",
            "organization": "Test Department of Water Resources",
            "source_system": "MOCK_GEM",
            "status": "READY",
            "tenders": [
                {
                    "id": self.tender_id,
                    "tender_reference": self.procurement_id,
                    "title": "Supply of Automated Water Quality Monitors",
                    "estimated_value": 50000000.0,
                    "category": "GOODS",
                    "requirements": [],
                }
            ],
        }
        db_client._IN_MEMORY_PROCUREMENTS[self.procurement_id] = self.proc_record

        # Seed synthetic bidder evaluations (Bidder Alpha PASS, Bidder Beta FAIL)
        self.bidder_alpha_id = "BIDDER-ALPHA-01"
        self.bidder_beta_id = "BIDDER-BETA-02"

        self.eval_alpha = {
            "tender_id": self.procurement_id,
            "bidder_name": "Alpha Infrastructure Ltd",
            "bid_id": self.bidder_alpha_id,
            "evaluation_data": {
                "bidder_name": "Alpha Infrastructure Ltd",
                "bidder_id": self.bidder_alpha_id,
                "compliance_findings": [
                    {
                        "requirement_id": "REQ-001",
                        "state": "PASS",
                        "risk_level": "NONE",
                        "reasoning_trace": "Valid active GSTIN certificate verified.",
                        "evidence_ids": ["EVD-GST-01"],
                    }
                ],
                "financial_evaluation": {
                    "total_bid_value": 42000000.0,
                    "math_errors_found": False,
                    "abnormally_low_bid": False,
                    "audit_notes": ["Mathematical calculation verified."],
                },
            },
        }

        self.eval_beta = {
            "tender_id": self.procurement_id,
            "bidder_name": "Beta Water Tech",
            "bid_id": self.bidder_beta_id,
            "evaluation_data": {
                "bidder_name": "Beta Water Tech",
                "bidder_id": self.bidder_beta_id,
                "compliance_findings": [
                    {
                        "requirement_id": "REQ-002",
                        "state": "FAIL",
                        "risk_level": "HIGH",
                        "reasoning_trace": "Missing mandatory Manufacturer Authorization Form (MAF).",
                        "evidence_ids": ["EVD-MAF-MISSING"],
                    }
                ],
            },
        }

        db_client._IN_MEMORY_EVALUATIONS.extend([self.eval_alpha, self.eval_beta])

    def tearDown(self):
        """Cleanup synthetic test records."""
        db_client._IN_MEMORY_PROCUREMENTS.pop(self.procurement_id, None)

    def test_01_action_context_consumes_canonical_technical_results(self):
        """1. Action context correctly consumes canonical technical results."""
        context = asyncio.run(ActionStudioContextService.build_evidence_context(self.procurement_id))
        tech = context["technical"]

        self.assertTrue(tech["technical_freeze_completed"])
        eligible_names = [b["legal_name"] for b in tech["technically_eligible_bidders"]]
        excluded_names = [b["legal_name"] for b in tech["excluded_bidders"]]

        self.assertIn("Alpha Infrastructure Ltd", eligible_names)
        self.assertIn("Beta Water Tech", excluded_names)

    def test_02_action_context_consumes_canonical_financial_results(self):
        """2. Action context correctly consumes canonical financial results when available."""
        context = asyncio.run(ActionStudioContextService.build_evidence_context(self.procurement_id))
        fin = context["financial"]

        self.assertTrue(fin["financial_evaluation_completed"])
        self.assertEqual(fin["evaluated_amounts"].get("Alpha Infrastructure Ltd"), 42000000.0)
        self.assertIsNotNone(fin["l1_bidder"])
        self.assertEqual(fin["l1_bidder"]["bidder_name"], "Alpha Infrastructure Ltd")

    def test_03_draft_generation_is_evidence_grounded(self):
        """3. Draft generation is evidence-grounded."""
        req = CreateDraftRequest(document_type=ActionDocumentType.NOTE_FOR_FILE)
        doc = asyncio.run(ActionStudioService.create_draft(self.procurement_id, req))

        self.assertTrue(doc.is_draft)
        self.assertEqual(doc.decision_authority, "HUMAN_PROCUREMENT_OFFICER")
        self.assertIn("Alpha Infrastructure Ltd", doc.content)
        self.assertIn("Beta Water Tech", doc.content)
        self.assertTrue(len(doc.evidence_references) > 0)

    def test_04_ai_draft_never_changes_procurement_state(self):
        """4. AI draft never changes procurement/evaluation state."""
        proc_before = db_client._IN_MEMORY_PROCUREMENTS[self.procurement_id].copy()

        req = CreateDraftRequest(document_type=ActionDocumentType.NOTE_FOR_FILE)
        asyncio.run(ActionStudioService.create_draft(self.procurement_id, req))

        proc_after = db_client._IN_MEMORY_PROCUREMENTS[self.procurement_id]
        self.assertEqual(proc_before["status"], proc_after["status"])
        self.assertEqual(proc_before["title"], proc_after["title"])

    def test_05_deterministic_fallback_works_if_ai_fails(self):
        """5. Deterministic fallback works if AI fails or key is missing."""
        context = asyncio.run(ActionStudioContextService.build_evidence_context(self.procurement_id))
        
        content = ActionStudioAiDraftingService._generate_deterministic_fallback(
            ActionDocumentType.NOTE_FOR_FILE, context
        )

        self.assertIn("# PROCUREMENT NOTE FOR FILE", content)
        self.assertIn("Alpha Infrastructure Ltd", content)
        self.assertIn("PENDING HUMAN PROCUREMENT OFFICER DECISION", content)

    def test_06_note_for_file_draft_creation(self):
        """6. Note for File draft creation."""
        req = CreateDraftRequest(document_type=ActionDocumentType.NOTE_FOR_FILE)
        doc = asyncio.run(ActionStudioService.create_draft(self.procurement_id, req))

        self.assertEqual(doc.document_type, ActionDocumentType.NOTE_FOR_FILE)
        self.assertEqual(doc.status, ActionDocumentStatus.DRAFT)
        self.assertIn("PROCUREMENT NOTE FOR FILE", doc.content)

    def test_07_evaluation_committee_report_creation(self):
        """7. Evaluation Committee Report draft creation."""
        req = CreateDraftRequest(document_type=ActionDocumentType.EVALUATION_COMMITTEE_REPORT)
        doc = asyncio.run(ActionStudioService.create_draft(self.procurement_id, req))

        self.assertEqual(doc.document_type, ActionDocumentType.EVALUATION_COMMITTEE_REPORT)
        self.assertIn("TENDER EVALUATION COMMITTEE REPORT", doc.content)
        self.assertIn("Alpha Infrastructure Ltd", doc.content)

    def test_08_loa_generation_blocked_when_no_legitimate_l1_exists(self):
        """8. LoA generation blocked when no legitimate L1 exists or Cover 2 not opened."""
        # Create procurement with technical freeze completed but without financial evaluation
        no_fin_proc_id = f"PROC-NOFIN-{uuid.uuid4().hex[:8]}"
        db_client._IN_MEMORY_PROCUREMENTS[no_fin_proc_id] = {
            "id": no_fin_proc_id,
            "external_reference": no_fin_proc_id,
            "title": "No Financial Eval Procurement",
            "organization": "Test Agency",
            "status": "READY",
        }

        req = CreateDraftRequest(document_type=ActionDocumentType.LETTER_OF_AWARD)
        with self.assertRaises(ValueError) as err_ctx:
            asyncio.run(ActionStudioService.create_draft(no_fin_proc_id, req))

        self.assertIn("Cover 2 financial evaluation has not completed", str(err_ctx.exception))

    def test_09_rejection_regret_draft_uses_actual_exclusion_reason(self):
        """9. Rejection/regret draft uses actual exclusion reason."""
        req = CreateDraftRequest(
            document_type=ActionDocumentType.REJECTION_LETTER,
            target_bidder_id=self.bidder_beta_id,
        )
        doc = asyncio.run(ActionStudioService.create_draft(self.procurement_id, req))

        self.assertEqual(doc.document_type, ActionDocumentType.REJECTION_LETTER)
        self.assertIn("Beta Water Tech", doc.content)
        self.assertIn("Missing mandatory Manufacturer Authorization Form (MAF)", doc.content)

    def test_10_draft_editing_does_not_mutate_procurement(self):
        """10. Draft editing does not mutate procurement state or findings."""
        req_create = CreateDraftRequest(document_type=ActionDocumentType.NOTE_FOR_FILE)
        doc = asyncio.run(ActionStudioService.create_draft(self.procurement_id, req_create))

        req_edit = UpdateDraftRequest(
            content="Officer customized draft content note for file.",
            updated_by="OFFICER_SMITH",
            change_summary="Refined introduction paragraph.",
        )
        updated_doc = asyncio.run(ActionStudioService.update_draft_content(doc.id, req_edit))

        self.assertEqual(updated_doc.version, 2)
        self.assertEqual(updated_doc.status, ActionDocumentStatus.EDITED)
        self.assertEqual(updated_doc.content, "Officer customized draft content note for file.")

        # Procurement status remains READY
        proc = db_client._IN_MEMORY_PROCUREMENTS[self.procurement_id]
        self.assertEqual(proc["status"], "READY")

    def test_11_version_history_works(self):
        """11. Version history works."""
        req_create = CreateDraftRequest(document_type=ActionDocumentType.NOTE_FOR_FILE)
        doc = asyncio.run(ActionStudioService.create_draft(self.procurement_id, req_create))

        req_edit = UpdateDraftRequest(content="Version 2 content", updated_by="OFFICER_A")
        asyncio.run(ActionStudioService.update_draft_content(doc.id, req_edit))

        versions = asyncio.run(ActionStudioService.list_draft_versions(doc.id))
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].version, 1)
        self.assertEqual(versions[1].version, 2)
        self.assertEqual(versions[1].content, "Version 2 content")

    def test_12_approval_requires_appropriate_actor(self):
        """12. Approval requires appropriate human officer actor."""
        req_create = CreateDraftRequest(document_type=ActionDocumentType.NOTE_FOR_FILE)
        doc = asyncio.run(ActionStudioService.create_draft(self.procurement_id, req_create))

        # Blank/whitespace officer actor should raise Exception
        with self.assertRaises(Exception):
            req_app_invalid = ApproveDraftRequest(officer_actor="", notes="Approved")
            asyncio.run(ActionStudioService.approve_draft(doc.id, req_app_invalid))

        # Valid officer actor should succeed
        req_app_valid = ApproveDraftRequest(officer_actor="OFFICER_JOHN_DOE", notes="Approved after committee review.")
        approved_doc = asyncio.run(ActionStudioService.approve_draft(doc.id, req_app_valid))

        self.assertEqual(approved_doc.status, ActionDocumentStatus.APPROVED)
        self.assertEqual(approved_doc.approved_by, "OFFICER_JOHN_DOE")
        self.assertFalse(approved_doc.is_draft)

    def test_13_approval_does_not_dispatch(self):
        """13. Approval does not dispatch."""
        req_create = CreateDraftRequest(
            document_type=ActionDocumentType.LETTER_OF_AWARD,
            target_bidder_id=self.bidder_alpha_id,
        )
        doc = asyncio.run(ActionStudioService.create_draft(self.procurement_id, req_create))

        req_app = ApproveDraftRequest(officer_actor="CHIEF_PROCUREMENT_OFFICER")
        approved_doc = asyncio.run(ActionStudioService.approve_draft(doc.id, req_app))

        self.assertEqual(approved_doc.status, ActionDocumentStatus.APPROVED)
        self.assertNotIn("DISPATCHED", [approved_doc.status.value])
        self.assertFalse(hasattr(approved_doc, "dispatched_at"))

    def test_14_audit_events_are_generated(self):
        """14. Audit events are generated."""
        audit_count_before = len(_ACTION_STUDIO_AUDIT_LOGS)

        req_create = CreateDraftRequest(document_type=ActionDocumentType.NOTE_FOR_FILE)
        doc = asyncio.run(ActionStudioService.create_draft(self.procurement_id, req_create))

        req_edit = UpdateDraftRequest(content="Edited content", updated_by="OFFICER_1")
        asyncio.run(ActionStudioService.update_draft_content(doc.id, req_edit))

        req_app = ApproveDraftRequest(officer_actor="OFFICER_1")
        asyncio.run(ActionStudioService.approve_draft(doc.id, req_app))

        audit_count_after = len(_ACTION_STUDIO_AUDIT_LOGS)
        self.assertTrue(audit_count_after > audit_count_before)

        event_types = [e["event_type"] for e in _ACTION_STUDIO_AUDIT_LOGS if e["document_id"] == doc.id]
        self.assertIn("ACTION_DRAFT_CREATED", event_types)
        self.assertIn("ACTION_DRAFT_EDITED", event_types)
        self.assertIn("ACTION_DRAFT_APPROVED", event_types)

    def test_15_api_endpoints_integration(self):
        """15. REST API Endpoints Integration Test."""
        # 1. Create Draft
        resp_create = self.client.post(
            f"/api/procurements/{self.procurement_id}/action-studio/drafts",
            json={"document_type": "NOTE_FOR_FILE"},
        )
        self.assertEqual(resp_create.status_code, 201)
        doc_data = resp_create.json()
        draft_id = doc_data["id"]

        # 2. Get Draft Detail
        resp_get = self.client.get(f"/api/action-studio/drafts/{draft_id}")
        self.assertEqual(resp_get.status_code, 200)

        # 3. Patch Edit Content
        resp_patch = self.client.patch(
            f"/api/action-studio/drafts/{draft_id}",
            json={"content": "Patched content via API", "updated_by": "API_OFFICER"},
        )
        self.assertEqual(resp_patch.status_code, 200)
        self.assertEqual(resp_patch.json()["version"], 2)

        # 4. List Versions
        resp_versions = self.client.get(f"/api/action-studio/drafts/{draft_id}/versions")
        self.assertEqual(resp_versions.status_code, 200)
        self.assertEqual(len(resp_versions.json()), 2)

        # 5. Approve Draft
        resp_approve = self.client.post(
            f"/api/action-studio/drafts/{draft_id}/approve",
            json={"officer_actor": "API_APPROVING_OFFICER", "notes": "Approved via API"},
        )
        self.assertEqual(resp_approve.status_code, 200)
        self.assertEqual(resp_approve.json()["status"], "APPROVED")

        # 6. List Procurements Drafts
        resp_list = self.client.get(f"/api/procurements/{self.procurement_id}/action-studio")
        self.assertEqual(resp_list.status_code, 200)
        self.assertTrue(resp_list.json()["total"] >= 1)


if __name__ == "__main__":
    unittest.main()
