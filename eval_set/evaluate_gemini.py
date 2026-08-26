"""Evaluation script to test Gemini GST extraction against the test dataset.

This script:
1. Loops through all PDF documents in eval_set/.
2. Passes each PDF through the text extraction and Gemini AI extraction pipeline.
3. Compares the extracted fields against the expected ground truth.
4. Generates a clean, detailed comparison table and accuracy diagnostic report.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.extractors.gemini_gst import extract_gst_fields
from backend.app.parsers.pdf_extractor import extract_text_from_pdf


def normalize_value(val: Optional[Any]) -> str:
    """Normalizes string or numeric values for robust comparison."""
    if val is None:
        return ""
    val_str = str(val).strip().upper()
    # Normalize amount representations (e.g. 118000.00 vs 118,000.00 vs Rs. 118000)
    val_str = val_str.replace("RS.", "").replace("INR", "").replace(",", "").strip()
    try:
        float_val = float(val_str)
        return f"{float_val:.2f}"
    except ValueError:
        return val_str


def load_ground_truth(eval_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Loads ground_truth.json if present in the eval_set folder."""
    gt_file = eval_dir / "ground_truth.json"
    if gt_file.exists():
        with open(gt_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def format_cell(text: str, width: int) -> str:
    """Formats cell text to fit within a given column width."""
    text = str(text) if text is not None else ""
    if len(text) > width:
        return text[: width - 3] + "..."
    return text.ljust(width)


def run_evaluation():
    eval_dir = Path(__file__).resolve().parent
    pdf_files = sorted(list(eval_dir.glob("*.pdf")))

    if not pdf_files:
        print(f"[!] No PDF files found in {eval_dir}.")
        print("Please place sample PDFs in eval_set/ or run generate_samples.py.")
        sys.exit(1)

    ground_truth = load_ground_truth(eval_dir)

    print("=" * 105)
    print(" GEMINI EXTRACTION LAYER - EVALUATION & BENCHMARK REPORT")
    print(f" Target Directory: {eval_dir}")
    print(f" Sample Count    : {len(pdf_files)} PDF(s)")
    print("=" * 105)

    total_fields = 0
    matched_fields = 0
    document_results = []

    for index, pdf_path in enumerate(pdf_files, start=1):
        filename = pdf_path.name
        expected = ground_truth.get(filename, {})
        print(f"\n[{index}/{len(pdf_files)}] Processing: {filename}...")

        start_time = time.time()
        try:
            # 1. Extract text using PyMuPDF parser
            pdf_data = extract_text_from_pdf(pdf_path)
            raw_text = pdf_data.get("raw_text", "")
            is_scanned = pdf_data.get("is_scanned", False)

            if is_scanned or not raw_text.strip():
                print(f"  [WARNING] Document detected as scanned or empty (length: {len(raw_text)} chars).")

            # 2. Extract structured GST fields using Gemini
            extracted = extract_gst_fields(raw_text)
            elapsed = time.time() - start_time

            # 3. Compare fields
            fields_to_check = ["gstin", "legal_name", "status", "total_amount"]
            field_comparisons = {}

            for field in fields_to_check:
                ext_val = extracted.get(field)
                exp_val = expected.get(field)

                if exp_val is not None:
                    total_fields += 1
                    norm_ext = normalize_value(ext_val)
                    norm_exp = normalize_value(exp_val)

                    is_match = (norm_ext == norm_exp) or (
                        norm_exp in norm_ext or norm_ext in norm_exp if norm_ext and norm_exp else False
                    )

                    if is_match:
                        matched_fields += 1
                        status = "PASS"
                    else:
                        status = "FAIL" if ext_val else "MISSING"
                else:
                    status = "EXTRACTED"

                field_comparisons[field] = {
                    "extracted": ext_val,
                    "expected": exp_val,
                    "status": status,
                }

            document_results.append({
                "filename": filename,
                "elapsed": elapsed,
                "is_scanned": is_scanned,
                "comparisons": field_comparisons,
                "extracted": extracted,
                "error": None,
            })

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"  [ERROR] Extraction failed for {filename}: {e}")
            document_results.append({
                "filename": filename,
                "elapsed": elapsed,
                "is_scanned": False,
                "comparisons": {},
                "extracted": {},
                "error": str(e),
            })

    # Render Clean Comparison Table
    print("\n" + "=" * 105)
    print(" DETAILED FIELD-BY-FIELD COMPARISON TABLE")
    print("=" * 105)
    header = f"| {'Document':<24} | {'Field':<14} | {'Extracted Value':<28} | {'Expected Value':<24} | {'Status':<6} |"
    divider = f"+{'-' * 26}+{'-' * 16}+{'-' * 30}+{'-' * 26}+{'-' * 8}+"

    print(divider)
    print(header)
    print(divider)

    for doc in document_results:
        filename = doc["filename"]
        if doc["error"]:
            err_line = f"| {format_cell(filename, 24)} | {'ERROR':<14} | {format_cell(doc['error'], 28)} | {'N/A':<24} | {'FAIL':<6} |"
            print(err_line)
            print(divider)
            continue

        comps = doc["comparisons"]
        first = True
        for field, comp in comps.items():
            doc_label = filename if first else ""
            first = False
            ext_display = str(comp["extracted"]) if comp["extracted"] is not None else "<None>"
            exp_display = str(comp["expected"]) if comp["expected"] is not None else "-"
            status_tag = comp["status"]

            row = f"| {format_cell(doc_label, 24)} | {format_cell(field, 14)} | {format_cell(ext_display, 28)} | {format_cell(exp_display, 24)} | {status_tag:<6} |"
            print(row)
        print(divider)

    # Accuracy Summary
    print("\n" + "=" * 105)
    print(" SUMMARY METRICS")
    print("=" * 105)
    accuracy = (matched_fields / total_fields * 100) if total_fields > 0 else 100.0
    print(f" Total Documents Evaluated : {len(pdf_files)}")
    print(f" Total Benchmark Fields    : {total_fields}")
    print(f" Successfully Matched      : {matched_fields}")
    print(f" Overall Accuracy Rate     : {accuracy:.2f}%")
    print("=" * 105 + "\n")

    if accuracy < 100.0:
        print("[!] Some fields mismatched or were missing. Check the comparison table above.")
    else:
        print("[SUCCESS] All evaluated fields matched the expected ground truth perfectly!")


if __name__ == "__main__":
    run_evaluation()
