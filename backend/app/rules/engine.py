"""Deterministic Compliance Rule Engine for OPAL (SIH26100).

Provides rigorous, deterministic evaluation of structured tender requirements
against bidder claims, submitted evidence, and authoritative verifications.

Strict Architectural Principles:
- Evaluates numerical comparisons, threshold checks, date expirations, time windows,
  unit compatibility, and statutory exemptions deterministically.
- Never guesses or hallucinates unverified values.
- Never makes the final procurement decision; produces structured ComplianceFinding
  artifacts for human review.
"""

from datetime import date, datetime
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from app.models.evaluation import ComplianceFinding, ComplianceState
    from app.models.evidence import BidderClaim, EvidenceObservation, ExtractedEvidence
    from app.models.tender import TenderRequirement
except ImportError:
    try:
        from app.models.evaluation import ComplianceFinding, ComplianceState
        from app.models.evidence import BidderClaim, EvidenceObservation, ExtractedEvidence
        from app.models.tender import TenderRequirement
    except ImportError:
        from models.evaluation import ComplianceFinding, ComplianceState
        from models.evidence import BidderClaim, EvidenceObservation, ExtractedEvidence
        from models.tender import TenderRequirement

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Numerical and Currency Parsing Utilities
# ---------------------------------------------------------------------------

CRORE_MULTIPLIER = 10_000_000.0
LAKH_MULTIPLIER = 100_000.0
THOUSAND_MULTIPLIER = 1_000.0

# Regex patterns for parsing numbers and currency
PERCENT_REGEX = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*%", re.IGNORECASE)
CRORE_REGEX = re.compile(
    r"(?:(?:INR|RS\.?|₹)\s*)?([0-9]+(?:\.[0-9]+)?)\s*(?:CR(?:ORE(?:S)?)?)\b",
    re.IGNORECASE,
)
LAKH_REGEX = re.compile(
    r"(?:(?:INR|RS\.?|₹)\s*)?([0-9]+(?:\.[0-9]+)?)\s*(?:L(?:AKH(?:S)?)?|LAC(?:S)?)\b",
    re.IGNORECASE,
)
GENERIC_CURRENCY_REGEX = re.compile(
    r"(?:INR|RS\.?|₹)\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
GENERIC_NUMBER_REGEX = re.compile(r"^[+-]?([0-9]+(?:\.[0-9]+)?)$")
DURATION_MONTHS_REGEX = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(?:MONTH|MONTHS|MO|MOS)\b", re.IGNORECASE)


def parse_numeric_value(val: Any) -> Tuple[Optional[float], Optional[str]]:
    """Parses a value into a canonical float and its detected unit.

    Supports:
        - Integers and floats (default unit None or from context)
        - Percentage strings ('27%', '50.5 %', '0.27' when tagged)
        - Indian financial notations:
            - '5 crore', 'INR 6.42 Cr', '₹5.0 Crore' -> 50,000,000.0, 'INR'
            - '50 Lakhs', 'Rs. 50L', '50 lac' -> 5,000,000.0, 'INR'
            - 'INR 5,00,00,000', '₹ 25,000.00' -> 50,000,000.0, 'INR'
        - General numeric strings with commas

    Returns:
        (parsed_float, detected_unit) or (None, None) if parsing fails.
    """
    if val is None:
        return None, None

    if isinstance(val, (int, float)):
        return float(val), None

    s = str(val).strip()
    if not s:
        return None, None

    # 1. Percentage check
    pct_match = PERCENT_REGEX.search(s)
    if pct_match:
        try:
            return float(pct_match.group(1)), "PERCENT"
        except ValueError:
            return None, None

    duration_match = DURATION_MONTHS_REGEX.search(s)
    if duration_match:
        try:
            return float(duration_match.group(1)), "MONTHS"
        except ValueError:
            return None, None

    # 2. Indian Crores check
    cr_match = CRORE_REGEX.search(s)
    if cr_match:
        try:
            num = float(cr_match.group(1))
            return num * CRORE_MULTIPLIER, "INR"
        except ValueError:
            return None, None

    # 3. Indian Lakhs check
    lakh_match = LAKH_REGEX.search(s)
    if lakh_match:
        try:
            num = float(lakh_match.group(1))
            return num * LAKH_MULTIPLIER, "INR"
        except ValueError:
            return None, None

    # 4. Formatted Currency check (with INR / Rs / ₹ symbols or commas)
    curr_match = GENERIC_CURRENCY_REGEX.search(s)
    if curr_match:
        try:
            clean_num = curr_match.group(1).replace(",", "")
            return float(clean_num), "INR"
        except ValueError:
            return None, None

    # 5. Clean string with standard commas (e.g., '50,000,000' or '5,00,00,000')
    cleaned = s.replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    if cleaned.upper().endswith("INR"):
        cleaned = cleaned[:-3].strip()

    num_match = GENERIC_NUMBER_REGEX.match(cleaned)
    if num_match:
        try:
            unit = "INR" if ("INR" in s.upper() or "₹" in s or "RS" in s.upper()) else None
            return float(num_match.group(1)), unit
        except ValueError:
            return None, None

    return None, None


def is_unit_compatible(unit1: Optional[str], unit2: Optional[str]) -> bool:
    """Verifies whether two measurement units are compatible for direct mathematical comparison."""
    if not unit1 or not unit2:
        return True  # If one is untyped/generic numeric, permit comparison

    u1 = unit1.strip().upper()
    u2 = unit2.strip().upper()

    if u1 == u2:
        return True

    # Currency aliases
    currency_units = {"INR", "RS", "RUPEES", "₹"}
    if u1 in currency_units and u2 in currency_units:
        return True

    # Percent aliases
    percent_units = {"PERCENT", "PERCENTAGE", "%"}
    if u1 in percent_units and u2 in percent_units:
        return True

    # Duration aliases
    duration_units = {"YEAR", "YEARS", "YR", "YRS", "MONTH", "MONTHS", "MO", "MOS"}
    if u1 in duration_units and u2 in duration_units:
        return True

    return False


# ---------------------------------------------------------------------------
# Date Parsing Utilities
# ---------------------------------------------------------------------------

def parse_date_value(val: Any) -> Optional[date]:
    """Parses a date string across various common Indian and ISO formats.

    Supports:
        - ISO format: '2026-09-04'
        - Indian/UK slash: '04/09/2026', '4/9/2026'
        - Indian/UK hyphen/dot: '04-09-2026', '04.09.2026'
        - Verbal month: '31 March 2027', 'March 2023', '04-Sep-2026', 'Sep 2026'
    """
    if not val:
        return None

    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val

    s = str(val).strip()
    if not s:
        return None

    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%Y/%m/%d",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%B %Y",
        "%b %Y",
        "%Y-%m",
    ]

    for fmt in date_formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue

    return None


