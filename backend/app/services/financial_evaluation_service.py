"""Canonical Cover 2 Financial / Commercial Evaluation Service.

Provides complete, deterministic Cover 2 commercial evaluation for SIH26100:
1. Cover 2 Gate: Strict technical qualification filter (TECHNICALLY_ELIGIBLE, TECHNICAL_REVIEW_REQUIRED, TECHNICALLY_FAILED).
2. BOQ & Price Extraction: Reuses existing parsing infrastructure to extract line items, unit rates, quantities, taxes, freight, and totals.
3. Deterministic Normalization: Computes verified subtotal, taxes, freight, discounts, and comparable evaluated amount.
4. BOQ Parity Check: Verifies line items against expected RFP BOQ structure, detecting missing items, extra items, quantity/unit mismatches, and arithmetic errors.
5. L1 Ranking: Deterministically ranks eligible valid bids ascending by evaluated price, handling ties cleanly.
6. Financial Anomaly Signals: Identifies peer median distance, benchmark variance, and clustering without claiming statistical finality.
7. Auditability & Persistence: Records auditable gate decisions, exclusion reasons, and persists results.
"""

import logging
import math
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import HTTPException, status

from app.models.financial import (
    BOQItemEvaluation,
    BidderFinancialEvaluation,
    CommercialEvaluationStatus,
    CommercialFinding,
    Cover2State,
    FinancialAnomalySignal,
    ProcurementFinancialEvaluationResponse,
    TechnicalEligibilityState,
)
from app.models.procurement import DocumentType
from app.db.client import (
    get_procurement_hierarchy,
    get_bid_evaluations,
    save_procurement_financial_evaluation,
    get_procurement_financial_evaluation,
)

logger = logging.getLogger(__name__)

# Expected canonical BOQ for CPCL Water Quality Monitoring tender (DEMO/CPCL/WQM/2026/017)
CPCL_EXPECTED_BOQ = [
    {
        "item_number": 1,
        "keywords": ["water quality", "analyzer", "sensor network", "online multichannel", "wq-900"],
        "description": "Online Multichannel Water Quality Analyzer Units",
        "expected_quantity": 5.0,
        "expected_unit": "units",
    },
    {
        "item_number": 2,
        "keywords": ["probe", "telemetry", "submersible", "sensor probe"],
        "description": "Submersible Sensor Probes & Telemetry Modules",
        "expected_quantity": 5.0,
        "expected_unit": "sets",
    },
    {
        "item_number": 3,
        "keywords": ["installation", "testing", "calibration", "commissioning"],
        "description": "Installation, Testing, Calibration & Commissioning",
        "expected_quantity": 1.0,
        "expected_unit": "lot",
    },
    {
        "item_number": 4,
        "keywords": ["warranty", "amc", "maintenance", "annual maintenance", "onsite warranty"],
        "description": "2-Year Comprehensive Annual Maintenance & Warranty",
        "expected_quantity": 1.0,
        "expected_unit": "lot",
    },
]


