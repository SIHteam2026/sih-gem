"""Canonical Forensic Models and Normalization Utilities.

Defines schemas, signals, enumerations, and normalization routines for
Level 4: Anti-Collusion and Relatedness cross-bidder forensic engine.
"""

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

# Recognized generic/public email service providers (where shared domain is not suspicious)
PUBLIC_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.co.in",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "rediffmail.com",
    "icloud.com",
    "protonmail.com",
    "proton.me",
    "zoho.com",
    "zoho.in",
    "mail.com",
    "aol.com",
}

# Standard address abbreviation expansions for robust normalization
ADDRESS_ABBREVIATIONS = [
    (r"\bst\b|\bstr\b", "street"),
    (r"\brd\b", "road"),
    (r"\bave\b|\bav\b", "avenue"),
    (r"\bblvd\b", "boulevard"),
    (r"\bflr\b|\bfl\b", "floor"),
    (r"\bbldg\b|\bbld\b", "building"),
    (r"\bopp\b|\bopposite\b", "opposite"),
    (r"\bnr\b", "near"),
    (r"\bapt\b|\bapts\b", "apartment"),
    (r"\bind\b|\bindl\b", "industrial"),
    (r"\best\b|\bestate\b", "estate"),
    (r"\bsoc\b|\bsociety\b", "society"),
    (r"\bdist\b", "district"),
    (r"\bpo\b|\bp\.o\.\b", "post office"),
    (r"\bno\b|\bno\.\b", "number"),
    (r"\bsec\b|\bsect\b", "sector"),
    (r"\bplt\b|\bplot\b", "plot"),
    (r"\bph\b|\bphase\b", "phase"),
    (r"\bmarg\b", "marg"),
    (r"\bnagar\b", "nagar"),
    (r"\bpvt\b|\bltd\b|\bllp\b|\bcorp\b|\binc\b", ""),
]

# Honorifics / professional designations to strip from signatories
SIGNATORY_HONORIFICS_PATTERN = re.compile(
    r"^(mr\.?|mrs\.?|ms\.?|dr\.?|shri\.?|smt\.?|er\.?|ca\.?|adv\.?|prof\.?)\s+",
    re.IGNORECASE,
)


class ForensicType(str, Enum):
    """Four core verification checks under Level 4 Anti-Collusion."""
    DIGITAL_METADATA_COLLISION = "DIGITAL_METADATA_COLLISION"
    BIDDER_TIE_IN = "BIDDER_TIE_IN"
    FINANCIAL_INSTRUMENT_OVERLAP = "FINANCIAL_INSTRUMENT_OVERLAP"
    FORMATTING_CLONE = "FORMATTING_CLONE"


