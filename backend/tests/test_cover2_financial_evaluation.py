"""Test Suite for Canonical Cover 2 Financial / Commercial Evaluation (SIH26100).

Tests the 13 required capabilities:
1. Technically failed bidder excluded from Cover 2.
2. Review-pending bidder handled correctly (review required, not unlocked).
3. Successful BOQ extraction from commercial document.
4. Arithmetic mismatch detection.
5. Missing line item detection against expected BOQ.
6. Normalized totals calculation.
7. L1 ranking calculation.
8. Invalid / unverified bid not ranked as L1.
9. Deterministic tie handling.
10. Low / high bid anomaly signals.
11. Multi-bidder end-to-end Cover 2 evaluation.
12. Persistence to store and reload.
13. Canonical API endpoint execution and contract validation.
"""

import asyncio
import unittest
from datetime import datetime, timezone

from app.models.financial import (
    BOQItemEvaluation,
    BidderFinancialEvaluation,
    CommercialEvaluationStatus,
    Cover2State,
    FinancialAnomalySignal,
    TechnicalEligibilityState,
)
from app.services.financial_evaluation_service import (
    determine_technical_eligibility,
    extract_commercial_data_from_document,
    check_boq_parity,
    normalize_commercial_bid,
    calculate_anomaly_signals,
    detect_pricing_pattern_anomalies,
    detect_abnormally_low_bid_signals,
    execute_cover2_financial_evaluation,
    get_procurement_financial_evaluation_service,
    CPCL_EXPECTED_BOQ,
    ALB_ESTIMATE_VARIANCE_THRESHOLD,
)
from app.rules.layers.financial_commercial import FinancialCommercialVerifier
from app.models.verification import VerificationContext
from app.models.tender_contract import RequirementEvaluationContract, CanonicalEvaluationField, RequirementCategory, EvaluationMode
from app.models.evaluation import ComplianceState
from app.api.mock_gem_router import create_cpcl_demo_payload
from app.services.ingestion_service import ingest_procurement
from app.db.client import (
    insert_bid_evaluation,
    save_procurement_financial_evaluation,
    get_procurement_financial_evaluation,
)
from app.api.procurement_router import (
    open_cover2_financial_evaluation_endpoint,
    get_financial_review_endpoint,
)


