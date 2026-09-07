"""Comprehensive Unit & Integration Tests for Canonical Layered Verification Engine (SIH26100)."""

import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.models.evaluation import ComplianceState
from app.models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
from app.models.procurement import Document, DocumentType
from app.models.tender import RequirementCategory, TenderRequirement
from app.models.tender_contract import CanonicalEvaluationField, RequirementEvaluationContract
from app.models.verification import (
    FindingSeverity,
    IdentityVerificationStatus,
    VerificationContext,
    VerificationFinding,
    VerificationLayer,
)
from app.rules.layers import (
    AdministrativeIdentityVerifier,
    AdversarialTechnicalVerifier,
    AntiCollusionVerifier,
    BaseVerifier,
    CorporateRiskVerifier,
    DocumentIntegrityVerifier,
    FinancialCommercialVerifier,
    PastPerformanceCapacityVerifier,
)
from app.rules.verification_engine import CanonicalVerificationEngine, canonical_verification_engine
from app.services.master_pipeline import evaluate_canonical_submission
from app.services.tender_contract_service import build_requirement_evaluation_contract


def make_contract(req_id: str, category: RequirementCategory, description: str, **kwargs) -> RequirementEvaluationContract:
    return build_requirement_evaluation_contract(
        TenderRequirement(requirement_id=req_id, category=category, description=description, **kwargs),
        tender_id="DEMO/CPCL/WQM/2026/017",
    )


