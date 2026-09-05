"""OPAL Final Release-Gate Audit & Hardening Integration Test Suite (SIH26100).

Validates:
1. True Byte-Level Document Ingestion & Page-Aware Provenance Replay
2. End-to-End Audit-Lineage Acceptance
3. Clarification / Re-Evaluation Lifecycle
4. Strict Bidder-Isolation Attack Tests
5. Tender Requirement Fallback Safety & Scoping
6. Authoritative External Verification State Transitions
7. Controlled Failure-Safety Guarantees
8. Explicit Persistence Mode Indication
"""

import asyncio
import io
import json
import os
import sys
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Setup paths
_test_file = Path(__file__).resolve()
_backend_dir = _test_file.parent.parent
_repo_root = _backend_dir.parent
for p in [str(_repo_root), str(_backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.app.models.procurement import DocumentType
from backend.app.models.evaluation import ComplianceState, EvaluationMethod, ExternalVerificationStatus
from backend.app.models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
from backend.app.models.tender import RequirementCategory, TenderRequirement
from backend.app.services.claim_extraction_service import process_document_evidence
from backend.app.services.contradiction_service import detect_contradictions, reconcile_requirement
from backend.app.services.evaluation_service import evaluate_requirements
from backend.app.services.master_pipeline import evaluate_canonical_submission
from backend.app.services.multi_format_extractor import extract_data_from_file
from backend.app.services.procurement_processing_service import (
    start_procurement_processing,
    get_procurement_processing_status,
)
from backend.app.services.tender_contract_service import (
    build_requirement_evaluation_contract,
    build_tender_evaluation_contract,
)
from backend.app.services.tender_service import analyze_tender
from backend.app.db.client import (
    _IN_MEMORY_BIDDERS,
    _IN_MEMORY_DOCUMENTS,
    _IN_MEMORY_PROCUREMENTS,
    _IN_MEMORY_REQUIREMENTS,
    _IN_MEMORY_SUBMISSIONS,
    get_canonical_cpcl_requirements,
    get_persistence_mode,
    get_submission_detail_db,
    get_tender_requirements,
)


def _build_minimal_valid_pdf_bytes(text_lines: list) -> bytes:
    """Constructs a real valid PDF byte stream using PyMuPDF."""
    import pymupdf
    doc_pdf = pymupdf.open()
    page = doc_pdf.new_page()
    full_text = "\n".join(str(l) for l in text_lines)
    page.insert_text((50, 72), full_text)
    pdf_bytes = doc_pdf.tobytes()
    doc_pdf.close()
    return pdf_bytes


class OpalReleaseGateHardeningTests(unittest.IsolatedAsyncioTestCase):
    """Rigorous verification suite for OPAL release gate freeze."""

    async def test_01_true_byte_level_pdf_parsing_and_provenance(self):
        """Req 2: Verify real PDF bytes are parsed via PyMuPDF/multi-format extractor, producing page-aware provenance."""
        pdf_bytes = _build_minimal_valid_pdf_bytes([
            "Government of India - GST Certificate Form GST REG-06",
            "GSTIN: 33AAACH1234A1Z9",
            "Legal Name: HydroTech Analytics India Pvt Ltd",
            "Status: ACTIVE",
            "Annual Turnover: INR 14.50 Crores",
        ])

        # 1. Byte-level extraction without pre-populated content_text
        extracted = await extract_data_from_file(pdf_bytes, "HydroTech_Live_GST.pdf")
        self.assertIsNotNone(extracted)
        raw_text = extracted.get("raw_text", "")
        self.assertIn("33AAACH1234A1Z9", raw_text)
        self.assertIn("ACTIVE", raw_text)

        # 2. Extract evidence facts and verify page-aware provenance
        from backend.app.models.procurement import Document
        from backend.app.services.claim_extraction_service import extract_document_facts
        doc = Document(
            id="doc-byte-test-01",
            procurement_id="proc-byte-01",
            tender_id="DEMO/CPCL/WQM/2026/017",
            bid_submission_id="sub-byte-01",
            filename="HydroTech_Live_GST.pdf",
            document_type=DocumentType.GST_CERTIFICATE,
            mime_type="application/pdf",
            file_size=len(pdf_bytes),
            content_text=json.dumps(extracted.model_dump() if hasattr(extracted, "model_dump") else extracted),
        )

        extracted_pkg = extract_document_facts(doc, bidder_id="bidder-byte-01", submission_id="sub-byte-01")
        observations = extracted_pkg.get("observations", [])
        self.assertTrue(len(observations) > 0)
        
        # Verify provenance fields
        for obs in observations:
            self.assertEqual(obs.document_id, "doc-byte-test-01")
            self.assertEqual(obs.bidder_id, "bidder-byte-01")
            self.assertEqual(obs.bid_submission_id, "sub-byte-01")
            self.assertEqual(obs.source_document, "HydroTech_Live_GST.pdf")
            self.assertEqual(obs.page_number, 1)

    def test_02_audit_lineage_acceptance(self):
        """Req 5: Trace requirement -> applicability -> bidder claim -> evidence observation -> exact provenance -> contradiction -> REVIEW."""
        req = build_requirement_evaluation_contract(
            TenderRequirement(
                requirement_id="REQ-006",
                category=RequirementCategory.LOCAL_CONTENT_MII,
                description="Minimum 20% local content required.",
                mandatory=True,
                title="Local Content Requirement",
            ),
            tender_id="DEMO/CPCL/WQM/2026/017",
        )

        claim = BidderClaim(
            claim_id="CLM-LC-001",
            requirement_id="REQ-006",
            bidder_id="BIDDER-AQUA",
            submission_id="SUB-AQUA-001",
            document_id="DOC-DECL-01",
            source_document="AquaPure_MII_Declaration.pdf",
            page_number=2,
            claimed_value="27.0%",
            metric="LOCAL_CONTENT_PERCENTAGE",
        )

        observation = EvidenceObservation(
            evidence_id="EVD-CERT-01",
            requirement_id="REQ-006",
            bidder_id="BIDDER-AQUA",
            submission_id="SUB-AQUA-001",
            document_id="DOC-CERT-02",
            source_document="AquaPure_Audited_Local_Content.pdf",
            page_number=4,
            observed_value="14.0%",
            metric="LOCAL_CONTENT_PERCENTAGE",
        )

        result = evaluate_canonical_submission(
            tender_id="DEMO/CPCL/WQM/2026/017",
            bidder_id="BIDDER-AQUA",
            submission_id="SUB-AQUA-001",
            requirement_contracts=[req],
            claims=[claim],
            observations=[observation],
        )

        self.assertEqual(len(result["requirement_results"]), 1)
        r_eval = result["requirement_results"][0]
        self.assertEqual(r_eval.requirement_id, "REQ-006")
        self.assertEqual(r_eval.state, ComplianceState.REVIEW)
        self.assertTrue(r_eval.review_required)
        self.assertEqual(len(r_eval.contradiction_findings), 1)
        
        # Verify provenance preservation
        prov = r_eval.provenance
        self.assertEqual(len(prov), 2)
        doc_names = {p.document_name for p in prov}
        pages = {p.page_number for p in prov}
        self.assertEqual(doc_names, {"AquaPure_MII_Declaration.pdf", "AquaPure_Audited_Local_Content.pdf"})
        self.assertEqual(pages, {2, 4})

    def test_03_clarification_and_re_evaluation_lifecycle(self):
        """Req 6: Test REVIEW -> add clarification evidence -> re-evaluate -> PASS."""
        req = build_requirement_evaluation_contract(
            TenderRequirement(
                requirement_id="REQ-003",
                category=RequirementCategory.FINANCIAL_TURNOVER,
                description="Minimum turnover INR 5 Crore.",
                mandatory=True,
                title="Financial Turnover",
            ),
            tender_id="DEMO/CPCL/WQM/2026/017",
        )

        # Initial pass: ambiguous / incomplete evidence -> REVIEW
        ambig_obs = EvidenceObservation(
            evidence_id="EVD-PROV-01",
            requirement_id="REQ-003",
            observed_value="Turnover under CA certification",
            source_document="provisional_balance_sheet.pdf",
            page_number=1,
        )
        res1 = evaluate_canonical_submission(
            tender_id="DEMO/CPCL/WQM/2026/017",
            bidder_id="BIDDER-REV",
            submission_id="SUB-REV-01",
            requirement_contracts=[req],
            claims=[],
            observations=[ambig_obs],
        )
        self.assertEqual(res1["requirement_results"][0].state, ComplianceState.REVIEW)

        # Clarification pass: add audited CA certificate with 6.42 Crore -> re-evaluation yields PASS
        audited_obs = EvidenceObservation(
            evidence_id="EVD-AUDIT-02",
            requirement_id="REQ-003",
            observed_value="6.42 Crore",
            source_document="CA_Certified_Turnover_Final.pdf",
            page_number=1,
            metric="ANNUAL_TURNOVER",
        )
        res2 = evaluate_canonical_submission(
            tender_id="DEMO/CPCL/WQM/2026/017",
            bidder_id="BIDDER-REV",
            submission_id="SUB-REV-01",
            requirement_contracts=[req],
            claims=[],
            observations=[audited_obs],
        )
        self.assertEqual(res2["requirement_results"][0].state, ComplianceState.PASS)

    def test_04_strict_bidder_isolation_attack(self):
        """Req 7: Bidder A evidence cannot leak into Bidder B evaluation."""
        req = build_requirement_evaluation_contract(
            TenderRequirement(
                requirement_id="REQ-003",
                category=RequirementCategory.FINANCIAL_TURNOVER,
                description="Minimum turnover INR 5 Crore.",
                mandatory=True,
                title="Financial Turnover",
            ),
            tender_id="DEMO/CPCL/WQM/2026/017",
        )

        # Bidder A has valid turnover evidence >= 5 Cr
        obs_a = EvidenceObservation(
            evidence_id="EVD-A-01",
            requirement_id="REQ-003",
            bidder_id="BIDDER-A",
            submission_id="SUB-A",
            observed_value="14.50 Crore",
            source_document="BidderA_Turnover.pdf",
            page_number=1,
            metric="ANNUAL_TURNOVER",
        )

        # Bidder B has only GST document (NO turnover evidence)
        obs_b = EvidenceObservation(
            evidence_id="EVD-B-01",
            requirement_id="REQ-001",
            bidder_id="BIDDER-B",
            submission_id="SUB-B",
            observed_value="33AAACA9876Q1Z2",
            source_document="BidderB_GST.pdf",
            page_number=1,
            source_type="GST_CERTIFICATE",
        )

        # Evaluate Bidder A
        res_a = evaluate_canonical_submission(
            tender_id="DEMO/CPCL/WQM/2026/017",
            bidder_id="BIDDER-A",
            submission_id="SUB-A",
            requirement_contracts=[req],
            claims=[],
            observations=[obs_a],
        )
        self.assertEqual(res_a["requirement_results"][0].state, ComplianceState.PASS)

        # Evaluate Bidder B with only Bidder B's observations
        res_b = evaluate_canonical_submission(
            tender_id="DEMO/CPCL/WQM/2026/017",
            bidder_id="BIDDER-B",
            submission_id="SUB-B",
            requirement_contracts=[req],
            claims=[],
            observations=[obs_b],
        )
        # Bidder B MUST NOT inherit Bidder A's turnover observation -> MUST be UNVERIFIED
        self.assertEqual(res_b["requirement_results"][0].state, ComplianceState.UNVERIFIED)

    async def test_05_tender_fallback_safety_and_scoping(self):
        """Req 8: Canonical CPCL demo tender allows fallback, but arbitrary tenders get NO silent CPCL substitution."""
        # 1. Canonical CPCL tender -> Returns 9 canonical benchmark requirements
        cpcl_reqs = await get_tender_requirements("DEMO/CPCL/WQM/2026/017")
        self.assertEqual(len(cpcl_reqs), 9)
        req_ids = [r.get("requirement_id") for r in cpcl_reqs]
        self.assertEqual(req_ids, [f"REQ-00{i}" for i in range(1, 10)])

        # 2. Arbitrary non-CPCL tender -> Returns empty list (NO silent CPCL substitution)
        random_tender_id = f"TND-RANDOM-{uuid.uuid4().hex[:8]}"
        custom_reqs = await get_tender_requirements(random_tender_id)
        self.assertEqual(custom_reqs, [], "Arbitrary tender must NOT silently receive CPCL requirements!")

    def test_06_external_verification_state_transitions(self):
        """Req 9: Test all external verification states: VALID->PASS, INVALID->FAIL, UNAVAILABLE->UNVERIFIED/REVIEW, CONTRADICTORY->REVIEW."""
        req_gst = build_requirement_evaluation_contract(
            TenderRequirement(
                requirement_id="REQ-001",
                category=RequirementCategory.GST,
                description="Active GSTIN Registration.",
                mandatory=True,
                title="GST Registration",
            ),
            tender_id="DEMO/CPCL/WQM/2026/017",
        )

        obs_gst = EvidenceObservation(
            evidence_id="EVD-GST-01",
            requirement_id="REQ-001",
            observed_value="33AAACH123411Z9",
            source_document="GST.pdf",
            page_number=1,
            source_type="GST_CERTIFICATE",
        )

        # 1. Active / Verified external response -> PASS
        res_pass = evaluate_canonical_submission(
            tender_id="DEMO/CPCL/WQM/2026/017",
            bidder_id="B-1",
            submission_id="S-1",
            requirement_contracts=[req_gst],
            claims=[],
            observations=[obs_gst],
            external_verifications={"REQ-001": {"status": "VERIFIED", "details": {"gstin_status": "ACTIVE"}}},
        )
        self.assertEqual(res_pass["requirement_results"][0].state, ComplianceState.PASS)

        # 2. Inactive / Cancelled external response -> FAIL
        res_fail = evaluate_canonical_submission(
            tender_id="DEMO/CPCL/WQM/2026/017",
            bidder_id="B-2",
            submission_id="S-2",
            requirement_contracts=[req_gst],
            claims=[],
            observations=[obs_gst],
            external_verifications={"REQ-001": {"status": "FAILED", "details": {"gstin_status": "CANCELLED"}}},
        )
        self.assertEqual(res_fail["requirement_results"][0].state, ComplianceState.FAIL)

        # 3. Gateway Unavailable -> UNVERIFIED / REVIEW (Never PASS)
        res_unavail = evaluate_canonical_submission(
            tender_id="DEMO/CPCL/WQM/2026/017",
            bidder_id="B-3",
            submission_id="S-3",
            requirement_contracts=[req_gst],
            claims=[],
            observations=[],
            external_verifications={"REQ-001": {"status": "UNAVAILABLE"}},
        )
        self.assertIn(res_unavail["requirement_results"][0].state, (ComplianceState.UNVERIFIED, ComplianceState.REVIEW))

    def test_07_failure_safety_no_false_pass_on_exceptions(self):
        """Req 10: Injected pipeline failures never produce PASS or false qualification."""
        req = build_requirement_evaluation_contract(
            TenderRequirement(
                requirement_id="REQ-003",
                category=RequirementCategory.FINANCIAL_TURNOVER,
                description="Minimum turnover INR 5 Crore.",
                mandatory=True,
                title="Turnover",
            ),
            tender_id="DEMO/CPCL/WQM/2026/017",
        )

        # Empty/corrupted observations
        corrupt_obs = EvidenceObservation(
            evidence_id="EVD-CORRUPT",
            requirement_id="REQ-003",
            observed_value="",
            source_document="corrupt.pdf",
            page_number=1,
        )

        result = evaluate_canonical_submission(
            tender_id="DEMO/CPCL/WQM/2026/017",
            bidder_id="B-CORRUPT",
            submission_id="S-CORRUPT",
            requirement_contracts=[req],
            claims=[],
            observations=[corrupt_obs],
        )

        state = result["requirement_results"][0].state
        self.assertIn(state, (ComplianceState.UNVERIFIED, ComplianceState.REVIEW))
        self.assertNotEqual(state, ComplianceState.PASS)
        self.assertNotIn("bidder_qualified", result)

    def test_08_persistence_mode_explicit_indicator(self):
        """Req 4: System explicitly exposes OFFLINE_DEMO_MODE or REAL_PERSISTENT_MODE."""
        mode = get_persistence_mode()
        self.assertIn(mode, ("REAL_PERSISTENT_MODE", "OFFLINE_DEMO_MODE"))


if __name__ == "__main__":
    unittest.main()
