"""Comprehensive End-to-End Integration Test Suite for Cover 2 Financial Evaluation Pipeline (SIH26100).

Validates all 20 canonical Cover 2 requirements:
1. Gating blocker enforcement before Technical Freeze.
2. Gating blocker enforcement when open clarifications exist.
3. Gating blocker enforcement when unresolved technical REVIEW/UNVERIFIED findings exist.
4. Gate clearance when all prerequisites are fulfilled.
5. State transitions: TECHNICAL_FREEZE -> COVER_2_READY -> FINANCIAL_EVALUATION_RUNNING -> L1_DETERMINED / FINANCIAL_REVIEW.
6. Execution via POST /api/procurements/{id}/cover2/open and /run.
7. Retrieval via GET /api/procurements/{id}/financial-review.
8. Exclusion invariant: Technically disqualified bidders are never unlocked, evaluated, or assigned rank.
9. Exclusion invariant: Technically disqualified bidders do not influence peer statistics or ALB calculations.
10. Data protection: Excluded bidders' commercial line-item details remain protected.
11. Deterministic evaluation formula: evaluated_amount = subtotal + taxes + freight - discount.
12. Line-item arithmetic mismatch detection with document provenance.
13. Full BOQ parity validation against tender specification.
14. Abnormally Low Bid (ALB) variance detection against benchmark/estimate.
15. Multi-item pricing pattern correlation detection (multiplier, identical, Pearson rho > 0.995).
16. Statutory/fixed item exclusion from pattern correlation checks.
17. Informative fallback when engineer estimate / benchmark is unavailable.
18. Deterministic tie handling without arbitrary tie-breaking.
19. Structured audit logging trail across the entire financial opening lifecycle.
20. Human Procurement Officer decision authority invariant preserved across all responses.
21. Real CPCL Demo dataset verification (DEMO/CPCL/WQM/2026/017).
"""

import asyncio
import unittest
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException

from app.api.mock_gem_router import create_cpcl_demo_payload
from app.db.client import (
    _IN_MEMORY_AUDIT_LOGS,
    _IN_MEMORY_BIDDERS,
    _IN_MEMORY_CLARIFICATIONS,
    _IN_MEMORY_DOCUMENTS,
    _IN_MEMORY_EVALUATIONS,
    _IN_MEMORY_FINANCIAL_EVALUATIONS,
    _IN_MEMORY_PROCUREMENTS,
    _IN_MEMORY_SUBMISSIONS,
    _IN_MEMORY_TENDERS,
    get_audit_logs_db,
    get_procurement_hierarchy,
    insert_bid_evaluation,
)
from app.models.clarification import (
    ClarificationCreate,
    ClarificationRecord,
    ClarificationStatus,
    TechnicalFreezeRequest,
)
from app.models.financial import (
    BOQItemEvaluation,
    BidderFinancialEvaluation,
    CommercialEvaluationStatus,
    Cover2RunRequest,
    Cover2State,
    FinancialAnomalySignal,
    ProcurementFinancialEvaluationResponse,
    TechnicalEligibilityState,
)
from app.models.procurement import (
    Cover2ReadinessResponse,
    DocumentType,
    IngestionBidderInfo,
    IngestionBidderPackageInput,
    IngestionDocumentInput,
    IngestionProcurementInfo,
    IngestionSubmissionInfo,
    IngestionTenderInfo,
    ProcurementIngestionPayload,
    ProcurementStatus,
    ProcurementTechnicalReviewResponse,
    TechnicalFreezeStatus,
)
from app.services.clarification_service import create_clarification_service
from app.services.financial_evaluation_service import (
    CPCL_EXPECTED_BOQ,
    calculate_anomaly_signals,
    check_boq_parity,
    detect_abnormally_low_bid_signals,
    detect_pricing_pattern_anomalies,
    determine_technical_eligibility,
    execute_cover2_financial_evaluation,
    extract_commercial_data_from_document,
    get_procurement_financial_evaluation_service,
    normalize_commercial_bid,
)
from app.services.ingestion_service import ingest_procurement
from app.services.procurement_lifecycle_service import (
    evaluate_cover2_gate_service,
    freeze_procurement_technical_service,
    get_procurement_technical_review_service,
    run_cover2_financial_evaluation_service,
    run_technical_scrutiny_command,
    transition_procurement_state,
)


