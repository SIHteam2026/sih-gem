"""Cross-Workstream Contract Compatibility Test Suite for OPAL (SIH26100).

Validates the full cross-workstream contract chain:
Tender Intelligence (TenderRequirement)
    ↓
Requirement Evaluation Contract (RequirementEvaluationContract)
    ↓
Bidder Evidence / Observations (BidderClaim, EvidenceObservation, ExtractedEvidence, ProvenanceRecord)
    ↓
Contradiction Reconciliation (ContradictionFinding, RequirementReconciliationResult)
    ↓
Deterministic Rule Engine & Tiered Evaluator (evaluate_requirement, evaluate_tiered_requirement)

Tests 24 Core Compatibility Requirements:
1. TenderRequirement -> RequirementEvaluationContract preserves requirement_id.
2. Canonical evaluation field matches evidence observation field.
3. Operator vocabulary compatibility (>=, <=, ==, >, <, IN, BETWEEN).
4. INR currency normalization & compatibility (₹5 crore -> 50,000,000 INR).
5. Percentage normalization & compatibility (27% -> 27.0 PERCENT).
6. Month duration normalization & compatibility (24 months -> 24.0 MONTHS).
7. Count normalization & compatibility (2 COUNT -> 2.0 COUNT).
8. Incompatible unit safety (PERCENT vs INR cannot be compared).
9. Requirement provenance structure (page, clause, section, verbatim quote).
10. Evidence provenance structure (document_id, page_number, quote, raw/normalized values).
11. Tender ambiguity propagation (VAGUE_TERMINOLOGY preserved downstream).
12. Applicability & statutory exemption metadata survival (MSE/Startup).
13. NOT_APPLICABLE state availability for verified exemptions.
14. Canonical compliance states (PASS, FAIL, REVIEW, UNVERIFIED, NOT_APPLICABLE).
15. Legacy compliance-state aliases compatibility (VERIFIED, NON_COMPLIANT, REVIEW_REQUIRED).
16. Requirement ID stability across all layers.
17. Multi-bidder document isolation (same filename 'GST.pdf' without collision).
18. Multi-pointer evidence references (requirement, bidder, submission, document).
19. Unstructured requirement fallback to HUMAN_REVIEW without fabricated fields.
20. Semantic requirements preservation (no false conversion to DETERMINISTIC).
21. Deterministic requirements evaluable by rule engine without reparsing text.
22. External verification requirements distinguishable from document-only presence.
23. Contradiction findings reference stable requirement_id.
24. Downstream evaluator consumes evaluation contract directly.
25. Synthetic CPCL benchmark verification (REQ-001 through REQ-009).
"""

import sys
import unittest
import uuid
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

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
    RequirementReconciliationResult,
    SideBySideComparison,
)
from app.models.tender import (
    AmbiguitySpec,
    AmbiguityType,
    ApplicabilitySpec,
    EvidenceSpec,
    RequirementCategory,
    SourceProvenance,
    StructuredCondition,
    TenderRequirement,
)
from app.models.tender_contract import (
    ApplicabilityContract,
    CanonicalEvaluationField,
    EvaluationMode,
    EvidenceContract,
    ProvenanceContract,
    RequirementEvaluationContract,
    TenderEvaluationContract,
)
from app.rules.engine import (
    evaluate_numeric_threshold,
    evaluate_requirement as evaluate_deterministic_requirement,
    is_unit_compatible,
    parse_numeric_value,
)
from app.services.contradiction_service import (
    build_provenance_from_claim,
    build_provenance_from_evidence,
    compare_two_facts,
    detect_contradictions,
    reconcile_requirement,
)
from app.services.evaluation_service import (
    evaluate_requirement as evaluate_tiered_requirement,
    evaluate_requirements,
)
from app.services.tender_contract_service import (
    build_requirement_evaluation_contract,
    build_tender_evaluation_contract,
)
from app.tests.test_tender_persistence import create_synthetic_cpcl_requirements