def determine_technical_eligibility(
    submission_id: str,
    tender_id: str,
    evaluations: List[Dict[str, Any]],
    external_submission_reference: Optional[str] = None,
    bidder_name: Optional[str] = None,
) -> Tuple[TechnicalEligibilityState, Optional[str]]:
    """Evaluates whether a bidder submission qualifies to enter Cover 2.

    Safety:
    - Excludes bidders with failing mandatory requirements.
    - Excludes bidders awaiting unresolved mandatory review or with missing evidence.
    - Distinguishes TECHNICALLY_ELIGIBLE, TECHNICAL_REVIEW_REQUIRED, TECHNICALLY_FAILED.
    - Never converts machine recommendation into a final officer award.
    """
    sub_eval = None
    target_ids = {s for s in (submission_id, external_submission_reference) if s}
    for ev in reversed(evaluations):
        e_data = ev.get("evaluation_data", {}) if isinstance(ev, dict) else {}
        ev_sub_id = e_data.get("submission_id") or ev.get("bid_id")
        ev_bidder = ev.get("bidder_name") or e_data.get("bidder_name")
        if ev_sub_id and ev_sub_id in target_ids:
            sub_eval = e_data or ev
            break
        if bidder_name and ev_bidder and (
            bidder_name.strip().lower() in str(ev_bidder).strip().lower()
            or str(ev_bidder).strip().lower() in bidder_name.strip().lower()
        ):
            sub_eval = e_data or ev
            break

    if not sub_eval:
        return (
            TechnicalEligibilityState.TECHNICAL_REVIEW_REQUIRED,
            "No technical evaluation record found for submission. Technical review is required before Cover 2 opening.",
        )

    req_results = sub_eval.get("requirement_results", [])
    if not req_results:
        summary = sub_eval.get("machine_review_summary", {})
        if summary.get("FAIL", 0) > 0:
            return (
                TechnicalEligibilityState.TECHNICALLY_FAILED,
                f"Technical evaluation resulted in {summary.get('FAIL')} failed requirement(s).",
            )
        if summary.get("REVIEW", 0) > 0 or summary.get("UNVERIFIED", 0) > 0:
            return (
                TechnicalEligibilityState.TECHNICAL_REVIEW_REQUIRED,
                f"Unresolved technical items: {summary.get('REVIEW', 0)} under review, {summary.get('UNVERIFIED', 0)} unverified.",
            )
        return (
            TechnicalEligibilityState.TECHNICAL_REVIEW_REQUIRED,
            "Technical requirement details missing from evaluation record.",
        )

    failed_reqs = []
    review_reqs = []
    unverified_reqs = []

    for r in req_results:
        req_id = getattr(r, "requirement_id", None) or (r.get("requirement_id") if isinstance(r, dict) else "")
        state = getattr(r, "state", None) or (r.get("state") if isinstance(r, dict) else "")
        if hasattr(state, "value"):
            state = state.value
        state_str = str(state).upper()

        is_mandatory = getattr(r, "mandatory", True) if hasattr(r, "mandatory") else (r.get("mandatory", True) if isinstance(r, dict) else True)

        if state_str in ("FAIL", "NON_COMPLIANT") and is_mandatory:
            failed_reqs.append(req_id)
        elif state_str in ("REVIEW", "REVIEW_REQUIRED") and is_mandatory:
            review_reqs.append(req_id)
        elif state_str == "UNVERIFIED" and is_mandatory:
            unverified_reqs.append(req_id)

    if failed_reqs:
        return (
            TechnicalEligibilityState.TECHNICALLY_FAILED,
            f"Failed mandatory technical requirement(s): {', '.join(failed_reqs)}.",
        )

    if review_reqs:
        return (
            TechnicalEligibilityState.TECHNICAL_REVIEW_REQUIRED,
            f"Mandatory requirement(s) awaiting officer review or contradiction resolution: {', '.join(review_reqs)}.",
        )

    if unverified_reqs:
        return (
            TechnicalEligibilityState.TECHNICAL_REVIEW_REQUIRED,
            f"Mandatory requirement(s) lacking verified documentary evidence: {', '.join(unverified_reqs)}.",
        )

    return TechnicalEligibilityState.TECHNICALLY_ELIGIBLE, None


