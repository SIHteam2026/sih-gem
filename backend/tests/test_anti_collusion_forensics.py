"""Deterministic Unit & Integration Tests for Level 4: Anti-Collusion Forensic Engine.

Validates all 4 forensic checks:
1. Digital Metadata Collisions (machine/user, timestamps, benign software)
2. Bidder-to-Bidder Tie-Ins (signatory, phone, address, email, CIN)
3. Financial Instrument Overlap (sequential BGs, same branch, missing evidence)
4. Formatting Clones (tender exclusion, boilerplate exclusion, narrative clones, typos)
Plus multi-signal reinforcement, pairwise comparison, cluster detection,
provenance preservation, and human decision boundary.
"""

from datetime import datetime, timezone
import json
import unittest

from app.models.evaluation import ComplianceState
from app.models.procurement import Document
from app.models.tender_contract import RequirementEvaluationContract
from app.models.verification import (
    FindingSeverity,
    VerificationContext,
    VerificationFinding,
    VerificationLayer,
)
from app.rules.layers.anti_collusion import AntiCollusionVerifier
from app.rules.forensics import (
    BidderTieInChecker,
    DigitalMetadataCollisionChecker,
    FinancialInstrumentOverlapChecker,
    FormattingCloneChecker,
    TenderTemplateExclusionIndex,
    normalize_address,
    normalize_email,
    normalize_phone,
    normalize_signatory,
)


