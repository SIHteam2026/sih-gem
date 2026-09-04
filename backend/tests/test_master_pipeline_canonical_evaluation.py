"""Tests for the canonical, requirement-level master evaluation path."""

import unittest

from backend.app.models.evidence import BidderClaim, EvidenceObservation
from backend.app.models.evaluation import ComplianceState
from backend.app.models.tender import RequirementCategory, TenderRequirement
from backend.app.services.master_pipeline import evaluate_canonical_submission
from backend.app.services.tender_contract_service import build_requirement_evaluation_contract


def contract(req_id, category, description, **kwargs):
    return build_requirement_evaluation_contract(
        TenderRequirement(requirement_id=req_id, category=category, description=description, **kwargs),
        tender_id="DEMO/CPCL/WQM/2026/017",
    )


class CanonicalMasterEvaluationTests(unittest.TestCase):
    def test_requirement_results_are_evaluated_independently_with_provenance(self):
        requirements = [
            contract("REQ-003", RequirementCategory.FINANCIAL_TURNOVER, "Minimum turnover INR 5 Crore."),
            contract("REQ-006", RequirementCategory.LOCAL_CONTENT_MII, "Minimum 20% Local Content."),
            contract("REQ-008", RequirementCategory.COMMERCIAL, "24 Months Warranty."),
            contract("REQ-009", RequirementCategory.TECHNICAL_SPECIFICATION, "Adequate capability and satisfactory reputation.", is_ambiguous=True, ambiguity_reason="Subjective clause."),
        ]
        result = evaluate_canonical_submission(
            tender_id="DEMO/CPCL/WQM/2026/017",
            bidder_id="BID-1",
            submission_id="SUB-1",
            requirement_contracts=requirements,
            claims=[BidderClaim(claim_id="CLM-006", requirement_id="REQ-006", claimed_value="27%", source_document="declaration.pdf", page_number=2)],
            observations=[
                EvidenceObservation(evidence_id="EVD-003", requirement_id="REQ-003", observed_value="6.42 Crore", source_document="ca.pdf", page_number=3),
                EvidenceObservation(evidence_id="EVD-006", requirement_id="REQ-006", observed_value="14%", source_document="certificate.pdf", page_number=4),
                EvidenceObservation(evidence_id="EVD-008", requirement_id="REQ-008", observed_value="24 Months", source_document="warranty.pdf", page_number=1),
                EvidenceObservation(evidence_id="EVD-009", requirement_id="REQ-009", observed_value="proposal", source_document="technical.pdf", page_number=5),
            ],
        )
        states = {item.requirement_id: item.state for item in result["requirement_results"]}
        self.assertEqual(states["REQ-003"], ComplianceState.PASS)
        self.assertEqual(states["REQ-006"], ComplianceState.REVIEW)
        self.assertEqual(states["REQ-008"], ComplianceState.PASS)
        self.assertEqual(states["REQ-009"], ComplianceState.REVIEW)
        local = next(item for item in result["requirement_results"] if item.requirement_id == "REQ-006")
        self.assertTrue(local.review_required)
        self.assertEqual(len(local.contradiction_findings), 1)
        self.assertEqual(len(local.provenance), 2)
        self.assertFalse("bidder_qualified" in result)

    def test_missing_evidence_and_unavailable_external_verification_never_pass(self):
        requirements = [
            contract("REQ-GST", RequirementCategory.GST, "GST certificate", evidence_required=["GST Certificate"]),
            contract("REQ-PAN", RequirementCategory.OTHER, "PAN registry verification"),
        ]
        result = evaluate_canonical_submission(
            tender_id="T-1", bidder_id="B-1", submission_id="S-1", requirement_contracts=requirements,
            claims=[], observations=[], external_verifications={"REQ-PAN": {"status": "UNAVAILABLE", "source": "Registry"}},
        )
        states = {item.requirement_id: item.state for item in result["requirement_results"]}
        self.assertEqual(states["REQ-GST"], ComplianceState.UNVERIFIED)
        self.assertNotEqual(states["REQ-PAN"], ComplianceState.PASS)
        self.assertTrue(result["review_required"])


if __name__ == "__main__":
    unittest.main()