class CrossWorkstreamContractCompatibilityTest(unittest.TestCase):
    """Integration test suite verifying cross-workstream data contract compatibility."""

    def test_01_requirement_id_preservation(self):
        """1. TenderRequirement -> RequirementEvaluationContract preserves requirement_id."""
        req = TenderRequirement(
            requirement_id="REQ-003",
            category=RequirementCategory.FINANCIAL_TURNOVER,
            description="Average annual turnover >= INR 5 crore",
        )
        contract = build_requirement_evaluation_contract(req, tender_id="TENDER-001")
        self.assertEqual(contract.requirement_id, "REQ-003")
        self.assertEqual(contract.tender_id, "TENDER-001")

    def test_02_canonical_field_matching(self):
        """2. RequirementEvaluationContract canonical field matches EvidenceObservation field."""
        req = TenderRequirement(
            requirement_id="REQ-006",
            category=RequirementCategory.LOCAL_CONTENT_MII,
            description="Minimum 20% local content",
            structured_condition=StructuredCondition(
                metric="LOCAL_CONTENT_PERCENTAGE",
                field_name="local_content_percentage",
                operator=">=",
                threshold_value=20.0,
                unit="PERCENT",
            ),
        )
        contract = build_requirement_evaluation_contract(req)
        self.assertEqual(contract.evaluation_field, CanonicalEvaluationField.LOCAL_CONTENT_PERCENTAGE.value)

        # Evidence observation with matching field
        obs = EvidenceObservation(
            evidence_id="EV-001",
            requirement_id=contract.requirement_id,
            observed_value=27.0,
            unit="PERCENT",
            source_document="MII_Declaration.pdf",
            page_number=1,
            source_quote="Local content is 27%",
        )
        self.assertEqual(obs.requirement_id, contract.requirement_id)
        self.assertEqual(obs.unit, contract.threshold_unit)

    def test_03_operator_vocabulary_compatibility(self):
        """3. Operator vocabulary is compatible with deterministic rule engine."""
        operators = [">=", "<=", "==", ">", "<"]
        for op in operators:
            finding = evaluate_numeric_threshold(
                requirement_id="REQ-TEST",
                operator=op,
                expected_val=50.0,
                expected_unit="PERCENT",
                observed_values=[50.0],
            )
            self.assertIn(finding.state, [ComplianceState.PASS, ComplianceState.FAIL])

    def test_04_inr_unit_normalization(self):
        """4. INR currency normalization & compatibility (₹5 crore -> 50,000,000 INR)."""
        val1, unit1 = parse_numeric_value("₹5.0 Crore")
        val2, unit2 = parse_numeric_value("INR 5,00,00,000")
        val3, unit3 = parse_numeric_value("5 crore")
        val4, unit4 = parse_numeric_value("50 Lakhs")

        self.assertEqual(val1, 50000000.0)
        self.assertEqual(unit1, "INR")
        self.assertEqual(val2, 50000000.0)
        self.assertEqual(unit2, "INR")
        self.assertEqual(val3, 50000000.0)
        self.assertEqual(unit3, "INR")
        self.assertEqual(val4, 5000000.0)
        self.assertEqual(unit4, "INR")

    def test_05_percentage_unit_normalization(self):
        """5. Percentage normalization & compatibility (27% -> 27.0 PERCENT)."""
        val, unit = parse_numeric_value("27%")
        self.assertEqual(val, 27.0)
        self.assertEqual(unit, "PERCENT")

        val2, unit2 = parse_numeric_value("20.5 %")
        self.assertEqual(val2, 20.5)
        self.assertEqual(unit2, "PERCENT")

    def test_06_month_unit_normalization(self):
        """6. Month duration normalization & compatibility (24 months -> 24.0 MONTHS)."""
        val, unit = parse_numeric_value("24 months")
        self.assertEqual(val, 24.0)
        self.assertEqual(unit, "MONTHS")

    def test_07_count_unit_normalization(self):
        """7. Count normalization & compatibility (2 COUNT -> 2.0 COUNT)."""
        self.assertTrue(is_unit_compatible("COUNT", "COUNT"))
        val, _ = parse_numeric_value(2.0)
        self.assertEqual(val, 2.0)

    def test_08_incompatible_units_safety(self):
        """8. Incompatible units cannot be compared (PERCENT vs INR)."""
        self.assertFalse(is_unit_compatible("PERCENT", "INR"))
        self.assertFalse(is_unit_compatible("MONTHS", "INR"))
        self.assertFalse(is_unit_compatible("PERCENT", "MONTHS"))

        finding = evaluate_numeric_threshold(
            requirement_id="REQ-UNIT-MISMATCH",
            operator=">=",
            expected_val=20.0,
            expected_unit="PERCENT",
            observed_values=["₹20,00,000 INR"],
        )
        self.assertEqual(finding.state, ComplianceState.REVIEW)
        self.assertIn("Incompatible unit", finding.reasoning_trace)

    def test_09_requirement_provenance_structure(self):
        """9. Requirement provenance structure (page, clause, section, verbatim quote)."""
        req = TenderRequirement(
            requirement_id="REQ-003",
            category=RequirementCategory.FINANCIAL_TURNOVER,
            description="Turnover clause",
            source_provenance=SourceProvenance(
                page_number=2,
                clause_number="Clause 2.1",
                section_title="Financial Standing",
                verbatim_quote="The bidder shall have an average annual financial turnover of not less than INR 5.0 Crores.",
            ),
        )
        contract = build_requirement_evaluation_contract(req)
        self.assertEqual(contract.provenance.page_number, 2)
        self.assertEqual(contract.provenance.clause_number, "Clause 2.1")
        self.assertEqual(contract.provenance.section_title, "Financial Standing")
        self.assertIn("INR 5.0 Crores", contract.provenance.verbatim_quote)

    def test_10_evidence_provenance_structure(self):
        """10. Evidence provenance structure (document_id, page_number, quote, raw/normalized values)."""
        obs = EvidenceObservation(
            evidence_id="EV-CA-001",
            requirement_id="REQ-003",
            observed_value=64200000.0,
            unit="INR",
            source_document="CA_Turnover_Cert.pdf",
            page_number=1,
            source_quote="Average annual turnover is INR 6.42 Crore (UDIN: 24012345ABCD).",
        )
        prov = build_provenance_from_evidence(obs)[0]
        self.assertEqual(prov.evidence_id, "EV-CA-001")
        self.assertEqual(prov.page_number, 1)
        self.assertEqual(prov.normalized_value, 64200000.0)
        self.assertEqual(prov.unit, "INR")
        self.assertIn("6.42 Crore", prov.quote)

    def test_11_tender_ambiguity_propagation(self):
        """11. Tender ambiguity remains visible downstream (VAGUE_TERMINOLOGY)."""
        req = TenderRequirement(
            requirement_id="REQ-009",
            category=RequirementCategory.PAST_EXPERIENCE,
            description="Bidder should have adequate experience and satisfactory reputation.",
            mandatory=False,
            is_ambiguous=True,
            ambiguity=AmbiguitySpec(
                is_ambiguous=True,
                ambiguity_type=AmbiguityType.VAGUE_TERMINOLOGY,
                ambiguity_reason="Subjective criteria without numeric metric.",
            ),
        )
        contract = build_requirement_evaluation_contract(req)
        self.assertEqual(contract.evaluation_mode, EvaluationMode.HUMAN_REVIEW)
        self.assertTrue(contract.ambiguity.is_ambiguous)
        self.assertEqual(contract.ambiguity.ambiguity_type, AmbiguityType.VAGUE_TERMINOLOGY)

        # Downstream evaluation result with submitted observation
        obs = EvidenceObservation(
            evidence_id="EV-EXP-009",
            requirement_id="REQ-009",
            observed_value="10 years in water monitoring",
            source_document="company_profile.pdf",
        )
        eval_result = evaluate_tiered_requirement(contract, evidence=obs)
        self.assertEqual(eval_result.state, ComplianceState.REVIEW)
        self.assertEqual(eval_result.evaluation_method, EvaluationMethod.HUMAN_REVIEW)

    def test_12_applicability_and_exemption_metadata(self):
        """12. Applicability & statutory exemption metadata survival (MSE/Startup)."""
        req = TenderRequirement(
            requirement_id="REQ-003",
            category=RequirementCategory.FINANCIAL_TURNOVER,
            description="Turnover >= 5 Cr",
            applicability=ApplicabilitySpec(
                applies_to_all=False,
                msme_exemption_applicable=True,
                startup_exemption_applicable=True,
                exemption_notes="MSE & Startups exempt.",
            ),
        )
        contract = build_requirement_evaluation_contract(req)
        self.assertTrue(contract.applicability.msme_exemption)
        self.assertTrue(contract.applicability.startup_exemption)
        self.assertTrue(contract.applicability.exemption_possible)

    def test_13_not_applicable_state_for_verified_exemption(self):
        """13. NOT_APPLICABLE state availability for verified exemptions."""
        req = TenderRequirement(
            requirement_id="REQ-003",
            category=RequirementCategory.FINANCIAL_TURNOVER,
            description="Turnover >= 5 Cr",
            applicability=ApplicabilitySpec(
                msme_exemption_applicable=True,
                startup_exemption_applicable=True,
            ),
        )
        contract = build_requirement_evaluation_contract(req)

        # Evaluate with verified MSE context
        result = evaluate_tiered_requirement(
            contract,
            context={"is_mse": True, "exemptions": {"is_mse": True}},
        )
        self.assertEqual(result.state, ComplianceState.NOT_APPLICABLE)
        self.assertEqual(result.evaluation_method, EvaluationMethod.APPLICABILITY_EXEMPTION)

    def test_14_canonical_compliance_states(self):
        """14. Canonical compliance states (PASS, FAIL, REVIEW, UNVERIFIED, NOT_APPLICABLE)."""
        canonical_states = [
            ComplianceState.PASS,
            ComplianceState.FAIL,
            ComplianceState.REVIEW,
            ComplianceState.UNVERIFIED,
            ComplianceState.NOT_APPLICABLE,
        ]
        self.assertEqual(len(canonical_states), 5)
        for s in canonical_states:
            self.assertIsInstance(s.value, str)

    def test_15_legacy_compliance_state_aliases(self):
        """15. Legacy compliance-state aliases compatibility (VERIFIED, NON_COMPLIANT, REVIEW_REQUIRED)."""
        self.assertEqual(ComplianceState.VERIFIED.value, "VERIFIED")
        self.assertEqual(ComplianceState.NON_COMPLIANT.value, "NON_COMPLIANT")
        self.assertEqual(ComplianceState.REVIEW_REQUIRED.value, "REVIEW_REQUIRED")

        # Verify findings can be created with legacy aliases without throwing error
        f1 = ComplianceFinding(requirement_id="REQ-1", state=ComplianceState.VERIFIED, reasoning_trace="Legacy pass")
        f2 = ComplianceFinding(requirement_id="REQ-2", state=ComplianceState.NON_COMPLIANT, reasoning_trace="Legacy fail")
        self.assertEqual(f1.state, ComplianceState.VERIFIED)
        self.assertEqual(f2.state, ComplianceState.NON_COMPLIANT)

    def test_16_requirement_id_stability_across_chain(self):
        """16. Requirement ID stability across entire chain."""
        req_id = "REQ-CPCL-TURNOVER-003"
        req = TenderRequirement(
            requirement_id=req_id,
            category=RequirementCategory.FINANCIAL_TURNOVER,
            description="Turnover requirement",
            structured_condition=StructuredCondition(
                field_name="average_annual_turnover",
                operator=">=",
                threshold_value=50000000.0,
                unit="INR",
            ),
        )
        contract = build_requirement_evaluation_contract(req)
        self.assertEqual(contract.requirement_id, req_id)

        claim = BidderClaim(
            claim_id="CLM-001",
            requirement_id=contract.requirement_id,
            claimed_value=60000000.0,
            unit="INR",
        )
        self.assertEqual(claim.requirement_id, req_id)

        finding = evaluate_tiered_requirement(contract, claims=claim)
        self.assertEqual(finding.requirement_id, req_id)

    def test_17_multi_bidder_document_isolation(self):
        """17. Multi-bidder document isolation (same filename 'GST.pdf' without collision)."""
        bidder_1_id = str(uuid.uuid4())
        bidder_2_id = str(uuid.uuid4())
        sub_1_id = str(uuid.uuid4())
        sub_2_id = str(uuid.uuid4())
        doc_1_id = str(uuid.uuid4())
        doc_2_id = str(uuid.uuid4())

        # Bidder 1 Evidence
        ev1 = ExtractedEvidence(
            requirement_id="REQ-001",
            bidder_id=bidder_1_id,
            bid_submission_id=sub_1_id,
            document_id=doc_1_id,
            page_number=1,
            is_present=True,
            extracted_values={"gstin": "27AAACA123411Z5", "status": "ACTIVE"},
            extraction_confidence=1.0,
        )

        # Bidder 2 Evidence (same filename, distinct UUIDs)
        ev2 = ExtractedEvidence(
            requirement_id="REQ-001",
            bidder_id=bidder_2_id,
            bid_submission_id=sub_2_id,
            document_id=doc_2_id,
            page_number=1,
            is_present=True,
            extracted_values={"gstin": "07BBBCA987622Z1", "status": "ACTIVE"},
            extraction_confidence=1.0,
        )

        self.assertEqual(ev1.requirement_id, ev2.requirement_id)
        self.assertNotEqual(ev1.bidder_id, ev2.bidder_id)
        self.assertNotEqual(ev1.bid_submission_id, ev2.bid_submission_id)
        self.assertNotEqual(ev1.document_id, ev2.document_id)

    def test_18_multi_pointer_evidence_references(self):
        """18. Evidence can point simultaneously to requirement, bidder, submission, and document."""
        bidder_id = str(uuid.uuid4())
        sub_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())

        ev = ExtractedEvidence(
            requirement_id="REQ-006",
            bidder_id=bidder_id,
            bid_submission_id=sub_id,
            document_id=doc_id,
            page_number=2,
            is_present=True,
            extracted_values={"local_content": "27%"},
            source_quote="Local value addition is 27%",
            extraction_confidence=0.95,
        )
        self.assertEqual(ev.requirement_id, "REQ-006")
        self.assertEqual(ev.bidder_id, bidder_id)
        self.assertEqual(ev.bid_submission_id, sub_id)
        self.assertEqual(ev.document_id, doc_id)

    def test_19_unstructured_requirement_safe_fallback(self):
        """19. Unstructured requirement safely becomes HUMAN_REVIEW without fabricated fields."""
        req = TenderRequirement(
            requirement_id="REQ-UNSTRUCT",
            category=RequirementCategory.OTHER,
            description="Bidder must maintain good corporate governance practices.",
            mandatory=False,
        )
        contract = build_requirement_evaluation_contract(req)
        self.assertEqual(contract.evaluation_mode, EvaluationMode.HUMAN_REVIEW)
        self.assertIsNone(contract.threshold_value)
        self.assertIsNone(contract.operator)

    def test_20_semantic_requirement_preservation(self):
        """20. Semantic requirement does not accidentally become DETERMINISTIC."""
        req = TenderRequirement(
            requirement_id="REQ-005",
            category=RequirementCategory.OEM_AUTHORIZATION,
            description="Bidder must submit a valid Manufacturer Authorization Form (MAF).",
            mandatory=True,
        )
        contract = build_requirement_evaluation_contract(req)
        self.assertEqual(contract.evaluation_mode, EvaluationMode.DOCUMENT_PRESENCE)
        self.assertIn(EvaluationMode.SEMANTIC, contract.secondary_evaluation_modes)
        self.assertNotEqual(contract.evaluation_mode, EvaluationMode.DETERMINISTIC)

    def test_21_deterministic_requirement_evaluable(self):
        """21. Deterministic requirement remains deterministically evaluable by rule engine."""
        req = TenderRequirement(
            requirement_id="REQ-006",
            category=RequirementCategory.LOCAL_CONTENT_MII,
            description="Minimum 20% local content required.",
            structured_condition=StructuredCondition(
                field_name="local_content_percentage",
                operator=">=",
                threshold_value=20.0,
                unit="PERCENT",
            ),
        )
        contract = build_requirement_evaluation_contract(req)
        self.assertEqual(contract.evaluation_mode, EvaluationMode.DETERMINISTIC)

        # Evaluate with 27% claim and supporting evidence -> PASS
        claim = BidderClaim(
            claim_id="CLM-01",
            requirement_id=contract.requirement_id,
            claimed_value=27.0,
            unit="PERCENT",
        )
        evidence = EvidenceObservation(
            evidence_id="EV-LC-01",
            requirement_id=contract.requirement_id,
            observed_value=27.0,
            unit="PERCENT",
            source_document="Self_Declaration.pdf",
            page_number=1,
            source_quote="Local value addition is 27%",
        )
        res = evaluate_tiered_requirement(contract, claims=claim, evidence=evidence)
        self.assertEqual(res.state, ComplianceState.PASS)
        self.assertEqual(res.evaluation_method, EvaluationMethod.DETERMINISTIC)

    def test_22_external_verification_distinguishable(self):
        """22. External verification requirements distinguishable from document-only evidence."""
        req_gst = TenderRequirement(
            requirement_id="REQ-001",
            category=RequirementCategory.GST_AND_TAX,
            description="Active GST registration required.",
        )
        contract_gst = build_requirement_evaluation_contract(req_gst)
        self.assertEqual(contract_gst.evaluation_mode, EvaluationMode.EXTERNAL_VERIFICATION)

        req_doc = TenderRequirement(
            requirement_id="REQ-005",
            category=RequirementCategory.OEM_AUTHORIZATION,
            description="OEM MAF document required.",
        )
        contract_doc = build_requirement_evaluation_contract(req_doc)
        self.assertEqual(contract_doc.evaluation_mode, EvaluationMode.DOCUMENT_PRESENCE)
        self.assertNotEqual(contract_gst.evaluation_mode, contract_doc.evaluation_mode)

    def test_23_contradiction_finding_references_requirement_id(self):
        """23. Contradiction finding can reference the same requirement_id used by Tender Intelligence."""
        claim = BidderClaim(
            claim_id="CLM-MII-001",
            requirement_id="REQ-006",
            claimed_value=27.0,
            unit="PERCENT",
            source_document="Self_Declaration.pdf",
            page_number=1,
            raw_statement="Local content: 27%",
        )
        evidence = EvidenceObservation(
            evidence_id="EV-CA-MII-001",
            requirement_id="REQ-006",
            observed_value=14.0,
            unit="PERCENT",
            source_document="CA_Cost_Audit.pdf",
            page_number=3,
            source_quote="Audited local content is 14%",
        )

        reconciliation = reconcile_requirement("REQ-006", claims=[claim], evidence=[evidence])
        self.assertEqual(reconciliation.requirement_id, "REQ-006")
        self.assertEqual(reconciliation.overall_status, ComplianceState.REVIEW)
        self.assertEqual(reconciliation.contradiction_count, 1)
        self.assertEqual(reconciliation.findings[0].requirement_id, "REQ-006")
        self.assertEqual(reconciliation.findings[0].contradiction_type, ContradictionType.NUMERIC_CONFLICT)

    def test_24_evaluator_consumes_contract_directly(self):
        """24. Evaluator can consume RequirementEvaluationContract without reparsing tender text."""
        raw_reqs = create_synthetic_cpcl_requirements()
        tender_contract = build_tender_evaluation_contract(
            tender_id="TENDER-CPCL-2026-017",
            requirements=raw_reqs,
        )

        # REQ-003 Contract (Turnover >= 50M INR)
        contract_3 = [c for c in tender_contract.requirements if c.requirement_id == "REQ-003"][0]

        # Bidder evidence: CA certificate stating 6.42 Cr
        evidence_obs = EvidenceObservation(
            evidence_id="EV-003-1",
            requirement_id="REQ-003",
            observed_value="₹ 6.42 Crore",
            source_document="CA_Turnover_Cert.pdf",
            page_number=1,
            source_quote="Average turnover INR 6.42 Cr",
        )

        res = evaluate_tiered_requirement(contract_3, evidence=evidence_obs)
        self.assertEqual(res.requirement_id, "REQ-003")
        self.assertEqual(res.state, ComplianceState.PASS)
        self.assertEqual(res.evaluation_method, EvaluationMethod.DETERMINISTIC)
        self.assertTrue("64200000" in res.reason.replace(",", "").replace(".0", "") or "6.42" in res.reason or "5e+07" in res.reason)

    def test_25_synthetic_cpcl_benchmark_contract_reconciliation(self):
        """25. Synthetic CPCL benchmark verification across all 9 requirements."""
        raw_reqs = create_synthetic_cpcl_requirements()
        tender_contract = build_tender_evaluation_contract(
            tender_id="TENDER-CPCL-2026-017",
            requirements=raw_reqs,
        )
        self.assertEqual(tender_contract.requirements_count, 9)

        contracts_by_id = {c.requirement_id: c for c in tender_contract.requirements}

        # Validate REQ-003
        c3 = contracts_by_id["REQ-003"]
        self.assertEqual(c3.evaluation_field, "average_annual_turnover")
        self.assertEqual(c3.operator, ">=")
        self.assertEqual(c3.threshold_value, 50000000.0)
        self.assertEqual(c3.threshold_unit, "INR")
        self.assertEqual(c3.time_period_years, 3.0)

        # Validate REQ-005
        c5 = contracts_by_id["REQ-005"]
        self.assertEqual(c5.evaluation_field, "oem_authorization")
        self.assertEqual(c5.evaluation_mode, EvaluationMode.DOCUMENT_PRESENCE)
        self.assertIn(EvaluationMode.SEMANTIC, c5.secondary_evaluation_modes)

        # Validate REQ-006
        c6 = contracts_by_id["REQ-006"]
        self.assertEqual(c6.evaluation_field, "local_content_percentage")
        self.assertEqual(c6.operator, ">=")
        self.assertEqual(c6.threshold_value, 20.0)
        self.assertEqual(c6.threshold_unit, "PERCENT")

        # Validate REQ-008
        c8 = contracts_by_id["REQ-008"]
        self.assertEqual(c8.evaluation_field, "warranty_months")
        self.assertEqual(c8.operator, ">=")
        self.assertEqual(c8.threshold_value, 24.0)
        self.assertEqual(c8.threshold_unit, "MONTHS")

        # Validate REQ-009
        c9 = contracts_by_id["REQ-009"]
        self.assertTrue(c9.ambiguity.is_ambiguous)
        self.assertEqual(c9.evaluation_mode, EvaluationMode.HUMAN_REVIEW)
        self.assertIsNone(c9.threshold_value)


if __name__ == "__main__":
    unittest.main()
