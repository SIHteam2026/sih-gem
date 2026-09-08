"""Comprehensive Unit & Integration Tests for Layer 6: Past Performance and Capacity (SIH26100)."""

import unittest
from datetime import datetime, timezone, timedelta

from app.models.evaluation import ComplianceState
from app.models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
from app.models.tender import RequirementCategory, TenderRequirement
from app.models.tender_contract import CanonicalEvaluationField, RequirementEvaluationContract
from app.models.verification import (
    FindingSeverity,
    VerificationContext,
    VerificationFinding,
    VerificationLayer,
)
from app.rules.layers.past_performance_capacity import PastPerformanceCapacityVerifier
from app.rules.utils.past_performance_helpers import (
    calculate_past_performance_ratio,
    classify_evidence_authority,
    evaluate_capacity_saturation,
    is_recent,
    normalize_to_months,
    normalize_to_years,
)
from app.services.tender_contract_service import build_requirement_evaluation_contract


def make_contract(req_id: str, category: RequirementCategory, description: str, **kwargs) -> RequirementEvaluationContract:
    return build_requirement_evaluation_contract(
        TenderRequirement(requirement_id=req_id, category=category, description=description, **kwargs),
        tender_id="DEMO/CPCL/WQM/2026/017",
    )


class TestPastPerformanceCapacityEvaluation(unittest.IsolatedAsyncioTestCase):
    """Rigorous tests for Layer 6 verification logic, capacity saturation, and recency arithmetic."""

    def setUp(self):
        self.verifier = PastPerformanceCapacityVerifier()

    # -----------------------------------------------------------------------
    # 1. Helper Function Tests
    # -----------------------------------------------------------------------
    def test_01_normalization_helpers(self):
        self.assertEqual(normalize_to_years(100, "YEAR"), 100.0)
        self.assertEqual(normalize_to_years(10, "MONTH"), 120.0)
        self.assertEqual(normalize_to_years(2, "WEEK"), 104.0)
        self.assertEqual(normalize_to_years(1, "DAY"), 365.0)

        self.assertEqual(normalize_to_months(120, "YEAR"), 10.0)
        self.assertEqual(normalize_to_months(50, "MONTH"), 50.0)

    def test_02_recency_parsing_and_utc_safety(self):
        now_utc = datetime.now(timezone.utc)
        recent_iso = (now_utc - timedelta(days=200)).strftime("%Y-%m-%d")
        old_iso = (now_utc - timedelta(days=1500)).strftime("%Y-%m-%d")

        self.assertTrue(is_recent(recent_iso, recency_days=1095))
        self.assertFalse(is_recent(old_iso, recency_days=1095))
        self.assertIsNone(is_recent("invalid-date-string", recency_days=1095))
        self.assertIsNone(is_recent(None, recency_days=1095))

    def test_03_capacity_saturation_arithmetic(self):
        # Scenario A: Healthy capacity (500 capacity, 200 committed, 150 required)
        res_healthy = evaluate_capacity_saturation(total_capacity=500, committed_capacity=200, required_capacity=150)
        self.assertEqual(res_healthy["net_available_capacity"], 300)
        self.assertEqual(res_healthy["saturation_percentage"], 40.0)
        self.assertFalse(res_healthy["is_overcommitted"])
        self.assertTrue(res_healthy["is_sufficient"])

        # Scenario B: Overcommitted capacity (500 capacity, 550 committed, 50 required)
        res_over = evaluate_capacity_saturation(total_capacity=500, committed_capacity=550, required_capacity=50)
        self.assertEqual(res_over["net_available_capacity"], 0.0)
        self.assertTrue(res_over["is_overcommitted"])
        self.assertFalse(res_over["is_sufficient"])

        # Scenario C: Insufficient net available capacity (500 capacity, 400 committed, 150 required)
        res_insufficient = evaluate_capacity_saturation(total_capacity=500, committed_capacity=400, required_capacity=150)
        self.assertEqual(res_insufficient["net_available_capacity"], 100)
        self.assertFalse(res_insufficient["is_overcommitted"])
        self.assertFalse(res_insufficient["is_sufficient"])

    def test_04_evidence_authority_classification(self):
        self.assertEqual(classify_evidence_authority(source_document="client_completion_certificate.pdf", quote="UDIN certified"), "CERTIFIED")
        self.assertEqual(classify_evidence_authority(source_document="gem_portal_performance_record.pdf"), "INDEPENDENT")
        self.assertEqual(classify_evidence_authority(source_document="self_declaration.pdf"), "DECLARED")

    # -----------------------------------------------------------------------
    # 2. Verifier Integration Tests
    # -----------------------------------------------------------------------
    async def test_05_contract_count_compliance_states(self):
        reqs = [
            make_contract(
                "REQ-EXP-01",
                RequirementCategory.EXPERIENCE,
                "Minimum 3 completed similar contracts in last 3 years.",
                threshold_value=3,
                evaluation_field=CanonicalEvaluationField.SIMILAR_CONTRACT_COUNT,
            )
        ]

        # 1. Missing evidence -> UNVERIFIED
        ctx_missing = VerificationContext(
            requirements=reqs,
            bidders=[{"id": "b-1", "legal_name": "Newbie Tech"}],
        )
        findings_missing = await self.verifier.verify(ctx_missing)
        self.assertEqual(findings_missing[0].status, ComplianceState.UNVERIFIED)
        self.assertIn("PAST_PERFORMANCE_UNVERIFIED", findings_missing[0].machine_readable_flags)

        # 2. Deficit count (1 out of 3) -> FAIL
        ctx_fail = VerificationContext(
            requirements=reqs,
            bidders=[{"id": "b-2", "legal_name": "Junior Tech"}],
            observations=[
                EvidenceObservation(
                    evidence_id="e1",
                    bidder_id="b-2",
                    requirement_id="REQ-EXP-01",
                    observed_value="1 Contract completed 2025-01-10",
                    source_document="completion_cert_1.pdf",
                )
            ],
        )
        findings_fail = await self.verifier.verify(ctx_fail)
        self.assertEqual(findings_fail[0].status, ComplianceState.FAIL)
        self.assertIn("EXPERIENCE_DEFICIT", findings_fail[0].machine_readable_flags)

        # 3. Sufficient count (3 out of 3) -> PASS
        ctx_pass = VerificationContext(
            requirements=reqs,
            bidders=[{"id": "b-3", "legal_name": "Senior Tech"}],
            observations=[
                EvidenceObservation(evidence_id="e1", bidder_id="b-3", requirement_id="REQ-EXP-01", observed_value="Contract A 2024-05-01", source_document="ca_cert_1.pdf"),
                EvidenceObservation(evidence_id="e2", bidder_id="b-3", requirement_id="REQ-EXP-01", observed_value="Contract B 2024-08-01", source_document="ca_cert_2.pdf"),
                EvidenceObservation(evidence_id="e3", bidder_id="b-3", requirement_id="REQ-EXP-01", observed_value="Contract C 2025-02-01", source_document="ca_cert_3.pdf"),
            ],
        )
        findings_pass = await self.verifier.verify(ctx_pass)
        self.assertEqual(findings_pass[0].status, ComplianceState.PASS)
        self.assertIn("PAST_PERFORMANCE_MET", findings_pass[0].machine_readable_flags)

    async def test_06_monetary_ratio_and_recency_expiration(self):
        reqs = [
            make_contract(
                "REQ-EXP-VAL",
                RequirementCategory.EXPERIENCE,
                "Past single work order value must be >= INR 2 Crore completed within past 3 years.",
                threshold_value=20000000.0,
                threshold_unit="INR",
                evaluation_field=CanonicalEvaluationField.GENERAL_EXPERIENCE,
            )
        ]

        # 1. Compliant value (2.5 Cr >= 2.0 Cr) -> PASS
        ctx_val_pass = VerificationContext(
            requirements=reqs,
            bidders=[{"id": "b-val-pass", "legal_name": "Big Works Ltd"}],
            observations=[
                EvidenceObservation(
                    evidence_id="ev-1",
                    bidder_id="b-val-pass",
                    requirement_id="REQ-EXP-VAL",
                    observed_value="INR 2.50 Crore Work Order completed 2025-01-15",
                    source_document="client_cert.pdf",
                    source_quote="Client completion certificate for INR 2.50 Crore water quality analyzer installation dated 2025-01-15",
                )
            ],
        )
        findings_val = await self.verifier.verify(ctx_val_pass)
        self.assertEqual(findings_val[0].status, ComplianceState.PASS)
        self.assertIn("MONETARY_THRESHOLD_SATISFIED", findings_val[0].machine_readable_flags)

        # 2. Deficit value (1.2 Cr < 2.0 Cr) -> FAIL
        ctx_val_fail = VerificationContext(
            requirements=reqs,
            bidders=[{"id": "b-val-fail", "legal_name": "Small Works Ltd"}],
            observations=[
                EvidenceObservation(
                    evidence_id="ev-2",
                    bidder_id="b-val-fail",
                    requirement_id="REQ-EXP-VAL",
                    observed_value="INR 1.20 Crore",
                    source_document="client_cert.pdf",
                    source_quote="Completion value: INR 1.20 Crore",
                )
            ],
        )
        findings_fail = await self.verifier.verify(ctx_val_fail)
        self.assertEqual(findings_fail[0].status, ComplianceState.FAIL)
        self.assertIn("MONETARY_THRESHOLD_DEFICIT", findings_fail[0].machine_readable_flags)

    async def test_07_capacity_saturation_overcommitment_review(self):
        reqs = [
            make_contract(
                "REQ-CAP-01",
                RequirementCategory.TECHNICAL_SPECIFICATION,
                "Manufacturing and supply capacity requirement: 100 units per month.",
                threshold_value=100.0,
                threshold_unit="UNITS/MONTH",
                evaluation_field=CanonicalEvaluationField.DELIVERY_TIMELINE_DAYS,
            )
        ]

        # Capacity overcommitment flagged -> REVIEW
        ctx_overcommit = VerificationContext(
            requirements=reqs,
            bidders=[{"id": "b-cap", "legal_name": "Overbooked Sensors Corp"}],
            observations=[
                EvidenceObservation(
                    evidence_id="ev-cap",
                    bidder_id="b-cap",
                    requirement_id="REQ-CAP-01",
                    observed_value="Stated capacity: 200 units per month",
                    source_document="factory_audit.pdf",
                    source_quote="Total capacity 200 units per month. Existing committed backlog: 250 units per month. Active project commitments are heavily backlogged and overcommitted.",
                )
            ],
        )
        findings_cap = await self.verifier.verify(ctx_overcommit)
        self.assertEqual(findings_cap[0].status, ComplianceState.REVIEW)
        self.assertIn("CAPACITY_OVERCOMMITMENT_RISK", findings_cap[0].machine_readable_flags)

    async def test_08_statutory_msme_experience_exemption(self):
        reqs = [
            make_contract(
                "REQ-EXP-MSME",
                RequirementCategory.EXPERIENCE,
                "Prior experience of 3 years required. MSME relaxation applicable as per GeM GTC.",
                threshold_value=3,
                evaluation_field=CanonicalEvaluationField.GENERAL_EXPERIENCE,
            )
        ]

        ctx_msme = VerificationContext(
            requirements=reqs,
            bidders=[{"id": "b-msme", "legal_name": "Innovate Micro Sensors LLP"}],
            extra_context={"is_mse": True},
        )
        findings_msme = await self.verifier.verify(ctx_msme)
        self.assertEqual(findings_msme[0].status, ComplianceState.NOT_APPLICABLE)
        self.assertIn("STATUTORY_EXPERIENCE_EXEMPTION_APPLIED", findings_msme[0].machine_readable_flags)


if __name__ == "__main__":
    unittest.main()