class TestLayeredVerificationEngine(unittest.IsolatedAsyncioTestCase):
    """Rigorous test suite for all 7 layers, standard contracts, and master orchestration."""

    # -----------------------------------------------------------------------
    # 1. Verifier Contract & Architecture Tests
    # -----------------------------------------------------------------------
    def test_01_canonical_layers_and_finding_contracts(self):
        """Validates that all 7 named layers exist and FindingSeverity is decoupled from ComplianceState."""
        expected_layers = [
            "INGESTION_AND_DOCUMENT_INTEGRITY",
            "ADMINISTRATIVE_AND_IDENTITY",
            "CORPORATE_EXISTENCE_AND_RISK",
            "ANTI_COLLUSION_AND_RELATEDNESS",
            "ADVERSARIAL_TECHNICAL",
            "PAST_PERFORMANCE_AND_CAPACITY",
            "FINANCIAL_AND_COMMERCIAL",
        ]
        actual_layers = [l.value for l in VerificationLayer if not l.name.startswith("LAYER_")]
        for exp in expected_layers:
            self.assertIn(exp, actual_layers)

        # Ensure finding supports all mandatory attributes
        finding = VerificationFinding(
            verifier="TEST_VERIFIER",
            verification_layer=VerificationLayer.ADMINISTRATIVE_AND_IDENTITY,
            requirement_id="REQ-001",
            bidder_id="BIDDER-1",
            status=ComplianceState.PASS,
            severity=FindingSeverity.INFO,
            claim={"gstin": "27AAACW1234F1Z5"},
            observation="ACTIVE",
            reason="GSTIN structural format valid.",
            confidence=1.0,
            machine_readable_flags=["VALID_GSTIN_FORMAT"],
        )
        self.assertEqual(finding.status, ComplianceState.PASS)
        self.assertEqual(finding.severity, FindingSeverity.INFO)
        self.assertEqual(finding.verifier, "TEST_VERIFIER")

    # -----------------------------------------------------------------------
    # 2. Layer 1: Ingestion & Document Integrity Tests
    # -----------------------------------------------------------------------
    async def test_02_layer1_document_integrity(self):
        verifier = DocumentIntegrityVerifier()
        docs = [
            Document(id="doc-1", procurement_id="p-1", filename="valid.pdf", file_size=1024, content_text="Valid readable tender text"),
            Document(id="doc-2", procurement_id="p-1", filename="empty.pdf", file_size=0, content_text=None),
            Document(id="doc-3", procurement_id="p-1", filename="scanned.pdf", file_size=5000, processing_status="OCR_FALLBACK", content_text="Scanned OCR text"),
            Document(id="doc-4", procurement_id="p-1", filename="tampered.pdf", file_size=3000, content_text="Warning: modified after signature in metadata"),
        ]
        context = VerificationContext(documents=docs)
        findings = await verifier.verify(context)

        # Check empty file -> FAIL
        empty_f = next(f for f in findings if f.document_id == "doc-2")
        self.assertEqual(empty_f.status, ComplianceState.FAIL)
        self.assertEqual(empty_f.severity, FindingSeverity.HIGH)
        self.assertIn("EMPTY_DOCUMENT_PAYLOAD", empty_f.machine_readable_flags)

        # Check OCR fallback -> REVIEW (low severity notice)
        ocr_f = next(f for f in findings if f.document_id == "doc-3")
        self.assertEqual(ocr_f.status, ComplianceState.REVIEW)
        self.assertIn("OCR_FALLBACK_APPLIED", ocr_f.machine_readable_flags)

        # Check tampering metadata -> REVIEW (high severity)
        tamper_f = next(f for f in findings if f.document_id == "doc-4")
        self.assertEqual(tamper_f.status, ComplianceState.REVIEW)
        self.assertEqual(tamper_f.severity, FindingSeverity.HIGH)
        self.assertIn("SUSPICIOUS_METADATA_TAMPERING", tamper_f.machine_readable_flags)

        # Check valid file -> PASS
        valid_f = next(f for f in findings if f.document_id == "doc-1")
        self.assertEqual(valid_f.status, ComplianceState.PASS)

    # -----------------------------------------------------------------------
    # 3. Layer 2: Administrative & Identity Tests
    # -----------------------------------------------------------------------
    async def test_03_layer2_administrative_and_identity(self):
        verifier = AdministrativeIdentityVerifier()
        bidders = [
            {"id": "b-valid", "legal_name": "Apex Tech Solutions", "pan": "ABCDE1234F", "gstin": "27ABCDE1234F1Z5"},
            {"id": "b-inv-pan", "legal_name": "Bad Pan Corp", "pan": "INVALID12", "gstin": "27ABCDE1234F1Z5"},
            {"id": "b-inv-gst", "legal_name": "Bad GST Corp", "pan": "ABCDE1234F", "gstin": "999INVALID123"},
            {"id": "b-pan-gst-mismatch", "legal_name": "Mismatch Corp", "pan": "AAAAA1111A", "gstin": "27BBBBB2222B1Z5"},
            {"id": "b-debarred", "legal_name": "Debarred Vendor", "pan": "FRAUD1234X", "gstin": "22AAAAA0000A1Z5"},
        ]
        context = VerificationContext(bidders=bidders)
        findings = await verifier.verify(context)

        # Debarred vendor check -> FAIL (CRITICAL)
        debarred_f = [f for f in findings if f.bidder_id == "b-debarred" and "DEBARRED_ENTITY" in f.machine_readable_flags]
        self.assertTrue(len(debarred_f) > 0)
        self.assertEqual(debarred_f[0].status, ComplianceState.FAIL)
        self.assertEqual(debarred_f[0].severity, FindingSeverity.CRITICAL)

        # Invalid PAN check -> FAIL
        inv_pan_f = next(f for f in findings if f.bidder_id == "b-inv-pan" and "INVALID_PAN_FORMAT" in f.machine_readable_flags)
        self.assertEqual(inv_pan_f.status, ComplianceState.FAIL)

        # PAN/GSTIN Mismatch check -> FAIL
        mismatch_f = next(f for f in findings if f.bidder_id == "b-pan-gst-mismatch" and "PAN_GSTIN_MISMATCH" in f.machine_readable_flags)
        self.assertEqual(mismatch_f.status, ComplianceState.FAIL)

    async def test_04_layer2_external_verification_statuses(self):
        """Verifies external verification mapping: EXTERNALLY_VERIFIED, SERVICE_UNAVAILABLE, UNVERIFIED."""
        verifier = AdministrativeIdentityVerifier()
        bidders = [
            {"id": "b-ext-act", "legal_name": "Vertex Infra Pvt Ltd", "pan": "AABCV1234K", "gstin": "27AABCV1234K1Z5"},
            {"id": "b-ext-unavail", "legal_name": "Gateway Offline Ltd", "pan": "AABCG5678M", "gstin": "33AABCG5678M1Z2"},
            {"id": "b-ext-name-mismatch", "legal_name": "Declared Name Alpha", "pan": "AABCD9999P", "gstin": "29AABCD9999P1Z8"},
        ]
        ext_verifs = {
            "b-ext-act": {"status": "ACTIVE", "legal_name": "Vertex Infra Pvt Ltd"},
            "b-ext-unavail": {"status": "SERVICE_UNAVAILABLE", "error": "GSTN API HTTP 504 Gateway Timeout"},
            "b-ext-name-mismatch": {"status": "ACTIVE", "legal_name": "Completely Different Legal Name Beta"},
        }
        context = VerificationContext(bidders=bidders, external_verifications=ext_verifs)
        findings = await verifier.verify(context)

        # Service unavailable must yield UNVERIFIED (never PASS and never FAIL)
        unavail_f = next(f for f in findings if f.bidder_id == "b-ext-unavail" and "EXTERNAL_SERVICE_UNAVAILABLE" in f.machine_readable_flags)
        self.assertEqual(unavail_f.status, ComplianceState.UNVERIFIED)
        self.assertNotEqual(unavail_f.status, ComplianceState.PASS)
        self.assertNotEqual(unavail_f.status, ComplianceState.FAIL)

        # Name mismatch must yield REVIEW
        mismatch_f = next(f for f in findings if f.bidder_id == "b-ext-name-mismatch" and "REGISTRY_NAME_MISMATCH" in f.machine_readable_flags)
        self.assertEqual(mismatch_f.status, ComplianceState.REVIEW)

        # Valid active external verification must yield PASS
        act_f = next(f for f in findings if f.bidder_id == "b-ext-act" and "EXTERNALLY_VERIFIED" in f.machine_readable_flags)
        self.assertEqual(act_f.status, ComplianceState.PASS)

    # -----------------------------------------------------------------------
    # 4. Layer 3: Corporate Existence & Risk Tests
    # -----------------------------------------------------------------------
    async def test_05_layer3_corporate_risk(self):
        verifier = CorporateRiskVerifier()
        bidders = [
            {
                "id": "b-new-entity",
                "legal_name": "Fly By Night Tech",
                "incorporation_date": "2026-01-01",
                "claimed_years_in_business": 10.0,
                "gstin": "27AAACW1234F1Z5",
            },
            {
                "id": "b-state-mismatch",
                "legal_name": "Delta Systems",
                "gstin": "27AAACW1234F1Z5",  # 27 = Maharashtra
                "address": "Plot 42, Electronics City, Bangalore, Karnataka 560100",  # Karnataka = 29
            },
        ]
        context = VerificationContext(bidders=bidders)
        findings = await verifier.verify(context)

        # Entity age discrepancy
        age_f = next(f for f in findings if f.bidder_id == "b-new-entity" and "ENTITY_AGE_DISCREPANCY" in f.machine_readable_flags)
        self.assertEqual(age_f.status, ComplianceState.REVIEW)
        self.assertEqual(age_f.severity, FindingSeverity.HIGH)

        # State address inconsistency
        state_f = next(f for f in findings if f.bidder_id == "b-state-mismatch" and "ADDRESS_STATE_INCONSISTENCY" in f.machine_readable_flags)
        self.assertEqual(state_f.status, ComplianceState.REVIEW)

    # -----------------------------------------------------------------------
    # 5. Layer 4: Anti-Collusion & Relatedness Tests
    # -----------------------------------------------------------------------
    async def test_06_layer4_collusion_signals(self):
        verifier = AntiCollusionVerifier()
        bidders = [
            {
                "id": "BIDDER-A",
                "legal_name": "Alpha Solutions Pvt Ltd",
                "phone": "+91 9876543210",
                "email": "contact@tenders-bid.in",
                "address": "Suite 301, Nariman Point, Mumbai 400021",
                "bank_account": "000105001234",
            },
            {
                "id": "BIDDER-B",
                "legal_name": "Beta Enterprises LLP",
                "phone": "+91 9876543210",  # Shared phone
                "email": "contact@tenders-bid.in",  # Shared email
                "address": "Suite 301, Nariman Point, Mumbai 400021",  # Shared address
                "bank_account": "000105001234",  # Shared bank account!
            },
            {
                "id": "BIDDER-C",
                "legal_name": "Independent Gamma Corp",
                "phone": "+91 8888899999",
                "email": "gamma@gammacorp.com",
                "address": "Sector 62, Noida, UP 201301",
                "bank_account": "999911112222",
            }
        ]
        submissions = [
            {"id": "sub-a", "bidder_id": "BIDDER-A"},
            {"id": "sub-b", "bidder_id": "BIDDER-B"},
            {"id": "sub-c", "bidder_id": "BIDDER-C"},
        ]
        docs = [
            Document(id="doc-a", procurement_id="proc-1", bid_submission_id="sub-a", filename="tech_a.pdf", content_text="Author: J.Doe_Machine_Corp\nTechnical bid submission."),
            Document(id="doc-b", procurement_id="proc-1", bid_submission_id="sub-b", filename="tech_b.pdf", content_text="Author: J.Doe_Machine_Corp\nTechnical bid submission."),
        ]
        context = VerificationContext(bidders=bidders, submissions=submissions, documents=docs)
        findings = await verifier.verify(context)

        # Multi-signal collusion finding between BIDDER-A and BIDDER-B
        collusion_f = next(f for f in findings if "COLLUSION_RISK_FLAG" in f.machine_readable_flags)
        self.assertEqual(collusion_f.status, ComplianceState.REVIEW)
        self.assertEqual(collusion_f.severity, FindingSeverity.CRITICAL)
        self.assertIn("SHARED_BANK_ACCOUNT", collusion_f.machine_readable_flags)
        self.assertIn("SHARED_PHONE_NUMBER", collusion_f.machine_readable_flags)
        self.assertIn("SHARED_PHYSICAL_ADDRESS", collusion_f.machine_readable_flags)
        self.assertIn("SHARED_DOCUMENT_AUTHOR", collusion_f.machine_readable_flags)
        self.assertIn("Alpha Solutions Pvt Ltd", collusion_f.reason)
        self.assertIn("Beta Enterprises LLP", collusion_f.reason)

    # -----------------------------------------------------------------------
    # 6. Layer 5: Adversarial Technical Analysis Tests
    # -----------------------------------------------------------------------
    async def test_07_layer5_adversarial_technical(self):
        verifier = AdversarialTechnicalVerifier()
        reqs = [
            make_contract("REQ-TECH-01", RequirementCategory.TECHNICAL_SPECIFICATION, "Continuous Water Quality Analyzer 24x7 operation."),
            make_contract("REQ-WAR-01", RequirementCategory.COMMERCIAL, "24 Months Comprehensive Warranty.", evaluation_field=CanonicalEvaluationField.WARRANTY_MONTHS),
            make_contract("REQ-LC-01", RequirementCategory.LOCAL_CONTENT_MII, "Minimum 50% Local Content.", evaluation_field=CanonicalEvaluationField.LOCAL_CONTENT_PERCENTAGE),
        ]
        claims = [
            BidderClaim(
                claim_id="clm-1",
                requirement_id="REQ-TECH-01",
                claimed_value="We agree with the exception of continuous night sensor operations",
                raw_statement="We agree with the exception of continuous night sensor operations",
                source_document="bidder_tech_specs.pdf",
            ),
            BidderClaim(
                claim_id="clm-2",
                requirement_id="REQ-WAR-01",
                claimed_value="36 Months",
                raw_statement="We provide 36 Months Warranty",
                source_document="declaration.pdf",
            ),
            BidderClaim(
                claim_id="clm-3",
                requirement_id="REQ-LC-01",
                claimed_value="27%",
                raw_statement="We declare 27% local content",
                source_document="declaration.pdf",
            ),
        ]
        observations = [
            EvidenceObservation(
                evidence_id="ev-2",
                requirement_id="REQ-WAR-01",
                observed_value="12 Months",
                source_document="oem_warranty_cert.pdf",
                source_quote="OEM standard warranty coverage is strictly 12 Months.",
            ),
            EvidenceObservation(
                evidence_id="ev-3",
                requirement_id="REQ-LC-01",
                observed_value="14%",
                source_document="ca_audit_breakdown.pdf",
                source_quote="Audited local value addition achieved: 14%.",
            ),
        ]
        context = VerificationContext(requirements=reqs, claims=claims, observations=observations)
        findings = await verifier.verify(context)

        # 1. Hidden exception detected
        exc_f = next(f for f in findings if "HIDDEN_EXCEPTION_DETECTED" in f.machine_readable_flags)
        self.assertEqual(exc_f.status, ComplianceState.REVIEW)
        self.assertEqual(exc_f.severity, FindingSeverity.HIGH)

        # 2. Warranty contradiction (claimed 36 mos vs OEM 12 mos)
        war_f = next(f for f in findings if "WARRANTY_TERMS_CONTRADICTION" in f.machine_readable_flags)
        self.assertEqual(war_f.status, ComplianceState.REVIEW)
        self.assertEqual(war_f.severity, FindingSeverity.HIGH)

        # 3. Local content discrepancy (claimed 27% vs audited 14%)
        lc_f = next(f for f in findings if "LOCAL_CONTENT_CONTRADICTION" in f.machine_readable_flags)
        self.assertEqual(lc_f.status, ComplianceState.REVIEW)

    # -----------------------------------------------------------------------
    # 7. Layer 6: Past Performance & Capacity Tests
    # -----------------------------------------------------------------------
    async def test_08_layer6_past_performance_and_capacity(self):
        verifier = PastPerformanceCapacityVerifier()
        reqs = [
            make_contract("REQ-EXP-01", RequirementCategory.EXPERIENCE, "Minimum 3 Completed Similar Works.", threshold_value=3, evaluation_field=CanonicalEvaluationField.SIMILAR_CONTRACT_COUNT)
        ]
        # Bidder 1: Missing evidence
        context_missing = VerificationContext(
            requirements=reqs,
            bidders=[{"id": "b-missing", "legal_name": "No Experience Ltd"}],
            claims=[],
            observations=[],
        )
        findings_missing = await verifier.verify(context_missing)
        self.assertEqual(findings_missing[0].status, ComplianceState.UNVERIFIED)
        self.assertIn("PAST_PERFORMANCE_UNVERIFIED", findings_missing[0].machine_readable_flags)

        # Bidder 2: 3 qualifying contracts -> PASS
        context_pass = VerificationContext(
            requirements=reqs,
            bidders=[{"id": "b-pass", "legal_name": "Experienced Ltd"}],
            observations=[
                EvidenceObservation(evidence_id="e1", bidder_id="b-pass", requirement_id="REQ-EXP-01", observed_value="Contract 1", source_document="wo1.pdf"),
                EvidenceObservation(evidence_id="e2", bidder_id="b-pass", requirement_id="REQ-EXP-01", observed_value="Contract 2", source_document="wo2.pdf"),
                EvidenceObservation(evidence_id="e3", bidder_id="b-pass", requirement_id="REQ-EXP-01", observed_value="Contract 3", source_document="wo3.pdf"),
            ],
        )
        findings_pass = await verifier.verify(context_pass)
        pass_f = next(f for f in findings_pass if f.bidder_id == "b-pass")
        self.assertEqual(pass_f.status, ComplianceState.PASS)
        self.assertIn("PAST_PERFORMANCE_MET", pass_f.machine_readable_flags)

    # -----------------------------------------------------------------------
    # 8. Layer 7: Financial & Commercial Tests
    # -----------------------------------------------------------------------
    async def test_09_layer7_financial_and_commercial(self):
        verifier = FinancialCommercialVerifier()
        reqs = [
            make_contract("REQ-TO-01", RequirementCategory.FINANCIAL_TURNOVER, "Average annual turnover INR 5 Crore.", threshold_value=50000000.0, evaluation_field=CanonicalEvaluationField.AVERAGE_ANNUAL_TURNOVER)
        ]

        # Scenario A: MSE Exemption -> NOT_APPLICABLE
        context_mse = VerificationContext(
            requirements=reqs,
            bidders=[{"id": "b-mse", "legal_name": "Micro Enterprise Alpha"}],
            extra_context={"is_mse": True},
        )
        findings_mse = await verifier.verify(context_mse)
        self.assertEqual(findings_mse[0].status, ComplianceState.NOT_APPLICABLE)
        self.assertIn("STATUTORY_TURNOVER_EXEMPTION_APPLIED", findings_mse[0].machine_readable_flags)

        # Scenario B: Compliant turnover (6.42 Crore >= 5 Crore) -> PASS
        context_pass = VerificationContext(
            requirements=reqs,
            bidders=[{"id": "b-fin-pass", "legal_name": "Turnover High Corp"}],
            observations=[
                EvidenceObservation(
                    evidence_id="e-to",
                    bidder_id="b-fin-pass",
                    requirement_id="REQ-TO-01",
                    observed_value="6.42 Crore",
                    source_document="ca_cert.pdf",
                    source_quote="Average turnover for last 3 years: INR 6.42 Crore. UDIN: 23123456ABCDEF1234",
                )
            ],
        )
        findings_to = await verifier.verify(context_pass)
        to_f = next(f for f in findings_to if "TURNOVER_THRESHOLD_MET" in f.machine_readable_flags)
        self.assertEqual(to_f.status, ComplianceState.PASS)

        # Scenario C: Deficit turnover (2.5 Crore < 5 Crore) -> FAIL
        context_fail = VerificationContext(
            requirements=reqs,
            bidders=[{"id": "b-fin-fail", "legal_name": "Turnover Low Corp"}],
            observations=[
                EvidenceObservation(
                    evidence_id="e-to-low",
                    bidder_id="b-fin-fail",
                    requirement_id="REQ-TO-01",
                    observed_value="2.5 Crore",
                    source_document="ca_cert_low.pdf",
                    source_quote="Average turnover: INR 2.50 Crore. UDIN: 23123456ABCDEF1234",
                )
            ],
        )
        findings_fail = await verifier.verify(context_fail)
        to_fail_f = next(f for f in findings_fail if "TURNOVER_DEFICIT" in f.machine_readable_flags)
        self.assertEqual(to_fail_f.status, ComplianceState.FAIL)
        self.assertEqual(to_fail_f.severity, FindingSeverity.HIGH)

    # -----------------------------------------------------------------------
    # 9. Full Canonical Orchestration & Failure Isolation Tests
    # -----------------------------------------------------------------------
    async def test_10_canonical_engine_orchestration_and_fault_isolation(self):
        """Validates that all 7 layers execute sequentially and a buggy verifier is isolated without killing the case."""
        class BuggyVerifier(BaseVerifier):
            @property
            def verifier_id(self) -> str:
                return "BUGGY_CRASHING_VERIFIER"

            @property
            def layer(self) -> VerificationLayer:
                return VerificationLayer.ADVERSARIAL_TECHNICAL

            async def verify(self, context: VerificationContext) -> list:
                raise RuntimeError("Simulated unhandled hardware/driver crash in verifier")

        engine = CanonicalVerificationEngine()
        engine.register_verifier(BuggyVerifier())

        reqs = [
            make_contract("REQ-001", RequirementCategory.LOCAL_CONTENT_MII, "Minimum 50% Local Content.", evaluation_field=CanonicalEvaluationField.LOCAL_CONTENT_PERCENTAGE)
        ]
        context = VerificationContext(
            procurement_id="proc-test",
            tender_id="tender-test",
            requirements=reqs,
            bidders=[{"id": "b1", "legal_name": "Test Bidder", "pan": "ABCDE1234F", "gstin": "27ABCDE1234F1Z5"}],
        )

        report = await engine.run_verification(context)
        
        # Pipeline must NOT crash and must record the system error finding
        self.assertGreater(report.total_findings, 0)
        self.assertEqual(len(report.system_errors), 1)
        self.assertIn("VERIFIER_EXECUTION_ERROR", report.system_errors[0].machine_readable_flags)
        self.assertEqual(report.system_errors[0].status, ComplianceState.UNVERIFIED)

    # -----------------------------------------------------------------------
    # 10. Multi-Bidder Master Pipeline Integration Test
    # -----------------------------------------------------------------------
    def test_11_master_pipeline_canonical_submission_evaluation(self):
        """End-to-end multi-bidder CPCL scenario through evaluate_canonical_submission."""
        requirements = [
            make_contract("REQ-003", RequirementCategory.FINANCIAL_TURNOVER, "Minimum turnover INR 5 Crore.", threshold_value=50000000.0, evaluation_field=CanonicalEvaluationField.AVERAGE_ANNUAL_TURNOVER),
            make_contract("REQ-006", RequirementCategory.LOCAL_CONTENT_MII, "Minimum 50% Local Content.", threshold_value=50.0, evaluation_field=CanonicalEvaluationField.LOCAL_CONTENT_PERCENTAGE),
            make_contract("REQ-008", RequirementCategory.COMMERCIAL, "24 Months Warranty.", threshold_value=24.0, evaluation_field=CanonicalEvaluationField.WARRANTY_MONTHS),
        ]

        # Bidder 1: Local content contradiction (claims 27%, CA certificate shows 14%)
        res1 = evaluate_canonical_submission(
            tender_id="DEMO/CPCL/WQM/2026/017",
            bidder_id="BIDDER-1",
            submission_id="SUB-1",
            requirement_contracts=requirements,
            claims=[
                BidderClaim(claim_id="c1", requirement_id="REQ-006", claimed_value="27%", source_document="declaration.pdf", page_number=2),
                BidderClaim(claim_id="c2", requirement_id="REQ-008", claimed_value="24 Months", source_document="declaration.pdf", page_number=3),
            ],
            observations=[
                EvidenceObservation(evidence_id="e1", requirement_id="REQ-003", observed_value="6.42 Crore", source_document="ca_turnover.pdf", page_number=1),
                EvidenceObservation(evidence_id="e2", requirement_id="REQ-006", observed_value="14%", source_document="ca_local_content.pdf", page_number=4),
                EvidenceObservation(evidence_id="e3", requirement_id="REQ-008", observed_value="24 Months", source_document="oem_warranty.pdf", page_number=2),
            ],
            context={
                "bidder_profile": {"id": "BIDDER-1", "legal_name": "Apex Instruments Ltd", "pan": "ABCDE1234F", "gstin": "27ABCDE1234F1Z5"}
            }
        )

        # Verify states
        req_states = {r.requirement_id: r.state for r in res1["requirement_results"]}
        self.assertEqual(req_states["REQ-003"], ComplianceState.PASS)
        self.assertEqual(req_states["REQ-006"], ComplianceState.REVIEW)
        self.assertEqual(req_states["REQ-008"], ComplianceState.PASS)
        self.assertTrue(res1["review_required"])
        self.assertIn("verification_engine_report", res1)
        self.assertFalse("bidder_qualified" in res1)  # Never autonomous decision!


if __name__ == "__main__":
    unittest.main()