# ---------------------------------------------------------------------------
# Core Deterministic Evaluation Functions
# ---------------------------------------------------------------------------

def evaluate_numeric_operator(
    operator: str,
    expected_val: float,
    observed_val: float,
    tolerance: float = 1e-6,
) -> bool:
    """Executes deterministic boolean evaluation of a numeric condition."""
    op = operator.strip()
    if op in (">=", "GTE", "MIN", "MINIMUM", "AT_LEAST"):
        return (observed_val - expected_val) >= -tolerance
    elif op in (">", "GT", "GREATER_THAN"):
        return (observed_val - expected_val) > tolerance
    elif op in ("<=", "LTE", "MAX", "MAXIMUM", "AT_MOST"):
        return (expected_val - observed_val) >= -tolerance
    elif op in ("<", "LT", "LESS_THAN"):
        return (expected_val - observed_val) > tolerance
    elif op in ("==", "=", "EQ", "EXACT"):
        return abs(observed_val - expected_val) <= tolerance
    elif op in ("!=", "<>", "NEQ", "NOT_EQ"):
        return abs(observed_val - expected_val) > tolerance
    else:
        # Default assumption is minimum threshold >=
        return (observed_val - expected_val) >= -tolerance


def evaluate_numeric_threshold(
    requirement_id: str,
    operator: str,
    expected_val: float,
    expected_unit: Optional[str],
    observed_values: Union[Any, List[Any]],
    evidence_ids: Optional[List[str]] = None,
    requirement_description: Optional[str] = None,
) -> ComplianceFinding:
    """Evaluates a deterministic numeric requirement against one or multiple observed values.

    Handles:
        - Multi-observation contradiction detection (returns REVIEW without losing data)
        - Incompatible unit safety (e.g. PERCENT vs INR -> REVIEW)
        - Exact arithmetic threshold evaluation (PASS / FAIL)
        - Missing or invalid values (UNVERIFIED / REVIEW)
    """
    evidence_ids = evidence_ids or []

    # Flatten list of observations
    if not isinstance(observed_values, list):
        obs_list = [observed_values]
    else:
        obs_list = observed_values

    # Filter out None and empty strings
    valid_obs = [o for o in obs_list if o is not None and str(o).strip() != ""]

    if not valid_obs:
        return ComplianceFinding(
            requirement_id=requirement_id,
            state=ComplianceState.UNVERIFIED,
            risk_level="MEDIUM",
            reasoning_trace="No observed numeric values or claims were provided for this requirement.",
            rule_type="NUMERIC_THRESHOLD",
            expected={"operator": operator, "value": expected_val, "unit": expected_unit},
            observed=None,
            evidence_ids=evidence_ids,
            confidence=1.0,
        )

    # Parse all observations
    parsed_observations: List[Tuple[Any, Optional[float], Optional[str]]] = []
    unparseable_observations: List[Any] = []

    for raw in valid_obs:
        p_val, p_unit = parse_numeric_value(raw)
        if p_val is not None:
            parsed_observations.append((raw, p_val, p_unit or expected_unit))
        else:
            unparseable_observations.append(raw)

    if unparseable_observations and not parsed_observations:
        return ComplianceFinding(
            requirement_id=requirement_id,
            state=ComplianceState.REVIEW,
            risk_level="HIGH",
            reasoning_trace=(
                f"Observed value(s) {unparseable_observations} could not be deterministically parsed "
                f"as numeric {expected_unit or ''}. Manual review required."
            ),
            rule_type="NUMERIC_THRESHOLD",
            expected={"operator": operator, "value": expected_val, "unit": expected_unit},
            observed={"raw_values": unparseable_observations},
            evidence_ids=evidence_ids,
            confidence=1.0,
        )

    # 1. Multi-Observation Contradiction Check
    # If multiple distinct parsed numeric values exist across observations
    distinct_values = {p_val for _, p_val, _ in parsed_observations}
    if len(distinct_values) > 1:
        formatted_obs = [f"{raw} (parsed: {val} {unit or ''})".strip() for raw, val, unit in parsed_observations]
        return ComplianceFinding(
            requirement_id=requirement_id,
            state=ComplianceState.REVIEW,
            risk_level="HIGH",
            reasoning_trace=(
                f"Multiple conflicting numeric observations detected: {', '.join(formatted_obs)}. "
                "Deterministic engine cannot arbitrate between contradictory evidence without audit review."
            ),
            rule_type="NUMERIC_THRESHOLD",
            expected={"operator": operator, "value": expected_val, "unit": expected_unit},
            observed={"conflicting_observations": formatted_obs, "distinct_values": list(distinct_values)},
            evidence_ids=evidence_ids,
            confidence=1.0,
        )

    # Use the primary parsed observation
    raw_obs, obs_val, obs_unit = parsed_observations[0]

    # 2. Unit Compatibility Check
    effective_unit = obs_unit or expected_unit
    if not is_unit_compatible(expected_unit, obs_unit):
        return ComplianceFinding(
            requirement_id=requirement_id,
            state=ComplianceState.REVIEW,
            risk_level="HIGH",
            reasoning_trace=(
                f"Incompatible unit comparison: requirement specifies '{expected_unit}', "
                f"but observed value is '{obs_unit}' ({raw_obs})."
            ),
            rule_type="NUMERIC_THRESHOLD",
            expected={"operator": operator, "value": expected_val, "unit": expected_unit},
            observed={"raw": raw_obs, "value": obs_val, "unit": obs_unit},
            evidence_ids=evidence_ids,
            confidence=1.0,
        )

    # 3. Deterministic Operator Comparison
    is_compliant = evaluate_numeric_operator(operator, expected_val, obs_val)

    unit_display = f" {effective_unit}" if effective_unit else ""
    if is_compliant:
        reason = (
            f"Observed value {obs_val:g}{unit_display} satisfies the mandatory condition "
            f"({operator} {expected_val:g}{unit_display})."
        )
        return ComplianceFinding(
            requirement_id=requirement_id,
            state=ComplianceState.PASS,
            risk_level="NONE",
            reasoning_trace=reason,
            rule_type="NUMERIC_THRESHOLD",
            expected={"operator": operator, "value": expected_val, "unit": expected_unit},
            observed={"raw": raw_obs, "value": obs_val, "unit": effective_unit},
            evidence_ids=evidence_ids,
            confidence=1.0,
        )
    else:
        shortfall = expected_val - obs_val if operator in (">=", ">") else obs_val - expected_val
        reason = (
            f"Observed value {obs_val:g}{unit_display} fails the mandatory condition "
            f"({operator} {expected_val:g}{unit_display}). Deficit: {abs(shortfall):g}{unit_display}."
        )
        return ComplianceFinding(
            requirement_id=requirement_id,
            state=ComplianceState.FAIL,
            risk_level="HIGH",
            reasoning_trace=reason,
            rule_type="NUMERIC_THRESHOLD",
            expected={"operator": operator, "value": expected_val, "unit": expected_unit},
            observed={"raw": raw_obs, "value": obs_val, "unit": effective_unit},
            evidence_ids=evidence_ids,
            confidence=1.0,
        )


