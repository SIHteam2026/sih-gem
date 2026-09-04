"""Comprehensive End-to-End Canonical Evaluation Test Suite for OPAL (SIH26100).

Validates the full canonical procurement evaluation pipeline:
Procurement -> Tender -> Canonical Tender Requirements -> Requirement Evaluation Contracts
    -> Bid Submission -> Canonical Documents -> Claims / Evidence Observations
    -> Requirement Mapping -> Contradiction Reconciliation -> Tiered Evaluation
    -> Requirement-Level Results -> Human Officer Review Required.

Verifies the 22 core safety, provenance, isolation, and deterministic compliance requirements:
1. Real canonical tender requirements load.
2. Real requirement contract conversion works.
3. Canonical bidder/submission identity resolves.
4. Documents remain linked to correct submission.
5. Claims/evidence extraction works.
6. Requirement mapping assigns real requirement IDs.
7. Uncertain mapping remains unresolved rather than falsely assigned.
8. 27% vs 14% contradiction reaches final REVIEW.
9. Missing mandatory evidence reaches UNVERIFIED.
10. Ambiguous date semantics reach REVIEW.
11. Numeric deterministic PASS works.
12. Numeric deterministic FAIL works.
13. Verified exemption produces NOT_APPLICABLE.
14. Unverified exemption produces REVIEW.
15. External verification unavailable never becomes PASS.
16. Multi-bidder isolation works.
17. Provenance survives end-to-end.
18. Legacy endpoint compatibility remains.
19. No automatic qualification/disqualification occurs.
20. No automatic LoA/rejection occurs.
21. All tender requirements are evaluated rather than only documents that happen to exist.
22. A requirement with no evidence remains visible as UNVERIFIED rather than disappearing.
"""

