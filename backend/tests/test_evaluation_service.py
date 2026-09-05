"""Unit tests for OPAL Tiered Requirement Evaluator Service (SIH26100)."""

from datetime import date
import unittest
from unittest.mock import MagicMock

from app.models.evaluation import (
    ComplianceFinding,
    ComplianceState,
    EvaluationMethod,
    ExternalVerificationStatus,
    RequirementEvaluationResult,
)
from app.models.evidence import (
    BidderClaim,
    ContradictionFinding,
    ContradictionType,
    EvidenceObservation,
    ExtractedEvidence,
    ProvenanceRecord,
    RelationshipClassification,
)
from app.models.tender import (
    AmbiguitySpec,
    AmbiguityType,
    ApplicabilitySpec,
    RequirementCategory,
    StructuredCondition,
    TenderRequirement,
)
from app.services.evaluation_service import (
    DefaultSemanticEvaluator,
    SemanticEvaluatorProtocol,
    evaluate_requirement,
    evaluate_requirements,
    get_semantic_evaluator,
    set_semantic_evaluator,
)


class MockSemanticEvaluator:
    """Mock semantic evaluator for testing live LLM responses."""
    def __init__(self, available: bool = True):
        self.available = available

    def evaluate_semantic(self, requirement_dict, claims, evidence, context):
        if not self.available:
            return None
        return RequirementEvaluationResult(
            requirement_id=requirement_dict.get("requirement_id", "REQ-SEM"),
            state=ComplianceState.REVIEW,
            risk_level="MEDIUM",
            evaluation_method=EvaluationMethod.SEMANTIC_LLM,
            reason="Mock LLM interpreted technical specification scope as requiring human review.",
            expected_condition={"description": requirement_dict.get("description")},
            observed_values=[p.raw_value for p in claims + evidence],
            supporting_evidence=evidence,
            conflicting_evidence=[],
            review_required=True,
            provenance=claims + evidence,
            contradiction_findings=[],
            evaluator_metadata={"evaluator": "MockSemanticEvaluator", "tier": "SEMANTIC_LLM"},
            confidence=0.90,
        )