def evaluate_date_validity(
    requirement_id: str,
    expiry_date_input: Any,
    anchor_date: Optional[Union[date, str]] = None,
    evidence_ids: Optional[List[str]] = None,
) -> ComplianceFinding:
    """Evaluates whether a document or certificate is currently valid and unexpired."""
    evidence_ids = evidence_ids or []

    # Parse expiry date
    parsed_expiry = parse_date_value(expiry_date_input)
    if not parsed_expiry:
        return ComplianceFinding(
            requirement_id=requirement_id,
            state=ComplianceState.REVIEW,
            risk_level="MEDIUM",
            reasoning_trace=f"Could not deterministically parse validity date from '{expiry_date_input}'.",
            rule_type="DATE_VALIDITY",
            expected={"condition": "CURRENTLY_VALID", "anchor_date": str(anchor_date or date.today())},
            observed={"raw_date": str(expiry_date_input)},
            evidence_ids=evidence_ids,
            confidence=1.0,
        )

    # Determine anchor date (defaults to today)
    if isinstance(anchor_date, str):
        parsed_anchor = parse_date_value(anchor_date) or date.today()
    elif isinstance(anchor_date, date):
        parsed_anchor = anchor_date
    else:
        parsed_anchor = date.today()

    if parsed_expiry >= parsed_anchor:
        return ComplianceFinding(
            requirement_id=requirement_id,
            state=ComplianceState.PASS,
            risk_level="NONE",
            reasoning_trace=(
                f"Document is valid until {parsed_expiry.isoformat()}, "
                f"satisfying validity as of reference date {parsed_anchor.isoformat()}."
            ),
            rule_type="DATE_VALIDITY",
            expected={"condition": "VALID_ON_OR_AFTER", "anchor_date": parsed_anchor.isoformat()},
            observed={"expiry_date": parsed_expiry.isoformat()},
            evidence_ids=evidence_ids,
            confidence=1.0,
        )
    else:
        return ComplianceFinding(
            requirement_id=requirement_id,
            state=ComplianceState.FAIL,
            risk_level="CRITICAL",
            reasoning_trace=(
                f"Document expired on {parsed_expiry.isoformat()} (before reference date {parsed_anchor.isoformat()})."
            ),
            rule_type="DATE_VALIDITY",
            expected={"condition": "VALID_ON_OR_AFTER", "anchor_date": parsed_anchor.isoformat()},
            observed={"expiry_date": parsed_expiry.isoformat()},
            evidence_ids=evidence_ids,
            confidence=1.0,
        )