import asyncio
import json
import sys
import unittest
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Ensure backend directory and project root are in sys.path
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent
_repo_root = _backend_dir.parent
for _p in [str(_repo_root), str(_backend_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi.testclient import TestClient

from backend.app.api.main import app
from backend.app.models.evaluation import (
    ComplianceState,
    EvaluationMethod,
    ExternalVerificationStatus,
    RequirementEvaluationResult,
)
from backend.app.models.evidence import (
    BidderClaim,
    ContradictionFinding,
    EvidenceObservation,
    ProvenanceRecord,
)
from backend.app.models.procurement import Document, DocumentType
from backend.app.models.tender import (
    AmbiguityType,
    RequirementCategory,
    TenderRequirement,
)
from backend.app.models.tender_contract import (
    CanonicalEvaluationField,
    EvaluationMode,
    RequirementEvaluationContract,
    TenderEvaluationContract,
)
from backend.app.rules.engine import evaluate_experience_window
from backend.app.services.claim_extraction_service import (
    extract_document_facts,
    map_facts_to_requirements,
    process_document_evidence,
)
from backend.app.services.master_pipeline import (
    evaluate_canonical_submission,
    evaluate_canonical_submission_by_id,
)
from backend.app.services.tender_contract_service import (
    build_requirement_evaluation_contract,
    build_tender_evaluation_contract,
)
from backend.app.tests.test_tender_persistence import create_synthetic_cpcl_requirements


class EndToEndCanonicalEvaluationTests(unittest.TestCase):
    """22 Mandatory End-to-End Evaluation Tests for the OPAL Compliance Workstream."""

    def setUp(self):
        self.cpcl_tender_id = "DEMO/CPCL/WQM/2026/017"
        self.raw_requirements = create_synthetic_cpcl_requirements()
        self.tender_contract = build_tender_evaluation_contract(
            tender_id=self.cpcl_tender_id,
            requirements=self.raw_requirements,
            tender_title="Continuous Water Quality Monitoring System",
            tender_reference=self.cpcl_tender_id,
        )
        self.contracts = self.tender_contract.requirements
        self.contracts_by_id = {c.requirement_id: c for c in self.contracts}
        self.client = TestClient(app)

    # 1. Real canonical tender requirements load.
    def test_01_canonical_tender_requirements_load(self):
        """1. Real canonical tender requirements load with all metadata intact."""
        self.assertEqual(len(self.raw_requirements), 9)
        req_ids = [r.requirement_id for r in self.raw_requirements]
        self.assertEqual(req_ids, [f"REQ-{i:03d}" for i in range(1, 10)])
        # Verify statutory & financial properties
        req3 = next(r for r in self.raw_requirements if r.requirement_id == "REQ-003")
        self.assertEqual(req3.category, RequirementCategory.FINANCIAL_TURNOVER)
        self.assertTrue(req3.mandatory)
        self.assertTrue(req3.applicability.msme_exemption_applicable)

    # 2. Real requirement contract conversion works.
    def test_02_requirement_contract_conversion(self):
        """2. Real requirement contract conversion maps evaluation modes deterministically."""
        self.assertEqual(self.tender_contract.requirements_count, 9)
        self.assertEqual(len(self.contracts), 9)
        # REQ-003 Turnover -> DETERMINISTIC
        c3 = self.contracts_by_id["REQ-003"]
        self.assertEqual(c3.evaluation_mode, EvaluationMode.DETERMINISTIC)
        self.assertEqual(c3.threshold_value, 50000000.0)
        self.assertEqual(c3.threshold_unit, "INR")
        # REQ-006 Local Content -> DETERMINISTIC
        c6 = self.contracts_by_id["REQ-006"]
        self.assertEqual(c6.evaluation_mode, EvaluationMode.DETERMINISTIC)
        self.assertEqual(c6.threshold_value, 20.0)
        self.assertEqual(c6.threshold_unit, "PERCENT")
        # REQ-009 Vague capability clause -> HUMAN_REVIEW
        c9 = self.contracts_by_id["REQ-009"]
        self.assertEqual(c9.evaluation_mode, EvaluationMode.HUMAN_REVIEW)
        self.assertTrue(c9.ambiguity.is_ambiguous)

    # 3. Canonical bidder/submission identity resolves.
    def test_03_canonical_bidder_submission_identity_resolution(self):
        """3. Master pipeline resolves canonical bidder and submission identities."""
        submission_id = "SUB-CPCL-2026-001"
        bidder_id = "BID-CHENNAI-INSTRUMENTS"
        mock_sub_data = {
            "id": submission_id,
            "tender_id": self.cpcl_tender_id,
            "bidder_id": bidder_id,
            "bidder": {"legal_name": "Chennai Instruments Pvt Ltd", "gstin": "33AABCC1234D1Z5"},
            "documents": [
                {
                    "id": "DOC-GST-01",
                    "filename": "GST_Certificate.pdf",
                    "document_type": "GST_CERTIFICATE",
                    "content_text": json.dumps([{"page": 1, "text": "GSTIN: 33AABCC1234D1Z5 active"}]),
                }
            ],
        }

        async def _run():
            with patch("backend.app.db.client.get_submission_detail_db", new_callable=AsyncMock) as mock_db, \
                 patch("backend.app.services.tender_contract_service.get_tender_evaluation_contract", new_callable=AsyncMock) as mock_contract:
                mock_db.return_value = mock_sub_data
                mock_contract.return_value = self.tender_contract

                return await evaluate_canonical_submission_by_id(submission_id=submission_id)

        result = asyncio.run(_run())
        self.assertEqual(result["submission_id"], submission_id)
        self.assertEqual(result["bidder_id"], bidder_id)
        self.assertEqual(result["tender_id"], self.cpcl_tender_id)

    # 4. Documents remain linked to correct submission.
    def test_04_documents_remain_linked_to_correct_submission(self):
        """4. Documents and extracted observations preserve submission linkage."""
        doc = Document(
            id="DOC-999",
            procurement_id="PROC-101",
            tender_id=self.cpcl_tender_id,
            bid_submission_id="SUB-777",
            filename="GST_Doc.pdf",
            document_type=DocumentType.GST_CERTIFICATE,
            content_text=json.dumps([{"page": 1, "text": "GSTIN: 33AABCC1234D1Z5"}]),
        )
        facts = process_document_evidence(doc, {"bidder_id": "BID-888", "bid_submission_id": "SUB-777"})
        self.assertEqual(len(facts["observations"]), 1)
        obs = facts["observations"][0]
        self.assertEqual(obs.bid_submission_id, "SUB-777")
        self.assertEqual(obs.bidder_id, "BID-888")
        self.assertEqual(obs.document_id, "DOC-999")

    # 5. Claims/evidence extraction works.
    def test_05_claim_and_evidence_extraction(self):
        """5. Deterministic extractor extracts claims and observations across multiple domains."""
        doc = Document(
            id="DOC-MULTI-01",
            procurement_id="PROC-101",
            bid_submission_id="SUB-001",
            filename="CA_Turnover_Cert.pdf",
            document_type=DocumentType.TURNOVER_CERTIFICATE,
            content_text=json.dumps([
                {"page": 1, "text": "Average annual turnover of INR 6.42 Crore for the last three years (UDIN: 240123)."},
                {"page": 2, "text": "Comprehensive 24 Months onsite warranty is guaranteed."},
            ]),
        )
        facts = process_document_evidence(doc, {"bidder_id": "BID-001", "bid_submission_id": "SUB-001"})
        self.assertGreaterEqual(len(facts["observations"]), 2)
        turnover_obs = next(o for o in facts["observations"] if o.unit == "INR")
        warranty_obs = next(o for o in facts["observations"] if o.unit == "MONTHS")
        self.assertEqual(turnover_obs.page_number, 1)
        self.assertIn("6.42 Crore", turnover_obs.source_quote)
        self.assertEqual(warranty_obs.page_number, 2)
        self.assertIn("24 Months", warranty_obs.source_quote)

    # 6. Requirement mapping assigns real requirement IDs.
    def test_06_requirement_mapping_assigns_real_ids(self):
        """6. Requirement mapper replaces placeholder IDs with canonical CPCL requirement IDs."""
        placeholder_facts = {
            "claims": [
                BidderClaim(
                    claim_id="CLM-01",
                    requirement_id="REQ-LC-UNKNOWN",
                    claimed_value="27%",
                    unit="PERCENT",
                    source_document="MII_Declaration.pdf",
                    page_number=1,
                    raw_statement="27% local content",
                )
            ],
            "observations": [
                EvidenceObservation(
                    evidence_id="EVD-01",
                    requirement_id="REQ-TURNOVER-UNKNOWN",
                    observed_value="6.42 Crore",
                    unit="INR",
                    source_document="CA_Turnover.pdf",
                    page_number=1,
                    source_quote="Turnover INR 6.42 Crore",
                ),
                EvidenceObservation(
                    evidence_id="EVD-02",
                    requirement_id="REQ-WARRANTY-UNKNOWN",
                    observed_value="24 Months",
                    unit="MONTHS",
                    source_document="Warranty_Letter.pdf",
                    page_number=1,
                    source_quote="24 Months warranty",
                ),
            ],
        }
        mapped = map_facts_to_requirements(placeholder_facts, self.contracts)
        self.assertEqual(len(mapped["unmapped"]), 0)
        self.assertEqual(mapped["claims"][0].requirement_id, "REQ-006")
        self.assertEqual(mapped["observations"][0].requirement_id, "REQ-003")
        self.assertEqual(mapped["observations"][1].requirement_id, "REQ-008")

    # 7. Uncertain mapping remains unresolved rather than falsely assigned.
    def test_07_uncertain_mapping_remains_unresolved(self):
        """7. Ambiguous or unknown facts remain unmapped and flagged for review rather than force-mapped."""
        ambiguous_facts = {
            "claims": [
                BidderClaim(
                    claim_id="CLM-UNCERTAIN-01",
                    requirement_id="REQ-UNKNOWN-CUSTOM",
                    claimed_value="Some obscure technical parameter",
                    source_document="Miscellaneous_Brochure.pdf",
                    page_number=4,
                    raw_statement="Advanced acoustic damping applied.",
                )
            ],
            "observations": [],
        }
        mapped = map_facts_to_requirements(ambiguous_facts, self.contracts)
        self.assertEqual(len(mapped["claims"]), 0)
        self.assertEqual(len(mapped["unmapped"]), 1)
        unmapped_entry = mapped["unmapped"][0]
        self.assertEqual(unmapped_entry["fact_id"], "CLM-UNCERTAIN-01")
        self.assertEqual(unmapped_entry["reason"], "No unique canonical requirement match")

    # 8. 27% vs 14% contradiction reaches final REVIEW.
    def test_08_contradiction_27_vs_14_reaches_review(self):
        """8. Contradiction between 27% declaration and 14% certificate yields REVIEW, neither PASS nor automatic FAIL."""
        result = evaluate_canonical_submission(
            tender_id=self.cpcl_tender_id,
            bidder_id="BID-001",
            submission_id="SUB-001",
            requirement_contracts=[self.contracts_by_id["REQ-006"]],
            claims=[
                BidderClaim(
                    claim_id="CLM-LC",
                    requirement_id="REQ-006",
                    claimed_value="27%",
                    unit="PERCENT",
                    source_document="Self_Declaration_MII.pdf",
                    page_number=2,
                    raw_statement="We declare 27% Local Content under MII policy.",
                )
            ],
            observations=[
                EvidenceObservation(
                    evidence_id="EVD-LC",
                    requirement_id="REQ-006",
                    observed_value="14%",
                    unit="PERCENT",
                    source_document="Auditor_MII_Certificate.pdf",
                    page_number=1,
                    source_quote="Verified Local Content is 14% based on audited bills of materials.",
                    is_authoritative=True,
                )
            ],
        )
        res_006 = result["requirement_results"][0]
        self.assertEqual(res_006.requirement_id, "REQ-006")
        self.assertEqual(res_006.state, ComplianceState.REVIEW)
        self.assertTrue(res_006.review_required)
        self.assertNotEqual(res_006.state, ComplianceState.PASS)
        self.assertNotEqual(res_006.state, ComplianceState.FAIL)
        self.assertEqual(len(res_006.contradiction_findings), 1)
        finding = res_006.contradiction_findings[0]
        self.assertIsNotNone(finding.side_by_side)
        left_val = str(finding.side_by_side.left.raw_value or finding.side_by_side.left.normalized_value)
        right_val = str(finding.side_by_side.right.raw_value or finding.side_by_side.right.normalized_value)
        self.assertTrue("27" in left_val or "27" in right_val)
        self.assertTrue("14" in left_val or "14" in right_val)
        self.assertEqual(result["unresolved_contradiction_count"], 1)

    # 9. Missing mandatory evidence reaches UNVERIFIED.
    def test_09_missing_mandatory_evidence_reaches_unverified(self):
        """9. Absence of mandatory evidence yields UNVERIFIED with no guessing or fabricated facts."""
        maf_req = self.contracts_by_id["REQ-005"]  # Mandatory OEM Authorization
        result = evaluate_canonical_submission(
            tender_id=self.cpcl_tender_id,
            bidder_id="BID-001",
            submission_id="SUB-001",
            requirement_contracts=[maf_req],
            claims=[],
            observations=[],
        )
        res_005 = result["requirement_results"][0]
        self.assertEqual(res_005.requirement_id, "REQ-005")
        self.assertEqual(res_005.state, ComplianceState.UNVERIFIED)
        self.assertNotEqual(res_005.state, ComplianceState.PASS)
        self.assertIn("Mandatory", res_005.reason)
        self.assertEqual(len(res_005.observed_values), 0)

    # 10. Ambiguous date semantics reach REVIEW.
    def test_10_ambiguous_date_semantics_reach_review(self):
        """10. Experience date window straddling cutoff yields REVIEW preserving the ambiguity reason."""
        finding = evaluate_experience_window(
            requirement_id="REQ-004",
            past_years_required=5,
            work_order_date_input="2021-08-15",
            completion_date_input="2023-03-20",
            tender_closing_date="2027-01-01",  # 5-year cutoff is 2022-01-01
        )
        self.assertEqual(finding.state, ComplianceState.REVIEW)
        self.assertIn("straddle", finding.reasoning_trace.lower())
        self.assertIn("cutoff", finding.reasoning_trace.lower())

    # 11. Numeric deterministic PASS works.
    def test_11_numeric_deterministic_pass(self):
        """11. Valid numeric values meeting or exceeding thresholds produce deterministic PASS."""
        result = evaluate_canonical_submission(
            tender_id=self.cpcl_tender_id,
            bidder_id="BID-001",
            submission_id="SUB-001",
            requirement_contracts=[self.contracts_by_id["REQ-003"], self.contracts_by_id["REQ-008"]],
            claims=[],
            observations=[
                EvidenceObservation(
                    evidence_id="EVD-TO",
                    requirement_id="REQ-003",
                    observed_value=64200000.0,
                    unit="INR",
                    source_document="CA_Certificate.pdf",
                    page_number=1,
                    source_quote="Turnover INR 6.42 Crore",
                ),
                EvidenceObservation(
                    evidence_id="EVD-WAR",
                    requirement_id="REQ-008",
                    observed_value=24.0,
                    unit="MONTHS",
                    source_document="Warranty.pdf",
                    page_number=1,
                    source_quote="24 Months Onsite Warranty",
                ),
            ],
        )
        states = {r.requirement_id: r.state for r in result["requirement_results"]}
        self.assertEqual(states["REQ-003"], ComplianceState.PASS)
        self.assertEqual(states["REQ-008"], ComplianceState.PASS)
        self.assertFalse(result["requirement_results"][0].review_required)
        self.assertEqual(result["requirement_results"][0].evaluation_method, EvaluationMethod.DETERMINISTIC)

    # 12. Numeric deterministic FAIL works.
    def test_12_numeric_deterministic_fail(self):
        """12. Values below threshold produce deterministic FAIL."""
        result = evaluate_canonical_submission(
            tender_id=self.cpcl_tender_id,
            bidder_id="BID-001",
            submission_id="SUB-001",
            requirement_contracts=[self.contracts_by_id["REQ-003"]],
            claims=[],
            observations=[
                EvidenceObservation(
                    evidence_id="EVD-TO-DEFICIT",
                    requirement_id="REQ-003",
                    observed_value=35000000.0,  # 3.5 Crore < 5.0 Crore
                    unit="INR",
                    source_document="CA_Certificate.pdf",
                    page_number=1,
                    source_quote="Turnover INR 3.5 Crore",
                )
            ],
        )
        res = result["requirement_results"][0]
        self.assertEqual(res.state, ComplianceState.FAIL)
        self.assertEqual(res.evaluation_method, EvaluationMethod.DETERMINISTIC)
        self.assertIn("deficit", res.reason.lower())

    # 13. Verified exemption produces NOT_APPLICABLE.
    def test_13_verified_exemption_produces_not_applicable(self):
        """13. Verified statutory exemption produces NOT_APPLICABLE rather than PASS or FAIL."""
        context = {
            "exemptions": {
                "REQ-003": {
                    "is_exempt": True,
                    "type": "MSE_TURNOVER_EXEMPTION",
                    "reason": "Bidder is verified Micro & Small Enterprise under Udyam Registration.",
                }
            }
        }
        result = evaluate_canonical_submission(
            tender_id=self.cpcl_tender_id,
            bidder_id="BID-MSE-01",
            submission_id="SUB-001",
            requirement_contracts=[self.contracts_by_id["REQ-003"]],
            claims=[],
            observations=[],
            context=context,
        )
        res = result["requirement_results"][0]
        self.assertEqual(res.state, ComplianceState.NOT_APPLICABLE)
        self.assertEqual(res.evaluation_method, EvaluationMethod.APPLICABILITY_EXEMPTION)
        self.assertFalse(res.review_required)

    # 14. Unverified exemption produces REVIEW.
    def test_14_unverified_exemption_produces_review(self):
        """14. Claimed but unverified exemption produces REVIEW requiring officer review."""
        context = {
            "exemptions": {
                "REQ-003": {
                    "is_exempt": None,  # Claimed but unverified
                    "type": "MSE_TURNOVER_EXEMPTION",
                }
            }
        }
        result = evaluate_canonical_submission(
            tender_id=self.cpcl_tender_id,
            bidder_id="BID-MSE-UNVERIFIED",
            submission_id="SUB-001",
            requirement_contracts=[self.contracts_by_id["REQ-003"]],
            claims=[],
            observations=[],
            context=context,
        )
        res = result["requirement_results"][0]
        self.assertEqual(res.state, ComplianceState.REVIEW)
        self.assertTrue(res.review_required)
        self.assertIn("unverified", res.reason.lower())

    # 15. External verification unavailable never becomes PASS.
    def test_15_external_verification_unavailable_never_becomes_pass(self):
        """15. External verification with UNAVAILABLE status never defaults to PASS."""
        ext_verifications = {
            "REQ-001": {
                "status": ExternalVerificationStatus.UNAVAILABLE.value,
                "registry": "GSTN_PORTAL",
                "details": {"error": "Timeout querying GST portal API"},
            }
        }
        result = evaluate_canonical_submission(
            tender_id=self.cpcl_tender_id,
            bidder_id="BID-001",
            submission_id="SUB-001",
            requirement_contracts=[self.contracts_by_id["REQ-001"]],
            claims=[],
            observations=[],
            external_verifications=ext_verifications,
        )
        res = result["requirement_results"][0]
        self.assertNotEqual(res.state, ComplianceState.PASS)
        self.assertEqual(res.state, ComplianceState.REVIEW)
        self.assertTrue(res.review_required)

    # 16. Multi-bidder isolation works.
    def test_16_multi_bidder_isolation(self):
        """16. Bidder A and Bidder B with identically named files remain strictly isolated."""
        doc_a = Document(
            id="DOC-A-GST",
            procurement_id="PROC-101",
            tender_id=self.cpcl_tender_id,
            bid_submission_id="SUB-A",
            filename="GST.pdf",
            document_type=DocumentType.GST_CERTIFICATE,
            content_text=json.dumps([{"page": 1, "text": "GSTIN: 33AAAAA1111A1Z1"}]),
        )
        doc_b = Document(
            id="DOC-B-GST",
            procurement_id="PROC-101",
            tender_id=self.cpcl_tender_id,
            bid_submission_id="SUB-B",
            filename="GST.pdf",
            document_type=DocumentType.GST_CERTIFICATE,
            content_text=json.dumps([{"page": 1, "text": "GSTIN: 27BBBBB2222B2Z2"}]),
        )

        facts_a = process_document_evidence(doc_a, {"bidder_id": "BIDDER-A", "bid_submission_id": "SUB-A"})
        facts_b = process_document_evidence(doc_b, {"bidder_id": "BIDDER-B", "bid_submission_id": "SUB-B"})

        obs_a = facts_a["observations"][0]
        obs_b = facts_b["observations"][0]

        # Verify identity isolation
        self.assertNotEqual(obs_a.document_id, obs_b.document_id)
        self.assertEqual(obs_a.bidder_id, "BIDDER-A")
        self.assertEqual(obs_b.bidder_id, "BIDDER-B")
        self.assertEqual(obs_a.bid_submission_id, "SUB-A")
        self.assertEqual(obs_b.bid_submission_id, "SUB-B")
        self.assertEqual(obs_a.observed_value, "33AAAAA1111A1Z1")
        self.assertEqual(obs_b.observed_value, "27BBBBB2222B2Z2")

        # Evaluate separately
        res_a = evaluate_canonical_submission(
            tender_id=self.cpcl_tender_id,
            bidder_id="BIDDER-A",
            submission_id="SUB-A",
            requirement_contracts=[self.contracts_by_id["REQ-001"]],
            claims=[],
            observations=facts_a["observations"],
        )
        res_b = evaluate_canonical_submission(
            tender_id=self.cpcl_tender_id,
            bidder_id="BIDDER-B",
            submission_id="SUB-B",
            requirement_contracts=[self.contracts_by_id["REQ-001"]],
            claims=[],
            observations=facts_b["observations"],
        )

        self.assertEqual(res_a["bidder_id"], "BIDDER-A")
        self.assertEqual(res_b["bidder_id"], "BIDDER-B")
        self.assertEqual(res_a["requirement_results"][0].provenance[0].document_id, "DOC-A-GST")
        self.assertEqual(res_b["requirement_results"][0].provenance[0].document_id, "DOC-B-GST")

    # 17. Provenance survives end-to-end.
    def test_17_provenance_replay_end_to_end(self):
        """17. Provenance replay links requirement -> quote -> page -> doc -> contradiction -> method -> state."""
        claim = BidderClaim(
            claim_id="CLM-PROV-01",
            requirement_id="REQ-006",
            claimed_value="27%",
            unit="PERCENT",
            source_document="Declaration_MII.pdf",
            page_number=2,
            raw_statement="Declared local content is 27%.",
            document_id="DOC-DECL-01",
        )
        observation = EvidenceObservation(
            evidence_id="EVD-PROV-01",
            requirement_id="REQ-006",
            observed_value="14%",
            unit="PERCENT",
            source_document="Auditor_Cert.pdf",
            page_number=5,
            source_quote="Audited local content is 14%.",
            document_id="DOC-CERT-01",
            is_authoritative=True,
        )

        result = evaluate_canonical_submission(
            tender_id=self.cpcl_tender_id,
            bidder_id="BID-AUDIT-01",
            submission_id="SUB-AUDIT-01",
            requirement_contracts=[self.contracts_by_id["REQ-006"]],
            claims=[claim],
            observations=[observation],
        )

        res = result["requirement_results"][0]
        # Check requirement provenance from tender contract
        contract_provenance = self.contracts_by_id["REQ-006"].provenance
        self.assertEqual(contract_provenance.clause_number, "Clause 3.2")
        self.assertEqual(contract_provenance.page_number, 3)

        # Check evidence provenance survival
        self.assertEqual(len(res.provenance), 2)
        prov_claim = next(p for p in res.provenance if p.source_type == "BIDDER_DECLARATION")
        prov_obs = next(p for p in res.provenance if p.source_type != "BIDDER_DECLARATION")

        self.assertEqual(prov_claim.document_id, "DOC-DECL-01")
        self.assertEqual(prov_claim.document_name, "Declaration_MII.pdf")
        self.assertEqual(prov_claim.page_number, 2)
        self.assertEqual(prov_claim.quote, "Declared local content is 27%.")

        self.assertEqual(prov_obs.document_id, "DOC-CERT-01")
        self.assertEqual(prov_obs.document_name, "Auditor_Cert.pdf")
        self.assertEqual(prov_obs.page_number, 5)
        self.assertEqual(prov_obs.quote, "Audited local content is 14%.")

        # Contradiction and resulting state
        self.assertEqual(res.evaluation_method, EvaluationMethod.CONTRADICTION_RECONCILIATION)
        self.assertEqual(res.state, ComplianceState.REVIEW)

    # 18. Legacy endpoint compatibility remains.
    def test_18_legacy_endpoint_compatibility(self):
        """18. API endpoint /api/evaluate/complete supports canonical contracts, canonical submission ID, and legacy mode."""
        # 1. Canonical contract mode
        canonical_payload = {
            "tender_id": self.cpcl_tender_id,
            "bidder_name": "Testing Instruments Ltd",
            "requirement_contracts": [c.model_dump() for c in self.contracts[:2]],
            "bidder_claims": [],
            "evidence_observations": [],
        }
        resp = self.client.post("/api/evaluate/complete", json=canonical_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["requirement_results"]), 2)
        self.assertIn("machine_review_summary", data)
        self.assertIsNone(data.get("letter_of_award"))

        # 2. Canonical submission_id mode
        with patch("backend.app.db.client.get_submission_detail_db", new_callable=AsyncMock) as mock_sub, \
             patch("backend.app.services.tender_contract_service.get_tender_evaluation_contract", new_callable=AsyncMock) as mock_contract:
            mock_sub.return_value = {
                "id": "SUB-TEST-18",
                "tender_id": self.cpcl_tender_id,
                "bidder_id": "BID-TEST-18",
                "documents": [],
            }
            mock_contract.return_value = self.tender_contract

            resp2 = self.client.post("/api/evaluate/complete", json={
                "tender_id": self.cpcl_tender_id,
                "bidder_name": "Testing Instruments Ltd",
                "submission_id": "SUB-TEST-18",
            })
            self.assertEqual(resp2.status_code, 200)
            data2 = resp2.json()
            self.assertEqual(len(data2["requirement_results"]), 9)
            self.assertIsNone(data2.get("letter_of_award"))

        # 3. Legacy mode with raw documents
        legacy_payload = {
            "tender_id": "LEGACY-TENDER-01",
            "bidder_name": "Legacy Vendor",
            "raw_documents": [
                {"filename": "Vendor_Profile.txt", "text": "GSTIN: 29ABCDE1234F2Z5 active"}
            ],
        }
        resp3 = self.client.post("/api/evaluate/complete", json=legacy_payload)
        self.assertEqual(resp3.status_code, 200)

    # 19. No automatic qualification/disqualification occurs.
    def test_19_no_automatic_qualification_or_disqualification(self):
        """19. Canonical evaluation output contains no automatic qualification or disqualification decision."""
        result = evaluate_canonical_submission(
            tender_id=self.cpcl_tender_id,
            bidder_id="BID-001",
            submission_id="SUB-001",
            requirement_contracts=self.contracts,
            claims=[],
            observations=[],
        )
        # Verify prohibited decision keys do not exist in the response
        self.assertNotIn("qualified", result)
        self.assertNotIn("bidder_qualified", result)
        self.assertNotIn("accepted", result)
        self.assertNotIn("rejected", result)
        self.assertNotIn("final_recommendation", result)
        self.assertEqual(result["evaluation_metadata"]["decision_authority"], "HUMAN_PROCUREMENT_OFFICER")

    # 20. No automatic LoA/rejection occurs.
    def test_20_no_automatic_loa_or_rejection(self):
        """20. Canonical evaluation never produces automated Letter of Award (LoA) or rejection."""
        result = evaluate_canonical_submission(
            tender_id=self.cpcl_tender_id,
            bidder_id="BID-001",
            submission_id="SUB-001",
            requirement_contracts=self.contracts,
            claims=[],
            observations=[],
        )
        self.assertNotIn("letter_of_award", result)
        self.assertNotIn("shortfall_notice", result)
        # Result stops at requirements and review summary
        self.assertIn("requirement_results", result)
        self.assertIn("machine_review_summary", result)
        self.assertIn("review_required", result)

    # 21. All tender requirements are evaluated rather than only documents that happen to exist.
    def test_21_all_tender_requirements_evaluated(self):
        """21. All 9 tender requirements are evaluated even if bidder only submitted evidence for 2."""
        # Bidder only submitted GST and PAN
        partial_observations = [
            EvidenceObservation(
                evidence_id="EVD-01",
                requirement_id="REQ-001",
                observed_value="33AABCC1234D1Z5",
                unit="STATUS",
                source_document="GST.pdf",
            ),
            EvidenceObservation(
                evidence_id="EVD-02",
                requirement_id="REQ-002",
                observed_value="AABCC1234D",
                unit="STATUS",
                source_document="PAN.pdf",
            ),
        ]
        result = evaluate_canonical_submission(
            tender_id=self.cpcl_tender_id,
            bidder_id="BID-PARTIAL-01",
            submission_id="SUB-PARTIAL-01",
            requirement_contracts=self.contracts,
            claims=[],
            observations=partial_observations,
        )
        evaluated_req_ids = [r.requirement_id for r in result["requirement_results"]]
        self.assertEqual(len(evaluated_req_ids), 9)
        self.assertEqual(evaluated_req_ids, [f"REQ-{i:03d}" for i in range(1, 10)])

    # 22. A requirement with no evidence remains visible as UNVERIFIED rather than disappearing.
    def test_22_un_evidenced_requirements_remain_visible_as_unverified(self):
        """22. Un-evidenced requirements remain visible as UNVERIFIED rather than being dropped."""
        result = evaluate_canonical_submission(
            tender_id=self.cpcl_tender_id,
            bidder_id="BID-EMPTY",
            submission_id="SUB-EMPTY",
            requirement_contracts=self.contracts,
            claims=[],
            observations=[],
        )
        results_by_id = {r.requirement_id: r for r in result["requirement_results"]}
        # REQ-005 has no evidence submitted -> must be UNVERIFIED and visible
        self.assertIn("REQ-005", results_by_id)
        self.assertEqual(results_by_id["REQ-005"].state, ComplianceState.UNVERIFIED)
        # REQ-007 has no evidence submitted -> must be UNVERIFIED and visible
        self.assertIn("REQ-007", results_by_id)
        self.assertEqual(results_by_id["REQ-007"].state, ComplianceState.UNVERIFIED)
        # Count of UNVERIFIED in machine review summary
        self.assertGreaterEqual(result["machine_review_summary"][ComplianceState.UNVERIFIED.value], 7)


if __name__ == "__main__":
    unittest.main()