class TestTieredEvaluationService(unittest.TestCase):
    """Test suite covering the tiered requirement evaluation service across all 21 scenarios."""

    def setUp(self):
        # Reset default semantic evaluator
        set_semantic_evaluator(DefaultSemanticEvaluator())

    # -----------------------------------------------------------------------
    # 1. Numeric PASS (27% >= 20%)
    # -----------------------------------------------------------------------
    def test_case_1_numeric_threshold_pass(self):
        req = TenderRequirement(
            requirement_id="REQ-LC-01",
            category=RequirementCategory.LOCAL_CONTENT,
            description="Minimum 20% Local Content under Make in India policy.",
            mandatory=True,
        )
        claim = BidderClaim(
            claim_id="CLM-01",
            requirement_id="REQ-LC-01",
            claimed_value="27%",
            unit="PERCENT",
            source_document="declaration.pdf",
        )
        evidence = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-LC-01",
            observed_value="27%",
            unit="PERCENT",
            source_document="ca_certificate.pdf",
        )
        res = evaluate_requirement(requirement=req, claims=claim, evidence=evidence)
        self.assertEqual(res.state, ComplianceState.PASS)
        self.assertEqual(res.evaluation_method, EvaluationMethod.DETERMINISTIC)
        self.assertEqual(res.risk_level, "NONE")
        self.assertFalse(res.review_required)
        self.assertIn("satisfies the mandatory condition", res.reason)

    # -----------------------------------------------------------------------
    # 2. Numeric FAIL (14% >= 20%)
    # -----------------------------------------------------------------------
    def test_case_2_numeric_threshold_fail(self):
        req = TenderRequirement(
            requirement_id="REQ-LC-01",
            category=RequirementCategory.LOCAL_CONTENT,
            description="Minimum 20% Local Content required.",
            mandatory=True,
        )
        evidence = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-LC-01",
            observed_value="14%",
            unit="PERCENT",
            source_document="ca_certificate.pdf",
        )
        res = evaluate_requirement(requirement=req, claims=[], evidence=evidence)
        self.assertEqual(res.state, ComplianceState.FAIL)
        self.assertEqual(res.evaluation_method, EvaluationMethod.DETERMINISTIC)
        self.assertEqual(res.risk_level, "HIGH")
        self.assertIn("fails the mandatory condition", res.reason)

    # -----------------------------------------------------------------------
    # 3. Exact Boundary PASS (20% >= 20%)
    # -----------------------------------------------------------------------
    def test_case_3_exact_boundary_pass(self):
        req = TenderRequirement(
            requirement_id="REQ-LC-01",
            category=RequirementCategory.LOCAL_CONTENT,
            description="Minimum 20% Local Content required.",
            mandatory=True,
        )
        evidence = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-LC-01",
            observed_value="20.0%",
            unit="PERCENT",
            source_document="ca_certificate.pdf",
        )
        res = evaluate_requirement(requirement=req, evidence=evidence)
        self.assertEqual(res.state, ComplianceState.PASS)
        self.assertEqual(res.evaluation_method, EvaluationMethod.DETERMINISTIC)
        self.assertEqual(res.risk_level, "NONE")

    # -----------------------------------------------------------------------
    # 4. Turnover PASS (₹6.42 crore >= ₹5 crore)
    # -----------------------------------------------------------------------
    def test_case_4_turnover_pass(self):
        req = TenderRequirement(
            requirement_id="REQ-TO-01",
            category=RequirementCategory.FINANCIAL_TURNOVER,
            description="Average Annual Turnover of minimum INR 5 Crore over past 3 financial years.",
            mandatory=True,
        )
        evidence = EvidenceObservation(
            evidence_id="EVD-TO-01",
            requirement_id="REQ-TO-01",
            observed_value="INR 6.42 crore",
            source_document="audited_financials.pdf",
        )
        res = evaluate_requirement(requirement=req, evidence=evidence)
        self.assertEqual(res.state, ComplianceState.PASS)
        self.assertEqual(res.evaluation_method, EvaluationMethod.DETERMINISTIC)
        self.assertEqual(res.risk_level, "NONE")

    # -----------------------------------------------------------------------
    # 5. Missing Mandatory Evidence -> UNVERIFIED
    # -----------------------------------------------------------------------
    def test_case_5_missing_mandatory_evidence_unverified(self):
        req = TenderRequirement(
            requirement_id="REQ-GST-01",
            category=RequirementCategory.GST,
            description="Valid GSTIN Registration Certificate must be submitted.",
            mandatory=True,
            evidence_required=["GST Registration Certificate"],
        )
        res = evaluate_requirement(requirement=req, claims=[], evidence=[])
        self.assertEqual(res.state, ComplianceState.UNVERIFIED)
        self.assertEqual(res.evaluation_method, EvaluationMethod.DOCUMENT_PRESENCE)
        self.assertEqual(res.risk_level, "HIGH")
        self.assertIn("was not submitted", res.reason)

    # -----------------------------------------------------------------------
    # 6. Contradiction (Claim 27% vs CA Certificate 14%) -> REVIEW
    # -----------------------------------------------------------------------
    def test_case_6_contradiction_yields_review(self):
        req = TenderRequirement(
            requirement_id="REQ-LC-01",
            category=RequirementCategory.LOCAL_CONTENT,
            description="Minimum 20% Local Content.",
            mandatory=True,
        )
        claim = BidderClaim(
            claim_id="CLM-01",
            requirement_id="REQ-LC-01",
            claimed_value="27%",
            unit="PERCENT",
            source_document="self_declaration.pdf",
        )
        evidence = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-LC-01",
            observed_value="14%",
            unit="PERCENT",
            source_document="ca_certificate.pdf",
        )
        res = evaluate_requirement(requirement=req, claims=claim, evidence=evidence)
        self.assertEqual(res.state, ComplianceState.REVIEW)
        self.assertEqual(res.evaluation_method, EvaluationMethod.CONTRADICTION_RECONCILIATION)
        self.assertEqual(res.risk_level, "HIGH")
        self.assertTrue(res.review_required)
        self.assertEqual(len(res.contradiction_findings), 1)
        self.assertEqual(len(res.conflicting_evidence), 2)
        self.assertIn("The evidence conflicts and requires officer review", res.reason)

    # -----------------------------------------------------------------------
    # 7. Multiple Consistent Observations (27%, 27%) -> Deterministic PASS
    # -----------------------------------------------------------------------
    def test_case_7_multiple_consistent_observations_pass(self):
        req = TenderRequirement(
            requirement_id="REQ-LC-01",
            category=RequirementCategory.LOCAL_CONTENT,
            description="Minimum 20% Local Content.",
            mandatory=True,
        )
        ev1 = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-LC-01",
            observed_value="27%",
            unit="PERCENT",
            source_document="ca_certificate.pdf",
        )
        ev2 = EvidenceObservation(
            evidence_id="EVD-02",
            requirement_id="REQ-LC-01",
            observed_value="27%",
            unit="PERCENT",
            source_document="bom_breakdown.pdf",
        )
        res = evaluate_requirement(requirement=req, evidence=[ev1, ev2])
        self.assertEqual(res.state, ComplianceState.PASS)
        self.assertEqual(res.evaluation_method, EvaluationMethod.DETERMINISTIC)
        self.assertEqual(res.risk_level, "NONE")

    # -----------------------------------------------------------------------
    # 8. Unsupported Claim (Claim without Evidence) -> UNVERIFIED
    # -----------------------------------------------------------------------
    def test_case_8_unsupported_claim_unverified(self):
        req = TenderRequirement(
            requirement_id="REQ-LC-01",
            category=RequirementCategory.LOCAL_CONTENT,
            description="Minimum 20% Local Content with CA Certificate.",
            mandatory=True,
            evidence_required=["CA Certificate"],
        )
        claim = BidderClaim(
            claim_id="CLM-01",
            requirement_id="REQ-LC-01",
            claimed_value="27%",
            unit="PERCENT",
            source_document="bidder_letter.pdf",
        )
        res = evaluate_requirement(requirement=req, claims=claim, evidence=[])
        self.assertEqual(res.state, ComplianceState.UNVERIFIED)
        self.assertEqual(res.evaluation_method, EvaluationMethod.DOCUMENT_PRESENCE)
        self.assertIn("supporting proof document was not submitted", res.reason)

    # -----------------------------------------------------------------------
    # 9. Ambiguous Date Semantics (WO 2020 vs Completion 2023 with 5-yr window) -> REVIEW
    # -----------------------------------------------------------------------
    def test_case_9_ambiguous_date_semantics_review(self):
        req = TenderRequirement(
            requirement_id="REQ-EXP-01",
            category=RequirementCategory.EXPERIENCE,
            description="Experience of similar works completed during last 5 years.",
            mandatory=True,
        )
        ev_wo = EvidenceObservation(
            evidence_id="EVD-WO",
            requirement_id="REQ-EXP-01",
            observed_value="15 August 2020",
            source_document="work_order.pdf",
            source_quote="Work Order Date: 15-08-2020",
        )
        ev_comp = EvidenceObservation(
            evidence_id="EVD-COMP",
            requirement_id="REQ-EXP-01",
            observed_value="15 March 2023",
            source_document="completion_cert.pdf",
            source_quote="Completion Date: 15-03-2023",
        )
        context = {
            "anchor_date": date(2026, 9, 4),
            "work_order_date": "15 August 2020",
            "completion_date": "15 March 2023",
        }
        res = evaluate_requirement(requirement=req, evidence=[ev_wo, ev_comp], context=context)
        self.assertEqual(res.state, ComplianceState.REVIEW)
        self.assertEqual(res.evaluation_method, EvaluationMethod.DETERMINISTIC)
        self.assertEqual(res.risk_level, "MEDIUM")
        self.assertIn("Date semantics ambiguity", res.reason)

    # -----------------------------------------------------------------------
    # 10. Verified Exemption -> NOT_APPLICABLE
    # -----------------------------------------------------------------------
    def test_case_10_verified_exemption_not_applicable(self):
        req = TenderRequirement(
            requirement_id="REQ-TO-01",
            category=RequirementCategory.FINANCIAL_TURNOVER,
            description="Minimum Turnover of 5 Crore. MSE bidders are exempt as per policy.",
            mandatory=True,
            applicability=ApplicabilitySpec(msme_exemption_applicable=True),
        )
        context = {"is_mse": True}
        res = evaluate_requirement(requirement=req, context=context)
        self.assertEqual(res.state, ComplianceState.NOT_APPLICABLE)
        self.assertEqual(res.evaluation_method, EvaluationMethod.APPLICABILITY_EXEMPTION)
        self.assertEqual(res.risk_level, "NONE")
        self.assertIn("verified MSE exemption applies", res.reason)

    # -----------------------------------------------------------------------
    # 11. Unverified Exemption -> REVIEW
    # -----------------------------------------------------------------------
    def test_case_11_unverified_exemption_review(self):
        req = TenderRequirement(
            requirement_id="REQ-TO-01",
            category=RequirementCategory.FINANCIAL_TURNOVER,
            description="Minimum Turnover of 5 Crore.",
            mandatory=True,
            applicability=ApplicabilitySpec(msme_exemption_applicable=True),
        )
        context = {"is_mse": None, "exemptions": {"MSE": {"is_exempt": None, "type": "MSE Exemption"}}}
        res = evaluate_requirement(requirement=req, context=context)
        self.assertEqual(res.state, ComplianceState.REVIEW)
        self.assertEqual(res.evaluation_method, EvaluationMethod.APPLICABILITY_EXEMPTION)
        self.assertEqual(res.risk_level, "MEDIUM")
        self.assertIn("unverified", res.reason)

    # -----------------------------------------------------------------------
    # 12. Semantic Requirement with LLM Available -> SEMANTIC_LLM
    # -----------------------------------------------------------------------
    def test_case_12_semantic_requirement_with_llm_available(self):
        set_semantic_evaluator(MockSemanticEvaluator(available=True))
        req = TenderRequirement(
            requirement_id="REQ-TECH-01",
            category=RequirementCategory.TECHNICAL_SPECIFICATION,
            description="Bidder must provide adequate cloud architecture and satisfactory SLA compliance.",
            mandatory=True,
        )
        evidence = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-TECH-01",
            observed_value="Standard SLA proposal",
            source_document="technical_bid.pdf",
        )
        res = evaluate_requirement(requirement=req, evidence=evidence)
        self.assertEqual(res.state, ComplianceState.REVIEW)
        self.assertEqual(res.evaluation_method, EvaluationMethod.SEMANTIC_LLM)
        self.assertTrue(res.review_required)

    # -----------------------------------------------------------------------
    # 13. Semantic Requirement with LLM Unavailable -> HUMAN_REVIEW (Never Fabricate PASS/FAIL)
    # -----------------------------------------------------------------------
    def test_case_13_semantic_requirement_with_llm_unavailable_human_review(self):
        set_semantic_evaluator(MockSemanticEvaluator(available=False))
        req = TenderRequirement(
            requirement_id="REQ-TECH-01",
            category=RequirementCategory.TECHNICAL_SPECIFICATION,
            description="Bidder must provide custom architecture overview.",
            mandatory=True,
        )
        evidence = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-TECH-01",
            observed_value="Custom Diagram",
            source_document="technical_bid.pdf",
        )
        res = evaluate_requirement(requirement=req, evidence=evidence)
        self.assertEqual(res.state, ComplianceState.REVIEW)
        self.assertEqual(res.evaluation_method, EvaluationMethod.HUMAN_REVIEW)
        self.assertEqual(res.risk_level, "MEDIUM")
        self.assertIn("human review required", res.reason.lower())

    # -----------------------------------------------------------------------
    # 14. External Verification Unavailable -> Never PASS (Returns REVIEW)
    # -----------------------------------------------------------------------
    def test_case_14_external_verification_unavailable_never_pass(self):
        req = TenderRequirement(
            requirement_id="REQ-GST-01",
            category=RequirementCategory.GST,
            description="GSTIN verification via GSTN portal.",
            mandatory=True,
        )
        ext_verif = {
            "status": "UNAVAILABLE",
            "source": "GSTN API Gateway",
        }
        res = evaluate_requirement(requirement=req, external_verification=ext_verif)
        self.assertEqual(res.state, ComplianceState.REVIEW)
        self.assertEqual(res.evaluation_method, EvaluationMethod.EXTERNAL_VERIFICATION)
        self.assertNotEqual(res.state, ComplianceState.PASS)
        self.assertEqual(res.risk_level, "HIGH")
        self.assertIn("unavailable", res.reason)

    # -----------------------------------------------------------------------
    # 15. External Verification Verified -> Usable as Evidence (PASS)
    # -----------------------------------------------------------------------
    def test_case_15_external_verification_verified_pass(self):
        req = TenderRequirement(
            requirement_id="REQ-GST-01",
            category=RequirementCategory.GST,
            description="GSTIN verification via GSTN portal.",
            mandatory=True,
        )
        ext_verif = {
            "status": "VERIFIED",
            "source": "GSTN Authoritative Registry",
            "details": {"gstin": "27AABCU9603R1ZN", "legal_name": "Bharat Heavy Electricals"},
        }
        res = evaluate_requirement(requirement=req, external_verification=ext_verif)
        self.assertEqual(res.state, ComplianceState.PASS)
        self.assertEqual(res.evaluation_method, EvaluationMethod.EXTERNAL_VERIFICATION)
        self.assertEqual(res.risk_level, "NONE")
        self.assertIn("confirmed valid and active", res.reason)

    # -----------------------------------------------------------------------
    # 16. Incompatible Units -> REVIEW (20% vs ₹20 lakh)
    # -----------------------------------------------------------------------
    def test_case_16_incompatible_units_review(self):
        req = TenderRequirement(
            requirement_id="REQ-LC-01",
            category=RequirementCategory.LOCAL_CONTENT,
            description="Minimum 20% Local Content.",
            mandatory=True,
        )
        evidence = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-LC-01",
            observed_value="₹20 lakh",
            source_document="invoice.pdf",
        )
        res = evaluate_requirement(requirement=req, evidence=evidence)
        self.assertEqual(res.state, ComplianceState.REVIEW)
        self.assertEqual(res.risk_level, "HIGH")
        self.assertIn("Incompatible unit comparison", res.reason)

    # -----------------------------------------------------------------------
    # 17. Provenance Survives Evaluation Result
    # -----------------------------------------------------------------------
    def test_case_17_provenance_integrity(self):
        req = TenderRequirement(
            requirement_id="REQ-LC-01",
            category=RequirementCategory.LOCAL_CONTENT,
            description="Minimum 20% Local Content.",
            mandatory=True,
        )
        claim = BidderClaim(
            claim_id="CLM-LC-101",
            requirement_id="REQ-LC-01",
            claimed_value="27%",
            unit="PERCENT",
            source_document="tender_bid_submission.pdf",
            page_number=14,
            raw_statement="Clause 4.2 Local content percentage: 27%",
        )
        evidence = EvidenceObservation(
            evidence_id="EVD-LC-101",
            requirement_id="REQ-LC-01",
            observed_value="27%",
            unit="PERCENT",
            source_document="chartered_accountant_certificate.pdf",
            page_number=3,
            source_quote="We certify local value addition is 27.0%.",
        )
        res = evaluate_requirement(requirement=req, claims=claim, evidence=evidence)
        self.assertEqual(len(res.provenance), 2)
        p1 = res.provenance[0]
        self.assertEqual(p1.document_name, "tender_bid_submission.pdf")
        self.assertEqual(p1.page_number, 14)
        self.assertEqual(p1.normalized_value, 27.0)

        p2 = res.provenance[1]
        self.assertEqual(p2.document_name, "chartered_accountant_certificate.pdf")
        self.assertEqual(p2.page_number, 3)
        self.assertEqual(p2.quote, "We certify local value addition is 27.0%.")

    # -----------------------------------------------------------------------
    # 18. Contradictory Evidence Remains Preserved
    # -----------------------------------------------------------------------
    def test_case_18_conflicting_evidence_preserved_side_by_side(self):
        req = TenderRequirement(
            requirement_id="REQ-LC-01",
            category=RequirementCategory.LOCAL_CONTENT,
            description="Minimum 20% Local Content.",
            mandatory=True,
        )
        claim = BidderClaim(
            claim_id="CLM-01",
            requirement_id="REQ-LC-01",
            claimed_value="27%",
            source_document="declaration.pdf",
        )
        evidence = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-LC-01",
            observed_value="14%",
            source_document="ca_certificate.pdf",
        )
        res = evaluate_requirement(requirement=req, claims=claim, evidence=evidence)
        self.assertEqual(len(res.conflicting_evidence), 2)
        self.assertEqual(len(res.contradiction_findings), 1)
        finding = res.contradiction_findings[0]
        self.assertIsNotNone(finding.side_by_side)
        self.assertEqual(finding.side_by_side.left.raw_value, "27%")
        self.assertEqual(finding.side_by_side.right.raw_value, "14%")

    # -----------------------------------------------------------------------
    # 19. evaluate_requirements Evaluates Multiple Requirements Independently
    # -----------------------------------------------------------------------
    def test_case_19_evaluate_requirements_multi_batch(self):
        req1 = TenderRequirement(
            requirement_id="REQ-GST-01",
            category=RequirementCategory.GST,
            description="GST Certificate",
            mandatory=True,
        )
        req2 = TenderRequirement(
            requirement_id="REQ-TO-01",
            category=RequirementCategory.FINANCIAL_TURNOVER,
            description="Turnover minimum 5 Crore",
            mandatory=True,
        )
        req3 = TenderRequirement(
            requirement_id="REQ-LC-01",
            category=RequirementCategory.LOCAL_CONTENT,
            description="Local Content 20%",
            mandatory=True,
        )

        claims = {
            "REQ-LC-01": BidderClaim(claim_id="C1", requirement_id="REQ-LC-01", claimed_value="27%"),
        }
        evidence = {
            "REQ-TO-01": EvidenceObservation(evidence_id="E1", requirement_id="REQ-TO-01", observed_value="6.42 Crore"),
            "REQ-LC-01": EvidenceObservation(evidence_id="E2", requirement_id="REQ-LC-01", observed_value="14%"),
        }
        verifs = {
            "REQ-GST-01": {"status": "VERIFIED", "source": "GSTN", "details": {"gstin": "27AABCU9603R1ZN"}},
        }

        results = evaluate_requirements(
            requirements=[req1, req2, req3],
            claims_by_req=claims,
            evidence_by_req=evidence,
            verifications_by_req=verifs,
        )
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].requirement_id, "REQ-GST-01")
        self.assertEqual(results[0].state, ComplianceState.PASS)
        self.assertEqual(results[0].evaluation_method, EvaluationMethod.EXTERNAL_VERIFICATION)

        self.assertEqual(results[1].requirement_id, "REQ-TO-01")
        self.assertEqual(results[1].state, ComplianceState.PASS)
        self.assertEqual(results[1].evaluation_method, EvaluationMethod.DETERMINISTIC)

        self.assertEqual(results[2].requirement_id, "REQ-LC-01")
        self.assertEqual(results[2].state, ComplianceState.REVIEW)
        self.assertEqual(results[2].evaluation_method, EvaluationMethod.CONTRADICTION_RECONCILIATION)

    # -----------------------------------------------------------------------
    # 20. No Cross-Contamination of Deterministic Results by Ambiguous Clauses
    # -----------------------------------------------------------------------
    def test_case_20_no_cross_contamination(self):
        req_clean = TenderRequirement(
            requirement_id="REQ-WARR-01",
            category=RequirementCategory.COMMERCIAL,
            description="24 Months Warranty.",
            mandatory=True,
        )
        req_ambiguous = TenderRequirement(
            requirement_id="REQ-VAGUE-01",
            category=RequirementCategory.OTHER,
            description="Satisfactory track record and good standing.",
            is_ambiguous=True,
            ambiguity_reason="Underspecified subjective terminology.",
        )

        ev_warr = EvidenceObservation(
            evidence_id="EVD-W",
            requirement_id="REQ-WARR-01",
            observed_value="24 Months",
        )
        ev_vague = EvidenceObservation(
            evidence_id="EVD-V",
            requirement_id="REQ-VAGUE-01",
            observed_value="Satisfactory report",
        )

        results = evaluate_requirements(
            requirements=[req_clean, req_ambiguous],
            evidence_by_req={"REQ-WARR-01": ev_warr, "REQ-VAGUE-01": ev_vague},
        )
        self.assertEqual(results[0].state, ComplianceState.PASS)
        self.assertEqual(results[0].evaluation_method, EvaluationMethod.DETERMINISTIC)

        self.assertEqual(results[1].state, ComplianceState.REVIEW)
        self.assertEqual(results[1].evaluation_method, EvaluationMethod.HUMAN_REVIEW)

    # -----------------------------------------------------------------------
    # 21. Compatibility with Legacy ExtractedEvidence and Synthetic Tender Demo
    # -----------------------------------------------------------------------
    def test_case_21_synthetic_demo_and_legacy_model_compatibility(self):
        # Synthetic Tender DEMO/CPCL/WQM/2026/017
        req_to = TenderRequirement(
            requirement_id="REQ-003",
            category=RequirementCategory.FINANCIAL_TURNOVER,
            description="Minimum Average Annual Turnover of INR 5.00 Crore during last 3 FYs.",
            mandatory=True,
        )
        req_lc = TenderRequirement(
            requirement_id="REQ-006",
            category=RequirementCategory.LOCAL_CONTENT_MII,
            description="Minimum 20% Local Content under Make in India policy.",
            mandatory=True,
        )
        req_warr = TenderRequirement(
            requirement_id="REQ-008",
            category=RequirementCategory.COMMERCIAL,
            description="24 Months Comprehensive Onsite Warranty.",
            mandatory=True,
        )
        req_vague = TenderRequirement(
            requirement_id="REQ-009",
            category=RequirementCategory.TECHNICAL_SPECIFICATION,
            description="Adequate experience and satisfactory reputation in water quality monitoring.",
            mandatory=True,
            is_ambiguous=True,
            ambiguity_reason="Vague and subjective clause without objective metrics.",
        )

        # Evidence inputs
        claims = {
            "REQ-006": BidderClaim(claim_id="CLM-006", requirement_id="REQ-006", claimed_value="27%"),
        }
        legacy_evidence = {
            "REQ-003": ExtractedEvidence(
                requirement_id="REQ-003",
                is_present=True,
                extracted_values={"turnover": "6.42 Crore"},
                extraction_confidence=0.98,
            ),
            "REQ-006": ExtractedEvidence(
                requirement_id="REQ-006",
                is_present=True,
                extracted_values={"local_content": "14%"},
                extraction_confidence=0.95,
            ),
            "REQ-008": ExtractedEvidence(
                requirement_id="REQ-008",
                is_present=True,
                extracted_values={"warranty": "24 Months"},
                extraction_confidence=0.99,
            ),
            "REQ-009": ExtractedEvidence(
                requirement_id="REQ-009",
                is_present=True,
                source_quote="Bidder has 5 years presence in domain.",
                extraction_confidence=0.80,
            ),
        }

        results = evaluate_requirements(
            requirements=[req_to, req_lc, req_warr, req_vague],
            claims_by_req=claims,
            evidence_by_req=legacy_evidence,
        )

        # REQ-003 Turnover: PASS
        self.assertEqual(results[0].requirement_id, "REQ-003")
        self.assertEqual(results[0].state, ComplianceState.PASS)
        self.assertEqual(results[0].evaluation_method, EvaluationMethod.DETERMINISTIC)

        # REQ-006 Local Content: REVIEW due to contradiction (27% vs 14%)
        self.assertEqual(results[1].requirement_id, "REQ-006")
        self.assertEqual(results[1].state, ComplianceState.REVIEW)
        self.assertEqual(results[1].evaluation_method, EvaluationMethod.CONTRADICTION_RECONCILIATION)

        # REQ-008 Warranty: PASS
        self.assertEqual(results[2].requirement_id, "REQ-008")
        self.assertEqual(results[2].state, ComplianceState.PASS)
        self.assertEqual(results[2].evaluation_method, EvaluationMethod.DETERMINISTIC)

        # REQ-009 Vague capability: REVIEW
        self.assertEqual(results[3].requirement_id, "REQ-009")
        self.assertEqual(results[3].state, ComplianceState.REVIEW)

        # Convert to legacy ComplianceFinding
        finding = results[0].to_compliance_finding()
        self.assertIsInstance(finding, ComplianceFinding)
        self.assertEqual(finding.state, ComplianceState.PASS)


if __name__ == "__main__":
    unittest.main()