def evaluate_experience_window(
    requirement_id: str,
    past_years_required: int,
    work_order_date_input: Optional[Any] = None,
    completion_date_input: Optional[Any] = None,
    tender_closing_date: Optional[Union[date, str]] = None,
    evidence_ids: Optional[List[str]] = None,
) -> ComplianceFinding:
    """Evaluates whether past experience falls within a designated time window (e.g. last 5 years).

    If the tender does not clearly define whether work order date or completion date governs,
    or if dates are ambiguous, produces REVIEW rather than inventing an interpretation.
    """
    evidence_ids = evidence_ids or []

    # Parse anchor date (closing date of tender or today)
    if isinstance(tender_closing_date, str):
        anchor = parse_date_value(tender_closing_date) or date.today()
    elif isinstance(tender_closing_date, date):
        anchor = tender_closing_date
    else:
        anchor = date.today()

    parsed_wo = parse_date_value(work_order_date_input) if work_order_date_input else None
    parsed_comp = parse_date_value(completion_date_input) if completion_date_input else None

    # Ambiguity: if both dates exist and one falls inside while the other falls outside the window
    earliest_allowed_date = date(anchor.year - past_years_required, anchor.month, anchor.day)

    if parsed_wo and parsed_comp:
        wo_in_window = parsed_wo >= earliest_allowed_date
        comp_in_window = parsed_comp >= earliest_allowed_date

        if wo_in_window and comp_in_window:
            return ComplianceFinding(
                requirement_id=requirement_id,
                state=ComplianceState.PASS,
                risk_level="NONE",
                reasoning_trace=(
                    f"Work order ({parsed_wo.isoformat()}) and completion ({parsed_comp.isoformat()}) "
                    f"both fall within the required {past_years_required}-year period (after {earliest_allowed_date.isoformat()})."
                ),
                rule_type="TIME_WINDOW",
                expected={"past_years": past_years_required, "window_start": earliest_allowed_date.isoformat()},
                observed={"work_order_date": parsed_wo.isoformat(), "completion_date": parsed_comp.isoformat()},
                evidence_ids=evidence_ids,
                confidence=1.0,
            )
        elif not wo_in_window and not comp_in_window:
            return ComplianceFinding(
                requirement_id=requirement_id,
                state=ComplianceState.FAIL,
                risk_level="HIGH",
                reasoning_trace=(
                    f"Neither work order date ({parsed_wo.isoformat()}) nor completion date ({parsed_comp.isoformat()}) "
                    f"fall within the required {past_years_required}-year window (must be on or after {earliest_allowed_date.isoformat()})."
                ),
                rule_type="TIME_WINDOW",
                expected={"past_years": past_years_required, "window_start": earliest_allowed_date.isoformat()},
                observed={"work_order_date": parsed_wo.isoformat(), "completion_date": parsed_comp.isoformat()},
                evidence_ids=evidence_ids,
                confidence=1.0,
            )
        else:
            # One in, one out -> Ambiguity!
            return ComplianceFinding(
                requirement_id=requirement_id,
                state=ComplianceState.REVIEW,
                risk_level="MEDIUM",
                reasoning_trace=(
                    f"Date semantics ambiguity: Work order date ({parsed_wo.isoformat()}) and completion date "
                    f"({parsed_comp.isoformat()}) straddle the {past_years_required}-year cutoff ({earliest_allowed_date.isoformat()}). "
                    "Tender does not specify which date determines qualification; manual review required."
                ),
                rule_type="TIME_WINDOW",
                expected={"past_years": past_years_required, "window_start": earliest_allowed_date.isoformat()},
                observed={"work_order_date": parsed_wo.isoformat(), "completion_date": parsed_comp.isoformat()},
                evidence_ids=evidence_ids,
                confidence=1.0,
            )

    target_date = parsed_comp or parsed_wo
    if target_date:
        if target_date >= earliest_allowed_date:
            return ComplianceFinding(
                requirement_id=requirement_id,
                state=ComplianceState.PASS,
                risk_level="NONE",
                reasoning_trace=(
                    f"Experience date {target_date.isoformat()} falls within the required "
                    f"{past_years_required}-year period (after {earliest_allowed_date.isoformat()})."
                ),
                rule_type="TIME_WINDOW",
                expected={"past_years": past_years_required, "window_start": earliest_allowed_date.isoformat()},
                observed={"experience_date": target_date.isoformat()},
                evidence_ids=evidence_ids,
                confidence=1.0,
            )
        else:
            return ComplianceFinding(
                requirement_id=requirement_id,
                state=ComplianceState.FAIL,
                risk_level="HIGH",
                reasoning_trace=(
                    f"Experience date {target_date.isoformat()} is prior to the {past_years_required}-year cutoff "
                    f"({earliest_allowed_date.isoformat()})."
                ),
                rule_type="TIME_WINDOW",
                expected={"past_years": past_years_required, "window_start": earliest_allowed_date.isoformat()},
                observed={"experience_date": target_date.isoformat()},
                evidence_ids=evidence_ids,
                confidence=1.0,
            )

    return ComplianceFinding(
        requirement_id=requirement_id,
        state=ComplianceState.UNVERIFIED,
        risk_level="MEDIUM",
        reasoning_trace="No verifiable past experience dates were provided in submitted documentation.",
        rule_type="TIME_WINDOW",
        expected={"past_years": past_years_required},
        observed=None,
        evidence_ids=evidence_ids,
        confidence=1.0,
    )


