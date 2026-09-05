"""Unit tests for OPAL Deterministic Rule Engine (SIH26100)."""

from datetime import date
import unittest

from app.models.evaluation import ComplianceFinding, ComplianceState
from app.models.evidence import BidderClaim, EvidenceObservation, ExtractedEvidence
from app.models.tender import RequirementCategory, TenderRequirement
from app.rules.engine import (
    evaluate_applicability_exemption,
    evaluate_date_validity,
    evaluate_experience_window,
    evaluate_mandatory_evidence,
    evaluate_numeric_threshold,
    evaluate_requirement,
    parse_date_value,
    parse_numeric_value,
)


class TestDeterministicComplianceEngine(unittest.TestCase):
    """Test suite covering all deterministic compliance rules and edge cases."""

    # -----------------------------------------------------------------------
    # 1-3. Numeric Threshold Tests (Percentage)
    # -----------------------------------------------------------------------
    def test_case_1_local_content_pass(self):
        """Test Case 1: 27% >= 20% -> PASS"""
        finding = evaluate_numeric_threshold(
            requirement_id="REQ-LC-01",
            operator=">=",
            expected_val=20.0,
            expected_unit="PERCENT",
            observed_values="27%",
        )
        self.assertEqual(finding.state, ComplianceState.PASS)
        self.assertEqual(finding.risk_level, "NONE")
        self.assertIn("satisfies the mandatory condition", finding.reasoning_trace)
        self.assertEqual(finding.observed["value"], 27.0)

    def test_case_2_local_content_fail(self):
        """Test Case 2: 14% >= 20% -> FAIL"""
        finding = evaluate_numeric_threshold(
            requirement_id="REQ-LC-01",
            operator=">=",
            expected_val=20.0,
            expected_unit="PERCENT",
            observed_values="14%",
        )
        self.assertEqual(finding.state, ComplianceState.FAIL)
        self.assertEqual(finding.risk_level, "HIGH")
        self.assertIn("fails the mandatory condition", finding.reasoning_trace)
        self.assertEqual(finding.observed["value"], 14.0)

    def test_case_3_local_content_exact_boundary_pass(self):
        """Test Case 3: 20% >= 20% -> PASS"""
        finding = evaluate_numeric_threshold(
            requirement_id="REQ-LC-01",
            operator=">=",
            expected_val=20.0,
            expected_unit="PERCENT",
            observed_values="20.0%",
        )
        self.assertEqual(finding.state, ComplianceState.PASS)
        self.assertEqual(finding.risk_level, "NONE")
        self.assertEqual(finding.observed["value"], 20.0)

    # -----------------------------------------------------------------------
    # 4-5. Missing and Invalid Numeric Values
    # -----------------------------------------------------------------------
    def test_case_4_missing_numeric_observation(self):
        """Test Case 4: Missing numeric observation -> UNVERIFIED"""
        finding = evaluate_numeric_threshold(
            requirement_id="REQ-LC-01",
            operator=">=",
            expected_val=20.0,
            expected_unit="PERCENT",
            observed_values=None,
        )
        self.assertEqual(finding.state, ComplianceState.UNVERIFIED)
        self.assertIn("No observed numeric values", finding.reasoning_trace)

    def test_case_5_invalid_numeric_value(self):
        """Test Case 5: Invalid numeric value -> REVIEW"""
        finding = evaluate_numeric_threshold(
            requirement_id="REQ-LC-01",
            operator=">=",
            expected_val=20.0,
            expected_unit="PERCENT",
            observed_values="Not Applicable / Unspecified text",
        )
        self.assertEqual(finding.state, ComplianceState.REVIEW)
        self.assertEqual(finding.risk_level, "HIGH")
        self.assertIn("could not be deterministically parsed", finding.reasoning_trace)

    # -----------------------------------------------------------------------
    # 6-7. Financial Thresholds (Crores, Lakhs, INR)
    # -----------------------------------------------------------------------
    def test_case_6_turnover_6_42_crore_pass(self):
        """Test Case 6: Turnover 6.42 crore >= 5 crore -> PASS"""
        req_parsed, _ = parse_numeric_value("INR 5 crore")
        finding = evaluate_numeric_threshold(
            requirement_id="REQ-TO-01",
            operator=">=",
            expected_val=req_parsed,
            expected_unit="INR",
            observed_values="INR 6.42 crore",
        )
        self.assertEqual(finding.state, ComplianceState.PASS)
        self.assertEqual(finding.observed["value"], 64_200_000.0)
        self.assertEqual(finding.risk_level, "NONE")

    def test_case_7_turnover_4_crore_fail(self):
        """Test Case 7: Turnover 4 crore >= 5 crore -> FAIL"""
        req_parsed, _ = parse_numeric_value("₹5 Crore")
        finding = evaluate_numeric_threshold(
            requirement_id="REQ-TO-01",
            operator=">=",
            expected_val=req_parsed,
            expected_unit="INR",
            observed_values="4 Cr",
        )
        self.assertEqual(finding.state, ComplianceState.FAIL)
        self.assertEqual(finding.observed["value"], 40_000_000.0)
        self.assertEqual(finding.risk_level, "HIGH")

    # -----------------------------------------------------------------------
    # 8-10. Date Validity & Time Windows
    # -----------------------------------------------------------------------
    def test_case_8_valid_certificate_date_pass(self):
        """Test Case 8: Valid certificate until 31 March 2027 (today = 4 Sep 2026) -> PASS"""
        anchor = date(2026, 9, 4)
        finding = evaluate_date_validity(
            requirement_id="REQ-CERT-01",
            expiry_date_input="31 March 2027",
            anchor_date=anchor,
        )
        self.assertEqual(finding.state, ComplianceState.PASS)
        self.assertEqual(finding.risk_level, "NONE")
        self.assertIn("valid until 2027-03-31", finding.reasoning_trace)

    def test_case_9_expired_certificate_fail(self):
        """Test Case 9: Expired certificate on 31 March 2026 (today = 4 Sep 2026) -> FAIL"""
        anchor = date(2026, 9, 4)
        finding = evaluate_date_validity(
            requirement_id="REQ-CERT-01",
            expiry_date_input="31 March 2026",
            anchor_date=anchor,
        )
        self.assertEqual(finding.state, ComplianceState.FAIL)
        self.assertEqual(finding.risk_level, "CRITICAL")
        self.assertIn("expired on 2026-03-31", finding.reasoning_trace)

    def test_case_10_ambiguous_date_semantics_review(self):
        """Test Case 10: Ambiguous date semantics (WO date outside, completion date inside) -> REVIEW"""
        anchor = date(2026, 9, 4)
        finding = evaluate_experience_window(
            requirement_id="REQ-EXP-01",
            past_years_required=5,
            work_order_date_input="15 August 2020",  # Prior to 5-yr cutoff (2021-09-04)
            completion_date_input="15 March 2023",    # Within 5-yr window
            tender_closing_date=anchor,
        )
        self.assertEqual(finding.state, ComplianceState.REVIEW)
        self.assertEqual(finding.risk_level, "MEDIUM")
        self.assertIn("Date semantics ambiguity", finding.reasoning_trace)

    # -----------------------------------------------------------------------
    # 11-14. Evidence Presence, Exemptions, Conflict, Unit Compatibility
    # -----------------------------------------------------------------------
    def test_case_11_mandatory_evidence_absent_unverified(self):
        """Test Case 11: Mandatory evidence absent -> UNVERIFIED"""
        finding = evaluate_mandatory_evidence(
            requirement_id="REQ-OEM-01",
            evidence_present=False,
            evidence_name="Manufacturer Authorization Form (MAF)",
        )
        self.assertEqual(finding.state, ComplianceState.UNVERIFIED)
        self.assertEqual(finding.risk_level, "HIGH")
        self.assertIn("was not submitted", finding.reasoning_trace)

    def test_case_12_explicit_exemption_not_applicable(self):
        """Test Case 12: Explicit MSE exemption -> NOT_APPLICABLE"""
        finding = evaluate_applicability_exemption(
            requirement_id="REQ-TO-01",
            exemption_type="MSE Exemption under Public Procurement Policy",
            is_exempt=True,
            exemption_reason="Valid Udyam Registration Certificate verified on MSME portal.",
        )
        self.assertIsNotNone(finding)
        self.assertEqual(finding.state, ComplianceState.NOT_APPLICABLE)
        self.assertEqual(finding.risk_level, "NONE")
        self.assertIn("Requirement waived", finding.reasoning_trace)

    def test_case_13_conflicting_observations_review(self):
        """Test Case 13: Conflicting observations (27% vs 14%) -> REVIEW preserving both"""
        finding = evaluate_numeric_threshold(
            requirement_id="REQ-LC-01",
            operator=">=",
            expected_val=20.0,
            expected_unit="PERCENT",
            observed_values=["27%", "14%"],
        )
        self.assertEqual(finding.state, ComplianceState.REVIEW)
        self.assertEqual(finding.risk_level, "HIGH")
        self.assertIn("Multiple conflicting numeric observations detected", finding.reasoning_trace)
        self.assertIn("conflicting_observations", finding.observed)
        self.assertEqual(len(finding.observed["distinct_values"]), 2)

    def test_case_14_incompatible_units_review(self):
        """Test Case 14: Incompatible units (PERCENT vs INR) -> REVIEW"""
        finding = evaluate_numeric_threshold(
            requirement_id="REQ-LC-01",
            operator=">=",
            expected_val=20.0,
            expected_unit="PERCENT",
            observed_values="INR 20",
        )
        self.assertEqual(finding.state, ComplianceState.REVIEW)
        self.assertEqual(finding.risk_level, "HIGH")
        self.assertIn("Incompatible unit comparison", finding.reasoning_trace)

    # -----------------------------------------------------------------------
    # 15. High-Level evaluate_requirement Integration Test
    # -----------------------------------------------------------------------
    def test_evaluate_requirement_full_pipeline(self):
        """Test evaluate_requirement with TenderRequirement and BidderClaim/ExtractedEvidence models."""
        req = TenderRequirement(
            requirement_id="REQ-LC-001",
            category=RequirementCategory.LOCAL_CONTENT,
            description="Minimum 50% Local Content under Make in India policy.",
            mandatory=True,
            evidence_required=["Local Content Declaration"],
        )
        claim = BidderClaim(
            claim_id="CLM-01",
            requirement_id="REQ-LC-001",
            claimed_value="55%",
            unit="PERCENT",
        )
        evidence = ExtractedEvidence(
            requirement_id="REQ-LC-001",
            is_present=True,
            extracted_values={"local_content_percentage": "55%"},
            source_quote="Product contains 55% local content.",
            extraction_confidence=0.98,
        )

        finding = evaluate_requirement(requirement=req, claims=claim, evidence=evidence)
        self.assertEqual(finding.state, ComplianceState.PASS)
        self.assertEqual(finding.risk_level, "NONE")
        self.assertEqual(finding.observed["value"], 55.0)


if __name__ == "__main__":
    unittest.main()

