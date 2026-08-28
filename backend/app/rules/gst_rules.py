"""GST Rules Evaluation Engine."""

import difflib
from difflib import SequenceMatcher
from typing import Any, Dict


def evaluate_gst(extracted_data: dict, gov_data: dict) -> dict:
    """
    Evaluates extracted GST data against government registry records.

    1. Normalizes data: strips all whitespace and converts 'legal_name' and 'gstin'
       from both dictionaries to uppercase.
    2. Uses difflib.SequenceMatcher to compare the extracted company name against
       the government registry name.
    3. Evaluates GST validity and returns verification status, errors, and match metrics.

    Args:
        extracted_data: Dict containing extracted document data ('legal_name', 'gstin', 'status', etc.)
        gov_data: Dict containing government registry data ('legal_name', 'gstin', 'status', etc.)

    Returns:
        Dict containing 'status', 'errors', and 'confidence_metrics' (including 'name_match_score').
    """
    if not isinstance(extracted_data, dict):
        extracted_data = {}
    if not isinstance(gov_data, dict):
        gov_data = {}

    # 1. Data Normalization: strip whitespace and convert to uppercase
    def _normalize(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip().upper()

    extracted_legal_name = _normalize(extracted_data.get("legal_name"))
    extracted_gstin = _normalize(extracted_data.get("gstin"))

    gov_legal_name = _normalize(gov_data.get("legal_name"))
    gov_gstin = _normalize(gov_data.get("gstin"))

    # 2. String comparison using difflib.SequenceMatcher
    if not extracted_legal_name or not gov_legal_name:
        name_match_score = 0.0
    else:
        matcher = SequenceMatcher(None, extracted_legal_name, gov_legal_name)
        name_match_score = float(round(matcher.ratio(), 4))

    # 3. Rule checks and error collection
    errors = []

    # Check GSTIN existence and match
    if not extracted_gstin:
        errors.append("GSTIN is missing in extracted document data.")
    elif gov_gstin and extracted_gstin != gov_gstin:
        errors.append(f"GSTIN mismatch: Document has '{extracted_gstin}', registry has '{gov_gstin}'.")

    # Check Legal Name existence and similarity
    if not extracted_legal_name:
        errors.append("Legal name is missing in extracted document data.")
    elif not gov_legal_name:
        errors.append("Legal name is missing in government registry records.")
    elif name_match_score < 0.85:
        errors.append(
            f"Company name mismatch: '{extracted_legal_name}' vs '{gov_legal_name}' (match score: {name_match_score:.2f})."
        )

    # Check GST Registration Status if present in gov data
    gov_status = _normalize(gov_data.get("status"))
    if gov_status and gov_status not in ("ACTIVE", "VERIFIED", "APPROVED"):
        errors.append(f"GST registration status is '{gov_data.get('status')}', expected 'Active'.")

    # Determine overall status
    if not errors:
        status = "✅ VERIFIED"
    elif name_match_score >= 0.85 and not (gov_gstin and extracted_gstin and extracted_gstin != gov_gstin):
        status = "🟡 REVIEW"
    else:
        status = "🔴 MISMATCH"

    return {
        "status": status,
        "errors": errors,
        "confidence_metrics": {
            "name_match_score": name_match_score,
        },
    }