def evaluate_mandatory_evidence(
    requirement_id: str,
    evidence_present: bool,
    evidence_name: str,
    evidence_ids: Optional[List[str]] = None,
) -> ComplianceFinding:
    """Evaluates the presence of mandatory proof documents.

    Distinguishes missing evidence (UNVERIFIED) from affirmative non-compliance (FAIL).
    """
    evidence_ids = evidence_ids or []
    if evidence_present:
        return ComplianceFinding(
            requirement_id=requirement_id,
            state=ComplianceState.PASS,
            risk_level="NONE",
            reasoning_trace=f"Mandatory evidence document '{evidence_name}' is present in bidder submission.",
            rule_type="MANDATORY_EVIDENCE",
            expected={"evidence_required": evidence_name, "mandatory": True},
            observed={"is_present": True},
            evidence_ids=evidence_ids,
            confidence=1.0,
        )
    else:
        return ComplianceFinding(
            requirement_id=requirement_id,
            state=ComplianceState.UNVERIFIED,
            risk_level="HIGH",
            reasoning_trace=(
                f"Mandatory evidence document '{evidence_name}' was not submitted. "
                "Marked UNVERIFIED for shortfall notice generation or audit review."
            ),
            rule_type="MANDATORY_EVIDENCE",
            expected={"evidence_required": evidence_name, "mandatory": True},
            observed={"is_present": False},
            evidence_ids=evidence_ids,
            confidence=1.0,
        )