class SignalStrength(str, Enum):
    """Calibrated evidence strength for forensic signals."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    BENIGN = "BENIGN"


class ForensicSignal(BaseModel):
    """Machine-readable signal representing a detected cross-bidder correlation."""
    forensic_type: ForensicType = Field(..., description="Category of forensic check.")
    signal_code: str = Field(..., description="Unique machine-readable signal tag.")
    strength: SignalStrength = Field(default=SignalStrength.MEDIUM, description="Calibrated signal strength.")
    bidder_a_id: str = Field(..., description="First involved bidder identifier.")
    bidder_b_id: str = Field(..., description="Second involved bidder identifier.")
    description: str = Field(..., description="Human-readable audit explanation of the signal.")
    matched_field: str = Field(..., description="Field or property where collision occurred.")
    evidence_value_a: Optional[str] = Field(default=None, description="Observed value from Bidder A.")
    evidence_value_b: Optional[str] = Field(default=None, description="Observed value from Bidder B.")
    documents_a: List[str] = Field(default_factory=list, description="Associated document filenames from Bidder A.")
    documents_b: List[str] = Field(default_factory=list, description="Associated document filenames from Bidder B.")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="Confidence score for this signal.")
    provenance_quotes: List[str] = Field(default_factory=list, description="Exact quotes or provenances.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context attributes.")


# ---------------------------------------------------------------------------
# Normalization Functions
# ---------------------------------------------------------------------------

def normalize_phone(raw_phone: Optional[str]) -> Optional[str]:
    """Normalizes phone numbers to standard 10-digit Indian format or clean digits."""
    if not raw_phone:
        return None
    digits = re.sub(r"[^0-9]", "", str(raw_phone))
    if not digits:
        return None
    # Strip leading country code (+91 or 91) if 12 digits
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    # Strip leading 0 if 11 digits
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    
    if len(digits) >= 10:
        return digits[-10:]
    return digits if len(digits) >= 7 else None


def normalize_address(raw_address: Optional[str]) -> Tuple[str, Optional[str]]:
    """Normalizes an Indian or commercial physical address.
    
    Returns:
        Tuple[normalized_text, extracted_pincode]
    """
    if not raw_address:
        return "", None
    
    addr = str(raw_address).lower()
    
    # Extract Indian 6-digit PIN code (e.g. 110001, 400051, 600001)
    pin_match = re.search(r"\b([1-9][0-9]{5})\b", addr)
    pin_code = pin_match.group(1) if pin_match else None
    
    # Clean punctuation and standardize spaces
    addr = re.sub(r"[\r\n\t,;:\.\-\/\\#\(\)]+", " ", addr)
    
    # Apply standard abbreviation replacements
    for pattern, replacement in ADDRESS_ABBREVIATIONS:
        if replacement:
            addr = re.sub(pattern, f" {replacement} ", addr, flags=re.IGNORECASE)
        else:
            addr = re.sub(pattern, " ", addr, flags=re.IGNORECASE)
            
    # Collapse multiple whitespaces
    cleaned = re.sub(r"\s+", " ", addr).strip()
    return cleaned, pin_code


def normalize_signatory(raw_name: Optional[str]) -> str:
    """Normalizes an authorized signatory name by removing honorifics, titles, and punctuation."""
    if not raw_name:
        return ""
    name = str(raw_name).strip()
    # Strip leading honorifics
    name = SIGNATORY_HONORIFICS_PATTERN.sub("", name)
    # Strip trailing corporate roles like (Director), (Partner), Authorised Signatory
    name = re.sub(r"\s*\(?(director|managing director|md|partner|proprietor|ceo|signatory|authorized signatory|auth\.? sig\.?)\)?\s*$", "", name, flags=re.IGNORECASE)
    # Clean non-alphabetical characters (except spaces)
    name = re.sub(r"[^a-zA-Z\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip().lower()


def normalize_email(raw_email: Optional[str]) -> Tuple[str, str, bool]:
    """Normalizes email address and returns (normalized_email, domain, is_public_domain)."""
    if not raw_email:
        return "", "", False
    clean = str(raw_email).strip().lower()
    if "@" not in clean:
        return clean, "", False
    parts = clean.split("@", 1)
    domain = parts[1].strip()
    is_public = domain in PUBLIC_EMAIL_DOMAINS
    return clean, domain, is_public


def normalize_cin(raw_cin: Optional[str]) -> Optional[str]:
    """Normalizes 21-character corporate CIN or LLPIN."""
    if not raw_cin:
        return None
    cleaned = re.sub(r"[^0-9A-Za-z]", "", str(raw_cin)).upper()
    if len(cleaned) in (21, 8, 7):
        return cleaned
    return None


def parse_document_timestamp(raw_ts: Any) -> Optional[datetime]:
    """Robustly parses document creation/modification timestamps from PDF or ISO formats."""
    if not raw_ts:
        return None
    if isinstance(raw_ts, datetime):
        if raw_ts.tzinfo is None:
            return raw_ts.replace(tzinfo=timezone.utc)
        return raw_ts
    
    ts_str = str(raw_ts).strip()
    
    # PDF Date format: D:YYYYMMDDHHmmSSOHH'mm'
    if ts_str.startswith("D:"):
        pdf_digits = re.sub(r"[^0-9]", "", ts_str[2:16])
        if len(pdf_digits) >= 14:
            try:
                dt = datetime.strptime(pdf_digits[:14], "%Y%m%d%H%M%S")
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        elif len(pdf_digits) >= 8:
            try:
                dt = datetime.strptime(pdf_digits[:8], "%Y%m%d")
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

    # ISO formats (e.g. 2026-09-08T11:47:00, 2026-09-08 11:47:00)
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(ts_str[:19], fmt[:len(ts_str[:19])])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, IndexError):
            continue

    return None
