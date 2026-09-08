"""Utility functions for Layer 6: Past Performance and Capacity Verification.

- `normalize_to_years` / `normalize_to_months`: Converts quantities / capacities expressed per unit (year, month, week, day)
  into canonical period equivalents.
- `calculate_past_performance_ratio`: Evaluates percentage or monetary threshold of past qualifying contracts
  against tender requirement / estimated bid value.
- `is_recent`: Safely parses ISO-8601 dates, normalizes to UTC, and checks if within recency window.
  Returns None for unparseable dates (insufficient evidence).
- `evaluate_capacity_saturation`: Computes deterministic capacity saturation and net available capacity.
- `classify_evidence_authority`: Classifies source authority (DECLARED, CERTIFIED, INDEPENDENT) based on document type / source without inflating numerical confidence.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from app.rules.engine import evaluate_numeric_operator, parse_numeric_value, currency_to_inr
except ImportError:
    try:
        from rules.engine import evaluate_numeric_operator, parse_numeric_value, currency_to_inr
    except ImportError:
        pass


def normalize_to_years(value: float, unit: str) -> float:
    """Convert a quantity expressed per unit to an annual equivalent.
    Supported units (case-insensitive): YEAR, MONTH, WEEK, DAY.
    """
    unit_str = str(unit).upper().strip()
    if unit_str in {"YEAR", "YEARS", "Y", "YR", "YRS", "ANNUAL", "ANNUALLY", "PER_ANNUM", "PA"}:
        return float(value)
    if unit_str in {"MONTH", "MONTHS", "MO", "MOS", "M", "MONTHLY"}:
        return float(value) * 12.0
    if unit_str in {"WEEK", "WEEKS", "WK", "WKS", "W", "WEEKLY"}:
        return float(value) * 52.0
    if unit_str in {"DAY", "DAYS", "D", "DAILY"}:
        return float(value) * 365.0
    raise ValueError(f"Unsupported period unit: {unit}")


def normalize_to_months(value: float, unit: str) -> float:
    """Convert a quantity / capacity expressed per unit to a monthly equivalent."""
    unit_str = str(unit).upper().strip()
    if unit_str in {"MONTH", "MONTHS", "MO", "MOS", "M", "MONTHLY"}:
        return float(value)
    if unit_str in {"YEAR", "YEARS", "Y", "YR", "YRS", "ANNUAL", "ANNUALLY", "PER_ANNUM", "PA"}:
        return float(value) / 12.0
    if unit_str in {"WEEK", "WEEKS", "WK", "WKS", "W", "WEEKLY"}:
        return float(value) * (52.0 / 12.0)
    if unit_str in {"DAY", "DAYS", "D", "DAILY"}:
        return float(value) * 30.0
    return float(value)


def calculate_past_performance_ratio(
    past_value: float,
    reference_value: float,
    operator: str = ">=",
    required_pct: Optional[float] = None,
) -> Tuple[bool, float, str]:
    """Evaluate past-performance monetary threshold or percentage.
    
    Args:
        past_value: Cumulative or single past contract value (in INR).
        reference_value: Estimated tender value or base reference value (in INR).
        operator: Comparison operator ('>=', '>', '==', etc.).
        required_pct: Required percentage (e.g. 50.0 for 50%). If None, past_value is compared directly to reference_value.
        
    Returns:
        (passes, actual_pct_or_val, explanation)
    """
    if reference_value <= 0:
        return False, 0.0, "Reference / Tender value is non-positive; cannot compute past performance ratio"
    
    if required_pct is not None:
        actual_pct = (past_value / reference_value) * 100.0
        passes = evaluate_numeric_operator(operator, expected_val=required_pct, observed_val=actual_pct)
        explanation = f"Past performance ratio {actual_pct:.2f}% vs required {operator} {required_pct:.2f}% of tender value (INR {reference_value:,.2f})"
        return passes, actual_pct, explanation
    else:
        passes = evaluate_numeric_operator(operator, expected_val=reference_value, observed_val=past_value)
        explanation = f"Past contract value INR {past_value:,.2f} vs required {operator} INR {reference_value:,.2f}"
        return passes, past_value, explanation


def is_recent(
    date_str: Optional[str],
    recency_days: int = 1095,
    reference_date: Optional[datetime] = None,
) -> Optional[bool]:
    """Return True if ISO-8601 date_str is within recency_days from reference_date (UTC).
    
    Returns:
        True: Date is valid and strictly within the recency window.
        False: Date is valid and outside the recency window (expired).
        None: Date string is missing or cannot be reliably parsed (insufficient evidence).
    """
    if not date_str or not str(date_str).strip():
        return None
    
    clean_date = str(date_str).strip()
    dt: Optional[datetime] = None
    
    # Try ISO format
    try:
        dt = datetime.fromisoformat(clean_date.replace("Z", "+00:00"))
    except Exception:
        # Try common date formats DD-MM-YYYY, YYYY-MM-DD, DD/MM/YYYY
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y", "%b %Y", "%B %Y", "%b-%Y", "%B-%Y"):
            try:
                dt = datetime.strptime(clean_date, fmt)
                break
            except Exception:
                pass
                
    if dt is None:
        return None
        
    # Normalize to UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
        
    if reference_date is None:
        ref_utc = datetime.now(timezone.utc)
    else:
        if reference_date.tzinfo is None:
            ref_utc = reference_date.replace(tzinfo=timezone.utc)
        else:
            ref_utc = reference_date.astimezone(timezone.utc)
            
    days_diff = (ref_utc - dt).days
    # If date is in the future (within reasonable tolerance) or within recency window
    if 0 <= days_diff <= recency_days:
        return True
    elif days_diff < 0:
        # Future completion date or active
        return True
    else:
        return False


def evaluate_capacity_saturation(
    total_capacity: float,
    committed_capacity: float,
    required_capacity: float,
) -> Dict[str, Any]:
    """Computes deterministic capacity saturation and net available capacity.
    
    Returns:
        dict with:
        - total_capacity
        - committed_capacity
        - net_available_capacity
        - required_capacity
        - saturation_percentage
        - is_overcommitted (committed > total or saturation > 100%)
        - is_sufficient (net_available >= required)
        - summary
    """
    if total_capacity <= 0:
        return {
            "total_capacity": total_capacity,
            "committed_capacity": committed_capacity,
            "net_available_capacity": 0.0,
            "required_capacity": required_capacity,
            "saturation_percentage": 100.0 if committed_capacity > 0 else 0.0,
            "is_overcommitted": True,
            "is_sufficient": False,
            "summary": "Total stated capacity is non-positive.",
        }
        
    net_available = max(0.0, total_capacity - committed_capacity)
    saturation_pct = (committed_capacity / total_capacity) * 100.0
    is_overcommitted = committed_capacity > total_capacity or saturation_pct > 100.0
    is_sufficient = (not is_overcommitted) and (net_available >= required_capacity)
    
    summary = (
        f"Stated capacity: {total_capacity:,.2f}, Committed: {committed_capacity:,.2f} "
        f"({saturation_pct:.1f}% saturation). Net available: {net_available:,.2f} vs Required: {required_capacity:,.2f}."
    )
    
    return {
        "total_capacity": total_capacity,
        "committed_capacity": committed_capacity,
        "net_available_capacity": net_available,
        "required_capacity": required_capacity,
        "saturation_percentage": saturation_pct,
        "is_overcommitted": is_overcommitted,
        "is_sufficient": is_sufficient,
        "summary": summary,
    }


def classify_evidence_authority(
    document_type: Optional[str] = None,
    source_document: Optional[str] = None,
    quote: Optional[str] = None,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> str:
    """Classifies source authority explicitly into DECLARED, CERTIFIED, or INDEPENDENT.
    
    - INDEPENDENT: Government portals, GeM portal, third-party client verification registries, authoritative external APIs.
    - CERTIFIED: Practicing Chartered Accountant (CA) certificates with UDIN, Client Completion/Performance Certificates, OEM Authorized Certificates.
    - DECLARED: Self-declarations, bidder undertakings, technical compliance sheets without third-party endorsement.
    """
    combined = f"{document_type or ''} {source_document or ''} {quote or ''}".upper()
    if extra_meta:
        combined += f" {extra_meta}"
        
    if any(k in combined for k in ("GEM_PORTAL", "GOVERNMENT", "EXTERNAL_REGISTRY", "INDEPENDENT_VERIFICATION", "CLIENT_VERIFIED")):
        return "INDEPENDENT"
    if any(k in combined for k in ("CA_CERTIFICATE", "UDIN", "CHARTERED_ACCOUNTANT", "CLIENT_CERTIFICATE", "COMPLETION_CERTIFICATE", "PERFORMANCE_CERTIFICATE", "CERTIFIED")):
        return "CERTIFIED"
    return "DECLARED"