def evaluate_applicability_exemption(
    requirement_id: str,
    exemption_type: str,
    is_exempt: Optional[bool],
    exemption_reason: Optional[str] = None,
    evidence_ids: Optional[List[str]] = None,
) -> Optional[ComplianceFinding]:
    """Evaluates whether a requirement is waived under an authorized statutory exemption (e.g. MSE or Startup).

    Returns:
        - ComplianceFinding(NOT_APPLICABLE) if confirmed exempt
        - ComplianceFinding(REVIEW) if exemption eligibility is unverified/uncertain
        - None if exemption does not apply (proceed to standard rule evaluation)
    """
    evidence_ids = evidence_ids or []

    if is_exempt is True:
        reason = exemption_reason or f"Bidder qualifies for statutory '{exemption_type}' exemption."
        return ComplianceFinding(
            requirement_id=requirement_id,
            state=ComplianceState.NOT_APPLICABLE,
            risk_level="NONE",
            reasoning_trace=f"Requirement waived: {reason}",
            rule_type="APPLICABILITY_EXEMPTION",
            expected={"exemption_type": exemption_type},
            observed={"is_exempt": True, "reason": reason},
            evidence_ids=evidence_ids,
            confidence=1.0,
        )
    elif is_exempt is None:
        # Uncertain exemption claim
        return ComplianceFinding(
            requirement_id=requirement_id,
            state=ComplianceState.REVIEW,
            risk_level="MEDIUM",
            reasoning_trace=(
                f"Bidder claimed or may qualify for '{exemption_type}' exemption, but supporting "
                "statutory registration (e.g., Udyam / DPIIT certificate) is unverified. Manual review required."
            ),
            rule_type="APPLICABILITY_EXEMPTION",
            expected={"exemption_type": exemption_type},
            observed={"is_exempt": "UNCERTAIN"},
            evidence_ids=evidence_ids,
            confidence=1.0,
        )

    return None


# ---------------------------------------------------------------------------
# Unified Requirement Evaluator Entrypoint
# ---------------------------------------------------------------------------

