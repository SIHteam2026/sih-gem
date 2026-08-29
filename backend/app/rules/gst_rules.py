"""GST Rules Evaluation Engine."""

import difflib
from difflib import SequenceMatcher
from typing import Any, Dict, List


def evaluate_gst(extracted_data: dict, gov_data: dict) -> dict:
    """
    Evaluates extracted GST data against government registry records.

    1. Normalizes data: strips whitespace and converts GSTINs and legal names to uppercase.
    2. Uses difflib.SequenceMatcher to compare legal names and compute name_match_score (0.0 to 1.0).
    3. Enforces strict business logic:
       - If GSTINs do not match or government registration status is not 'Active',
         sets status to '🔴 MISMATCH' and appends an error message.
       - If name_match_score is below 0.85, sets status to '🟡 REVIEW' and appends an error.
       - Otherwise, sets status to '✅ VERIFIED'.

    Args:
        extracted_data: Dict containing extracted document data ('legal_name', 'gstin', etc.)
        gov_data: Dict containing government registry data ('legal_name', 'gstin', 'status', etc.)

    Returns:
        Dict with keys:
            - status (str): '✅ VERIFIED', '🟡 REVIEW', or '🔴 MISMATCH'
            - errors (List[str]): list of error messages
            - confidence_metrics (Dict[str, float]): containing 'name_match_score'
    """
    if not isinstance(extracted_data, dict):
        extracted_data = {}
    if not isinstance(gov_data, dict):
        gov_data = {}

    # 1. Normalize data: strip whitespace and convert to uppercase
    def _normalize(val: Any) -> str:
        if val is None:
            return ""
        return str(val).strip().upper()

    extracted_gstin = _normalize(extracted_data.get("gstin"))
    extracted_legal_name = _normalize(extracted_data.get("legal_name"))

    gov_gstin = _normalize(gov_data.get("gstin"))
    gov_legal_name = _normalize(gov_data.get("legal_name"))
    gov_status = _normalize(gov_data.get("status"))

    # 2. Compare legal names using difflib.SequenceMatcher
    if not extracted_legal_name or not gov_legal_name:
        name_match_score = 0.0
    else:
        matcher = SequenceMatcher(None, extracted_legal_name, gov_legal_name)
        name_match_score = float(round(matcher.ratio(), 4))

    # 3. Enforce strict business logic
    errors: List[str] = []
    is_mismatch = False

    # Check GSTIN match
    if not extracted_gstin:
        is_mismatch = True
        errors.append("GSTIN is missing from extracted document data.")
    elif gov_gstin and extracted_gstin != gov_gstin:
        is_mismatch = True
        errors.append(
            f"GSTIN mismatch: Document GSTIN '{extracted_gstin}' does not match Government Registry GSTIN '{gov_gstin}'."
        )

    # Check Government registration status
    if gov_status != "ACTIVE":
        is_mismatch = True
        current_status = gov_data.get("status") or "Missing"
        errors.append(f"Government registration status is '{current_status}', expected 'Active'.")

    # Check Name Match Score
    if name_match_score < 0.85:
        if not extracted_legal_name:
            errors.append("Legal name is missing from extracted document data.")
        elif not gov_legal_name:
            errors.append("Legal name is missing from government registry records.")
        else:
            errors.append(
                f"Legal name mismatch: '{extracted_legal_name}' vs '{gov_legal_name}' (match score: {name_match_score:.2f} is below 0.85 threshold)."
            )

    # Determine final status
    if is_mismatch:
        status = "🔴 MISMATCH"
    elif name_match_score < 0.85:
        status = "🟡 REVIEW"
    else:
        status = "✅ VERIFIED"

    return {
        "status": status,
        "errors": errors,
        "confidence_metrics": {
            "name_match_score": name_match_score,
        },
    }