class TestAntiCollusionForensics(unittest.IsolatedAsyncioTestCase):
    """Rigorous test suite for Level 4 Anti-Collusion and Relatedness."""

    def setUp(self):
        self.verifier = AntiCollusionVerifier()

    # -----------------------------------------------------------------------
    # 1. Digital Metadata Collisions
    # -----------------------------------------------------------------------
    async def test_01_metadata_collision_shared_machine_user(self):
        """Competing bidders submitting files authored by identical machine/user profile."""
        doc_a = Document(
            id="doc-a1",
            procurement_id="proc-1",
            filename="technical_bid_a.pdf",
            bid_submission_id="sub-a",
            content_text=json.dumps({
                "metadata": {
                    "author": "DESKTOP-77X9\\eng_admin",
                    "creator": "Custom App Builder",
                },
                "raw_text": "Technical proposal content for Bidder A",
            }),
        )
        doc_b = Document(
            id="doc-b1",
            procurement_id="proc-1",
            filename="technical_bid_b.pdf",
            bid_submission_id="sub-b",
            content_text=json.dumps({
                "metadata": {
                    "author": "DESKTOP-77X9\\eng_admin",
                    "creator": "Custom App Builder",
                },
                "raw_text": "Technical proposal content for Bidder B",
            }),
        )

        context = VerificationContext(
            procurement_id="proc-1",
            bidders=[
                {"id": "bidder-a", "legal_name": "Alpha Corp"},
                {"id": "bidder-b", "legal_name": "Beta Enterprises"},
            ],
            submissions=[
                {"id": "sub-a", "bidder_id": "bidder-a"},
                {"id": "sub-b", "bidder_id": "bidder-b"},
            ],
            documents=[doc_a, doc_b],
        )

        findings = await self.verifier.verify(context)
        review_findings = [f for f in findings if f.status == ComplianceState.REVIEW]
        self.assertGreaterEqual(len(review_findings), 1)

        f = review_findings[0]
        self.assertEqual(f.status, ComplianceState.REVIEW)
        self.assertEqual(f.severity, FindingSeverity.HIGH)
        self.assertIn("SHARED_MACHINE_USER", f.machine_readable_flags)
        self.assertIn("DESKTOP-77X9\\eng_admin", f.reason)
        self.assertTrue(len(f.evidence) > 0)

    async def test_02_benign_common_metadata_filtered(self):
        """Ubiquitous software (Adobe Acrobat, ReportLab, Word) must NOT trigger collusion findings."""
        doc_a = Document(
            id="doc-a2",
            procurement_id="proc-1",
            filename="bid_a.pdf",
            bid_submission_id="sub-a",
            content_text=json.dumps({
                "metadata": {
                    "author": "Microsoft Word",
                    "producer": "ReportLab PDF Library - www.reportlab.com",
                    "creator": "Adobe Acrobat Pro",
                }
            }),
        )
        doc_b = Document(
            id="doc-b2",
            procurement_id="proc-1",
            filename="bid_b.pdf",
            bid_submission_id="sub-b",
            content_text=json.dumps({
                "metadata": {
                    "author": "Microsoft Word",
                    "producer": "ReportLab PDF Library - www.reportlab.com",
                    "creator": "Adobe Acrobat Pro",
                }
            }),
        )

        context = VerificationContext(
            procurement_id="proc-1",
            bidders=[
                {"id": "bidder-a", "legal_name": "Vendor A"},
                {"id": "bidder-b", "legal_name": "Vendor B"},
            ],
            submissions=[
                {"id": "sub-a", "bidder_id": "bidder-a"},
                {"id": "sub-b", "bidder_id": "bidder-b"},
            ],
            documents=[doc_a, doc_b],
        )

        findings = await self.verifier.verify(context)
        # Should not have any REVIEW findings from benign metadata
        review_findings = [f for f in findings if f.status == ComplianceState.REVIEW]
        self.assertEqual(len(review_findings), 0)

    async def test_03_metadata_close_timestamp_proximity_is_review_not_fail(self):
        """Creation timestamps within close window must yield REVIEW, never FAIL."""
        doc_a = Document(
            id="doc-a3",
            procurement_id="proc-1",
            filename="specs_a.pdf",
            bid_submission_id="sub-a",
            content_text=json.dumps({
                "metadata": {
                    "creationDate": "D:20260908103000",
                }
            }),
        )
        doc_b = Document(
            id="doc-b3",
            procurement_id="proc-1",
            filename="specs_b.pdf",
            bid_submission_id="sub-b",
            content_text=json.dumps({
                "metadata": {
                    "creationDate": "D:20260908103115",  # 75 seconds apart
                }
            }),
        )

        context = VerificationContext(
            procurement_id="proc-1",
            bidders=[
                {"id": "bidder-a", "legal_name": "Vendor A"},
                {"id": "bidder-b", "legal_name": "Vendor B"},
            ],
            submissions=[
                {"id": "sub-a", "bidder_id": "bidder-a"},
                {"id": "sub-b", "bidder_id": "bidder-b"},
            ],
            documents=[doc_a, doc_b],
        )

        findings = await self.verifier.verify(context)
        proximity_findings = [f for f in findings if "SUSPICIOUS_TIMESTAMP_PROXIMITY" in f.machine_readable_flags]
        self.assertEqual(len(proximity_findings), 1)
        self.assertEqual(proximity_findings[0].status, ComplianceState.REVIEW)
        self.assertNotEqual(proximity_findings[0].status, ComplianceState.FAIL)

    # -----------------------------------------------------------------------
    # 2. Bidder-to-Bidder Tie-Ins
    # -----------------------------------------------------------------------
    async def test_04_signatory_collision(self):
        """Shared authorized signatory across competing bidders yields strong REVIEW."""
        context = VerificationContext(
            procurement_id="proc-1",
            bidders=[
                {"id": "b1", "legal_name": "Zenith Ltd", "authorized_signatory": "Mr. Rajesh V. Sharma (Director)"},
                {"id": "b2", "legal_name": "Apex Instruments", "authorized_signatory": "Rajesh V Sharma"},
            ],
            submissions=[
                {"id": "s1", "bidder_id": "b1"},
                {"id": "s2", "bidder_id": "b2"},
            ],
        )

        findings = await self.verifier.verify(context)
        sig_findings = [f for f in findings if "SHARED_SIGNATORY" in f.machine_readable_flags]
        self.assertEqual(len(sig_findings), 1)
        self.assertEqual(sig_findings[0].status, ComplianceState.REVIEW)
        self.assertEqual(sig_findings[0].severity, FindingSeverity.HIGH)
        self.assertIn("Rajesh V Sharma", sig_findings[0].reason)

    def test_05_phone_normalization_and_collision(self):
        """Phone normalization strips country codes and leading 0 to match 10-digit numbers."""
        p1 = normalize_phone("+91 98401 23456")
        p2 = normalize_phone("09840123456")
        p3 = normalize_phone("98401-23456")
        self.assertEqual(p1, "9840123456")
        self.assertEqual(p2, "9840123456")
        self.assertEqual(p3, "9840123456")

    def test_06_address_normalization_and_matching(self):
        """Normalizes common abbreviations (st, rd, indl, flr) and extracts PIN code."""
        addr1, pin1 = normalize_address("Plot No. 12, Indl. Area, 2nd Flr, Opp. Metro Station, Mumbai 400051")
        addr2, pin2 = normalize_address("Plot 12, Industrial Area, 2nd Floor, Opposite Metro Station, Mumbai 400051")
        self.assertEqual(pin1, "400051")
        self.assertEqual(pin2, "400051")
        self.assertIn("industrial area", addr1)
        self.assertIn("industrial area", addr2)

    def test_07_email_and_corporate_domain_handling(self):
        """Differentiates public mail providers from corporate domain tie-ins."""
        e1, d1, pub1 = normalize_email("sales@apexholding.co.in")
        e2, d2, pub2 = normalize_email("bids@apexholding.co.in")
        e3, d3, pub3 = normalize_email("tender.bidder@gmail.com")

        self.assertFalse(pub1)
        self.assertEqual(d1, "apexholding.co.in")
        self.assertEqual(d1, d2)
        self.assertTrue(pub3)

    async def test_08_related_entity_cin(self):
        """Shared CIN/LLPIN must be classified as RELATED_CORPORATE_ENTITY rather than automatic collusion."""
        context = VerificationContext(
            procurement_id="proc-1",
            bidders=[
                {"id": "b1", "legal_name": "Parent Co", "cin": "U72900MH2020PTC123456"},
                {"id": "b2", "legal_name": "Subsidiary Co", "cin": "U72900MH2020PTC123456"},
            ],
            submissions=[
                {"id": "s1", "bidder_id": "b1"},
                {"id": "s2", "bidder_id": "b2"},
            ],
        )

        findings = await self.verifier.verify(context)
        related_f = [f for f in findings if "RELATED_CORPORATE_ENTITY" in f.machine_readable_flags]
        self.assertEqual(len(related_f), 1)
        self.assertIn("RELATED_ENTITY", related_f[0].machine_readable_flags)
        self.assertIn("RELATED_ENTITY", related_f[0].metadata.get("classification", ""))

    # -----------------------------------------------------------------------
    # 3. Financial Instrument Overlap
    # -----------------------------------------------------------------------
    async def test_09_financial_instrument_sequential_serial_numbers(self):
        """Sequential BG numbers from the same branch must trigger CRITICAL REVIEW."""
        doc_a = Document(
            id="doc-bg-a",
            procurement_id="proc-1",
            filename="BG_Bidder_A.pdf",
            document_type="EMD_PROOF",
            bid_submission_id="sub-a",
            content_text="Bank Guarantee No: BG/2026/00912\nIssuing Bank: State Bank of India\nBranch: Commercial Branch Chennai",
        )
        doc_b = Document(
            id="doc-bg-b",
            procurement_id="proc-1",
            filename="BG_Bidder_B.pdf",
            document_type="EMD_PROOF",
            bid_submission_id="sub-b",
            content_text="Bank Guarantee No: BG/2026/00913\nIssuing Bank: State Bank of India\nBranch: Commercial Branch Chennai",
        )

        context = VerificationContext(
            procurement_id="proc-1",
            bidders=[
                {"id": "bid-a", "legal_name": "Bidder A Ltd"},
                {"id": "bid-b", "legal_name": "Bidder B Ltd"},
            ],
            submissions=[
                {"id": "sub-a", "bidder_id": "bid-a"},
                {"id": "sub-b", "bidder_id": "bid-b"},
            ],
            documents=[doc_a, doc_b],
        )

        findings = await self.verifier.verify(context)
        seq_findings = [f for f in findings if "SEQUENTIAL_FINANCIAL_INSTRUMENTS" in f.machine_readable_flags]
        self.assertEqual(len(seq_findings), 1)
        self.assertEqual(seq_findings[0].status, ComplianceState.REVIEW)
        self.assertEqual(seq_findings[0].severity, FindingSeverity.CRITICAL)
        self.assertIn("serial difference: 1", seq_findings[0].reason)

    async def test_10_financial_instrument_same_bank_alone_benign(self):
        """Same bank at different branches must NOT be flagged as collusion."""
        doc_a = Document(
            id="doc-bg-a",
            procurement_id="proc-1",
            filename="BG_A.pdf",
            document_type="EMD_PROOF",
            bid_submission_id="sub-a",
            content_text="Bank Guarantee No: BG-A-100\nIssuing Bank: State Bank of India\nBranch: Guindy Industrial Estate",
        )
        doc_b = Document(
            id="doc-bg-b",
            procurement_id="proc-1",
            filename="BG_B.pdf",
            document_type="EMD_PROOF",
            bid_submission_id="sub-b",
            content_text="Bank Guarantee No: BG-B-999\nIssuing Bank: State Bank of India\nBranch: Nariman Point Branch",
        )

        context = VerificationContext(
            procurement_id="proc-1",
            bidders=[
                {"id": "bid-a", "legal_name": "Company A"},
                {"id": "bid-b", "legal_name": "Company B"},
            ],
            submissions=[
                {"id": "sub-a", "bidder_id": "bid-a"},
                {"id": "sub-b", "bidder_id": "bid-b"},
            ],
            documents=[doc_a, doc_b],
        )

        findings = await self.verifier.verify(context)
        # Should NOT flag financial collusion
        fin_findings = [f for f in findings if f.metadata.get("forensic_type") == "FINANCIAL_INSTRUMENT_OVERLAP" and f.status == ComplianceState.REVIEW]
        self.assertEqual(len(fin_findings), 0)

    async def test_11_financial_instrument_missing_evidence_unverified(self):
        """Absence of financial instrument evidence produces UNVERIFIED without hallucinating data."""
        doc_a = Document(id="d1", procurement_id="p1", filename="gst.pdf", bid_submission_id="s1", content_text="GST Registration only")
        doc_b = Document(id="d2", procurement_id="p1", filename="gst.pdf", bid_submission_id="s2", content_text="GST Registration only")

        context = VerificationContext(
            procurement_id="p1",
            bidders=[
                {"id": "b1", "legal_name": "Alpha"},
                {"id": "b2", "legal_name": "Beta"},
            ],
            submissions=[
                {"id": "s1", "bidder_id": "b1"},
                {"id": "s2", "bidder_id": "b2"},
            ],
            documents=[doc_a, doc_b],
        )

        findings = await self.verifier.verify(context)
        unverified_fin = [f for f in findings if "FINANCIAL_INSTRUMENT_EVIDENCE_ABSENT" in f.machine_readable_flags]
        self.assertEqual(len(unverified_fin), 1)
        self.assertEqual(unverified_fin[0].status, ComplianceState.UNVERIFIED)
        self.assertEqual(unverified_fin[0].metadata.get("status"), "NO_CONCLUSIVE_EVIDENCE")

    # -----------------------------------------------------------------------
    # 4. Formatting Clones
    # -----------------------------------------------------------------------
    async def test_12_tender_template_exclusion(self):
        """Text copied directly from tender RFP specification is excluded and NOT treated as collusion."""
        tender_meta = {
            "title": "Turnkey Procurement of Industrial Water Quality Monitoring Sensor Network",
            "description": "Comprehensive scope of supply for multichannel analyzers with automatic chemical cleaning.",
        }
        tender_doc = Document(
            id="rfp-doc",
            procurement_id="proc-1",
            filename="RFP_Specification.pdf",
            document_type="TENDER_SPECIFICATION",
            content_text="The contractor shall provide continuous online dissolved oxygen and turbidity sensors with telemetry.",
        )

        # Both bidders quote the exact tender description
        quoted_text = "The contractor shall provide continuous online dissolved oxygen and turbidity sensors with telemetry."
        doc_a = Document(id="da", procurement_id="p1", filename="tech_a.pdf", bid_submission_id="sa", content_text=f"Our bid confirms: {quoted_text}")
        doc_b = Document(id="db", procurement_id="p1", filename="tech_b.pdf", bid_submission_id="sb", content_text=f"We agree that: {quoted_text}")

        context = VerificationContext(
            procurement_id="proc-1",
            tender_metadata=tender_meta,
            bidders=[
                {"id": "ba", "legal_name": "Vendor A"},
                {"id": "bb", "legal_name": "Vendor B"},
            ],
            submissions=[
                {"id": "sa", "bidder_id": "ba"},
                {"id": "sb", "bidder_id": "bb"},
            ],
            documents=[tender_doc, doc_a, doc_b],
        )

        findings = await self.verifier.verify(context)
        # Tender quote must NOT be flagged as formatting clone
        clone_findings = [f for f in findings if "IDENTICAL_NON_TENDER_TEXT" in f.machine_readable_flags]
        self.assertEqual(len(clone_findings), 0)

    async def test_13_formatting_clone_identical_non_tender_narrative(self):
        """Identical non-tender, non-statutory narrative paragraph triggers REVIEW."""
        suspicious_narrative = (
            "Proprietary hydrodynamic cavitation chamber incorporates dual-stage ultrasonic transducers "
            "engineered exclusively to eliminate microbubble interference in high-viscosity effluents."
        )
        doc_a = Document(id="da", procurement_id="p1", filename="solution_a.pdf", bid_submission_id="sa", content_text=f"Design note: {suspicious_narrative}")
        doc_b = Document(id="db", procurement_id="p1", filename="solution_b.pdf", bid_submission_id="sb", content_text=f"System architecture: {suspicious_narrative}")

        context = VerificationContext(
            procurement_id="proc-1",
            bidders=[
                {"id": "ba", "legal_name": "AquaCorp"},
                {"id": "bb", "legal_name": "HydraTech"},
            ],
            submissions=[
                {"id": "sa", "bidder_id": "ba"},
                {"id": "sb", "bidder_id": "bb"},
            ],
            documents=[doc_a, doc_b],
        )

        findings = await self.verifier.verify(context)
        clone_findings = [f for f in findings if "IDENTICAL_NON_TENDER_TEXT" in f.machine_readable_flags]
        self.assertEqual(len(clone_findings), 1)
        self.assertEqual(clone_findings[0].status, ComplianceState.REVIEW)
        self.assertIn("Identical Non-Tender Text Block Detected", clone_findings[0].reason)

    async def test_14_identical_typographical_error(self):
        """Shared unusual typographical error indicates common document authorship."""
        doc_a = Document(id="da", procurement_id="p1", filename="proposal_a.pdf", bid_submission_id="sa", content_text="We ensure robust field infrasturcture and deployment.")
        doc_b = Document(id="db", procurement_id="p1", filename="proposal_b.pdf", bid_submission_id="sb", content_text="Maintenance of regional site infrasturcture will be provided.")

        context = VerificationContext(
            procurement_id="proc-1",
            bidders=[
                {"id": "ba", "legal_name": "Supplier 1"},
                {"id": "bb", "legal_name": "Supplier 2"},
            ],
            submissions=[
                {"id": "sa", "bidder_id": "ba"},
                {"id": "sb", "bidder_id": "bb"},
            ],
            documents=[doc_a, doc_b],
        )

        findings = await self.verifier.verify(context)
        typo_findings = [f for f in findings if "IDENTICAL_TYPOGRAPHICAL_ERROR" in f.machine_readable_flags]
        self.assertEqual(len(typo_findings), 1)
        self.assertIn("infrasturcture", typo_findings[0].reason)

    # -----------------------------------------------------------------------
    # 5. Multi-Signal Reinforcement & Cartel Clustering
    # -----------------------------------------------------------------------
    async def test_15_multi_signal_reinforcement_and_clustering(self):
        """Independent signals across categories reinforce severity to CRITICAL; cluster ring detected."""
        # Bidder A and B share phone + shared metadata author + identical narrative
        suspicious_text = (
            "Proprietary multi-wavelength spectroscopic analysis utilizing titanium nitride coated flowcells "
            "with zero baseline thermal drift under tropical industrial conditions."
        )
        doc_a = Document(
            id="da",
            procurement_id="p1",
            filename="tech_a.pdf",
            bid_submission_id="sa",
            content_text=json.dumps({
                "metadata": {"author": "TECH-LEAD-DELL\\s_kumar"},
                "raw_text": f"Proposal: {suspicious_text}",
            }),
        )
        doc_b = Document(
            id="db",
            procurement_id="p1",
            filename="tech_b.pdf",
            bid_submission_id="sb",
            content_text=json.dumps({
                "metadata": {"author": "TECH-LEAD-DELL\\s_kumar"},
                "raw_text": f"System overview: {suspicious_text}",
            }),
        )

        context = VerificationContext(
            procurement_id="p1",
            bidders=[
                {"id": "ba", "legal_name": "Company A", "phone": "9840199999"},
                {"id": "bb", "legal_name": "Company B", "phone": "09840199999"},
                {"id": "bc", "legal_name": "Company C", "phone": "9840199999"},  # C also tied to B & A via phone
            ],
            submissions=[
                {"id": "sa", "bidder_id": "ba"},
                {"id": "sb", "bidder_id": "bb"},
                {"id": "sc", "bidder_id": "bc"},
            ],
            documents=[doc_a, doc_b],
        )

        findings = await self.verifier.verify(context)
        # Pair A-B has metadata + phone + formatting clone -> multi-signal CRITICAL
        ab_finding = next(
            (f for f in findings if f.status == ComplianceState.REVIEW and "ba" in f.claim.get("involved_bidders", []) and "bb" in f.claim.get("involved_bidders", [])),
            None,
        )
        self.assertIsNotNone(ab_finding)
        self.assertEqual(ab_finding.severity, FindingSeverity.CRITICAL)
        self.assertGreaterEqual(ab_finding.confidence, 0.95)
        self.assertGreaterEqual(len(ab_finding.observation.get("categories", [])), 2)

        # Cartel cluster containing all 3 linked bidders
        cluster_bidders = ab_finding.metadata.get("cluster_bidders", [])
        self.assertIn("ba", cluster_bidders)
        self.assertIn("bb", cluster_bidders)
        self.assertIn("bc", cluster_bidders)

    # -----------------------------------------------------------------------
    # 6. Clean Bidders Yield Canonical PASS Audit
    # -----------------------------------------------------------------------
    async def test_16_clean_bidders_yield_canonical_pass_audit(self):
        """Screening across completely independent clean bidders produces PASS audit record."""
        doc_a = Document(
            id="da",
            procurement_id="p1",
            filename="clean_a.pdf",
            bid_submission_id="sa",
            content_text=json.dumps({
                "metadata": {"author": "Clean Engineering Pvt Ltd"},
                "raw_text": "Independent technological offering with patented membrane technology.",
            }),
        )
        doc_b = Document(
            id="db",
            procurement_id="p1",
            filename="clean_b.pdf",
            bid_submission_id="sb",
            content_text=json.dumps({
                "metadata": {"author": "Solaris Instruments Inc"},
                "raw_text": "Different analytical approach using solid state semiconductor sensors.",
            }),
        )

        context = VerificationContext(
            procurement_id="p1",
            bidders=[
                {"id": "ba", "legal_name": "Clean Engineering", "phone": "9811111111", "email": "info@cleaneng.com", "address": "101 Nehru Place New Delhi"},
                {"id": "bb", "legal_name": "Solaris Instruments", "phone": "9822222222", "email": "sales@solaris.in", "address": "505 MG Road Bengaluru"},
            ],
            submissions=[
                {"id": "sa", "bidder_id": "ba"},
                {"id": "sb", "bidder_id": "bb"},
            ],
            documents=[doc_a, doc_b],
        )

        findings = await self.verifier.verify(context)
        # Must have PASS audit finding
        pass_findings = [f for f in findings if f.status == ComplianceState.PASS]
        self.assertEqual(len(pass_findings), 1)
        self.assertIn("NO_COLLUSION_DETECTED", pass_findings[0].machine_readable_flags)
        self.assertIn("NO_SUSPICIOUS_LINKAGE_DETECTED", pass_findings[0].machine_readable_flags)
        self.assertIn("FORENSIC_SCREENING_CLEAR", pass_findings[0].machine_readable_flags)

    # -----------------------------------------------------------------------
    # 7. Human Decision Boundary & Provenance Retention
    # -----------------------------------------------------------------------
    async def test_17_human_decision_boundary_and_provenance(self):
        """Findings preserve human decision boundary authority and exact quote provenance."""
        context = VerificationContext(
            procurement_id="p1",
            bidders=[
                {"id": "b1", "legal_name": "Bidder 1", "phone": "9999988888"},
                {"id": "b2", "legal_name": "Bidder 2", "phone": "9999988888"},
            ],
            submissions=[
                {"id": "s1", "bidder_id": "b1"},
                {"id": "s2", "bidder_id": "b2"},
            ],
        )

        findings = await self.verifier.verify(context)
        review_f = next(f for f in findings if f.status == ComplianceState.REVIEW)

        # Decision authority must explicitly state human procurement officer
        self.assertEqual(review_f.metadata.get("decision_authority"), "HUMAN_PROCUREMENT_OFFICER")
        self.assertIn("HUMAN_PROCUREMENT_OFFICER", review_f.metadata.get("decision_authority"))
        # Provenance records must be populated
        self.assertGreaterEqual(len(review_f.evidence), 1)
        self.assertTrue(len(review_f.evidence[0].quote) > 0)


if __name__ == "__main__":
    unittest.main()