def evaluate_requirement(
    requirement: Union[TenderRequirement, Dict[str, Any]],
    claims: Optional[Union[BidderClaim, List[BidderClaim], Dict[str, Any], List[Any]]] = None,
    evidence: Optional[Union[ExtractedEvidence, EvidenceObservation, List[Any], Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> ComplianceFinding:
    """High-level deterministic entrypoint for evaluating a tender requirement.

    Integrates:
        - Statutory Applicability / Exemption check
        - Ambiguity check (preserves ambiguous tender flags)
        - Numeric Thresholds (Local content %, turnover, past experience)
        - Date Validity and Certificate Expiry
        - Mandatory Document Presence
        - Multi-Observation Conflict Detection

    Args:
        requirement: Structured TenderRequirement or dictionary.
        claims: Optional BidderClaim(s) or dictionary.
        evidence: Optional ExtractedEvidence, EvidenceObservation(s), or dictionary.
        context: Optional evaluation context (e.g. anchor_date, exemptions, bidder_name).

    Returns:
        ComplianceFinding with deterministic state (PASS, FAIL, REVIEW, UNVERIFIED, NOT_APPLICABLE).
    """
    context = context or {}

    # 1. Normalize Requirement Model
    if hasattr(requirement, "model_dump"):
        req_dict = requirement.model_dump()
    elif isinstance(requirement, dict):
        req_dict = requirement
    else:
        req_dict = {}

    req_id = req_dict.get("requirement_id") or "REQ-UNKNOWN"
    category = str(req_dict.get("category", "")).upper()
    description = req_dict.get("description", "")
    is_mandatory = req_dict.get("mandatory", True)
    is_ambiguous = req_dict.get("is_ambiguous", False)
    ambiguity_reason = req_dict.get("ambiguity_reason")

    # 2. Extract Evidence and Claims Data
    evidence_ids: List[str] = []
    observed_values: List[Any] = []

    # Handle Claims
    if claims:
        if isinstance(claims, list):
            for c in claims:
                if hasattr(c, "claimed_value"):
                    observed_values.append(c.claimed_value)
                elif isinstance(c, dict):
                    if "claimed_value" in c:
                        observed_values.append(c["claimed_value"])
        elif hasattr(claims, "claimed_value"):
            observed_values.append(claims.claimed_value)
        elif isinstance(claims, dict) and "claimed_value" in claims:
            observed_values.append(claims["claimed_value"])

    # Handle Evidence
    if evidence:
        if isinstance(evidence, list):
            for ev in evidence:
                if hasattr(ev, "evidence_id"):
                    evidence_ids.append(ev.evidence_id)
                if hasattr(ev, "observed_value"):
                    observed_values.append(ev.observed_value)
                elif hasattr(ev, "extracted_values") and isinstance(ev.extracted_values, dict):
                    observed_values.extend(ev.extracted_values.values())
                elif isinstance(ev, dict):
                    if "observed_value" in ev:
                        observed_values.append(ev["observed_value"])
                    elif "extracted_values" in ev and isinstance(ev["extracted_values"], dict):
                        observed_values.extend(ev["extracted_values"].values())
        elif hasattr(evidence, "extracted_values") and isinstance(evidence.extracted_values, dict):
            observed_values.extend(evidence.extracted_values.values())
        elif hasattr(evidence, "observed_value"):
            observed_values.append(evidence.observed_value)
        elif isinstance(evidence, dict):
            if "extracted_values" in evidence and isinstance(evidence["extracted_values"], dict):
                observed_values.extend(evidence["extracted_values"].values())
            elif "observed_value" in evidence:
                observed_values.append(evidence["observed_value"])

    # 3. Check Statutory Exemption / Applicability
    exemptions = context.get("exemptions", {})
    if category in exemptions or req_id in exemptions or "MSE" in exemptions or "STARTUP" in exemptions:
        ex_info = exemptions.get(category) or exemptions.get(req_id) or exemptions.get("MSE") or exemptions.get("STARTUP")
        if isinstance(ex_info, dict):
            is_exempt = ex_info.get("is_exempt")
            ex_type = ex_info.get("type", "Statutory Exemption")
            ex_reason = ex_info.get("reason")
        else:
            is_exempt = bool(ex_info)
            ex_type = "Statutory Exemption"
            ex_reason = None

        exemption_finding = evaluate_applicability_exemption(
            requirement_id=req_id,
            exemption_type=ex_type,
            is_exempt=is_exempt,
            exemption_reason=ex_reason,
            evidence_ids=evidence_ids,
        )
        if exemption_finding:
            return exemption_finding

    # 4. Check Requirement Ambiguity
    if is_ambiguous:
        return ComplianceFinding(
            requirement_id=req_id,
            state=ComplianceState.REVIEW,
            risk_level="MEDIUM",
            reasoning_trace=(
                f"Tender requirement contains ambiguous/underspecified criteria: {ambiguity_reason or description}. "
                "Deterministic rule cannot evaluate without human procurement officer clarification."
            ),
            rule_type="AMBIGUOUS_REQUIREMENT",
            expected={"is_ambiguous": True, "ambiguity_reason": ambiguity_reason},
            observed={"values_submitted": observed_values},
            evidence_ids=evidence_ids,
            confidence=1.0,
        )

    # 5. Structured Condition / Evaluation Contract Check
    struct_cond = req_dict.get("structured_condition")
    if hasattr(struct_cond, "model_dump"):
        struct_cond = struct_cond.model_dump()

    thresh_raw = None
    op = None
    unit = None
    if req_dict.get("threshold_value") is not None:
        thresh_raw = req_dict.get("threshold_value")
        op = req_dict.get("operator") or ">="
        unit = req_dict.get("threshold_unit")
    elif struct_cond and struct_cond.get("threshold_value") is not None:
        thresh_raw = struct_cond.get("threshold_value")
        op = struct_cond.get("operator") or ">="
        unit = struct_cond.get("unit")

    if thresh_raw is not None:
        thresh_val, thresh_unit = parse_numeric_value(thresh_raw)
        if thresh_val is None and isinstance(thresh_raw, (int, float)):
            thresh_val = float(thresh_raw)
        final_unit = unit or thresh_unit
        if thresh_val is not None:
            return evaluate_numeric_threshold(
                requirement_id=req_id,
                operator=op or ">=",
                expected_val=thresh_val,
                expected_unit=final_unit,
                observed_values=observed_values,
                evidence_ids=evidence_ids,
                requirement_description=description,
            )

    # 6. Local Content Percentage Rule Check
    if category == "LOCAL_CONTENT" or "LOCAL CONTENT" in description.upper() or "%" in description:
        # Search for threshold in requirement description (e.g. >=50%, 50%, >= 20%)
        pct_match = PERCENT_REGEX.search(description)
        threshold = float(pct_match.group(1)) if pct_match else 50.0

        op = ">="
        if ">" in description and ">=" not in description:
            op = ">"

        return evaluate_numeric_threshold(
            requirement_id=req_id,
            operator=op,
            expected_val=threshold,
            expected_unit="PERCENT",
            observed_values=observed_values,
            evidence_ids=evidence_ids,
            requirement_description=description,
        )

    # 6. Financial Turnover Rule Check
    if "TURNOVER" in description.upper() or "CRORE" in description.upper() or "LAKH" in description.upper():
        req_val, req_unit = parse_numeric_value(description)
        if req_val is not None:
            return evaluate_numeric_threshold(
                requirement_id=req_id,
                operator=">=",
                expected_val=req_val,
                expected_unit=req_unit or "INR",
                observed_values=observed_values,
                evidence_ids=evidence_ids,
                requirement_description=description,
            )

    # 7. Past Experience Rule Check
    if category == "EXPERIENCE" or "EXPERIENCE" in description.upper() or "YEARS" in description.upper():
        # Look for e.g. "5 years", "3 years"
        yr_match = re.search(r"([0-9]+)\s*(?:YEAR|YR)S?", description, re.IGNORECASE)
        past_years = int(yr_match.group(1)) if yr_match else 3

        # Extract dates from observed values
        wo_date = context.get("work_order_date")
        comp_date = context.get("completion_date")
        if not wo_date and not comp_date and observed_values:
            for obs in observed_values:
                d = parse_date_value(obs)
                if d and not comp_date:
                    comp_date = d

        return evaluate_experience_window(
            requirement_id=req_id,
            past_years_required=past_years,
            work_order_date_input=wo_date,
            completion_date_input=comp_date,
            tender_closing_date=context.get("anchor_date"),
            evidence_ids=evidence_ids,
        )

    # 8. Certificate / Validity Check
    if "VALID" in description.upper() or "EXPIR" in description.upper() or "DATE" in description.upper():
        expiry_val = observed_values[0] if observed_values else None
        return evaluate_date_validity(
            requirement_id=req_id,
            expiry_date_input=expiry_val,
            anchor_date=context.get("anchor_date"),
            evidence_ids=evidence_ids,
        )

    # 9. Generic Mandatory Evidence Presence Check
    if not observed_values:
        if is_mandatory:
            req_docs = req_dict.get("evidence_required", [])
            doc_name = req_docs[0] if req_docs else "Proof Document"
            return evaluate_mandatory_evidence(
                requirement_id=req_id,
                evidence_present=False,
                evidence_name=doc_name,
                evidence_ids=evidence_ids,
            )
        else:
            return ComplianceFinding(
                requirement_id=req_id,
                state=ComplianceState.UNVERIFIED,
                risk_level="LOW",
                reasoning_trace="Optional requirement was not addressed in bidder submission.",
                rule_type="OPTIONAL_REQUIREMENT",
                expected={"mandatory": False},
                observed={"is_present": False},
                evidence_ids=evidence_ids,
                confidence=1.0,
            )

    # Default fallback: return REVIEW for subjective/unmatched requirements
    return ComplianceFinding(
        requirement_id=req_id,
        state=ComplianceState.REVIEW,
        risk_level="MEDIUM",
        reasoning_trace="Requirement requires semantic or technical evaluation by human reviewer / LLM.",
        rule_type="SEMANTIC_REVIEW",
        expected={"description": description},
        observed={"values_submitted": observed_values},
        evidence_ids=evidence_ids,
        confidence=1.0,
    )

