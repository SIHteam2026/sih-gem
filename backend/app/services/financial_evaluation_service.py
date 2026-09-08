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

# Level 7 Financial Anomaly Detection Parameters
ALB_ESTIMATE_VARIANCE_THRESHOLD = 0.15  # 15% below engineer estimate screening threshold
CORRELATION_THRESHOLD = 0.995           # Pearson correlation threshold for pricing pattern
FIXED_ITEM_KEYWORDS = {
    "statutory", "fixed", "provisional sum", "contingency",
    "departmental charges", "fixed rate", "labour cess", "mandatory fee",
    "tax", "gst", "cess",
}

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
    mandatory_map: Optional[Dict[str, bool]] = None,
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

        if mandatory_map is not None and req_id in mandatory_map:
            is_mandatory = mandatory_map[req_id]
        elif hasattr(r, "mandatory"):
            is_mandatory = getattr(r, "mandatory")
        elif isinstance(r, dict) and "mandatory" in r:
            is_mandatory = r["mandatory"]
        else:
            is_mandatory = True

        if is_mandatory:
            if state_str in ("FAIL", "NON_COMPLIANT"):
                failed_reqs.append(req_id)
            elif state_str in ("REVIEW", "REVIEW_REQUIRED"):
                review_reqs.append(req_id)
            elif state_str == "UNVERIFIED":
                unverified_reqs.append(req_id)

    if failed_reqs:
        msg = f"Failed mandatory technical requirement(s): {', '.join(failed_reqs)}."
        if review_reqs:
            msg += f" Additionally pending review on: {', '.join(review_reqs)}."
        return (
            TechnicalEligibilityState.TECHNICALLY_FAILED,
            msg,
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

    # 1. Try reading physical file bytes from disk if storage_path exists
    f_bytes = None
    if storage_path and os.path.exists(storage_path):
        try:
            with open(storage_path, "rb") as f:
                f_bytes = f.read()
        except Exception as read_err:
            logger.debug("Failed reading file from storage_path %s: %s", storage_path, read_err)

    # If text is empty or missing, and f_bytes is available:
    if not text and f_bytes:
        if filename.lower().endswith(".pdf"):
            try:
                import pymupdf
                doc_fitz = pymupdf.open(stream=f_bytes, filetype="pdf")
                pages_text = [p.get_text() for p in doc_fitz]
                doc_fitz.close()
                text = "\n".join(pages_text).strip()
            except Exception:
                try:
                    import pdfplumber
                    with pdfplumber.open(io.BytesIO(f_bytes)) as pl_pdf:
                        pages_text = [p.extract_text() or "" for p in pl_pdf.pages]
                        text = "\n".join(pages_text).strip()
                except Exception as pl_err:
                    logger.debug("PDF text extraction failed: %s", pl_err)
        else:
            try:
                from app.services.multi_format_extractor import (
                    detect_file_format,
                    _extract_tabular_from_csv,
                    _extract_structured_from_docx,
                    _extract_sheets_from_xlsx,
                    _extract_text_from_txt,
                )
                fmt = detect_file_format(filename, f_bytes, doc.get("mime_type"))
                if fmt == "csv":
                    res = _extract_tabular_from_csv(f_bytes, filename)
                    text = res.raw_text
                elif fmt == "docx":
                    res = _extract_structured_from_docx(f_bytes, filename)
                    text = res.raw_text
                elif fmt == "xlsx":
                    res = _extract_sheets_from_xlsx(f_bytes, filename)
                    text = res.raw_text
                elif fmt == "txt":
                    res = _extract_text_from_txt(f_bytes, filename)
                    text = res.raw_text
            except Exception as mfe_err:
                logger.debug("Multi-format extraction fallback failed for %s: %s", filename, mfe_err)

    # If content_text is serialized JSON from extractor, unpack raw_text
    if isinstance(text, str) and text.strip().startswith("{"):
        try:
            import json
            parsed_doc = json.loads(text)
            if isinstance(parsed_doc, dict):
                text = parsed_doc.get("raw_text") or parsed_doc.get("text") or text
        except Exception:
            pass

    # 2. Try table extraction synchronously if physical file exists and is a PDF
    extracted_tables = []
    if f_bytes and filename.lower().endswith(".pdf"):
        try:
            from app.services.boq_parser import extract_financial_tables_sync
            extracted_tables = extract_financial_tables_sync(f_bytes)
        except Exception as te:
            logger.debug("Table extraction via boq_parser failed on %s: %s", filename, te)

    # 3. Extract line items from table records if available
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
            disc_note = None if is_valid else f"Line total mismatch (Arithmetic mismatch): {qty} * {rate} = {expected_total} != quoted {total}."

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
                        "file_path": storage_path,
                        "page_number": 1,
                        "context": f"Table extraction row {idx}: {desc} (Qty: {qty} {unit} @ INR {rate:,.2f})",
                        "confidence": 0.95,
                    },
                )
            )

    # 4. Text pattern extraction (fallback and for synthetic/mock strings)
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
                disc_note = None if is_valid else f"Line total mismatch (Arithmetic mismatch): {qty} * {rate} = {expected_total} != quoted {total}."

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
                            "file_path": storage_path,
                            "page_number": 1,
                            "context": f"Item {item_idx}: {desc}, Qty: {qty} {unit} @ INR {rate:,.2f} = INR {total:,.2f}",
                            "confidence": 0.90,
                        },
                    )
                )

    # 5. Extract commercial summary totals from text
    if text:
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
    if text or line_items:
        snippet = (text[:200] if text else f"Extracted {len(line_items)} BOQ items from {filename}").replace("\n", " ").strip()
        provenance_list.append({
            "document_id": doc_id,
            "source_document": filename,
            "file_path": storage_path,
            "page_number": 1,
            "snippet": f"Financial Quote Excerpt: {snippet}...",
            "confidence": 0.95 if extracted_tables else 0.90,
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
                    finding_type="SUBTOTAL_MISMATCH",
                    severity="HIGH",
                    message=f"Subtotal mismatch: Sum of line items (INR {calculated_subtotal:,.2f}) does not match quoted subtotal (INR {extracted_subtotal:,.2f}). Requires officer review.",
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
                    finding_type="GRAND_TOTAL_MISMATCH",
                    severity="HIGH",
                    message=f"Grand total mismatch: Evaluated sum (subtotal INR {subtotal:,.2f} + tax INR {tax_amount:,.2f} + freight INR {freight_amount:,.2f} - discount INR {discount_amount:,.2f} = INR {evaluated_total:,.2f}) does not match quoted grand total (INR {extracted_total_bid:,.2f}). Requires officer review; value is not silently repaired.",
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


def detect_pricing_pattern_anomalies(
    evaluations: List[BidderFinancialEvaluation],
    expected_boq: Optional[List[Dict[str, Any]]] = None,
) -> List[FinancialAnomalySignal]:
    """Detects multi-item cross-bidder pricing patterns across eligible bids.

    Forensic Checks:
    1. Uniform Pricing Multiplier (k != 1.0): Cross-bidder line-item rates scaled by a constant factor.
    2. Identical Line-Item Rates (k == 1.0): Identical unit pricing across competitive items.
    3. High Vector Correlation: Pearson correlation rho > 0.995 across line items.
    4. Shared Rounding Anomaly: Identical non-standard decimal fractions across items.
    5. Tender-fixed Item Exclusion: Statutory, fixed-rate, or provisional items are excluded from pattern analysis.
    """
    signals: List[FinancialAnomalySignal] = []

    # Only inspect eligible, unlocked bidders with line items
    eligible_bids = [
        b for b in evaluations
        if b.is_cover2_unlocked and b.evaluated_amount is not None and b.evaluated_amount > 0 and b.line_items
    ]

    if len(eligible_bids) < 2:
        return signals

    # Identify tender-fixed item numbers from expected_boq if flagged
    fixed_item_numbers = set()
    if expected_boq:
        for exp in expected_boq:
            desc_l = (exp.get("description") or "").lower()
            if any(kw in desc_l for kw in FIXED_ITEM_KEYWORDS) or exp.get("is_fixed"):
                fixed_item_numbers.add(str(exp.get("item_number")))

    for i in range(len(eligible_bids)):
        for j in range(i + 1, len(eligible_bids)):
            b1 = eligible_bids[i]
            b2 = eligible_bids[j]

            # Match items between b1 and b2 by item_number or matching description
            items1 = b1.line_items
            items2 = b2.line_items

            matched_rates: List[Tuple[float, float, str]] = []

            # Map by item_number first
            map2 = {str(it.item_number): it for it in items2}
            for it1 in items1:
                key = str(it1.item_number)
                desc1_l = it1.description.lower()

                # Check fixed item exclusion
                if key in fixed_item_numbers or any(kw in desc1_l for kw in FIXED_ITEM_KEYWORDS):
                    continue

                if key in map2:
                    it2 = map2[key]
                    desc2_l = it2.description.lower()
                    if any(kw in desc2_l for kw in FIXED_ITEM_KEYWORDS):
                        continue
                    if it1.unit_rate > 0 and it2.unit_rate > 0:
                        matched_rates.append((it1.unit_rate, it2.unit_rate, it1.description))

            # Need at least 2 competitive items (prefer 3+) to assess patterns
            n_items = len(matched_rates)
            if n_items < 2:
                continue

            r1_list = [r[0] for r in matched_rates]
            r2_list = [r[1] for r in matched_rates]

            # 1. Identical Pricing Pattern (k == 1.0)
            identical_count = sum(1 for r1, r2, _ in matched_rates if math.isclose(r1, r2, rel_tol=1e-3, abs_tol=0.01))
            if identical_count == n_items:
                sig = FinancialAnomalySignal(
                    signal_type="IDENTICAL_PRICING_PATTERN",
                    severity="WARNING",
                    description=(
                        f"Identical line-item unit rates detected between '{b1.bidder_name}' and '{b2.bidder_name}' "
                        f"across all {n_items} competitive BOQ line items (k = 1.0000). Potential cover bidding or bid-rigging arrangement."
                    ),
                    metric_name="identical_line_items_count",
                    metric_value=float(identical_count),
                    threshold=float(n_items),
                    requires_officer_review=True,
                    bidders_involved=[b1.bidder_name, b2.bidder_name],
                    details={
                        "matched_items_count": n_items,
                        "identical_rates": r1_list,
                        "bidders": [b1.bidder_name, b2.bidder_name],
                    },
                    calculation_basis=f"All {n_items} competitive line item unit rates identical (rel_tol=1e-3)",
                    decision_authority="HUMAN_PROCUREMENT_OFFICER",
                )
                signals.append(sig)
                b1.anomalies.append(sig)
                b2.anomalies.append(sig)
            else:
                # 2. Constant Multiplier Pattern (k != 1.0)
                ratios = [r1 / r2 for r1, r2, _ in matched_rates]
                mean_ratio = sum(ratios) / n_items
                var_ratio = sum((r - mean_ratio) ** 2 for r in ratios) / n_items
                std_ratio = math.sqrt(var_ratio)
                cv_ratio = (std_ratio / mean_ratio) if mean_ratio > 0 else 0.0

                # Check if mean_ratio != 1.0 and variance of ratios is near zero (CV < 0.02)
                if abs(mean_ratio - 1.0) >= 0.02 and cv_ratio < 0.02:
                    sig = FinancialAnomalySignal(
                        signal_type="PRICING_MULTIPLIER_DETECTED",
                        severity="WARNING",
                        description=(
                            f"Uniform pricing multiplier detected between '{b1.bidder_name}' and '{b2.bidder_name}' "
                            f"across {n_items} BOQ items (ratio k = {mean_ratio:.4f}, CV = {cv_ratio:.4f} < 0.02). "
                            f"Consistent line-item scaling indicates potential coordinated bid preparation."
                        ),
                        metric_name="pricing_multiplier_k",
                        metric_value=round(mean_ratio, 4),
                        threshold=0.02,
                        requires_officer_review=True,
                        bidders_involved=[b1.bidder_name, b2.bidder_name],
                        details={
                            "matched_items_count": n_items,
                            "multiplier_k": round(mean_ratio, 4),
                            "ratio_coefficient_of_variation": round(cv_ratio, 4),
                            "ratios": [round(r, 4) for r in ratios],
                            "bidders": [b1.bidder_name, b2.bidder_name],
                        },
                        calculation_basis=f"Coefficient of variation of item unit rate ratios = {cv_ratio:.4f} < 0.02 across {n_items} items",
                        decision_authority="HUMAN_PROCUREMENT_OFFICER",
                    )
                    signals.append(sig)
                    b1.anomalies.append(sig)
                    b2.anomalies.append(sig)

            # 3. High Vector Correlation (Pearson rho > 0.995)
            if n_items >= 3:
                mean1 = sum(r1_list) / n_items
                mean2 = sum(r2_list) / n_items
                var1 = sum((x - mean1) ** 2 for x in r1_list)
                var2 = sum((y - mean2) ** 2 for y in r2_list)
                if var1 > 0 and var2 > 0:
                    cov = sum((r1_list[k] - mean1) * (r2_list[k] - mean2) for k in range(n_items))
                    rho = cov / math.sqrt(var1 * var2)
                    if rho > CORRELATION_THRESHOLD:
                        sig = FinancialAnomalySignal(
                            signal_type="HIGH_VECTOR_CORRELATION",
                            severity="WARNING",
                            description=(
                                f"Extremely high line-item price vector correlation (Pearson r = {rho:.5f} > {CORRELATION_THRESHOLD}) "
                                f"between '{b1.bidder_name}' and '{b2.bidder_name}' across {n_items} competitive BOQ items."
                            ),
                            metric_name="pearson_correlation_coefficient",
                            metric_value=round(rho, 5),
                            threshold=CORRELATION_THRESHOLD,
                            requires_officer_review=True,
                            bidders_involved=[b1.bidder_name, b2.bidder_name],
                            details={
                                "matched_items_count": n_items,
                                "pearson_r": round(rho, 5),
                                "bidders": [b1.bidder_name, b2.bidder_name],
                            },
                            calculation_basis=f"Pearson r = {rho:.5f} across {n_items} matched line items",
                            decision_authority="HUMAN_PROCUREMENT_OFFICER",
                        )
                        signals.append(sig)
                        b1.anomalies.append(sig)
                        b2.anomalies.append(sig)

            # 4. Shared Rounding Anomaly
            # Detect identical non-zero decimal fractions across >= 2 line items
            shared_fractions = []
            for r1, r2, desc in matched_rates:
                f1 = round(r1 - math.floor(r1), 3)
                f2 = round(r2 - math.floor(r2), 3)
                if f1 > 0.001 and math.isclose(f1, f2, abs_tol=1e-3):
                    shared_fractions.append((desc, f1))

            if len(shared_fractions) >= 2:
                sig = FinancialAnomalySignal(
                    signal_type="SHARED_ROUNDING_ANOMALY",
                    severity="INFO",
                    description=(
                        f"Shared non-standard decimal rounding pattern detected between '{b1.bidder_name}' and '{b2.bidder_name}' "
                        f"across {len(shared_fractions)} line items. Possible common source estimation tool or spreadsheet."
                    ),
                    metric_name="shared_fractional_count",
                    metric_value=float(len(shared_fractions)),
                    threshold=2.0,
                    requires_officer_review=True,
                    bidders_involved=[b1.bidder_name, b2.bidder_name],
                    details={
                        "shared_instances": len(shared_fractions),
                        "fractional_matches": [f"{d}: fraction {f}" for d, f in shared_fractions],
                        "bidders": [b1.bidder_name, b2.bidder_name],
                    },
                    calculation_basis=f"{len(shared_fractions)} line items share identical non-zero decimal fractions",
                    decision_authority="HUMAN_PROCUREMENT_OFFICER",
                )
                signals.append(sig)
                b1.anomalies.append(sig)
                b2.anomalies.append(sig)

    return signals


def detect_abnormally_low_bid_signals(
    evaluations: List[BidderFinancialEvaluation],
    estimated_value: Optional[float] = None,
    raw_material_floor: Optional[float] = None,
    estimate_variance_threshold: float = ALB_ESTIMATE_VARIANCE_THRESHOLD,
) -> List[FinancialAnomalySignal]:
    """Detects Abnormally Low Bid (ALB) risk and peer-group pricing anomalies.

    Components:
    1. Engineer Estimate Variance: 1.0 - (bid / estimate), threshold = 0.15 (15% below).
       Screening heuristic for officer review; missing estimate emits ENGINEER_ESTIMATE_UNAVAILABLE.
    2. Peer-Group Anomaly:
       - Sample size n >= 4: computes z-score and flags z < -1.5.
       - Sample size n < 4: withholds z-score and reports median distance with small-sample disclaimer.
    3. Bid Clustering: < 1.0% separation between bids.
    4. Raw Material Floor Check: Compares bid to authoritative raw material floor if provided;
       if unavailable, emits RAW_MATERIAL_BASELINE_UNAVAILABLE without fabricating data.
    """
    signals: List[FinancialAnomalySignal] = []

    valid_bids = [
        e for e in evaluations
        if e.evaluated_amount is not None and e.evaluated_amount > 0 and e.is_cover2_unlocked
    ]

    if not valid_bids:
        return signals

    n = len(valid_bids)
    amounts = [b.evaluated_amount for b in valid_bids if b.evaluated_amount is not None]
    sorted_amounts = sorted(amounts)
    median_amount = (
        sorted_amounts[n // 2]
        if n % 2 != 0
        else (sorted_amounts[n // 2 - 1] + sorted_amounts[n // 2]) / 2.0
    )

    # 1. Engineer Estimate Analysis
    if estimated_value is None or estimated_value <= 0:
        sig = FinancialAnomalySignal(
            signal_type="ENGINEER_ESTIMATE_UNAVAILABLE",
            severity="INFO",
            description="Official engineer estimate benchmark is unavailable in tender specifications. Variance against engineer estimate could not be evaluated.",
            metric_name="engineer_estimate_available",
            metric_value=0.0,
            threshold=None,
            requires_officer_review=False,
            bidders_involved=[],
            details={"tender_estimated_value": None},
            calculation_basis="Tender estimated_value is None or <= 0",
            decision_authority="HUMAN_PROCUREMENT_OFFICER",
        )
        signals.append(sig)
    else:
        threshold_pct = estimate_variance_threshold * 100.0
        for b in valid_bids:
            if b.evaluated_amount is None:
                continue
            variance_below = (estimated_value - b.evaluated_amount) / estimated_value
            diff_pct = ((b.evaluated_amount - estimated_value) / estimated_value) * 100.0

            if variance_below >= estimate_variance_threshold:
                sig = FinancialAnomalySignal(
                    signal_type="UNUSUALLY_LOW_BID",
                    severity="WARNING",
                    description=(
                        f"Bidder '{b.bidder_name}' quoted INR {b.evaluated_amount:,.2f} "
                        f"({variance_below * 100.0:.1f}% below estimated tender benchmark of INR {estimated_value:,.2f}, "
                        f"exceeding screening threshold of {threshold_pct:.0f}%). Potential Abnormally Low Bid (ALB) "
                        f"under GFR Rule 149 (Screening indicator for officer review, sample size n={n})."
                    ),
                    metric_name="benchmark_variance_pct",
                    metric_value=round(diff_pct, 2),
                    threshold=-round(threshold_pct, 1),
                    requires_officer_review=True,
                    bidders_involved=[b.bidder_name],
                    details={
                        "bidder_name": b.bidder_name,
                        "evaluated_amount": b.evaluated_amount,
                        "estimated_value": estimated_value,
                        "variance_fraction": round(variance_below, 4),
                        "sample_size": n,
                    },
                    calculation_basis=f"1.0 - ({b.evaluated_amount} / {estimated_value}) = {variance_below:.4f} >= {estimate_variance_threshold}",
                    decision_authority="HUMAN_PROCUREMENT_OFFICER",
                )
                signals.append(sig)
                b.anomalies.append(sig)
            elif diff_pct > 20.0:
                sig = FinancialAnomalySignal(
                    signal_type="UNUSUALLY_HIGH_BID",
                    severity="INFO",
                    description=(
                        f"Bidder '{b.bidder_name}' quoted INR {b.evaluated_amount:,.2f} "
                        f"({diff_pct:.1f}% above estimated tender benchmark of INR {estimated_value:,.2f}, sample size n={n})."
                    ),
                    metric_name="benchmark_variance_pct",
                    metric_value=round(diff_pct, 2),
                    threshold=20.0,
                    requires_officer_review=False,
                    bidders_involved=[b.bidder_name],
                    details={"bidder_name": b.bidder_name, "evaluated_amount": b.evaluated_amount, "sample_size": n},
                    calculation_basis=f"(({b.evaluated_amount} - {estimated_value}) / {estimated_value}) * 100 = {diff_pct:.2f}%",
                    decision_authority="HUMAN_PROCUREMENT_OFFICER",
                )
                signals.append(sig)
                b.anomalies.append(sig)

    # 2. Peer Group Analysis
    if n >= 4:
        mean_amt = sum(amounts) / n
        var_amt = sum((x - mean_amt) ** 2 for x in amounts) / n
        std_amt = math.sqrt(var_amt)
        for b in valid_bids:
            if b.evaluated_amount is None:
                continue
            z = (b.evaluated_amount - mean_amt) / std_amt if std_amt > 0 else 0.0
            if z < -1.5:
                sig = FinancialAnomalySignal(
                    signal_type="PEER_GROUP_VARIANCE",
                    severity="WARNING",
                    description=(
                        f"Bidder '{b.bidder_name}' exhibits significant negative peer deviation "
                        f"(z-score = {z:.2f}, below peer mean INR {mean_amt:,.2f}, n={n}). "
                        f"Screening indicator for officer review."
                    ),
                    metric_name="peer_z_score",
                    metric_value=round(z, 2),
                    threshold=-1.5,
                    requires_officer_review=True,
                    bidders_involved=[b.bidder_name],
                    details={
                        "z_score": round(z, 2),
                        "sample_size": n,
                        "peer_mean": round(mean_amt, 2),
                        "peer_std": round(std_amt, 2),
                    },
                    calculation_basis=f"z = ({b.evaluated_amount} - {mean_amt:.2f}) / {std_amt:.2f} = {z:.2f} (n={n} >= 4)",
                    decision_authority="HUMAN_PROCUREMENT_OFFICER",
                )
                signals.append(sig)
                b.anomalies.append(sig)
    elif n >= 2:
        for b in valid_bids:
            if b.evaluated_amount is None:
                continue
            peer_diff_pct = ((b.evaluated_amount - median_amount) / median_amount) * 100.0
            if peer_diff_pct < -20.0:
                sig = FinancialAnomalySignal(
                    signal_type="DISTANCE_FROM_MEDIAN",
                    severity="WARNING",
                    description=(
                        f"Bidder '{b.bidder_name}' is {abs(peer_diff_pct):.1f}% below peer bid median INR {median_amount:,.2f} "
                        f"(z-score withheld due to small sample size n={n} < 4; screening indicator for officer review)."
                    ),
                    metric_name="peer_median_distance_pct",
                    metric_value=round(peer_diff_pct, 2),
                    threshold=-20.0,
                    requires_officer_review=True,
                    bidders_involved=[b.bidder_name],
                    details={
                        "median": median_amount,
                        "sample_size": n,
                        "z_score_withheld": True,
                        "reason": "Sample size n < 4 insufficient for statistical z-score",
                    },
                    calculation_basis=f"(({b.evaluated_amount} - {median_amount}) / {median_amount}) * 100 = {peer_diff_pct:.2f}%",
                    decision_authority="HUMAN_PROCUREMENT_OFFICER",
                )
                signals.append(sig)
                b.anomalies.append(sig)

    # 3. Bid Clustering (< 1.0% separation)
    if n >= 2:
        for i in range(n):
            for j in range(i + 1, n):
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
                            description=(
                                f"Bids from '{b1.bidder_name}' (INR {b1.evaluated_amount:,.2f}) and '{b2.bidder_name}' "
                                f"(INR {b2.evaluated_amount:,.2f}) cluster suspiciously close ({cluster_pct:.2f}% variance). "
                                f"Potential coordinated pricing (Screening indicator for officer review, sample size n={n})."
                            ),
                            metric_name="bid_clustering_variance_pct",
                            metric_value=round(cluster_pct, 3),
                            threshold=1.0,
                            requires_officer_review=True,
                            bidders_involved=[b1.bidder_name, b2.bidder_name],
                            details={
                                "bidder_1": b1.bidder_name,
                                "bidder_2": b2.bidder_name,
                                "amount_1": b1.evaluated_amount,
                                "amount_2": b2.evaluated_amount,
                                "variance_pct": round(cluster_pct, 3),
                                "sample_size": n,
                            },
                            calculation_basis=f"abs({b1.evaluated_amount} - {b2.evaluated_amount}) / avg = {cluster_pct:.3f}% < 1.0%",
                            decision_authority="HUMAN_PROCUREMENT_OFFICER",
                        )
                        signals.append(sig)
                        b1.anomalies.append(sig)
                        b2.anomalies.append(sig)

    # 4. Raw Material Floor Check
    if raw_material_floor is not None and raw_material_floor > 0:
        for b in valid_bids:
            if b.evaluated_amount is not None and b.evaluated_amount < raw_material_floor:
                deficit = raw_material_floor - b.evaluated_amount
                sig = FinancialAnomalySignal(
                    signal_type="RAW_MATERIAL_FLOOR_BREACH",
                    severity="CRITICAL",
                    description=(
                        f"Bidder '{b.bidder_name}' quoted INR {b.evaluated_amount:,.2f}, which is below the "
                        f"authoritative raw material cost floor of INR {raw_material_floor:,.2f} (deficit: INR {deficit:,.2f}). "
                        f"High risk of contractual non-performance or sub-standard materials."
                    ),
                    metric_name="raw_material_floor_deficit",
                    metric_value=round(deficit, 2),
                    threshold=raw_material_floor,
                    requires_officer_review=True,
                    bidders_involved=[b.bidder_name],
                    details={
                        "raw_material_floor": raw_material_floor,
                        "bid_amount": b.evaluated_amount,
                        "deficit": round(deficit, 2),
                    },
                    calculation_basis=f"Evaluated bid INR {b.evaluated_amount:,.2f} < Raw material floor INR {raw_material_floor:,.2f}",
                    decision_authority="HUMAN_PROCUREMENT_OFFICER",
                )
                signals.append(sig)
                b.anomalies.append(sig)
    else:
        sig = FinancialAnomalySignal(
            signal_type="RAW_MATERIAL_BASELINE_UNAVAILABLE",
            severity="INFO",
            description="Authoritative raw material cost baseline not specified in tender documents. Floor check withheld without synthetic baseline fabrication.",
            metric_name="raw_material_baseline_available",
            metric_value=0.0,
            threshold=None,
            requires_officer_review=False,
            bidders_involved=[],
            details={"raw_material_floor": None},
            calculation_basis="Tender raw_material_floor is None or <= 0",
            decision_authority="HUMAN_PROCUREMENT_OFFICER",
        )
        signals.append(sig)

    return signals


def calculate_anomaly_signals(
    evaluations: List[BidderFinancialEvaluation],
    estimated_value: Optional[float] = None,
    raw_material_floor: Optional[float] = None,
    expected_boq: Optional[List[Dict[str, Any]]] = None,
    estimate_variance_threshold: float = ALB_ESTIMATE_VARIANCE_THRESHOLD,
) -> List[FinancialAnomalySignal]:
    """Computes comparative anomaly signals across participating commercial bids.

    Safety: Comparative pricing metrics serve strictly as screening indicators
    for human procurement officer review and do not claim definitive statistical proof,
    especially on small sample sizes. Final determination remains with the procurement officer.
    """
    signals: List[FinancialAnomalySignal] = []

    # 1. Pricing Pattern Anomalies (multi-item multiplier, identical, correlation, rounding)
    pattern_signals = detect_pricing_pattern_anomalies(evaluations, expected_boq=expected_boq)
    signals.extend(pattern_signals)

    # 2. ALB & Peer-Group Anomalies (engineer estimate variance, peer median/z-score, clustering, raw material floor)
    alb_signals = detect_abnormally_low_bid_signals(
        evaluations=evaluations,
        estimated_value=estimated_value,
        raw_material_floor=raw_material_floor,
        estimate_variance_threshold=estimate_variance_threshold,
    )
    signals.extend(alb_signals)

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
    raw_material_floor = tender.get("raw_material_floor") or tender.get("minimum_cost_baseline") or proc_full.get("raw_material_floor")

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

    # Build mandatory requirements map from tender definitions if available
    mandatory_map: Dict[str, bool] = {}
    try:
        from app.db.client import get_tender_requirements
        req_rows = await get_tender_requirements(tender_id)
        if not req_rows and tender_uuid:
            req_rows = await get_tender_requirements(tender_uuid)
        if not req_rows and tender_ref:
            req_rows = await get_tender_requirements(tender_ref)
        if req_rows:
            for r_row in req_rows:
                rid = r_row.get("requirement_id") or r_row.get("id")
                is_m = r_row.get("mandatory", True) if "mandatory" in r_row else r_row.get("is_mandatory", True)
                if rid:
                    mandatory_map[str(rid)] = bool(is_m)
    except Exception as me:
        logger.debug("Could not fetch tender requirements for mandatory map: %s", me)

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
            mandatory_map=mandatory_map,
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

        audit_trail.append({
            "event": "BIDDER_UNLOCKED_FOR_COVER_2",
            "bidder_name": bidder_name,
            "submission_id": sub_id,
            "status": eligibility_state.value,
        })

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
        resolved_expected_boq = tender.get("expected_boq")
        if not resolved_expected_boq and any(kw in str(tender_ref or "").upper() or kw in str(procurement_id).upper() for kw in ("CPCL", "WQM", "017")):
            resolved_expected_boq = CPCL_EXPECTED_BOQ

        if resolved_expected_boq:
            parity_findings = check_boq_parity(all_items, resolved_expected_boq)
            b_eval.commercial_findings.extend(parity_findings)

        # Check line item arithmetic errors
        for it in all_items:
            if not it.is_arithmetic_valid:
                b_eval.commercial_findings.append(
                    CommercialFinding(
                        finding_type="LINE_TOTAL_MISMATCH",
                        severity="HIGH",
                        message=it.discrepancy_note or f"Line item {it.item_number} has arithmetic mismatch between unit rate and total price.",
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

        # Record findings audit event if any
        if b_eval.commercial_findings:
            audit_trail.append({
                "event": "COMMERCIAL_FINDINGS_DETECTED",
                "bidder_name": bidder_name,
                "submission_id": sub_id,
                "findings_count": len(b_eval.commercial_findings),
                "finding_types": [f.finding_type for f in b_eval.commercial_findings],
            })

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
        raw_material_floor=raw_material_floor,
        expected_boq=CPCL_EXPECTED_BOQ,
    )

    if anomaly_signals:
        audit_trail.append({
            "event": "FINANCIAL_ANOMALY_SIGNALS_DETECTED",
            "signals_count": len(anomaly_signals),
            "signal_types": [s.signal_type for s in anomaly_signals],
        })

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
        subs = list(proc_full.get("submissions", []))
        for t in tenders:
            subs.extend(t.get("submissions", []))
        total_bidders = len(subs)

        return ProcurementFinancialEvaluationResponse(
            procurement_id=procurement_id,
            tender_id=tender_id,
            cover2_status=Cover2State.LOCKED,
            evaluated_at=datetime.now(timezone.utc),
            evaluator_version="opal-cover2-v1.0",
            currency="INR",
            estimated_tender_value=tender.get("estimated_value"),
            total_bidders=total_bidders,
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