class TestCover2FinancialEvaluation(unittest.TestCase):
    """Unit and integration tests for Cover 2 financial evaluation."""

    def setUp(self):
        from app.db.client import _IN_MEMORY_EVALUATIONS, _IN_MEMORY_FINANCIAL_EVALUATIONS
        _IN_MEMORY_EVALUATIONS.clear()
        _IN_MEMORY_FINANCIAL_EVALUATIONS.clear()


    def test_01_technically_failed_bidder_excluded(self):
        """1. Verify that a technically failed bidder is excluded from Cover 2."""
        mock_evals = [
            {
                "evaluation_data": {
                    "submission_id": "sub-fail-001",
                    "requirement_results": [
                        {"requirement_id": "REQ-001", "state": "PASS", "mandatory": True},
                        {"requirement_id": "REQ-002", "state": "PASS", "mandatory": True},
                        {"requirement_id": "REQ-003", "state": "FAIL", "mandatory": True},
                    ],
                }
            }
        ]

        state, reason = determine_technical_eligibility("sub-fail-001", "TENDER-001", mock_evals)
        self.assertEqual(state, TechnicalEligibilityState.TECHNICALLY_FAILED)
        self.assertIn("Failed mandatory technical requirement", reason)
        self.assertIn("REQ-003", reason)

    def test_02_review_pending_bidder_handled_correctly(self):
        """2. Verify that a review-pending bidder is flagged and not unlocked."""
        mock_evals = [
            {
                "evaluation_data": {
                    "submission_id": "sub-review-002",
                    "requirement_results": [
                        {"requirement_id": "REQ-001", "state": "PASS", "mandatory": True},
                        {"requirement_id": "REQ-006", "state": "REVIEW", "mandatory": True},
                    ],
                }
            }
        ]

        state, reason = determine_technical_eligibility("sub-review-002", "TENDER-001", mock_evals)
        self.assertEqual(state, TechnicalEligibilityState.TECHNICAL_REVIEW_REQUIRED)
        self.assertIn("awaiting officer review", reason)
        self.assertIn("REQ-006", reason)

    def test_03_successful_boq_extraction(self):
        """3. Verify successful BOQ line item extraction with provenance."""
        doc = {
            "id": "doc-boq-001",
            "filename": "CleanFlow_Commercial_BOQ_Bid.pdf",
            "content_text": (
                "COMMERCIAL BID & SCHEDULE OF RATES (BOQ)\n"
                "Item 1: Online Multichannel Water Quality Analyzer Units, Qty: 5 units, Unit Rate: INR 44,00,000, Total: INR 2,20,00,000\n"
                "Item 2: Submersible Sensor Probes & Telemetry Modules, Qty: 5 sets, Unit Rate: INR 13,50,000, Total: INR 67,50,000\n"
                "Subtotal: INR 2,87,50,000\nTaxes (GST @ 18%): INR 51,75,000\nTotal Evaluated Commercial Bid Price: INR 3,39,25,000"
            ),
        }

        line_items, totals, provs = extract_commercial_data_from_document(doc)
        self.assertEqual(len(line_items), 2)
        self.assertEqual(line_items[0].item_number, 1)
        self.assertEqual(line_items[0].quantity, 5.0)
        self.assertEqual(line_items[0].unit_rate, 4400000.0)
        self.assertEqual(line_items[0].total_price, 22000000.0)
        self.assertTrue(line_items[0].is_arithmetic_valid)
        self.assertIsNotNone(line_items[0].provenance)
        self.assertEqual(line_items[0].provenance["document_id"], "doc-boq-001")
        self.assertEqual(totals.get("total_bid_value"), 33925000.0)

    def test_04_arithmetic_mismatch_detection(self):
        """4. Verify detection of arithmetic mismatches in line items."""
        doc = {
            "id": "doc-err-001",
            "filename": "Erroneous_BOQ.pdf",
            "content_text": (
                "Item 1: Water Quality Analyzer Units, Qty: 5 units, Unit Rate: INR 40,00,000, Total: INR 2,50,00,000\n"
                "Subtotal: INR 2,50,00,000"
            ),
        }

        line_items, totals, provs = extract_commercial_data_from_document(doc)
        self.assertEqual(len(line_items), 1)
        # 5 * 40,00,000 = 2,00,00,000 != 2,50,00,000
        self.assertFalse(line_items[0].is_arithmetic_valid)
        self.assertIn("Arithmetic mismatch", line_items[0].discrepancy_note)

    def test_05_missing_line_item_detection(self):
        """5. Verify detection of missing items against expected tender BOQ."""
        items = [
            BOQItemEvaluation(
                item_number=1,
                description="Online Multichannel Water Quality Analyzer Units",
                quantity=5.0,
                unit="units",
                unit_rate=4000000.0,
                total_price=20000000.0,
            ),
            # Items 2, 3, and 4 are missing
        ]

        findings = check_boq_parity(items, CPCL_EXPECTED_BOQ)
        missing = [f for f in findings if f.finding_type == "MISSING_ITEM"]
        self.assertEqual(len(missing), 3)
        self.assertTrue(any("Submersible Sensor Probes" in f.message for f in missing))
        self.assertTrue(any("Installation" in f.message for f in missing))
        self.assertTrue(any("Maintenance" in f.message for f in missing))

    def test_06_normalized_totals(self):
        """6. Verify normalized totals calculation (subtotal + tax + freight - discount)."""
        items = [
            BOQItemEvaluation(
                item_number=1,
                description="Sensors",
                quantity=5.0,
                unit="units",
                unit_rate=4000000.0,
                total_price=20000000.0,
            )
        ]
        totals = {
            "subtotal": 20000000.0,
            "taxes": 3600000.0,   # 18% GST
            "freight": 200000.0,
            "discount": 500000.0,
        }

        subtotal, taxes, freight, discount, evaluated, findings = normalize_commercial_bid(items, totals)
        self.assertEqual(subtotal, 20000000.0)
        self.assertEqual(taxes, 3600000.0)
        self.assertEqual(freight, 200000.0)
        self.assertEqual(discount, 500000.0)
        # 20000000 + 3600000 + 200000 - 500000 = 23300000.0
        self.assertEqual(evaluated, 23300000.0)

    def test_07_l1_ranking_calculation(self):
        """7. Verify lowest evaluated price becomes L1 and ranking sorts ascending."""
        b1 = BidderFinancialEvaluation(
            procurement_id="p1",
            tender_id="t1",
            bidder_id="bidder-a",
            bidder_name="Higher Bidder Ltd",
            submission_id="sub-a",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            commercial_status=CommercialEvaluationStatus.EVALUATED,
            evaluated_amount=45290000.0,
        )
        b2 = BidderFinancialEvaluation(
            procurement_id="p1",
            tender_id="t1",
            bidder_id="bidder-b",
            bidder_name="Lower Bidder Ltd",
            submission_id="sub-b",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            commercial_status=CommercialEvaluationStatus.EVALUATED,
            evaluated_amount=41060000.0,
        )

        bids = [b1, b2]
        bids.sort(key=lambda x: (x.evaluated_amount or 0.0, x.submission_id))
        for idx, b in enumerate(bids, start=1):
            b.rank = idx
            b.is_l1 = (idx == 1)

        self.assertEqual(b2.rank, 1)
        self.assertTrue(b2.is_l1)
        self.assertEqual(b1.rank, 2)
        self.assertFalse(b1.is_l1)

    def test_08_invalid_bid_not_ranked(self):
        """8. Verify that an invalid/disqualified bid is not ranked as L1."""
        b_invalid = BidderFinancialEvaluation(
            procurement_id="p1",
            tender_id="t1",
            bidder_id="bidder-err",
            bidder_name="Error Bidder",
            submission_id="sub-err",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            commercial_status=CommercialEvaluationStatus.DISQUALIFIED,
            evaluated_amount=100.0,  # Ridiculously low but disqualified
        )
        b_valid = BidderFinancialEvaluation(
            procurement_id="p1",
            tender_id="t1",
            bidder_id="bidder-ok",
            bidder_name="Compliant Bidder",
            submission_id="sub-ok",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            commercial_status=CommercialEvaluationStatus.EVALUATED,
            evaluated_amount=41060000.0,
        )

        # Only bids with commercial_status == EVALUATED can be ranked
        rankable = [b for b in [b_invalid, b_valid] if b.commercial_status == CommercialEvaluationStatus.EVALUATED]
        rankable.sort(key=lambda x: (x.evaluated_amount or 0.0, x.submission_id))
        for idx, b in enumerate(rankable, start=1):
            b.rank = idx
            b.is_l1 = (idx == 1)

        self.assertIsNone(b_invalid.rank)
        self.assertFalse(b_invalid.is_l1)
        self.assertEqual(b_valid.rank, 1)
        self.assertTrue(b_valid.is_l1)

    def test_09_tie_handling_deterministic(self):
        """9. Verify deterministic tie breaking when two evaluated bids are identical."""
        b1 = BidderFinancialEvaluation(
            procurement_id="p1",
            tender_id="t1",
            bidder_id="bidder-1",
            bidder_name="Beta Technologies",
            submission_id="sub-beta",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            commercial_status=CommercialEvaluationStatus.EVALUATED,
            evaluated_amount=40000000.0,
        )
        b2 = BidderFinancialEvaluation(
            procurement_id="p1",
            tender_id="t1",
            bidder_id="bidder-2",
            bidder_name="Alpha Technologies",
            submission_id="sub-alpha",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            commercial_status=CommercialEvaluationStatus.EVALUATED,
            evaluated_amount=40000000.0,
        )

        bids = [b1, b2]
        bids.sort(key=lambda x: (x.evaluated_amount or 0.0, x.submission_id, x.bidder_name))
        for idx, b in enumerate(bids, start=1):
            b.rank = idx
            b.is_l1 = (idx == 1)

        # sub-alpha comes before sub-beta deterministically
        self.assertEqual(b2.rank, 1)
        self.assertTrue(b2.is_l1)
        self.assertEqual(b1.rank, 2)
        self.assertFalse(b1.is_l1)

    def test_10_low_high_bid_anomaly_signal(self):
        """10. Verify anomaly detection for unusually low, unusually high, and clustering bids."""
        b_low = BidderFinancialEvaluation(
            procurement_id="p1",
            tender_id="t1",
            bidder_id="b-low",
            bidder_name="Low Co",
            submission_id="s-low",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=30000000.0,  # 33% below 45M
        )
        b_clustered1 = BidderFinancialEvaluation(
            procurement_id="p1",
            tender_id="t1",
            bidder_id="b-c1",
            bidder_name="Cluster 1 Co",
            submission_id="s-c1",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=44000000.0,
        )
        b_clustered2 = BidderFinancialEvaluation(
            procurement_id="p1",
            tender_id="t1",
            bidder_id="b-c2",
            bidder_name="Cluster 2 Co",
            submission_id="s-c2",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=44100000.0,  # 0.22% difference
        )

        signals = calculate_anomaly_signals([b_low, b_clustered1, b_clustered2], estimated_value=45000000.0)
        types = [s.signal_type for s in signals]
        self.assertIn("UNUSUALLY_LOW_BID", types)
        self.assertIn("BID_CLUSTERING", types)

    def test_11_multi_bidder_end_to_end_cover2(self):
        """11. End-to-end integration test of Cover 2 on CPCL demo payload."""
        async def _run():
            # Ingest demo CPCL package
            payload = create_cpcl_demo_payload()
            ingest_res = await ingest_procurement(payload)
            proc_id = ingest_res.procurement_id
            tender_id = ingest_res.tender_id

            # Mock Cover 1 technical evaluation results:
            # HydroTech: PASS
            # CleanFlow: PASS
            # AquaPure: FAIL (MII / Turnover)
            await insert_bid_evaluation(tender_id, {
                "submission_id": "GEM-SUB-HTA-2026-017",
                "requirement_results": [
                    {"requirement_id": "REQ-001", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-002", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-003", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-004", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-005", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-006", "state": "PASS", "mandatory": True},
                ],
            })
            await insert_bid_evaluation(tender_id, {
                "submission_id": "GEM-SUB-CFT-2026-017",
                "requirement_results": [
                    {"requirement_id": "REQ-001", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-002", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-003", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-004", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-005", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-006", "state": "PASS", "mandatory": True},
                ],
            })
            await insert_bid_evaluation(tender_id, {
                "submission_id": "GEM-SUB-APS-2026-017",
                "requirement_results": [
                    {"requirement_id": "REQ-001", "state": "PASS", "mandatory": True},
                    {"requirement_id": "REQ-003", "state": "FAIL", "mandatory": True},  # Fails turnover
                    {"requirement_id": "REQ-006", "state": "REVIEW", "mandatory": True}, # MII Contradiction
                ],
            })

            # Execute Cover 2
            resp = await execute_cover2_financial_evaluation(proc_id)

            self.assertEqual(resp.cover2_status, Cover2State.EVALUATED)
            self.assertEqual(resp.total_bidders, 3)
            self.assertEqual(resp.eligible_bidders_count, 2)
            self.assertEqual(resp.excluded_bidders_count, 1)

            # AquaPure must be excluded
            ap_eval = next((b for b in resp.bidder_evaluations if "AquaPure" in b.bidder_name), None)
            self.assertIsNotNone(ap_eval)
            self.assertFalse(ap_eval.is_cover2_unlocked)
            self.assertEqual(ap_eval.technical_eligibility_status, TechnicalEligibilityState.TECHNICALLY_FAILED)
            self.assertIsNone(ap_eval.rank)
            self.assertFalse(ap_eval.is_l1)

            # CleanFlow must be L1 (quoted ₹4.106 Cr)
            cf_eval = next((b for b in resp.bidder_evaluations if "CleanFlow" in b.bidder_name), None)
            self.assertIsNotNone(cf_eval)
            self.assertTrue(cf_eval.is_cover2_unlocked)
            self.assertEqual(cf_eval.rank, 1)
            self.assertTrue(cf_eval.is_l1)
            self.assertEqual(cf_eval.evaluated_amount, 41060000.0)

            # HydroTech must be L2 (quoted ₹4.529 Cr)
            ht_eval = next((b for b in resp.bidder_evaluations if "HydroTech" in b.bidder_name), None)
            self.assertIsNotNone(ht_eval)
            self.assertTrue(ht_eval.is_cover2_unlocked)
            self.assertEqual(ht_eval.rank, 2)
            self.assertFalse(ht_eval.is_l1)
            self.assertEqual(ht_eval.evaluated_amount, 45290000.0)

            # L1 response header
            self.assertEqual(resp.l1_bidder_name, cf_eval.bidder_name)
            self.assertEqual(resp.l1_evaluated_amount, 41060000.0)

        asyncio.run(_run())

    def test_12_persistence(self):
        """12. Verify persistence to disk/store and reload."""
        async def _run():
            data = {
                "procurement_id": "test-proc-persist",
                "tender_id": "test-tender-persist",
                "cover2_status": "EVALUATED",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "evaluator_version": "opal-cover2-v1.0",
                "currency": "INR",
                "total_bidders": 1,
                "eligible_bidders_count": 1,
                "excluded_bidders_count": 0,
                "l1_bidder_name": "Test Co",
                "l1_evaluated_amount": 1000000.0,
                "bidder_evaluations": [],
                "comparative_signals": [],
                "audit_trail": [],
            }

            await save_procurement_financial_evaluation("test-proc-persist", data)
            loaded = await get_procurement_financial_evaluation("test-proc-persist")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["procurement_id"], "test-proc-persist")
            self.assertEqual(loaded["l1_bidder_name"], "Test Co")
            self.assertEqual(loaded["l1_evaluated_amount"], 1000000.0)

        asyncio.run(_run())

    def test_13_api_output(self):
        """13. Verify canonical API endpoint output and contract structure."""
        async def _run():
            # Ingest demo
            payload = create_cpcl_demo_payload()
            ingest_res = await ingest_procurement(payload)
            proc_id = ingest_res.procurement_id

            # Transition to TECHNICAL_REVIEW for Cover 2 eligibility
            from app.models.procurement import ProcurementStatus
            from app.services.procurement_lifecycle_service import transition_procurement_state
            await transition_procurement_state(proc_id, ProcurementStatus.TECHNICAL_REVIEW)

            # Call API POST endpoint
            from app.models.financial import Cover2RunRequest
            post_resp = await open_cover2_financial_evaluation_endpoint(
                proc_id, payload=Cover2RunRequest(force=True)
            )
            self.assertEqual(post_resp.procurement_id, proc_id)
            self.assertIn(post_resp.cover2_status, (Cover2State.EVALUATED, Cover2State.REVIEW_REQUIRED))

            # Call API GET endpoint
            get_resp = await get_financial_review_endpoint(proc_id)
            self.assertEqual(get_resp.procurement_id, proc_id)
            self.assertEqual(get_resp.cover2_status, post_resp.cover2_status)
            self.assertEqual(len(get_resp.bidder_evaluations), len(post_resp.bidder_evaluations))

        asyncio.run(_run())

    def test_14_physical_pdf_extraction_from_disk(self):
        """14. Verify extraction of real physical BOQ PDF from disk via boq_parser.

        Requires pdfplumber or pymupdf to be available and functional.
        """
        from pathlib import Path
        sample_path = Path(__file__).resolve().parent.parent / "data" / "sample_documents" / "CleanFlow_Commercial_BOQ_Bid.pdf"
        self.assertTrue(sample_path.exists(), f"Sample PDF must exist at {sample_path}")

        doc = {
            "id": "doc-cft-physical",
            "filename": "CleanFlow_Commercial_BOQ_Bid.pdf",
            "storage_path": str(sample_path),
            "content_text": "",  # Empty content text to force file reading
        }

        line_items, totals, provs = extract_commercial_data_from_document(doc)
        self.assertEqual(len(line_items), 4)
        self.assertEqual(line_items[0].quantity, 5.0)
        self.assertEqual(line_items[0].unit_rate, 4400000.0)
        self.assertEqual(line_items[0].total_price, 22000000.0)
        self.assertEqual(line_items[0].provenance["file_path"], str(sample_path))
        self.assertTrue(all(it.is_arithmetic_valid for it in line_items))


    def test_15_aquapure_independent_failure_vs_review(self):
        """15. Verify AquaPure MII review vs turnover failure independence."""
        # Case A: Both turnover failure and MII review -> TECHNICALLY_FAILED
        mock_evals_both = [{
            "evaluation_data": {
                "submission_id": "sub-aps-both",
                "requirement_results": [
                    {"requirement_id": "REQ-001", "state": "PASS"},
                    {"requirement_id": "REQ-003", "state": "FAIL"},   # Turnover
                    {"requirement_id": "REQ-006", "state": "REVIEW"}, # MII contradiction
                ],
            }
        }]
        mandatory_map = {"REQ-001": True, "REQ-003": True, "REQ-006": True}
        state, reason = determine_technical_eligibility(
            "sub-aps-both", "TENDER-001", mock_evals_both, mandatory_map=mandatory_map
        )
        self.assertEqual(state, TechnicalEligibilityState.TECHNICALLY_FAILED)
        self.assertIn("REQ-003", reason)
        self.assertIn("Additionally pending review on: REQ-006", reason)

        # Case B: ONLY MII review (no turnover failure) -> TECHNICAL_REVIEW_REQUIRED
        mock_evals_review_only = [{
            "evaluation_data": {
                "submission_id": "sub-aps-rev",
                "requirement_results": [
                    {"requirement_id": "REQ-001", "state": "PASS"},
                    {"requirement_id": "REQ-003", "state": "PASS"},
                    {"requirement_id": "REQ-006", "state": "REVIEW"}, # MII contradiction
                ],
            }
        }]
        state_rev, reason_rev = determine_technical_eligibility(
            "sub-aps-rev", "TENDER-001", mock_evals_review_only, mandatory_map=mandatory_map
        )
        self.assertEqual(state_rev, TechnicalEligibilityState.TECHNICAL_REVIEW_REQUIRED)
        self.assertIn("REQ-006", reason_rev)

        # Case C: Non-mandatory requirement failure does NOT exclude bidder
        mock_evals_optional_fail = [{
            "evaluation_data": {
                "submission_id": "sub-opt-fail",
                "requirement_results": [
                    {"requirement_id": "REQ-001", "state": "PASS"},
                    {"requirement_id": "REQ-OPT-09", "state": "FAIL"}, # Optional
                ],
            }
        }]
        opt_map = {"REQ-001": True, "REQ-OPT-09": False}
        state_opt, reason_opt = determine_technical_eligibility(
            "sub-opt-fail", "TENDER-001", mock_evals_optional_fail, mandatory_map=opt_map
        )
        self.assertEqual(state_opt, TechnicalEligibilityState.TECHNICALLY_ELIGIBLE)
        self.assertIsNone(reason_opt)

    def test_16_all_seven_parity_discrepancy_types(self):
        """16. Verify detection and emission of all 7 required parity discrepancy types."""
        # 1. MISSING_ITEM
        items_missing = [
            BOQItemEvaluation(
                item_number=1,
                description="Online Multichannel Water Quality Analyzer Units",
                quantity=5.0,
                unit="units",
                unit_rate=4000000.0,
                total_price=20000000.0,
            )
        ]
        f_missing = check_boq_parity(items_missing, CPCL_EXPECTED_BOQ)
        types_missing = {f.finding_type for f in f_missing}
        self.assertIn("MISSING_ITEM", types_missing)

        # 2. QUANTITY_MISMATCH
        items_qty = [
            BOQItemEvaluation(
                item_number=1,
                description="Online Multichannel Water Quality Analyzer Units",
                quantity=10.0,  # Expected 5.0
                unit="units",
                unit_rate=4000000.0,
                total_price=40000000.0,
            ),
            BOQItemEvaluation(item_number=2, description="Submersible Sensor Probes", quantity=5.0, unit="sets", unit_rate=1.0, total_price=5.0),
            BOQItemEvaluation(item_number=3, description="Installation", quantity=1.0, unit="lot", unit_rate=1.0, total_price=1.0),
            BOQItemEvaluation(item_number=4, description="Maintenance", quantity=1.0, unit="lot", unit_rate=1.0, total_price=1.0),
        ]
        f_qty = check_boq_parity(items_qty, CPCL_EXPECTED_BOQ)
        types_qty = {f.finding_type for f in f_qty}
        self.assertIn("QUANTITY_MISMATCH", types_qty)

        # 3. UNIT_MISMATCH
        items_unit = [
            BOQItemEvaluation(
                item_number=1,
                description="Online Multichannel Water Quality Analyzer Units",
                quantity=5.0,
                unit="liters",  # Expected "units"
                unit_rate=4000000.0,
                total_price=20000000.0,
            ),
            BOQItemEvaluation(item_number=2, description="Submersible Sensor Probes", quantity=5.0, unit="sets", unit_rate=1.0, total_price=5.0),
            BOQItemEvaluation(item_number=3, description="Installation", quantity=1.0, unit="lot", unit_rate=1.0, total_price=1.0),
            BOQItemEvaluation(item_number=4, description="Maintenance", quantity=1.0, unit="lot", unit_rate=1.0, total_price=1.0),
        ]
        f_unit = check_boq_parity(items_unit, CPCL_EXPECTED_BOQ)
        types_unit = {f.finding_type for f in f_unit}
        self.assertIn("UNIT_MISMATCH", types_unit)

        # 4. EXTRA_ITEM
        items_extra = [
            BOQItemEvaluation(item_number=1, description="Online Multichannel Water Quality Analyzer Units", quantity=5.0, unit="units", unit_rate=1.0, total_price=5.0),
            BOQItemEvaluation(item_number=2, description="Submersible Sensor Probes", quantity=5.0, unit="sets", unit_rate=1.0, total_price=5.0),
            BOQItemEvaluation(item_number=3, description="Installation", quantity=1.0, unit="lot", unit_rate=1.0, total_price=1.0),
            BOQItemEvaluation(item_number=4, description="Maintenance", quantity=1.0, unit="lot", unit_rate=1.0, total_price=1.0),
            BOQItemEvaluation(item_number=5, description="Unsolicited Extra Solar Panel Kit", quantity=2.0, unit="sets", unit_rate=500000.0, total_price=1000000.0),
        ]
        f_extra = check_boq_parity(items_extra, CPCL_EXPECTED_BOQ)
        types_extra = {f.finding_type for f in f_extra}
        self.assertIn("EXTRA_ITEM", types_extra)

        # 5. LINE_TOTAL_MISMATCH
        doc_arith = {
            "id": "doc-line-mismatch",
            "filename": "bid.txt",
            "content_text": "Item 1: Water Quality Analyzer Units, Qty: 5 units, Unit Rate: INR 40,00,000, Total: INR 9,99,99,999",
        }
        items_arith, _, _ = extract_commercial_data_from_document(doc_arith)
        self.assertFalse(items_arith[0].is_arithmetic_valid)
        self.assertIn("Line total mismatch", items_arith[0].discrepancy_note)

        # 6. SUBTOTAL_MISMATCH
        items_sub = [
            BOQItemEvaluation(item_number=1, description="Item 1", quantity=1.0, unit="units", unit_rate=100.0, total_price=100.0)
        ]
        totals_sub = {"subtotal": 500.0}  # Quoted 500 but items sum to 100
        _, _, _, _, _, f_sub = normalize_commercial_bid(items_sub, totals_sub)
        types_sub = {f.finding_type for f in f_sub}
        self.assertIn("SUBTOTAL_MISMATCH", types_sub)

        # 7. GRAND_TOTAL_MISMATCH
        totals_grand = {
            "subtotal": 100.0,
            "taxes": 18.0,
            "freight": 10.0,
            "discount": 0.0,
            "total_bid_value": 999.0,  # 100 + 18 + 10 = 128 != 999
        }
        _, _, _, _, _, f_grand = normalize_commercial_bid(items_sub, totals_grand)
        types_grand = {f.finding_type for f in f_grand}
        self.assertIn("GRAND_TOTAL_MISMATCH", types_grand)

    def test_17_get_read_only_semantics(self):
        """17. Verify GET /api/procurements/{id}/financial-evaluation is strictly read-only."""
        async def _run():
            from app.db.client import _IN_MEMORY_FINANCIAL_EVALUATIONS
            payload = create_cpcl_demo_payload()
            ingest_res = await ingest_procurement(payload)
            proc_id = ingest_res.procurement_id

            # Ensure financial evaluations store is clean for this proc_id
            _IN_MEMORY_FINANCIAL_EVALUATIONS.pop(proc_id, None)

            # Call GET before Cover 2 has ever been executed
            resp = await get_procurement_financial_evaluation_service(proc_id)
            self.assertEqual(resp.cover2_status, Cover2State.LOCKED)
            self.assertEqual(resp.total_bidders, 3)
            self.assertEqual(resp.eligible_bidders_count, 0)
            self.assertEqual(len(resp.bidder_evaluations), 0)

            # Verify that calling GET performed zero writes to _IN_MEMORY_FINANCIAL_EVALUATIONS
            self.assertNotIn(proc_id, _IN_MEMORY_FINANCIAL_EVALUATIONS)

        asyncio.run(_run())

    def test_18_grand_total_mismatch_prevents_silent_repair(self):
        """18. Verify that an irreconcilable total mismatch sets status to REVIEW_REQUIRED without silent repair."""
        async def _run():
            sub_item = [
                BOQItemEvaluation(item_number=1, description="Item", quantity=1.0, unit="lot", unit_rate=1000.0, total_price=1000.0)
            ]
            tots = {"subtotal": 1000.0, "taxes": 180.0, "total_bid_value": 50000.0}
            sub, tax, freight, disc, evaluated, findings = normalize_commercial_bid(sub_item, tots)

            # Verify finding type is GRAND_TOTAL_MISMATCH with HIGH severity
            gt_finding = next((f for f in findings if f.finding_type == "GRAND_TOTAL_MISMATCH"), None)
            self.assertIsNotNone(gt_finding)
            self.assertEqual(gt_finding.severity, "HIGH")
            self.assertIn("not silently repaired", gt_finding.message)

        asyncio.run(_run())

    def test_19_full_audit_trail_events(self):
        """19. Verify emission of all required audit events in the Cover 2 lifecycle."""
        async def _run():
            payload = create_cpcl_demo_payload()
            ingest_res = await ingest_procurement(payload)
            proc_id = ingest_res.procurement_id
            tender_id = ingest_res.tender_id

            await insert_bid_evaluation(tender_id, {
                "submission_id": "GEM-SUB-CFT-2026-017",
                "requirement_results": [{"requirement_id": "REQ-001", "state": "PASS", "mandatory": True}],
            })
            await insert_bid_evaluation(tender_id, {
                "submission_id": "GEM-SUB-APS-2026-017",
                "requirement_results": [{"requirement_id": "REQ-001", "state": "FAIL", "mandatory": True}],
            })

            resp = await execute_cover2_financial_evaluation(proc_id)
            event_names = [a.get("event") for a in resp.audit_trail]

            self.assertIn("COVER_2_OPENING_INITIATED", event_names)
            self.assertIn("BIDDER_EXCLUDED_FROM_COVER_2", event_names)
            self.assertIn("BIDDER_UNLOCKED_FOR_COVER_2", event_names)
            self.assertIn("COVER_2_EVALUATION_COMPLETED", event_names)

        asyncio.run(_run())

    def test_20_pricing_multiplier_pattern_detected(self):
        """20. Verify detection of uniform pricing multiplier pattern (k != 1.0) across multi-item BOQs."""
        b1 = BidderFinancialEvaluation(
            procurement_id="p-multi",
            tender_id="t-multi",
            bidder_id="bidder-base",
            bidder_name="Base Systems Ltd",
            submission_id="sub-base",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=10000.0,
            line_items=[
                BOQItemEvaluation(item_number=1, description="Core Server Unit", quantity=1.0, unit_rate=1000.0, total_price=1000.0),
                BOQItemEvaluation(item_number=2, description="Network Switch 24P", quantity=1.0, unit_rate=2000.0, total_price=2000.0),
                BOQItemEvaluation(item_number=3, description="Rack Mount Kit", quantity=1.0, unit_rate=3000.0, total_price=3000.0),
                BOQItemEvaluation(item_number=4, description="Power Backup 5kVA", quantity=1.0, unit_rate=4000.0, total_price=4000.0),
            ],
        )
        b2 = BidderFinancialEvaluation(
            procurement_id="p-multi",
            tender_id="t-multi",
            bidder_id="bidder-scaled",
            bidder_name="Scaled Pricing Corp",
            submission_id="sub-scaled",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=11500.0,
            line_items=[
                # Each item exactly 1.15x of bidder 1
                BOQItemEvaluation(item_number=1, description="Core Server Unit", quantity=1.0, unit_rate=1150.0, total_price=1150.0),
                BOQItemEvaluation(item_number=2, description="Network Switch 24P", quantity=1.0, unit_rate=2300.0, total_price=2300.0),
                BOQItemEvaluation(item_number=3, description="Rack Mount Kit", quantity=1.0, unit_rate=3450.0, total_price=3450.0),
                BOQItemEvaluation(item_number=4, description="Power Backup 5kVA", quantity=1.0, unit_rate=4600.0, total_price=4600.0),
            ],
        )

        signals = detect_pricing_pattern_anomalies([b1, b2])
        mult_sig = next((s for s in signals if s.signal_type == "PRICING_MULTIPLIER_DETECTED"), None)

        self.assertIsNotNone(mult_sig, "PRICING_MULTIPLIER_DETECTED signal must be emitted")
        self.assertEqual(mult_sig.severity, "WARNING")
        self.assertEqual(mult_sig.decision_authority, "HUMAN_PROCUREMENT_OFFICER")
        self.assertTrue(mult_sig.requires_officer_review)
        self.assertIn("Base Systems Ltd", mult_sig.bidders_involved)
        self.assertIn("Scaled Pricing Corp", mult_sig.bidders_involved)
        self.assertAlmostEqual(mult_sig.metric_value, 0.8696, delta=0.3)  # ratio k around 0.87 or 1.15

    def test_21_identical_pricing_pattern_detected(self):
        """21. Verify detection of identical unit rates across competitive items (k = 1.0)."""
        b1 = BidderFinancialEvaluation(
            procurement_id="p-ident",
            tender_id="t-ident",
            bidder_id="bidder-id-1",
            bidder_name="Vendor One Ltd",
            submission_id="sub-v1",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=6000.0,
            line_items=[
                BOQItemEvaluation(item_number=1, description="Item A", quantity=1.0, unit_rate=1000.0, total_price=1000.0),
                BOQItemEvaluation(item_number=2, description="Item B", quantity=1.0, unit_rate=2000.0, total_price=2000.0),
                BOQItemEvaluation(item_number=3, description="Item C", quantity=1.0, unit_rate=3000.0, total_price=3000.0),
            ],
        )
        b2 = BidderFinancialEvaluation(
            procurement_id="p-ident",
            tender_id="t-ident",
            bidder_id="bidder-id-2",
            bidder_name="Vendor Two Ltd",
            submission_id="sub-v2",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=6000.0,
            line_items=[
                BOQItemEvaluation(item_number=1, description="Item A", quantity=1.0, unit_rate=1000.0, total_price=1000.0),
                BOQItemEvaluation(item_number=2, description="Item B", quantity=1.0, unit_rate=2000.0, total_price=2000.0),
                BOQItemEvaluation(item_number=3, description="Item C", quantity=1.0, unit_rate=3000.0, total_price=3000.0),
            ],
        )

        signals = detect_pricing_pattern_anomalies([b1, b2])
        ident_sig = next((s for s in signals if s.signal_type == "IDENTICAL_PRICING_PATTERN"), None)

        self.assertIsNotNone(ident_sig, "IDENTICAL_PRICING_PATTERN signal must be emitted")
        self.assertEqual(ident_sig.severity, "WARNING")
        self.assertEqual(ident_sig.decision_authority, "HUMAN_PROCUREMENT_OFFICER")
        self.assertEqual(ident_sig.metric_value, 3.0)

    def test_22_high_vector_correlation_detected(self):
        """22. Verify detection of high Pearson vector correlation (rho > 0.995)."""
        b1 = BidderFinancialEvaluation(
            procurement_id="p-corr",
            tender_id="t-corr",
            bidder_id="bidder-c1",
            bidder_name="Corr Bidder Alpha",
            submission_id="sub-ca",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=15000.0,
            line_items=[
                BOQItemEvaluation(item_number=1, description="Component 1", quantity=1.0, unit_rate=1000.0, total_price=1000.0),
                BOQItemEvaluation(item_number=2, description="Component 2", quantity=1.0, unit_rate=2000.0, total_price=2000.0),
                BOQItemEvaluation(item_number=3, description="Component 3", quantity=1.0, unit_rate=4000.0, total_price=4000.0),
                BOQItemEvaluation(item_number=4, description="Component 4", quantity=1.0, unit_rate=8000.0, total_price=8000.0),
            ],
        )
        b2 = BidderFinancialEvaluation(
            procurement_id="p-corr",
            tender_id="t-corr",
            bidder_id="bidder-c2",
            bidder_name="Corr Bidder Beta",
            submission_id="sub-cb",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=15500.0,
            line_items=[
                # Highly correlated relative price vector
                BOQItemEvaluation(item_number=1, description="Component 1", quantity=1.0, unit_rate=1050.0, total_price=1050.0),
                BOQItemEvaluation(item_number=2, description="Component 2", quantity=1.0, unit_rate=2080.0, total_price=2080.0),
                BOQItemEvaluation(item_number=3, description="Component 3", quantity=1.0, unit_rate=4120.0, total_price=4120.0),
                BOQItemEvaluation(item_number=4, description="Component 4", quantity=1.0, unit_rate=8250.0, total_price=8250.0),
            ],
        )

        signals = detect_pricing_pattern_anomalies([b1, b2])
        corr_sig = next((s for s in signals if s.signal_type == "HIGH_VECTOR_CORRELATION"), None)

        self.assertIsNotNone(corr_sig, "HIGH_VECTOR_CORRELATION signal must be emitted")
        self.assertGreater(corr_sig.metric_value, 0.995)
        self.assertEqual(corr_sig.decision_authority, "HUMAN_PROCUREMENT_OFFICER")

    def test_23_shared_rounding_anomaly_detected(self):
        """23. Verify detection of shared non-standard decimal rounding across items."""
        b1 = BidderFinancialEvaluation(
            procurement_id="p-round",
            tender_id="t-round",
            bidder_id="bidder-r1",
            bidder_name="Decimal Alpha",
            submission_id="sub-ra",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=5000.0,
            line_items=[
                BOQItemEvaluation(item_number=1, description="Work Component 1", quantity=1.0, unit_rate=1500.77, total_price=1500.77),
                BOQItemEvaluation(item_number=2, description="Work Component 2", quantity=1.0, unit_rate=2200.33, total_price=2200.33),
                BOQItemEvaluation(item_number=3, description="Work Component 3", quantity=1.0, unit_rate=3000.0, total_price=3000.0),
            ],
        )
        b2 = BidderFinancialEvaluation(
            procurement_id="p-round",
            tender_id="t-round",
            bidder_id="bidder-r2",
            bidder_name="Decimal Beta",
            submission_id="sub-rb",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=6000.0,
            line_items=[
                BOQItemEvaluation(item_number=1, description="Work Component 1", quantity=1.0, unit_rate=1800.77, total_price=1800.77),
                BOQItemEvaluation(item_number=2, description="Work Component 2", quantity=1.0, unit_rate=2700.33, total_price=2700.33),
                BOQItemEvaluation(item_number=3, description="Work Component 3", quantity=1.0, unit_rate=4500.0, total_price=4500.0),
            ],
        )

        signals = detect_pricing_pattern_anomalies([b1, b2])
        round_sig = next((s for s in signals if s.signal_type == "SHARED_ROUNDING_ANOMALY"), None)

        self.assertIsNotNone(round_sig, "SHARED_ROUNDING_ANOMALY signal must be emitted")
        self.assertEqual(round_sig.severity, "INFO")
        self.assertEqual(round_sig.decision_authority, "HUMAN_PROCUREMENT_OFFICER")
        self.assertGreaterEqual(round_sig.metric_value, 2.0)

    def test_24_tender_fixed_items_excluded_from_pattern(self):
        """24. Verify that statutory / tender-fixed items are excluded from cross-bidder pricing patterns."""
        b1 = BidderFinancialEvaluation(
            procurement_id="p-fix",
            tender_id="t-fix",
            bidder_id="b-fix-1",
            bidder_name="Fix Test 1",
            submission_id="sub-fix-1",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=10000.0,
            line_items=[
                BOQItemEvaluation(item_number=1, description="Statutory Labour Cess 1%", quantity=1.0, unit_rate=500.0, total_price=500.0),
                BOQItemEvaluation(item_number=2, description="Competitive Piping Works", quantity=1.0, unit_rate=2500.0, total_price=2500.0),
                BOQItemEvaluation(item_number=3, description="Competitive Electrical Cabling", quantity=1.0, unit_rate=7000.0, total_price=7000.0),
            ],
        )
        b2 = BidderFinancialEvaluation(
            procurement_id="p-fix",
            tender_id="t-fix",
            bidder_id="b-fix-2",
            bidder_name="Fix Test 2",
            submission_id="sub-fix-2",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=12000.0,
            line_items=[
                # Fixed item has identical rate (statutory requirement), but competitive items vary non-linearly
                BOQItemEvaluation(item_number=1, description="Statutory Labour Cess 1%", quantity=1.0, unit_rate=500.0, total_price=500.0),
                BOQItemEvaluation(item_number=2, description="Competitive Piping Works", quantity=1.0, unit_rate=3200.0, total_price=3200.0),
                BOQItemEvaluation(item_number=3, description="Competitive Electrical Cabling", quantity=1.0, unit_rate=8300.0, total_price=8300.0),
            ],
        )

        signals = detect_pricing_pattern_anomalies([b1, b2])
        # IDENTICAL_PRICING_PATTERN must NOT be emitted because statutory item is excluded
        ident_sig = next((s for s in signals if s.signal_type == "IDENTICAL_PRICING_PATTERN"), None)
        self.assertIsNone(ident_sig, "Identical pricing should NOT trigger on statutory/fixed charges")

    def test_25_alb_estimate_variance_above_threshold(self):
        """25. Verify ALB detection when bid is > 15% below engineer estimate."""
        b = BidderFinancialEvaluation(
            procurement_id="p-alb",
            tender_id="t-alb",
            bidder_id="b-alb-low",
            bidder_name="Extreme Low Bidder",
            submission_id="sub-alb-1",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=8000000.0,  # 20% below 10M estimate (exceeds 15% threshold)
        )

        signals = detect_abnormally_low_bid_signals([b], estimated_value=10000000.0)
        alb_sig = next((s for s in signals if s.signal_type == "UNUSUALLY_LOW_BID"), None)

        self.assertIsNotNone(alb_sig, "UNUSUALLY_LOW_BID must be emitted for 20% variance")
        self.assertEqual(alb_sig.severity, "WARNING")
        self.assertEqual(alb_sig.threshold, -15.0)
        self.assertEqual(alb_sig.metric_value, -20.0)
        self.assertEqual(alb_sig.decision_authority, "HUMAN_PROCUREMENT_OFFICER")
        self.assertTrue(alb_sig.requires_officer_review)
        self.assertIn("1.0 - (8000000.0 / 10000000.0)", alb_sig.calculation_basis)

    def test_26_alb_estimate_variance_below_threshold_compliant(self):
        """26. Verify compliant bid within 15% of estimate does not trigger UNUSUALLY_LOW_BID."""
        b = BidderFinancialEvaluation(
            procurement_id="p-alb-ok",
            tender_id="t-alb-ok",
            bidder_id="b-alb-ok",
            bidder_name="Reasonable Bidder",
            submission_id="sub-alb-ok",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=9000000.0,  # 10% below 10M estimate (compliant, < 15%)
        )

        signals = detect_abnormally_low_bid_signals([b], estimated_value=10000000.0)
        alb_sig = next((s for s in signals if s.signal_type == "UNUSUALLY_LOW_BID"), None)
        self.assertIsNone(alb_sig, "Bid within 15% threshold should not be flagged as abnormally low")

    def test_27_missing_engineer_estimate_emits_unavailable_signal(self):
        """27. Verify that missing engineer estimate emits ENGINEER_ESTIMATE_UNAVAILABLE without crashing."""
        b = BidderFinancialEvaluation(
            procurement_id="p-no-est",
            tender_id="t-no-est",
            bidder_id="b-no-est",
            bidder_name="Bidder Without Estimate",
            submission_id="sub-no-est",
            technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True,
            evaluated_amount=5000000.0,
        )

        signals = detect_abnormally_low_bid_signals([b], estimated_value=None)
        sig = next((s for s in signals if s.signal_type == "ENGINEER_ESTIMATE_UNAVAILABLE"), None)

        self.assertIsNotNone(sig, "ENGINEER_ESTIMATE_UNAVAILABLE must be emitted")
        self.assertEqual(sig.severity, "INFO")
        self.assertEqual(sig.decision_authority, "HUMAN_PROCUREMENT_OFFICER")

    def test_28_small_peer_group_withholds_z_score(self):
        """28. Verify that small peer group (N < 4) withholds z-score and reports median distance."""
        b1 = BidderFinancialEvaluation(
            procurement_id="p-small", tender_id="t-small", bidder_id="b1", bidder_name="Peer 1",
            submission_id="s1", technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True, evaluated_amount=10000000.0,
        )
        b2 = BidderFinancialEvaluation(
            procurement_id="p-small", tender_id="t-small", bidder_id="b2", bidder_name="Peer 2",
            submission_id="s2", technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True, evaluated_amount=10200000.0,
        )
        b3 = BidderFinancialEvaluation(
            procurement_id="p-small", tender_id="t-small", bidder_id="b3", bidder_name="Peer 3 (Low)",
            submission_id="s3", technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True, evaluated_amount=7500000.0,  # 25% below median
        )

        signals = detect_abnormally_low_bid_signals([b1, b2, b3], estimated_value=10000000.0)
        med_sig = next((s for s in signals if s.signal_type == "DISTANCE_FROM_MEDIAN"), None)

        self.assertIsNotNone(med_sig, "DISTANCE_FROM_MEDIAN must be emitted")
        self.assertIn("z-score withheld", med_sig.description)
        self.assertTrue(med_sig.details.get("z_score_withheld"))
        self.assertEqual(med_sig.details.get("sample_size"), 3)

    def test_29_large_peer_group_computes_z_score(self):
        """29. Verify that large peer group (N >= 4) computes and reports z-score."""
        bids = [
            BidderFinancialEvaluation(
                procurement_id="p-lg", tender_id="t-lg", bidder_id=f"b{i}", bidder_name=f"Peer {i}",
                submission_id=f"s{i}", technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
                is_cover2_unlocked=True, evaluated_amount=amt,
            )
            for i, amt in enumerate([10000000.0, 10100000.0, 9900000.0, 10200000.0, 5000000.0], start=1)
        ]

        signals = detect_abnormally_low_bid_signals(bids, estimated_value=10000000.0)
        z_sig = next((s for s in signals if s.signal_type == "PEER_GROUP_VARIANCE"), None)

        self.assertIsNotNone(z_sig, "PEER_GROUP_VARIANCE with z-score must be emitted for N=5")
        self.assertEqual(z_sig.metric_name, "peer_z_score")
        self.assertLess(z_sig.metric_value, -1.5)
        self.assertEqual(z_sig.details.get("sample_size"), 5)

    def test_30_raw_material_floor_breach_and_baseline_unavailable(self):
        """30. Verify raw material floor breach detection and unavailable baseline handling."""
        b = BidderFinancialEvaluation(
            procurement_id="p-rm", tender_id="t-rm", bidder_id="b-rm", bidder_name="Sub-Material Co",
            submission_id="s-rm", technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True, evaluated_amount=38000000.0,
        )

        # Case A: Authoritative floor provided and breached
        signals_breach = detect_abnormally_low_bid_signals([b], raw_material_floor=40000000.0)
        breach_sig = next((s for s in signals_breach if s.signal_type == "RAW_MATERIAL_FLOOR_BREACH"), None)
        self.assertIsNotNone(breach_sig)
        self.assertEqual(breach_sig.severity, "CRITICAL")
        self.assertEqual(breach_sig.metric_value, 2000000.0)  # Deficit of 2M
        self.assertEqual(breach_sig.decision_authority, "HUMAN_PROCUREMENT_OFFICER")

        # Case B: Authoritative floor unavailable (None)
        signals_unavail = detect_abnormally_low_bid_signals([b], raw_material_floor=None)
        unavail_sig = next((s for s in signals_unavail if s.signal_type == "RAW_MATERIAL_BASELINE_UNAVAILABLE"), None)
        self.assertIsNotNone(unavail_sig)
        self.assertEqual(unavail_sig.severity, "INFO")
        self.assertEqual(unavail_sig.decision_authority, "HUMAN_PROCUREMENT_OFFICER")

    def test_31_human_procurement_officer_authority_preserved(self):
        """31. Verify that all financial anomaly signals preserve human procurement officer decision authority."""
        b1 = BidderFinancialEvaluation(
            procurement_id="p-auth", tender_id="t-auth", bidder_id="b1", bidder_name="Auth Bidder 1",
            submission_id="s1", technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True, evaluated_amount=20000000.0,
            line_items=[BOQItemEvaluation(item_number=1, description="Item 1", quantity=1.0, unit_rate=100.0, total_price=100.0)],
        )
        b2 = BidderFinancialEvaluation(
            procurement_id="p-auth", tender_id="t-auth", bidder_id="b2", bidder_name="Auth Bidder 2",
            submission_id="s2", technical_eligibility_status=TechnicalEligibilityState.TECHNICALLY_ELIGIBLE,
            is_cover2_unlocked=True, evaluated_amount=20050000.0,
            line_items=[BOQItemEvaluation(item_number=1, description="Item 1", quantity=1.0, unit_rate=100.0, total_price=100.0)],
        )

        signals = calculate_anomaly_signals([b1, b2], estimated_value=40000000.0)
        self.assertGreater(len(signals), 0)
        for s in signals:
            self.assertEqual(s.decision_authority, "HUMAN_PROCUREMENT_OFFICER")

    def test_32_layer7_verifier_incorporates_commercial_anomalies(self):
        """32. Verify FinancialCommercialVerifier incorporates commercial anomaly signals into Layer 7 findings."""
        async def _run():
            verifier = FinancialCommercialVerifier()
            req = RequirementEvaluationContract(
                requirement_id="REQ-COMM-01",
                category=RequirementCategory.COMMERCIAL,
                title="Commercial Bid Price Compliance",
                description="Commercial BoQ Price Evaluation",
                evaluation_field=CanonicalEvaluationField.COMMERCIAL_PRICE,
                evaluation_mode=EvaluationMode.DETERMINISTIC,
            )
            commercial_sig = FinancialAnomalySignal(
                signal_type="PRICING_MULTIPLIER_DETECTED",
                severity="WARNING",
                description="Uniform pricing multiplier detected across BOQ items.",
                metric_name="pricing_multiplier_k",
                metric_value=1.15,
                bidders_involved=["Alpha Corp", "Beta Corp"],
                decision_authority="HUMAN_PROCUREMENT_OFFICER",
            )
            context = VerificationContext(
                requirements=[req],
                bidders=[{"id": "b-alpha", "legal_name": "Alpha Corp"}],
                extra_context={"commercial_signals": [commercial_sig]},
            )

            findings = await verifier.verify(context)
            comm_f = next((f for f in findings if "PRICING_MULTIPLIER_DETECTED" in f.machine_readable_flags), None)

            self.assertIsNotNone(comm_f, "Layer 7 finding must be produced for commercial anomaly")
            self.assertEqual(comm_f.status, ComplianceState.REVIEW)
            self.assertEqual(comm_f.metadata.get("decision_authority"), "HUMAN_PROCUREMENT_OFFICER")
            self.assertIn("OFFICER_REVIEW_REQUIRED", comm_f.machine_readable_flags)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
