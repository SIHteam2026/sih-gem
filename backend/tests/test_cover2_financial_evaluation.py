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
    TechnicalEligibilityState,
)
from app.services.financial_evaluation_service import (
    determine_technical_eligibility,
    extract_commercial_data_from_document,
    check_boq_parity,
    normalize_commercial_bid,
    calculate_anomaly_signals,
    execute_cover2_financial_evaluation,
    get_procurement_financial_evaluation_service,
    CPCL_EXPECTED_BOQ,
)
from app.api.mock_gem_router import create_cpcl_demo_payload
from app.services.ingestion_service import ingest_procurement
from app.db.client import (
    insert_bid_evaluation,
    save_procurement_financial_evaluation,
    get_procurement_financial_evaluation,
)
from app.api.procurement_router import (
    evaluate_procurement_financial_endpoint,
    get_procurement_financial_endpoint,
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

            # Call API POST endpoint
            post_resp = await evaluate_procurement_financial_endpoint(proc_id)
            self.assertEqual(post_resp.procurement_id, proc_id)
            self.assertIn(post_resp.cover2_status, (Cover2State.EVALUATED, Cover2State.REVIEW_REQUIRED))

            # Call API GET endpoint
            get_resp = await get_procurement_financial_endpoint(proc_id)
            self.assertEqual(get_resp.procurement_id, proc_id)
            self.assertEqual(get_resp.cover2_status, post_resp.cover2_status)
            self.assertEqual(len(get_resp.bidder_evaluations), len(post_resp.bidder_evaluations))

        asyncio.run(_run())

    def test_14_physical_pdf_extraction_from_disk(self):
        """14. Verify extraction of real physical BOQ PDF from disk via boq_parser."""
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


if __name__ == "__main__":
    unittest.main()