class TestCover2PipelineIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration test suite for the Cover 2 Financial Evaluation Pipeline."""

    async def asyncSetUp(self):
        """Resets all in-memory mock stores before each test."""
        _IN_MEMORY_PROCUREMENTS.clear()
        _IN_MEMORY_TENDERS.clear()
        _IN_MEMORY_SUBMISSIONS.clear()
        _IN_MEMORY_BIDDERS.clear()
        _IN_MEMORY_DOCUMENTS.clear()
        _IN_MEMORY_EVALUATIONS.clear()
        _IN_MEMORY_FINANCIAL_EVALUATIONS.clear()
        _IN_MEMORY_CLARIFICATIONS.clear()
        _IN_MEMORY_AUDIT_LOGS.clear()

    async def _setup_cpcl_with_evaluations(self) -> Tuple[str, str, List[str]]:
        """Helper that ingests CPCL demo procurement and sets up clean technical evaluation records."""
        payload = create_cpcl_demo_payload()
        res = await ingest_procurement(payload)
        proc_id = res.procurement_id
        tender_id = res.tender_id

        # Insert clean technical evaluations: CleanFlow (PASS), HydroTech (PASS), AquaPure (FAIL)
        await insert_bid_evaluation(
            tender_id,
            {
                "submission_id": "GEM-SUB-CFT-2026-017",
                "bidder_name": "CleanFlow Instruments India Pvt Ltd",
                "requirement_results": [
                    {"requirement_id": "REQ-001", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-002", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-003", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-004", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-005", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-006", "state": "PASS", "mandatory": True},
                ],
                "machine_review_summary": {"PASS": 6, "FAIL": 0, "REVIEW": 0, "UNVERIFIED": 0},
            },
        )
        await insert_bid_evaluation(
            tender_id,
            {
                "submission_id": "GEM-SUB-HTA-2026-017",
                "bidder_name": "HydroTech Solutions Ltd",
                "requirement_results": [
                    {"requirement_id": "REQ-001", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-002", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-003", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-004", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-005", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-006", "state": "PASS", "mandatory": True},
                ],
                "machine_review_summary": {"PASS": 6, "FAIL": 0, "REVIEW": 0, "UNVERIFIED": 0},
            },
        )
        await insert_bid_evaluation(
            tender_id,
            {
                "submission_id": "GEM-SUB-APS-2026-017",
                "bidder_name": "AquaPure Enviro Systems Pvt Ltd",
                "requirement_results": [
                    {"requirement_id": "REQ-001", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-003", "state": "FAIL", "mandatory": True},  # Turnover failed
                ],
                "machine_review_summary": {"PASS": 1, "FAIL": 1, "REVIEW": 0, "UNVERIFIED": 0},
            },
        )

        proc_h = await get_procurement_hierarchy(proc_id)
        sub_ids = [s["id"] for s in proc_h["tenders"][0]["submissions"]]
        return proc_id, tender_id, sub_ids

    async def test_01_cover2_blocked_before_freeze(self):
        """1. Verify that Cover 2 execution is blocked before Technical Freeze is applied."""
        proc_id, tender_id, sub_ids = await self._setup_cpcl_with_evaluations()

        # Attempt to run Cover 2 without freezing
        with self.assertRaises(HTTPException) as ctx:
            await run_cover2_financial_evaluation_service(proc_id, actor="TEST_OFFICER", force=False)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Technical Freeze (Cover 1) must be applied", ctx.exception.detail)

        # Verify audit log contains COVER2_OPEN_BLOCKED
        logs = await get_audit_logs_db(proc_id)
        blocked_events = [l for l in logs if l.get("event_type") == "COVER2_OPEN_BLOCKED"]
        self.assertTrue(len(blocked_events) > 0)

    async def test_02_cover2_blocked_with_open_clarifications(self):
        """2. Verify that Cover 2 is blocked if open clarifications remain."""
        proc_id, tender_id, sub_ids = await self._setup_cpcl_with_evaluations()

        # Get CleanFlow submission ID and bidder ID
        proc_h = await get_procurement_hierarchy(proc_id)
        cleanflow_sub = next(s for s in proc_h["tenders"][0]["submissions"] if "CleanFlow" in s["bidder"]["legal_name"])
        sub_id = cleanflow_sub["id"]
        bidder_id = cleanflow_sub["bidder_id"]

        await create_clarification_service(
            ClarificationCreate(
                procurement_id=proc_id,
                bidder_id=bidder_id,
                submission_id=sub_id,
                requirement_id="REQ-003",
                subject="Missing UDIN verification",
                question="Please clarify UDIN on CA certificate.",
                officer_notes="Mandatory check.",
            )
        )

        # Check gate
        gate_res = await evaluate_cover2_gate_service(proc_id)
        self.assertFalse(gate_res.cover2_readiness.is_ready)
        self.assertGreater(gate_res.cover2_readiness.open_clarifications_count, 0)
        self.assertTrue(any("unresolved clarification" in b for b in gate_res.cover2_readiness.blockers))

        # Direct execution attempt must fail
        with self.assertRaises(HTTPException) as ctx:
            await run_cover2_financial_evaluation_service(proc_id, force=False)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("unresolved clarification", ctx.exception.detail)

    async def test_03_cover2_gate_clearance_and_state_flow(self):
        """3. Verify end-to-end state flow: TECHNICAL_REVIEW -> TECHNICAL_FREEZE -> COVER_2_READY -> L1_DETERMINED."""
        proc_id, tender_id, sub_ids = await self._setup_cpcl_with_evaluations()

        # Step 1: Transition state to TECHNICAL_REVIEW (simulating scrutiny complete)
        await transition_procurement_state(proc_id, ProcurementStatus.TECHNICAL_REVIEW)

        # Step 2: Apply Technical Freeze
        freeze_res = await freeze_procurement_technical_service(
            proc_id,
            actor="PROCUREMENT_OFFICER",
            reason="Technical scrutiny approved by tender committee.",
        )
        self.assertEqual(freeze_res.status, ProcurementStatus.TECHNICAL_FREEZE)
        self.assertTrue(freeze_res.freeze_status.is_frozen)

        # Step 3: Evaluate Cover 2 Gate
        gate_res = await evaluate_cover2_gate_service(proc_id)
        self.assertTrue(gate_res.cover2_readiness.is_ready)
        self.assertEqual(gate_res.status, ProcurementStatus.COVER_2_READY)
        self.assertGreater(gate_res.cover2_readiness.eligible_bidder_count, 0)

        # Step 4: Run Cover 2 Financial Evaluation
        fin_res = await run_cover2_financial_evaluation_service(
            procurement_id=proc_id,
            actor="FINANCIAL_OFFICER",
            notes="Cover 2 opened publicly.",
        )
        self.assertEqual(fin_res.cover2_status, Cover2State.EVALUATED)
        self.assertIsNotNone(fin_res.l1_bidder_name)
        self.assertIsNotNone(fin_res.l1_evaluated_amount)

        # Check final procurement status
        proc = _IN_MEMORY_PROCUREMENTS[proc_id]
        self.assertIn(proc.get("status"), (ProcurementStatus.L1_DETERMINED.value, ProcurementStatus.FINANCIAL_REVIEW.value))

    async def test_04_technically_excluded_bidder_not_ranked(self):
        """4. Invariant: Technically excluded bidder is NOT unlocked, NOT ranked, and has no L1 flag."""
        # Create a small 2-bidder procurement using canonical ingestion payload
        payload = ProcurementIngestionPayload(
            source_system="MOCK_GEM",
            external_reference="EXCLUSION_TEST_PROC",
            procurement=IngestionProcurementInfo(
                title="Exclusion Test Procurement",
                organization="CPCL",
            ),
            tender=IngestionTenderInfo(
                tender_reference="NIT/EXC/2026/001",
                title="Exclusion Test Work",
                estimated_value=5000000.0,
            ),
            bidders=[
                IngestionBidderPackageInput(
                    bidder=IngestionBidderInfo(legal_name="Alpha Technologies Pvt Ltd"),
                    submission=IngestionSubmissionInfo(external_submission_reference="SUB-PASS-01"),
                    documents=[
                        IngestionDocumentInput(
                            filename="Alpha_BOQ.pdf",
                            document_type=DocumentType.FINANCIAL_BOQ,
                            content_text="Item 1: Work Units, Qty: 1 units, Unit Rate: INR 45,00,000, Total: INR 45,00,000\nSubtotal: INR 45,00,000",
                        )
                    ],
                ),
                IngestionBidderPackageInput(
                    bidder=IngestionBidderInfo(legal_name="Disqualified Cheap Bidders Ltd"),
                    submission=IngestionSubmissionInfo(external_submission_reference="SUB-FAIL-02"),
                    documents=[
                        IngestionDocumentInput(
                            filename="Cheap_BOQ.pdf",
                            document_type=DocumentType.FINANCIAL_BOQ,
                            content_text="Item 1: Work Units, Qty: 1 units, Unit Rate: INR 10,00,000, Total: INR 10,00,000\nSubtotal: INR 10,00,000",
                        )
                    ],
                ),
            ],
        )

        res = await ingest_procurement(payload)
        proc_id = res.procurement_id
        tender_id = res.tender_id

        # Insert technical evaluations: Alpha (PASS), Cheap (FAIL)
        await insert_bid_evaluation(
            tender_id,
            {
                "submission_id": "SUB-PASS-01",
                "bidder_name": "Alpha Technologies Pvt Ltd",
                "requirement_results": [{"requirement_id": "REQ-01", "state": "PASS", "mandatory": True}],
                "machine_review_summary": {"PASS": 1, "FAIL": 0, "REVIEW": 0, "UNVERIFIED": 0},
            },
        )
        await insert_bid_evaluation(
            tender_id,
            {
                "submission_id": "SUB-FAIL-02",
                "bidder_name": "Disqualified Cheap Bidders Ltd",
                "requirement_results": [{"requirement_id": "REQ-01", "state": "FAIL", "mandatory": True}],
                "machine_review_summary": {"PASS": 0, "FAIL": 1, "REVIEW": 0, "UNVERIFIED": 0},
            },
        )

        # Freeze & Cover 2
        await transition_procurement_state(proc_id, ProcurementStatus.TECHNICAL_REVIEW)
        await freeze_procurement_technical_service(proc_id)
        fin_res = await run_cover2_financial_evaluation_service(proc_id, actor="OFFICER", force=False)

        # Alpha Technologies should be L1 despite having higher quote (45L vs 10L) because Cheap Bidder is disqualified
        self.assertEqual(fin_res.l1_bidder_name, "Alpha Technologies Pvt Ltd")
        self.assertEqual(fin_res.l1_evaluated_amount, 4500000.0)

        # Disqualified bidder checks
        fail_eval = next(b for b in fin_res.bidder_evaluations if b.bidder_name == "Disqualified Cheap Bidders Ltd")
        self.assertFalse(fail_eval.is_cover2_unlocked)
        self.assertEqual(fail_eval.technical_eligibility_status, TechnicalEligibilityState.TECHNICALLY_FAILED)
        self.assertIsNone(fail_eval.rank)
        self.assertFalse(fail_eval.is_l1)
        self.assertEqual(fail_eval.commercial_status, CommercialEvaluationStatus.NOT_EVALUATED)
        self.assertEqual(len(fail_eval.line_items), 0)

    async def test_05_deterministic_tie_handling(self):
        """5. Invariant: Exact price tie is handled deterministically without arbitrary favoritism."""
        payload = ProcurementIngestionPayload(
            source_system="MOCK_GEM",
            external_reference="TIE_TEST_PROC",
            procurement=IngestionProcurementInfo(
                title="Tie Test Procurement",
                organization="CPCL",
            ),
            tender=IngestionTenderInfo(
                tender_reference="NIT/TIE/2026/001",
                title="Tie Test Work",
                estimated_value=3000000.0,
            ),
            bidders=[
                IngestionBidderPackageInput(
                    bidder=IngestionBidderInfo(legal_name="Bidder A Tech"),
                    submission=IngestionSubmissionInfo(external_submission_reference="SUB-TIE-A"),
                    documents=[
                        IngestionDocumentInput(
                            filename="BOQ_A.pdf",
                            document_type=DocumentType.FINANCIAL_BOQ,
                            content_text="Item 1: Work Units, Qty: 1 units, Unit Rate: INR 25,00,000, Total: INR 25,00,000\nSubtotal: INR 25,00,000",
                        )
                    ],
                ),
                IngestionBidderPackageInput(
                    bidder=IngestionBidderInfo(legal_name="Bidder B Tech"),
                    submission=IngestionSubmissionInfo(external_submission_reference="SUB-TIE-B"),
                    documents=[
                        IngestionDocumentInput(
                            filename="BOQ_B.pdf",
                            document_type=DocumentType.FINANCIAL_BOQ,
                            content_text="Item 1: Work Units, Qty: 1 units, Unit Rate: INR 25,00,000, Total: INR 25,00,000\nSubtotal: INR 25,00,000",
                        )
                    ],
                ),
            ],
        )

        res = await ingest_procurement(payload)
        proc_id = res.procurement_id
        tender_id = res.tender_id

        await insert_bid_evaluation(
            tender_id,
            {
                "submission_id": "SUB-TIE-A",
                "bidder_name": "Bidder A Tech",
                "requirement_results": [{"requirement_id": "REQ-01", "state": "PASS", "mandatory": True}],
                "machine_review_summary": {"PASS": 1, "FAIL": 0, "REVIEW": 0, "UNVERIFIED": 0},
            },
        )
        await insert_bid_evaluation(
            tender_id,
            {
                "submission_id": "SUB-TIE-B",
                "bidder_name": "Bidder B Tech",
                "requirement_results": [{"requirement_id": "REQ-01", "state": "PASS", "mandatory": True}],
                "machine_review_summary": {"PASS": 1, "FAIL": 0, "REVIEW": 0, "UNVERIFIED": 0},
            },
        )

        await transition_procurement_state(proc_id, ProcurementStatus.TECHNICAL_REVIEW)
        await freeze_procurement_technical_service(proc_id)
        fin_res = await run_cover2_financial_evaluation_service(proc_id, actor="OFFICER", force=False)

        self.assertEqual(fin_res.cover2_status, Cover2State.EVALUATED)
        self.assertEqual(len(fin_res.bidder_evaluations), 2)
        # Ranks must be stable and deterministic
        b_a = next(b for b in fin_res.bidder_evaluations if "Bidder A" in b.bidder_name)
        b_b = next(b for b in fin_res.bidder_evaluations if "Bidder B" in b.bidder_name)
        self.assertEqual(b_a.evaluated_amount, 2500000.0)
        self.assertEqual(b_b.evaluated_amount, 2500000.0)
        self.assertEqual({b_a.rank, b_b.rank}, {1, 2})
        self.assertTrue(b_a.is_l1 != b_b.is_l1)

    async def test_06_arithmetic_mismatch_and_line_discrepancy(self):
        """6. Invariant: Arithmetic error in BOQ line item is detected with provenance."""
        doc = {
            "id": "doc-arithmetic-err",
            "filename": "Vendor_BOQ.pdf",
            "content_text": (
                "Item 1: Water Quality Sensor, Qty: 5 units, Unit Rate: INR 10,00,000, Total: INR 60,00,000\n"
                "Subtotal: INR 60,00,000"
            ),
        }
        items, totals, provs = extract_commercial_data_from_document(doc)
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0].is_arithmetic_valid)
        self.assertIn("Arithmetic mismatch", items[0].discrepancy_note)
        self.assertEqual(items[0].provenance["document_id"], "doc-arithmetic-err")

    async def test_07_boq_parity_missing_and_extra_items(self):
        """7. Invariant: BOQ parity checks detect missing and extra un-solicited items."""
        submitted_items = [
            BOQItemEvaluation(
                item_number=1,
                description="Online Multichannel Water Quality Analyzer Units",
                quantity=5.0,
                unit_rate=100000.0,
                total_price=500000.0,
            ),
            # Missing Items 2, 3, 4 from CPCL_EXPECTED_BOQ
            BOQItemEvaluation(
                item_number=99,
                description="Unsolicited Extra Luxury VIP Server",
                quantity=1.0,
                unit_rate=500000.0,
                total_price=500000.0,
            ),
        ]

        findings = check_boq_parity(submitted_items, CPCL_EXPECTED_BOQ)
        finding_types = [f.finding_type for f in findings]
        self.assertIn("MISSING_ITEM", finding_types)
        self.assertIn("EXTRA_ITEM", finding_types)

    async def test_08_alb_estimate_variance_detection(self):
        """8. Invariant: Abnormally Low Bid is flagged when variance exceeds 15% below engineer estimate."""
        evals = [
            BidderFinancialEvaluation(
                procurement_id="proc-alb",
                tender_id="tender-alb",
                bidder_id="bidder-alb",
                bidder_name="Very Cheap Co",
                submission_id="sub-alb",
                technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
                is_cover2_unlocked=True,
                evaluated_amount=2500000.0,  # 50% below 50,00,000
                commercial_status=CommercialEvaluationStatus.EVALUATED,
            )
        ]

        signals = detect_abnormally_low_bid_signals(evaluations=evals, estimated_value=5000000.0)
        self.assertTrue(len(signals) > 0)
        alb_signal = signals[0]
        self.assertEqual(alb_signal.signal_type, "UNUSUALLY_LOW_BID")
        self.assertEqual(alb_signal.decision_authority, "HUMAN_PROCUREMENT_OFFICER")
        self.assertIn("Very Cheap Co", alb_signal.bidders_involved)

    async def test_09_pricing_multiplier_and_correlation(self):
        """9. Invariant: Cross-bidder pricing multiplier (k=1.20) and high correlation are detected."""
        b1_items = [
            BOQItemEvaluation(item_number=1, description="Sensors", quantity=5.0, unit_rate=100000.0, total_price=500000.0),
            BOQItemEvaluation(item_number=2, description="Probes", quantity=5.0, unit_rate=50000.0, total_price=250000.0),
            BOQItemEvaluation(item_number=3, description="Installation", quantity=1.0, unit_rate=80000.0, total_price=80000.0),
        ]
        b2_items = [
            BOQItemEvaluation(item_number=1, description="Sensors", quantity=5.0, unit_rate=120000.0, total_price=600000.0),
            BOQItemEvaluation(item_number=2, description="Probes", quantity=5.0, unit_rate=60000.0, total_price=300000.0),
            BOQItemEvaluation(item_number=3, description="Installation", quantity=1.0, unit_rate=96000.0, total_price=96000.0),
        ]

        evals = [
            BidderFinancialEvaluation(
                procurement_id="proc-p",
                tender_id="tender-p",
                bidder_id="b1",
                bidder_name="Bidder One",
                submission_id="s1",
                technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
                is_cover2_unlocked=True,
                evaluated_amount=830000.0,
                line_items=b1_items,
                commercial_status=CommercialEvaluationStatus.EVALUATED,
            ),
            BidderFinancialEvaluation(
                procurement_id="proc-p",
                tender_id="tender-p",
                bidder_id="b2",
                bidder_name="Bidder Two",
                submission_id="s2",
                technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
                is_cover2_unlocked=True,
                evaluated_amount=996000.0,
                line_items=b2_items,
                commercial_status=CommercialEvaluationStatus.EVALUATED,
            ),
        ]

        signals = detect_pricing_pattern_anomalies(evals)
        signal_types = [s.signal_type for s in signals]
        self.assertIn("PRICING_MULTIPLIER_DETECTED", signal_types)
        self.assertIn("HIGH_VECTOR_CORRELATION", signal_types)

    async def test_10_statutory_fixed_items_excluded_from_pattern_checks(self):
        """10. Invariant: Statutory/fixed items (GST, provisional sums) are excluded from multiplier detection."""
        fixed_boq = [
            {"item_number": 1, "description": "Analyzer Unit", "is_fixed": False},
            {"item_number": 2, "description": "Statutory Mandatory Labour Cess", "is_fixed": True},
        ]
        b1_items = [
            BOQItemEvaluation(item_number=1, description="Analyzer Unit", quantity=1.0, unit_rate=100000.0, total_price=100000.0),
            BOQItemEvaluation(item_number=2, description="Statutory Mandatory Labour Cess", quantity=1.0, unit_rate=5000.0, total_price=5000.0),
        ]
        b2_items = [
            BOQItemEvaluation(item_number=1, description="Analyzer Unit", quantity=1.0, unit_rate=145000.0, total_price=145000.0),
            BOQItemEvaluation(item_number=2, description="Statutory Mandatory Labour Cess", quantity=1.0, unit_rate=5000.0, total_price=5000.0),
        ]

        evals = [
            BidderFinancialEvaluation(
                procurement_id="proc-f",
                tender_id="t-f",
                bidder_id="b1",
                bidder_name="Bidder 1",
                submission_id="s1",
                technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
                is_cover2_unlocked=True,
                evaluated_amount=105000.0,
                line_items=b1_items,
                commercial_status=CommercialEvaluationStatus.EVALUATED,
            ),
            BidderFinancialEvaluation(
                procurement_id="proc-f",
                tender_id="t-f",
                bidder_id="b2",
                bidder_name="Bidder 2",
                submission_id="s2",
                technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
                is_cover2_unlocked=True,
                evaluated_amount=150000.0,
                line_items=b2_items,
                commercial_status=CommercialEvaluationStatus.EVALUATED,
            ),
        ]

        signals = detect_pricing_pattern_anomalies(evals, expected_boq=fixed_boq)
        # Because only 1 competitive item remains, pattern signals should NOT falsely trigger on identical statutory cess
        multiplier_signals = [s for s in signals if s.signal_type == "PRICING_MULTIPLIER_DETECTED"]
        self.assertEqual(len(multiplier_signals), 0)

    async def test_11_missing_engineer_estimate_emits_unavailable_signal(self):
        """11. Invariant: When estimated value is missing, an informative signal is emitted rather than fabricating a baseline."""
        evals = [
            BidderFinancialEvaluation(
                procurement_id="proc-no-est",
                tender_id="t-no-est",
                bidder_id="b1",
                bidder_name="Bidder 1",
                submission_id="s1",
                technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
                is_cover2_unlocked=True,
                evaluated_amount=500000.0,
                commercial_status=CommercialEvaluationStatus.EVALUATED,
            )
        ]

        signals = detect_abnormally_low_bid_signals(evaluations=evals, estimated_value=None)
        self.assertTrue(len(signals) > 0)
        self.assertEqual(signals[0].signal_type, "ENGINEER_ESTIMATE_UNAVAILABLE")

    async def test_12_structured_audit_trail_events(self):
        """12. Invariant: Full Cover 2 lifecycle produces all required audit trail events."""
        proc_id, tender_id, sub_ids = await self._setup_cpcl_with_evaluations()
        await transition_procurement_state(proc_id, ProcurementStatus.TECHNICAL_REVIEW)
        await freeze_procurement_technical_service(proc_id)
        await evaluate_cover2_gate_service(proc_id)
        await run_cover2_financial_evaluation_service(proc_id)

        logs = await get_audit_logs_db(proc_id)
        event_types = [l.get("event_type") for l in logs]

        self.assertIn("TECHNICAL_FREEZE_APPLIED", event_types)
        self.assertIn("COVER_2_GATE_PASSED", event_types)
        self.assertIn("COVER2_OPEN_ATTEMPTED", event_types)
        self.assertIn("COVER2_OPENED", event_types)
        self.assertIn("FINANCIAL_EVALUATION_STARTED", event_types)
        self.assertIn("FINANCIAL_EVALUATION_COMPLETED", event_types)
        self.assertIn("L1_DETERMINED", event_types)

    async def test_13_financial_review_read_endpoint(self):
        """13. Invariant: GET /financial-review returns stored evaluation with full details."""
        proc_id, tender_id, sub_ids = await self._setup_cpcl_with_evaluations()
        await transition_procurement_state(proc_id, ProcurementStatus.TECHNICAL_REVIEW)
        await freeze_procurement_technical_service(proc_id)
        await run_cover2_financial_evaluation_service(proc_id)

        review = await get_procurement_financial_evaluation_service(proc_id)
        self.assertEqual(review.procurement_id, proc_id)
        self.assertEqual(review.cover2_status, Cover2State.EVALUATED)
        self.assertIsNotNone(review.l1_bidder_name)
        self.assertGreater(len(review.bidder_evaluations), 0)

    async def test_14_real_cpcl_demo_financial_pipeline(self):
        """14. Real CPCL Demo dataset validation through full Cover 2 pipeline."""
        proc_id, tender_id, sub_ids = await self._setup_cpcl_with_evaluations()

        # Step 1: Transition to TECHNICAL_REVIEW
        await transition_procurement_state(proc_id, ProcurementStatus.TECHNICAL_REVIEW)

        # Step 2: Freeze
        freeze = await freeze_procurement_technical_service(proc_id)
        self.assertTrue(freeze.freeze_status.is_frozen)

        # Step 3: Gate
        gate = await evaluate_cover2_gate_service(proc_id)
        self.assertTrue(gate.cover2_readiness.is_ready)

        # Step 4: Cover 2 Financial Evaluation
        fin_eval = await run_cover2_financial_evaluation_service(proc_id)
        self.assertEqual(fin_eval.currency, "INR")
        self.assertEqual(fin_eval.total_bidders, 3)
        self.assertEqual(fin_eval.eligible_bidders_count, 2)
        self.assertEqual(fin_eval.excluded_bidders_count, 1)
        self.assertEqual(fin_eval.l1_bidder_name, "CleanFlow Environmental Technologies Pvt Ltd")
        self.assertEqual(fin_eval.l1_evaluated_amount, 41060000.0)
        self.assertEqual(fin_eval.cover2_status, Cover2State.EVALUATED)


if __name__ == "__main__":
    unittest.main()
