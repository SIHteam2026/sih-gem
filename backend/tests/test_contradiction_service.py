"""Unit tests for OPAL Cross-Document Contradiction and Evidence Reconciliation Service (SIH26100)."""

from datetime import date
import unittest

from backend.app.models.evaluation import ComplianceFinding, ComplianceState
from backend.app.models.evidence import (
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
from backend.app.models.tender import RequirementCategory, TenderRequirement
from backend.app.services.contradiction_service import (
    build_provenance_from_claim,
    build_provenance_from_evidence,
    compare_two_facts,
    detect_contradictions,
    reconcile_requirement,
)


class TestContradictionReconciliationService(unittest.TestCase):
    """Test suite for contradiction detection and evidence reconciliation."""

    # -----------------------------------------------------------------------
    # 1. Claim 27%, evidence 27% -> SUPPORTS / CONSISTENT
    # -----------------------------------------------------------------------
    def test_case_1_claim_matches_evidence_supports(self):
        claim = BidderClaim(
            claim_id="CLM-01",
            requirement_id="REQ-LC-01",
            claimed_value="27%",
            unit="PERCENT",
            source_document="annexure_iv_declaration.pdf",
            page_number=2,
            raw_statement="Local content percentage offered is 27%",
        )
        evidence = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-LC-01",
            observed_value="27%",
            unit="PERCENT",
            source_document="ca_certificate.pdf",
            page_number=1,
            source_quote="Certified local content is 27%",
            is_authoritative=True,
        )
        findings = detect_contradictions(claims=[claim], evidence=[evidence], requirement_id="REQ-LC-01")
        self.assertEqual(len(findings), 0)

        result = reconcile_requirement(
            requirement="REQ-LC-01",
            claims=[claim],
            evidence=[evidence],
        )
        self.assertEqual(result.overall_status, ComplianceState.PASS)
        self.assertEqual(result.contradiction_count, 0)
        self.assertIn(RelationshipClassification.SUPPORTS, result.relationships)
        self.assertFalse(result.review_required)

    # -----------------------------------------------------------------------
    # 2. Claim 27%, evidence 14% -> CONTRADICTS + overall REVIEW
    # -----------------------------------------------------------------------
    def test_case_2_claim_contradicts_evidence_review(self):
        claim = BidderClaim(
            claim_id="CLM-01",
            requirement_id="REQ-LC-01",
            claimed_value="27%",
            unit="PERCENT",
            source_document="annexure_iv_declaration.pdf",
            page_number=2,
            raw_statement="Local content percentage offered is 27%",
        )
        evidence = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-LC-01",
            observed_value="14%",
            unit="PERCENT",
            source_document="ca_certificate.pdf",
            page_number=1,
            source_quote="Calculated local content is 14%",
            is_authoritative=True,
        )
        findings = detect_contradictions(claims=[claim], evidence=[evidence], requirement_id="REQ-LC-01")
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.contradiction_type, ContradictionType.NUMERIC_CONFLICT)
        self.assertEqual(finding.relationship_status, RelationshipClassification.CONTRADICTS)
        self.assertIsNotNone(finding.side_by_side)
        self.assertEqual(finding.side_by_side.delta_value, 13.0)

        result = reconcile_requirement(
            requirement="REQ-LC-01",
            claims=[claim],
            evidence=[evidence],
        )
        self.assertEqual(result.overall_status, ComplianceState.REVIEW)
        self.assertEqual(result.contradiction_count, 1)
        self.assertTrue(result.review_required)
        self.assertIn(RelationshipClassification.CONTRADICTS, result.relationships)

    # -----------------------------------------------------------------------
    # 3. Only evidence 14%, requirement >= 20% -> observation CONSISTENT, threshold FAIL
    # -----------------------------------------------------------------------
    def test_case_3_only_evidence_below_threshold_fail(self):
        evidence = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-LC-01",
            observed_value="14%",
            unit="PERCENT",
            source_document="ca_certificate.pdf",
            page_number=1,
            source_quote="Verified local content is 14%",
        )
        result = reconcile_requirement(
            requirement="REQ-LC-01",
            claims=[],
            evidence=[evidence],
            threshold_condition={"operator": ">=", "value": 20.0},
        )
        self.assertEqual(result.overall_status, ComplianceState.FAIL)
        self.assertEqual(result.contradiction_count, 0)
        self.assertIn(RelationshipClassification.CONSISTENT, result.relationships)
        self.assertFalse(result.review_required)
        self.assertIn("falls short of mandatory threshold", result.reconciliation_summary)

    # -----------------------------------------------------------------------
    # 4. Claim 27%, no evidence -> UNSUPPORTED / UNVERIFIED
    # -----------------------------------------------------------------------
    def test_case_4_claim_without_evidence_unverified(self):
        claim = BidderClaim(
            claim_id="CLM-01",
            requirement_id="REQ-LC-01",
            claimed_value="27%",
            unit="PERCENT",
            source_document="bidder_cover_letter.pdf",
            page_number=1,
            raw_statement="We confirm 27% local content.",
        )
        result = reconcile_requirement(
            requirement="REQ-LC-01",
            claims=[claim],
            evidence=[],
        )
        self.assertEqual(result.overall_status, ComplianceState.UNVERIFIED)
        self.assertIn(RelationshipClassification.UNSUPPORTED, result.relationships)
        self.assertEqual(result.missing_evidence_count, 1)
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].contradiction_type, ContradictionType.CLAIM_UNSUPPORTED)

    # -----------------------------------------------------------------------
    # 5. Two evidence observations both 27% -> CONSISTENT
    # -----------------------------------------------------------------------
    def test_case_5_two_consistent_evidence_pass(self):
        ev1 = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-LC-01",
            observed_value="27%",
            unit="PERCENT",
            source_document="ca_certificate.pdf",
            page_number=1,
            source_quote="CA audit confirms 27% local content",
        )
        ev2 = EvidenceObservation(
            evidence_id="EVD-02",
            requirement_id="REQ-LC-01",
            observed_value="27%",
            unit="PERCENT",
            source_document="bom_breakdown.pdf",
            page_number=4,
            source_quote="Bill of Materials shows local value add 27.0%",
        )
        findings = detect_contradictions(evidence=[ev1, ev2], requirement_id="REQ-LC-01")
        self.assertEqual(len(findings), 0)

        result = reconcile_requirement(
            requirement="REQ-LC-01",
            evidence=[ev1, ev2],
        )
        self.assertEqual(result.overall_status, ComplianceState.PASS)
        self.assertEqual(result.contradiction_count, 0)
        self.assertEqual(result.supporting_evidence_count, 2)

    # -----------------------------------------------------------------------
    # 6. Two evidence observations 27% and 14% -> EVIDENCE_DISAGREEMENT / CONTRADICTS
    # -----------------------------------------------------------------------
    def test_case_6_two_conflicting_evidence_disagreement(self):
        ev1 = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-LC-01",
            observed_value="27%",
            unit="PERCENT",
            source_document="self_declaration.pdf",
            page_number=1,
            source_quote="Declared 27%",
        )
        ev2 = EvidenceObservation(
            evidence_id="EVD-02",
            requirement_id="REQ-LC-01",
            observed_value="14%",
            unit="PERCENT",
            source_document="ca_certificate.pdf",
            page_number=1,
            source_quote="CA audited local content is 14%",
        )
        findings = detect_contradictions(evidence=[ev1, ev2], requirement_id="REQ-LC-01")
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.contradiction_type, ContradictionType.EVIDENCE_DISAGREEMENT)
        self.assertEqual(finding.relationship_status, RelationshipClassification.CONTRADICTS)
        self.assertEqual(len(finding.evidence_references), 2)
        self.assertEqual(finding.evidence_references, ["EVD-01", "EVD-02"])

        result = reconcile_requirement(
            requirement="REQ-LC-01",
            evidence=[ev1, ev2],
        )
        self.assertEqual(result.overall_status, ComplianceState.REVIEW)
        self.assertTrue(result.review_required)
        self.assertEqual(result.conflicting_evidence_count, 1)

    # -----------------------------------------------------------------------
    # 7. 20% vs ₹20 lakh -> Incompatible comparison, not false contradiction
    # -----------------------------------------------------------------------
    def test_case_7_incompatible_units_not_false_numeric_contradiction(self):
        rec_left = ProvenanceRecord(
            document_name="doc_a.pdf",
            raw_value="20%",
            normalized_value=20.0,
            unit="PERCENT",
        )
        rec_right = ProvenanceRecord(
            document_name="doc_b.pdf",
            raw_value="₹20 lakh",
            normalized_value=2000000.0,
            unit="INR",
        )
        rel, c_type, explanation, delta = compare_two_facts(rec_left, rec_right, requirement_id="REQ-MIXED")
        self.assertEqual(rel, RelationshipClassification.INSUFFICIENT_DATA)
        self.assertEqual(c_type, ContradictionType.INCOMPATIBLE_UNITS)
        self.assertIn("Incompatible unit comparison", explanation)
        self.assertIsNone(delta)

    # -----------------------------------------------------------------------
    # 8. Different date fields (order vs completion) -> not a contradiction
    # -----------------------------------------------------------------------
    def test_case_8_different_lifecycle_milestone_dates_consistent(self):
        rec_wo = ProvenanceRecord(
            document_name="work_order_123.pdf",
            quote="Purchase Order Award Date: 15-08-2021",
            raw_value="15 August 2021",
            normalized_value="2021-08-15",
            source_type="SUPPORTING_DOCUMENT",
        )
        rec_comp = ProvenanceRecord(
            document_name="completion_certificate.pdf",
            quote="Project Work Completion Date: 20-03-2023",
            raw_value="20 March 2023",
            normalized_value="2023-03-20",
            source_type="SUPPORTING_DOCUMENT",
        )
        rel, c_type, explanation, delta = compare_two_facts(rec_wo, rec_comp, requirement_id="REQ-EXP")
        self.assertEqual(rel, RelationshipClassification.CONSISTENT)
        self.assertIsNone(c_type)
        self.assertIn("distinct project lifecycle milestones", explanation)

    # -----------------------------------------------------------------------
    # 9. Same-field date conflict -> DATE_CONFLICT
    # -----------------------------------------------------------------------
    def test_case_9_same_field_date_conflict(self):
        rec_d1 = ProvenanceRecord(
            document_name="certificate_v1.pdf",
            quote="ISO Certificate Valid Until: 31-12-2025",
            raw_value="31-12-2025",
            normalized_value="2025-12-31",
            source_type="OEM_DECLARATION",
        )
        rec_d2 = ProvenanceRecord(
            document_name="iso_portal_verification.pdf",
            quote="Accreditation registry expiry: 30-06-2025",
            raw_value="30-06-2025",
            normalized_value="2025-06-30",
            source_type="REGISTRY_VERIFICATION",
        )
        rel, c_type, explanation, delta = compare_two_facts(rec_d1, rec_d2, requirement_id="REQ-ISO")
        self.assertEqual(rel, RelationshipClassification.CONTRADICTS)
        self.assertEqual(c_type, ContradictionType.DATE_CONFLICT)
        self.assertEqual(delta, 184)  # 184 days difference
        self.assertIn("Date conflict", explanation)

    # -----------------------------------------------------------------------
    # 10. 3+ observations -> all preserved
    # -----------------------------------------------------------------------
    def test_case_10_multiple_observations_all_preserved(self):
        ev1 = EvidenceObservation(
            evidence_id="EVD-01",
            requirement_id="REQ-LC-01",
            observed_value="27%",
            source_document="doc1.pdf",
        )
        ev2 = EvidenceObservation(
            evidence_id="EVD-02",
            requirement_id="REQ-LC-01",
            observed_value="14%",
            source_document="doc2.pdf",
        )
        ev3 = EvidenceObservation(
            evidence_id="EVD-03",
            requirement_id="REQ-LC-01",
            observed_value="20%",
            source_document="doc3.pdf",
        )
        findings = detect_contradictions(evidence=[ev1, ev2, ev3], requirement_id="REQ-LC-01")
        # 3 pairwise comparisons: (1 vs 2) -> conflict, (1 vs 3) -> conflict, (2 vs 3) -> conflict
        self.assertEqual(len(findings), 3)
        for f in findings:
            self.assertEqual(len(f.provenance_items), 2)
            self.assertEqual(f.contradiction_type, ContradictionType.EVIDENCE_DISAGREEMENT)

    # -----------------------------------------------------------------------
    # 11. Entity-name variation handled via entity resolution -> no false identity conflict
    # -----------------------------------------------------------------------
    def test_case_11_entity_resolution_no_false_conflict(self):
        rec_claim = ProvenanceRecord(
            document_name="bidder_details.pdf",
            raw_value="Bharat Heavy Electricals Pvt. Ltd.",
            normalized_value="Bharat Heavy Electricals Pvt. Ltd.",
            source_type="BIDDER_DECLARATION",
        )
        rec_ev = ProvenanceRecord(
            document_name="gst_certificate.pdf",
            raw_value="BHARAT HEAVY ELECTRICALS PRIVATE LIMITED",
            normalized_value="BHARAT HEAVY ELECTRICALS PRIVATE LIMITED",
            source_type="AUTHORITATIVE_REGISTRY",
        )
        rel, c_type, explanation, delta = compare_two_facts(
            rec_claim, rec_ev, requirement_id="REQ-AUTH", semantic_field="ENTITY_NAME"
        )
        self.assertEqual(rel, RelationshipClassification.SUPPORTS)
        self.assertIsNone(c_type)
        self.assertIn("Corporate entities match", explanation)

    # -----------------------------------------------------------------------
    # 12. Provenance survives into findings (document_name, page_number, quote, raw_value, normalized_value)
    # -----------------------------------------------------------------------
    def test_case_12_provenance_integrity_in_findings(self):
        claim = BidderClaim(
            claim_id="CLM-LC-99",
            requirement_id="REQ-LC-01",
            claimed_value="27%",
            unit="PERCENT",
            source_document="tender_bid_submission.pdf",
            page_number=14,
            raw_statement="Clause 4.2 Local content percentage: 27%",
        )
        evidence = EvidenceObservation(
            evidence_id="EVD-LC-99",
            requirement_id="REQ-LC-01",
            observed_value="14%",
            unit="PERCENT",
            source_document="chartered_accountant_certificate.pdf",
            page_number=3,
            source_quote="We certify local value addition is 14.0% for FY 2025-26.",
            is_authoritative=True,
        )
        findings = detect_contradictions(claims=[claim], evidence=[evidence], requirement_id="REQ-LC-01")
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(len(f.provenance_items), 2)

        p_claim = f.provenance_items[0]
        self.assertEqual(p_claim.document_name, "tender_bid_submission.pdf")
        self.assertEqual(p_claim.page_number, 14)
        self.assertEqual(p_claim.quote, "Clause 4.2 Local content percentage: 27%")
        self.assertEqual(p_claim.raw_value, "27%")
        self.assertEqual(p_claim.normalized_value, 27.0)

        p_ev = f.provenance_items[1]
        self.assertEqual(p_ev.document_name, "chartered_accountant_certificate.pdf")
        self.assertEqual(p_ev.page_number, 3)
        self.assertIn("We certify local value addition is 14.0%", p_ev.quote)
        self.assertEqual(p_ev.raw_value, "14%")
        self.assertEqual(p_ev.normalized_value, 14.0)

    # -----------------------------------------------------------------------
    # 13. Robust handling of missing provenance
    # -----------------------------------------------------------------------
    def test_case_13_missing_provenance_graceful_handling(self):
        # Claim with minimal info
        claim_dict = {"claimed_value": "50%"}
        rec_claim = build_provenance_from_claim(claim_dict)
        self.assertEqual(rec_claim.normalized_value, 50.0)
        self.assertEqual(rec_claim.document_name, "Bidder Self-Declaration")

        # Evidence with None / empty fields
        ev_dict = {"observed_value": "45%"}
        rec_ev_list = build_provenance_from_evidence(ev_dict)
        self.assertEqual(len(rec_ev_list), 1)
        self.assertEqual(rec_ev_list[0].normalized_value, 45.0)

        findings = detect_contradictions(claims=claim_dict, evidence=ev_dict, requirement_id="REQ-LC")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].contradiction_type, ContradictionType.NUMERIC_CONFLICT)

    # -----------------------------------------------------------------------
    # 14. Compatibility with legacy ExtractedEvidence dicts
    # -----------------------------------------------------------------------
    def test_case_14_legacy_extracted_evidence_compatibility(self):
        legacy_ev = ExtractedEvidence(
            requirement_id="REQ-LC-01",
            is_present=True,
            extracted_values={"local_content_pct": "27%"},
            source_quote="Self declaration confirms 27% local content",
            extraction_confidence=0.95,
        )
        records = build_provenance_from_evidence(legacy_ev)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].normalized_value, 27.0)
        self.assertEqual(records[0].unit, "PERCENT")
        self.assertEqual(records[0].quote, "Self declaration confirms 27% local content")

        result = reconcile_requirement(
            requirement="REQ-LC-01",
            evidence=legacy_ev,
        )
        self.assertEqual(result.overall_status, ComplianceState.PASS)
        self.assertEqual(result.contradiction_count, 0)


if __name__ == "__main__":
    unittest.main()