def _clean_number(val: Any) -> float:
    """Safely parses numeric values from text strings."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    s = s.replace(",", "").replace("₹", "").replace("INR", "").replace("Rs.", "").replace("Rs", "").strip()
    try:
        return float(s)
    except ValueError:
        match = re.search(r"[-+]?\d*\.?\d+", s)
        return float(match.group(0)) if match else 0.0


def extract_commercial_data_from_document(
    doc: Dict[str, Any],
) -> Tuple[List[BOQItemEvaluation], Dict[str, float], List[Dict[str, Any]]]:
    """Extracts line items, financial totals, and provenance citations from a commercial document.

    Reuses existing universal parsing & table extraction capabilities.
    """
    line_items: List[BOQItemEvaluation] = []
    totals: Dict[str, float] = {}
    provenance_list: List[Dict[str, Any]] = []

    filename = doc.get("filename", "commercial_bid.pdf")
    doc_id = doc.get("id", "doc_unknown")
    text = doc.get("content_text") or ""
    storage_path = doc.get("storage_path")

    # If content_text is serialized JSON from extractor, unpack raw_text
    if isinstance(text, str) and text.strip().startswith("{"):
        try:
            import json
            parsed_doc = json.loads(text)
            if isinstance(parsed_doc, dict):
                text = parsed_doc.get("raw_text") or parsed_doc.get("text") or text
        except Exception:
            pass

    # 1. Try table extraction if physical file exists
    extracted_tables = []
    if storage_path and os.path.exists(storage_path) and storage_path.lower().endswith(".pdf"):
        try:
            from app.services.boq_parser import extract_financial_tables
            with open(storage_path, "rb") as f:
                f_bytes = f.read()
            import asyncio
            extracted_tables = asyncio.run(extract_financial_tables(f_bytes))
        except Exception as te:
            logger.debug("Table extraction via pdfplumber failed on %s: %s", storage_path, te)

    # 2. Extract line items from table records if available
    if extracted_tables:
        for idx, row in enumerate(extracted_tables, start=1):
            desc = row.get("description") or row.get("item_description") or row.get("item") or f"Item {idx}"
            qty = _clean_number(row.get("quantity") or row.get("qty") or 1.0)
            rate = _clean_number(row.get("unit_rate") or row.get("unit_price") or row.get("rate") or 0.0)
            total = _clean_number(row.get("total_price") or row.get("total") or row.get("amount") or (qty * rate))
            unit = str(row.get("unit") or "units").strip()
            tax = _clean_number(row.get("taxes") or row.get("gst") or 0.0)

            expected_total = qty * rate
            is_valid = math.isclose(expected_total, total, rel_tol=1e-3, abs_tol=1.0) if (qty and rate) else True
            disc_note = None if is_valid else f"Arithmetic error: {qty} * {rate} = {expected_total} != quoted {total}."

            line_items.append(
                BOQItemEvaluation(
                    item_number=idx,
                    description=desc,
                    quantity=qty,
                    unit=unit,
                    unit_rate=rate,
                    total_price=total,
                    taxes=tax,
                    is_arithmetic_valid=is_valid,
                    discrepancy_note=disc_note,
                    provenance={
                        "document_id": doc_id,
                        "source_document": filename,
                        "page_number": 1,
                        "context": f"Table extraction row {idx}: {desc}",
                        "confidence": 0.95,
                    },
                )
            )

    # 3. Text pattern extraction (fallback and for synthetic/mock strings)
    if not line_items and text:
        # Line-by-line pattern for: Item <num>: <Desc>, Qty: <X> <unit>, Unit Rate: <Y>, Total: <Z>
        item_pattern = re.compile(
            r"Item\s*(\d+)[:\-\s]+(.+?)[,\s]+(?:Qty|Quantity)[:\-\s]*([\d\.]+)\s*(\w+)?.*?Unit\s*(?:Rate|Price)[:\-\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?).*?Total(?:[:\-\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?))?",
            re.IGNORECASE,
        )

        for line in text.splitlines():
            m = item_pattern.search(line)
            if m:
                item_idx = int(m.group(1))
                desc = m.group(2).strip()
                qty = _clean_number(m.group(3))
                unit = (m.group(4) or "units").strip()
                rate = _clean_number(m.group(5))
                total = _clean_number(m.group(6)) if m.group(6) else (qty * rate)

                expected_total = qty * rate
                is_valid = math.isclose(expected_total, total, rel_tol=1e-3, abs_tol=1.0) if (qty and rate) else True
                disc_note = None if is_valid else f"Arithmetic mismatch: {qty} * {rate} = {expected_total} != quoted {total}."

                line_items.append(
                    BOQItemEvaluation(
                        item_number=item_idx,
                        description=desc,
                        quantity=qty,
                        unit=unit,
                        unit_rate=rate,
                        total_price=total,
                        taxes=0.0,
                        is_arithmetic_valid=is_valid,
                        discrepancy_note=disc_note,
                        provenance={
                            "document_id": doc_id,
                            "source_document": filename,
                            "page_number": 1,
                            "context": f"Item {item_idx}: {desc}, Qty: {qty} {unit} @ ₹{rate} = ₹{total}",
                            "confidence": 0.90,
                        },
                    )
                )

    # 4. Extract commercial summary totals from text
    subtotal_match = re.search(r"Subtotal[:\-\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
    if subtotal_match:
        totals["subtotal"] = _clean_number(subtotal_match.group(1))

    taxes_match = re.search(
        r"(?:Taxes|GST|IGST|CGST|SGST)(?:\s*\([^)]*\))?(?:\s*@\s*\d+(?:\.\d+)?%)?[:\-\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )
    if taxes_match:
        totals["taxes"] = _clean_number(taxes_match.group(1))

    freight_match = re.search(r"(?:Freight|Transit\s*Insurance|Shipping)[:\-\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
    if freight_match:
        totals["freight"] = _clean_number(freight_match.group(1))

    discount_match = re.search(r"(?:Discount|Rebate)[:\-\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
    if discount_match:
        totals["discount"] = _clean_number(discount_match.group(1))

    total_match = re.search(
        r"(?:Total\s+(?:[A-Za-z]+\s+)*(?:Price|Value|Amount|Bid|Total)?|Grand\s*Total|Evaluated\s*(?:Bid)?\s*(?:Price|Amount))[:\-\s]*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )
    if total_match:
        totals["total_bid_value"] = _clean_number(total_match.group(1))

    # Add top-level provenance citation
    if text:
        snippet = text[:200].replace("\n", " ").strip()
        provenance_list.append({
            "document_id": doc_id,
            "source_document": filename,
            "page_number": 1,
            "snippet": f"Financial Quote Excerpt: {snippet}...",
            "confidence": 0.90,
        })

    return line_items, totals, provenance_list


def check_boq_parity(
    bidder_items: List[BOQItemEvaluation],
    expected_boq: List[Dict[str, Any]],
) -> List[CommercialFinding]:
    """Compares submitted bidder BOQ items against the expected RFP BOQ structure.

    Detects:
    - Missing line items
    - Quantity mismatches
    - Unit mismatches
    - Extra unexpected items
    """
    findings: List[CommercialFinding] = []
    if not expected_boq:
        return findings

    matched_bidder_indices = set()

    for exp in expected_boq:
        exp_item_no = exp.get("item_number")
        exp_desc = exp.get("description", "")
        exp_qty = exp.get("expected_quantity", 1.0)
        exp_unit = exp.get("expected_unit", "units").lower()
        keywords = exp.get("keywords", [])

        # Find matching bidder item
        matched_item: Optional[BOQItemEvaluation] = None
        matched_idx = -1
        for idx, b_item in enumerate(bidder_items):
            if idx in matched_bidder_indices:
                continue
            b_desc_lower = b_item.description.lower()
            if any(k in b_desc_lower for k in keywords) or str(b_item.item_number) == str(exp_item_no):
                matched_item = b_item
                matched_idx = idx
                matched_bidder_indices.add(idx)
                break

        if not matched_item:
            findings.append(
                CommercialFinding(
                    finding_type="MISSING_ITEM",
                    severity="CRITICAL",
                    message=f"Expected BOQ Item {exp_item_no} ('{exp_desc}') was not found in bidder's commercial schedule.",
                    expected={"item_number": exp_item_no, "description": exp_desc, "quantity": exp_qty},
                    observed=None,
                )
            )
        else:
            # Check quantity parity
            if not math.isclose(matched_item.quantity, exp_qty, rel_tol=1e-3):
                findings.append(
                    CommercialFinding(
                        finding_type="QUANTITY_MISMATCH",
                        severity="CRITICAL",
                        message=f"Quantity mismatch for '{exp_desc}': expected {exp_qty}, bidder quoted {matched_item.quantity}.",
                        expected={"quantity": exp_qty},
                        observed={"quantity": matched_item.quantity},
                        source_provenance=matched_item.provenance,
                    )
                )

            # Check unit parity
            if exp_unit and matched_item.unit.lower() != exp_unit:
                findings.append(
                    CommercialFinding(
                        finding_type="UNIT_MISMATCH",
                        severity="WARNING",
                        message=f"Unit mismatch for '{exp_desc}': expected '{exp_unit}', bidder quoted '{matched_item.unit}'.",
                        expected={"unit": exp_unit},
                        observed={"unit": matched_item.unit},
                        source_provenance=matched_item.provenance,
                    )
                )

    # Check for extra unexpected items
    for idx, b_item in enumerate(bidder_items):
        if idx not in matched_bidder_indices:
            findings.append(
                CommercialFinding(
                    finding_type="EXTRA_ITEM",
                    severity="INFO",
                    message=f"Bidder included extra un-solicited line item: '{b_item.description}'.",
                    expected=None,
                    observed={"description": b_item.description, "total_price": b_item.total_price},
                    source_provenance=b_item.provenance,
                )
            )

    return findings


def normalize_commercial_bid(
    line_items: List[BOQItemEvaluation],
    extracted_totals: Dict[str, float],
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], List[CommercialFinding]]:
    """Deterministically normalizes commercial components into a comparable evaluated price in INR.

    Formula: evaluated_amount = subtotal + taxes + freight - discounts.
    """
    findings: List[CommercialFinding] = []

    # 1. Compute or verify subtotal
    calculated_subtotal = sum(item.total_price for item in line_items) if line_items else None
    extracted_subtotal = extracted_totals.get("subtotal")

    if calculated_subtotal is not None and extracted_subtotal is not None:
        if not math.isclose(calculated_subtotal, extracted_subtotal, rel_tol=1e-3, abs_tol=1.0):
            findings.append(
                CommercialFinding(
                    finding_type="ARITHMETIC_ERROR",
                    severity="HIGH",
                    message=f"Sum of line items (INR {calculated_subtotal:,.2f}) does not match quoted subtotal (INR {extracted_subtotal:,.2f}).",
                    expected={"subtotal": calculated_subtotal},
                    observed={"subtotal": extracted_subtotal},
                )
            )
        subtotal = calculated_subtotal
    else:
        subtotal = calculated_subtotal if calculated_subtotal is not None else extracted_subtotal

    tax_amount = extracted_totals.get("taxes", 0.0)
    freight_amount = extracted_totals.get("freight", 0.0)
    discount_amount = extracted_totals.get("discount", 0.0)

    # If taxes were not extracted as a separate total, sum line item taxes if present
    if tax_amount == 0.0 and line_items:
        line_taxes = sum(item.taxes or 0.0 for item in line_items)
        if line_taxes > 0.0:
            tax_amount = line_taxes

    # Evaluated Total Calculation
    if subtotal is not None:
        evaluated_total = subtotal + tax_amount + freight_amount - discount_amount
        extracted_total_bid = extracted_totals.get("total_bid_value")

        if extracted_total_bid is not None and not math.isclose(evaluated_total, extracted_total_bid, rel_tol=1e-3, abs_tol=1.0):
            findings.append(
                CommercialFinding(
                    finding_type="TOTAL_MISMATCH",
                    severity="HIGH",
                    message=f"Evaluated sum (subtotal {subtotal:,.2f} + tax {tax_amount:,.2f} + freight {freight_amount:,.2f} - discount {discount_amount:,.2f} = INR {evaluated_total:,.2f}) does not match quoted grand total (INR {extracted_total_bid:,.2f}).",
                    expected={"evaluated_total": evaluated_total},
                    observed={"quoted_total": extracted_total_bid},
                )
            )
            # Use calculated evaluated total for parity audit
            final_evaluated = evaluated_total
        else:
            final_evaluated = evaluated_total
    elif extracted_totals.get("total_bid_value") is not None:
        final_evaluated = extracted_totals["total_bid_value"]
    else:
        final_evaluated = None
        findings.append(
            CommercialFinding(
                finding_type="NORMALIZATION_FAILURE",
                severity="CRITICAL",
                message="Unable to determine reliable commercial bid value from submitted documents.",
            )
        )

    return subtotal, tax_amount, freight_amount, discount_amount, final_evaluated, findings


def calculate_anomaly_signals(
    evaluations: List[BidderFinancialEvaluation],
    estimated_value: Optional[float] = None,
) -> List[FinancialAnomalySignal]:
    """Computes comparative anomaly signals across participating commercial bids."""
    signals: List[FinancialAnomalySignal] = []

    valid_bids = [
        e for e in evaluations
        if e.evaluated_amount is not None and e.evaluated_amount > 0 and e.is_cover2_unlocked
    ]

    if not valid_bids:
        return signals

    amounts = [b.evaluated_amount for b in valid_bids if b.evaluated_amount is not None]
    sorted_amounts = sorted(amounts)
    n = len(sorted_amounts)
    median_amount = (
        sorted_amounts[n // 2]
        if n % 2 != 0
        else (sorted_amounts[n // 2 - 1] + sorted_amounts[n // 2]) / 2.0
    )

    # 1. Variance against benchmark estimate
    if estimated_value and estimated_value > 0:
        for b in valid_bids:
            diff_pct = ((b.evaluated_amount - estimated_value) / estimated_value) * 100.0
            if diff_pct < -25.0:
                sig = FinancialAnomalySignal(
                    signal_type="UNUSUALLY_LOW_BID",
                    severity="WARNING",
                    description=f"Bidder '{b.bidder_name}' quoted INR {b.evaluated_amount:,.2f} ({abs(diff_pct):.1f}% below estimated tender benchmark of INR {estimated_value:,.2f}). Potential Abnormally Low Bid (ALB) under GFR Rule 149.",
                    metric_name="benchmark_variance_pct",
                    metric_value=round(diff_pct, 2),
                    threshold=-25.0,
                    requires_officer_review=True,
                )
                signals.append(sig)
                b.anomalies.append(sig)
            elif diff_pct > 20.0:
                sig = FinancialAnomalySignal(
                    signal_type="UNUSUALLY_HIGH_BID",
                    severity="INFO",
                    description=f"Bidder '{b.bidder_name}' quoted INR {b.evaluated_amount:,.2f} ({diff_pct:.1f}% above estimated tender benchmark of INR {estimated_value:,.2f}).",
                    metric_name="benchmark_variance_pct",
                    metric_value=round(diff_pct, 2),
                    threshold=20.0,
                    requires_officer_review=False,
                )
                signals.append(sig)
                b.anomalies.append(sig)

    # 2. Distance from peer median (if at least 2 bids)
    if len(valid_bids) >= 2:
        for b in valid_bids:
            peer_diff_pct = ((b.evaluated_amount - median_amount) / median_amount) * 100.0
            if peer_diff_pct < -20.0:
                sig = FinancialAnomalySignal(
                    signal_type="DISTANCE_FROM_MEDIAN",
                    severity="WARNING",
                    description=f"Bidder '{b.bidder_name}' is {abs(peer_diff_pct):.1f}% below the peer bid median (INR {median_amount:,.2f}).",
                    metric_name="peer_median_distance_pct",
                    metric_value=round(peer_diff_pct, 2),
                    threshold=-20.0,
                    requires_officer_review=True,
                )
                signals.append(sig)
                b.anomalies.append(sig)

    # 3. Bid clustering detection (< 1.0% separation)
    if len(valid_bids) >= 2:
        for i in range(len(valid_bids)):
            for j in range(i + 1, len(valid_bids)):
                b1 = valid_bids[i]
                b2 = valid_bids[j]
                if b1.evaluated_amount and b2.evaluated_amount:
                    cluster_diff = abs(b1.evaluated_amount - b2.evaluated_amount)
                    avg_amt = (b1.evaluated_amount + b2.evaluated_amount) / 2.0
                    cluster_pct = (cluster_diff / avg_amt) * 100.0
                    if cluster_pct < 1.0:
                        sig = FinancialAnomalySignal(
                            signal_type="BID_CLUSTERING",
                            severity="WARNING",
                            description=f"Bids from '{b1.bidder_name}' (INR {b1.evaluated_amount:,.2f}) and '{b2.bidder_name}' (INR {b2.evaluated_amount:,.2f}) cluster suspiciously close ({cluster_pct:.2f}% variance). Officer review recommended for possible coordinated pricing.",
                            metric_name="bid_clustering_variance_pct",
                            metric_value=round(cluster_pct, 3),
                            threshold=1.0,
                            requires_officer_review=True,
                        )
                        signals.append(sig)
                        b1.anomalies.append(sig)
                        b2.anomalies.append(sig)

    return signals


async def execute_cover2_financial_evaluation(
    procurement_id: str,
) -> ProcurementFinancialEvaluationResponse:
    """Executes the complete canonical Cover 2 Financial / Commercial Evaluation pipeline for a procurement.

    Step-by-step lifecycle:
    1. Load procurement hierarchy and technical evaluations.
    2. Enforce Cover 2 Gatekeeper on all participating bidders.
    3. For eligible bidders: discover commercial documents, extract BOQ items & totals.
    4. Check BOQ parity against expected tender BOQ.
    5. Deterministically normalize comparable evaluated values in INR.
    6. Rank eligible valid bids and assign L1.
    7. Calculate comparative financial anomaly signals.
    8. Persist results and compile audit trail.
    """
    logger.info("Initiating Cover 2 Financial Evaluation for procurement '%s'", procurement_id)
    proc_full = await get_procurement_hierarchy(procurement_id)
    if not proc_full:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Procurement with ID '{procurement_id}' not found.",
        )

    tenders = proc_full.get("tenders", [])
    tender = proc_full.get("tender") or (tenders[0] if tenders else {})
    tender_uuid = tender.get("id")
    tender_ref = tender.get("tender_reference")
    tender_id = tender_ref or tender_uuid or procurement_id
    estimated_value = tender.get("estimated_value")

    submissions = proc_full.get("submissions", [])
    for t in tenders:
        submissions.extend(t.get("submissions", []))

    # Fetch stored technical bid evaluations across candidate IDs (UUID, reference, procurement_id)
    seen_eval_ids = set()
    tech_evals = []
    for cand_id in {tender_id, tender_uuid, tender_ref, procurement_id}:
        if cand_id:
            fetched = await get_bid_evaluations(cand_id)
            for ev in fetched:
                ev_key = ev.get("id") or (ev.get("tender_id"), str(ev.get("evaluation_data", {}).get("submission_id")))
                if ev_key not in seen_eval_ids:
                    seen_eval_ids.add(ev_key)
                    tech_evals.append(ev)

    if not tech_evals:
        tech_evals = await get_bid_evaluations()

    bidder_evaluations: List[BidderFinancialEvaluation] = []
    audit_trail: List[Dict[str, Any]] = []

    # Audit log event: Cover 2 Opening Initiated
    audit_trail.append({
        "event": "COVER_2_OPENING_INITIATED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "procurement_id": procurement_id,
        "tender_id": tender_id,
        "total_submissions": len(submissions),
    })

    # Step A: Process each bidder through the Cover 2 Gatekeeper
    for sub in submissions:
        sub_id = sub.get("id")
        bidder_dict = sub.get("bidder") or sub.get("bidders") or {}
        bidder_id = sub.get("bidder_id") or bidder_dict.get("id", "bidder_unknown")
        bidder_name = bidder_dict.get("legal_name") or f"Bidder {bidder_id[:8]}"

        eligibility_state, exclusion_reason = determine_technical_eligibility(
            submission_id=sub_id,
            tender_id=tender_id,
            evaluations=tech_evals,
            external_submission_reference=sub.get("external_submission_reference"),
            bidder_name=bidder_name,
        )

        is_unlocked = (eligibility_state == TechnicalEligibilityState.TECHNICALLY_ELIGIBLE)

        b_eval = BidderFinancialEvaluation(
            procurement_id=procurement_id,
            tender_id=tender_id,
            bidder_id=bidder_id,
            bidder_name=bidder_name,
            submission_id=sub_id,
            technical_eligibility_status=eligibility_state,
            is_cover2_unlocked=is_unlocked,
            exclusion_reason=exclusion_reason,
            currency="INR",
            commercial_status=CommercialEvaluationStatus.NOT_EVALUATED,
        )

        if not is_unlocked:
            logger.info(
                "Bidder '%s' (submission %s) excluded from Cover 2: %s",
                bidder_name, sub_id, exclusion_reason,
            )
            audit_trail.append({
                "event": "BIDDER_EXCLUDED_FROM_COVER_2",
                "bidder_name": bidder_name,
                "submission_id": sub_id,
                "status": eligibility_state.value,
                "reason": exclusion_reason,
            })
            bidder_evaluations.append(b_eval)
            continue

        # Step B: Discover commercial documents and extract BOQ & totals
        docs = sub.get("documents", [])
        comm_docs = [
            d for d in docs
            if "FINANCIAL" in str(d.get("document_type", "")).upper()
            or "BOQ" in str(d.get("document_type", "")).upper()
            or any(kw in str(d.get("filename", "")).lower() for kw in ("boq", "commercial", "financial", "price", "quote"))
        ]

        if not comm_docs and docs:
            # Fallback: scan all attached documents
            comm_docs = docs

        all_items: List[BOQItemEvaluation] = []
        combined_totals: Dict[str, float] = {}
        all_provenance: List[Dict[str, Any]] = []

        for c_doc in comm_docs:
            items, tots, provs = extract_commercial_data_from_document(c_doc)
            if items:
                all_items.extend(items)
            combined_totals.update(tots)
            all_provenance.extend(provs)

        b_eval.line_items = all_items
        b_eval.provenance = all_provenance

        # Step D: BOQ Parity Check
        parity_findings = check_boq_parity(all_items, CPCL_EXPECTED_BOQ)
        b_eval.commercial_findings.extend(parity_findings)

        # Check line item arithmetic errors
        for it in all_items:
            if not it.is_arithmetic_valid:
                b_eval.commercial_findings.append(
                    CommercialFinding(
                        finding_type="ARITHMETIC_ERROR",
                        severity="HIGH",
                        message=it.discrepancy_note or f"Line item {it.item_number} has arithmetic error.",
                        expected={"unit_rate": it.unit_rate, "quantity": it.quantity, "total": it.quantity * it.unit_rate},
                        observed={"total": it.total_price},
                        source_provenance=it.provenance,
                    )
                )

        # Step C: Normalization
        subtotal, taxes, freight, discount, evaluated_amount, norm_findings = normalize_commercial_bid(
            line_items=all_items,
            extracted_totals=combined_totals,
        )
        b_eval.commercial_findings.extend(norm_findings)

        b_eval.subtotal = subtotal
        b_eval.tax_amount = taxes
        b_eval.freight_amount = freight
        b_eval.discount_amount = discount
        b_eval.quoted_amount = combined_totals.get("total_bid_value") or evaluated_amount
        b_eval.evaluated_amount = evaluated_amount

        # Determine Commercial Status
        has_critical_findings = any(f.severity == "CRITICAL" for f in b_eval.commercial_findings)
        has_high_findings = any(f.severity == "HIGH" for f in b_eval.commercial_findings)

        if has_critical_findings:
            b_eval.commercial_status = CommercialEvaluationStatus.DISQUALIFIED
        elif has_high_findings or evaluated_amount is None:
            b_eval.commercial_status = CommercialEvaluationStatus.REVIEW_REQUIRED
        else:
            b_eval.commercial_status = CommercialEvaluationStatus.EVALUATED

        b_eval.evaluated_at = datetime.now(timezone.utc)
        bidder_evaluations.append(b_eval)

    # Step E: L1 Calculation & Ranking for technically eligible bids
    rankable_bids = [
        b for b in bidder_evaluations
        if b.is_cover2_unlocked
        and b.commercial_status == CommercialEvaluationStatus.EVALUATED
        and b.evaluated_amount is not None
        and b.evaluated_amount > 0
    ]

    # Sort ascending by evaluated_amount (deterministic tie-break on submission_id, legal_name)
    rankable_bids.sort(key=lambda x: (x.evaluated_amount or 0.0, x.submission_id, x.bidder_name))

    for idx, b in enumerate(rankable_bids, start=1):
        b.rank = idx
        if idx == 1:
            b.is_l1 = True
        else:
            b.is_l1 = False

    # Step F: Calculate financial anomaly signals
    anomaly_signals = calculate_anomaly_signals(
        evaluations=bidder_evaluations,
        estimated_value=estimated_value,
    )

    # Audit log event: Ranking & L1 Determined
    l1_bidder = rankable_bids[0] if rankable_bids else None
    audit_trail.append({
        "event": "COVER_2_EVALUATION_COMPLETED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "eligible_bidders_count": len([b for b in bidder_evaluations if b.is_cover2_unlocked]),
        "ranked_bidders_count": len(rankable_bids),
        "l1_bidder": l1_bidder.bidder_name if l1_bidder else None,
        "l1_amount": l1_bidder.evaluated_amount if l1_bidder else None,
        "anomalies_detected": len(anomaly_signals),
    })

    # Assemble complete response
    cover2_status = Cover2State.EVALUATED if rankable_bids else Cover2State.REVIEW_REQUIRED
    eligible_count = sum(1 for b in bidder_evaluations if b.is_cover2_unlocked)
    excluded_count = sum(1 for b in bidder_evaluations if not b.is_cover2_unlocked)

    response = ProcurementFinancialEvaluationResponse(
        procurement_id=procurement_id,
        tender_id=tender_id,
        cover2_status=cover2_status,
        evaluated_at=datetime.now(timezone.utc),
        evaluator_version="opal-cover2-v1.0",
        currency="INR",
        estimated_tender_value=estimated_value,
        total_bidders=len(bidder_evaluations),
        eligible_bidders_count=eligible_count,
        excluded_bidders_count=excluded_count,
        l1_bidder_id=l1_bidder.bidder_id if l1_bidder else None,
        l1_bidder_name=l1_bidder.bidder_name if l1_bidder else None,
        l1_evaluated_amount=l1_bidder.evaluated_amount if l1_bidder else None,
        bidder_evaluations=bidder_evaluations,
        comparative_signals=anomaly_signals,
        audit_trail=audit_trail,
    )

    # Step I: Persist results
    await save_procurement_financial_evaluation(procurement_id, response.model_dump())

    logger.info(
        "Cover 2 evaluation finished for '%s'. Total: %d, Eligible: %d, L1: %s (INR %s)",
        procurement_id, len(bidder_evaluations), eligible_count,
        response.l1_bidder_name, response.l1_evaluated_amount,
    )
    return response


async def get_procurement_financial_evaluation_service(
    procurement_id: str,
) -> ProcurementFinancialEvaluationResponse:
    """Retrieves the stored Cover 2 financial evaluation for a procurement workspace."""
    stored = await get_procurement_financial_evaluation(procurement_id)
    if not stored:
        # Check if procurement exists
        proc_full = await get_procurement_hierarchy(procurement_id)
        if not proc_full:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procurement with ID '{procurement_id}' not found.",
            )
        # Cover 2 has not been executed yet
        tenders = proc_full.get("tenders", [])
        tender = proc_full.get("tender") or (tenders[0] if tenders else {})
        tender_id = tender.get("tender_reference") or tender.get("id") or procurement_id
        return ProcurementFinancialEvaluationResponse(
            procurement_id=procurement_id,
            tender_id=tender_id,
            cover2_status=Cover2State.LOCKED,
            evaluated_at=datetime.now(timezone.utc),
            evaluator_version="opal-cover2-v1.0",
            currency="INR",
            estimated_tender_value=tender.get("estimated_value"),
            total_bidders=len(proc_full.get("submissions", [])),
            eligible_bidders_count=0,
            excluded_bidders_count=0,
            bidder_evaluations=[],
            comparative_signals=[],
            audit_trail=[{
                "event": "COVER_2_LOCKED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Cover 2 has not yet been unlocked or evaluated.",
            }],
        )

    return ProcurementFinancialEvaluationResponse.model_validate(stored)
