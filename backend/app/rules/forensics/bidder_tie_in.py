"""Check 2: Bidder-to-Bidder Tie-In Forensics.

Cross-checks extracted bidder evidence for shared:
- Authorized signatory names
- Registered physical addresses (with PIN-code and abbreviation normalization)
- Telephone / mobile numbers (with country code and prefix normalization)
- Email addresses and corporate domain tie-ins (filtering public webmail domains)
- CIN / LLPIN identity linkages
- Shared banking identifiers (Account Number & IFSC)

Classifies evidence according to calibrated forensic strength.
Advisory to HUMAN_PROCUREMENT_OFFICER under GeM Anti-Collusion Guidelines.
"""

from difflib import SequenceMatcher
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models.procurement import Document
from app.models.evidence import BidderClaim, EvidenceObservation
from app.rules.forensics.models import (
    ForensicSignal,
    ForensicType,
    SignalStrength,
    normalize_address,
    normalize_cin,
    normalize_email,
    normalize_phone,
    normalize_signatory,
)

logger = logging.getLogger(__name__)

# Pattern to locate signatory blocks inside document text
SIGNATORY_EXTRACT_REGEX = re.compile(
    r"(?:authori[sz]ed\s+signatory|name\s+of\s+signatory|signatory\s+name|for\s+[a-z0-9\s,\.\-]+\n)\s*[:\-]?\s*([a-z\s\.\,\(\)]{3,40})",
    re.IGNORECASE,
)

# Pattern to locate telephone/mobile numbers in text
PHONE_EXTRACT_REGEX = re.compile(
    r"(?:tel|phone|mobile|contact|cell|ph\.?)\s*[:\-]?\s*(\+?91[\-\s]?[6-9]\d{9}|0\d{2,4}[\-\s]?\d{6,8}|[6-9]\d{9})",
    re.IGNORECASE,
)


class BidderProfileEvidence:
    """Aggregated corporate identity and contact evidence for a single bidder."""

    def __init__(
        self,
        bidder_id: str,
        legal_name: str,
        phones: Set[str],
        emails: Set[str],
        domains: Set[str],
        addresses: Set[str],
        pin_codes: Set[str],
        signatories: Set[str],
        cins: Set[str],
        bank_accounts: Set[str],
        raw_bidder: Dict[str, Any],
    ):
        self.bidder_id = bidder_id
        self.legal_name = legal_name
        self.phones = phones
        self.emails = emails
        self.domains = domains
        self.addresses = addresses
        self.pin_codes = pin_codes
        self.signatories = signatories
        self.cins = cins
        self.bank_accounts = bank_accounts
        self.raw_bidder = raw_bidder


def extract_bidder_identity_profile(
    bidder_dict: Dict[str, Any],
    documents: List[Document],
    claims: List[BidderClaim],
    observations: List[EvidenceObservation],
) -> BidderProfileEvidence:
    """Consolidates explicit profile attributes, claim assertions, and document text facts."""
    bid_id = str(bidder_dict.get("id") or bidder_dict.get("bidder_id") or "")
    legal_name = str(bidder_dict.get("legal_name") or bidder_dict.get("name") or f"Bidder-{bid_id}")

    phones: Set[str] = set()
    emails: Set[str] = set()
    domains: Set[str] = set()
    addresses: Set[str] = set()
    pin_codes: Set[str] = set()
    signatories: Set[str] = set()
    cins: Set[str] = set()
    bank_accounts: Set[str] = set()

    # 1. From bidder dictionary
    for p_key in ("phone", "mobile", "contact_number", "telephone"):
        raw_p = bidder_dict.get(p_key)
        norm_p = normalize_phone(raw_p)
        if norm_p:
            phones.add(norm_p)

    for e_key in ("email", "contact_email", "official_email"):
        raw_e = bidder_dict.get(e_key)
        norm_e, domain, is_public = normalize_email(raw_e)
        if norm_e:
            emails.add(norm_e)
        if domain and not is_public:
            domains.add(domain)

    for a_key in ("address", "registered_office", "registered_address"):
        raw_a = bidder_dict.get(a_key)
        norm_a, pin = normalize_address(raw_a)
        if norm_a and len(norm_a) > 10:
            addresses.add(norm_a)
        if pin:
            pin_codes.add(pin)

    for s_key in ("signatory", "authorized_signatory", "signatory_name", "contact_person"):
        raw_s = bidder_dict.get(s_key)
        norm_s = normalize_signatory(raw_s)
        if norm_s and len(norm_s) > 3:
            signatories.add(norm_s)

    for c_key in ("cin", "llpin", "corporate_id"):
        raw_c = bidder_dict.get(c_key)
        norm_c = normalize_cin(raw_c)
        if norm_c:
            cins.add(norm_c)

    for b_key in ("bank_account", "account_number"):
        raw_b = bidder_dict.get(b_key)
        if raw_b:
            clean_b = re.sub(r"[^0-9A-Za-z]", "", str(raw_b))
            if len(clean_b) >= 8:
                bank_accounts.add(clean_b)

    # 2. From document text content
    for doc in documents:
        text = doc.content_text or ""
        if not text:
            continue

        # Signatory patterns
        for m in SIGNATORY_EXTRACT_REGEX.finditer(text):
            cand_sig = normalize_signatory(m.group(1))
            if len(cand_sig) > 4 and not any(w in cand_sig for w in ("limited", "pvt", "corp", "tender", "date", "place")):
                signatories.add(cand_sig)

        # Phone patterns in document text
        for m in PHONE_EXTRACT_REGEX.finditer(text):
            cand_p = normalize_phone(m.group(1))
            if cand_p:
                phones.add(cand_p)

        # Bank accounts declared in text
        bank_matches = re.finditer(r"(?:A/C\s*(?:No\.?)?|Account\s*(?:Number|No\.?))\s*[:\-]?\s*([0-9]{9,18})", text, re.IGNORECASE)
        for bm in bank_matches:
            bank_accounts.add(bm.group(1))

    # 3. From observations / claims
    for obs in observations:
        if obs.bidder_id == bid_id:
            val_str = str(obs.observed_value or "")
            cin_val = normalize_cin(val_str)
            if cin_val:
                cins.add(cin_val)

    return BidderProfileEvidence(
        bidder_id=bid_id,
        legal_name=legal_name,
        phones=phones,
        emails=emails,
        domains=domains,
        addresses=addresses,
        pin_codes=pin_codes,
        signatories=signatories,
        cins=cins,
        bank_accounts=bank_accounts,
        raw_bidder=bidder_dict,
    )


class BidderTieInChecker:
    """Forensic engine for Check 2: Bidder-to-Bidder Tie-Ins."""

    @classmethod
    def analyze_bidder_pair(
        cls,
        bidder_a: Dict[str, Any],
        bidder_b: Dict[str, Any],
        docs_a: List[Document],
        docs_b: List[Document],
        claims_a: List[BidderClaim],
        claims_b: List[BidderClaim],
        obs_a: List[EvidenceObservation],
        obs_b: List[EvidenceObservation],
    ) -> List[ForensicSignal]:
        """Cross-checks identity fields and contact indicators between two bidders."""
        signals: List[ForensicSignal] = []

        prof_a = extract_bidder_identity_profile(bidder_a, docs_a, claims_a, obs_a)
        prof_b = extract_bidder_identity_profile(bidder_b, docs_b, claims_b, obs_b)

        bid_a_id = prof_a.bidder_id
        bid_b_id = prof_b.bidder_id
        name_a = prof_a.legal_name
        name_b = prof_b.legal_name

        # 1. Shared Bank Account (CRITICAL Signal)
        shared_accounts = prof_a.bank_accounts.intersection(prof_b.bank_accounts)
        for acc in shared_accounts:
            masked = f"...{acc[-4:]}" if len(acc) >= 4 else acc
            signals.append(
                ForensicSignal(
                    forensic_type=ForensicType.BIDDER_TIE_IN,
                    signal_code="SHARED_BANK_ACCOUNT",
                    strength=SignalStrength.CRITICAL,
                    bidder_a_id=bid_a_id,
                    bidder_b_id=bid_b_id,
                    description=(
                        f"Critical Identity Collision: Competing bidders '{name_a}' and '{name_b}' declare the "
                        f"identical bank account number '{masked}'."
                    ),
                    matched_field="bank_account",
                    evidence_value_a=acc,
                    evidence_value_b=acc,
                    confidence=0.98,
                    provenance_quotes=[f"Identical bank account '{masked}' shared across both submissions."],
                    metadata={"masked_account": masked},
                )
            )

        # 2. Shared Authorized Signatory (HIGH Signal)
        for sig_a in prof_a.signatories:
            for sig_b in prof_b.signatories:
                # Exact match or token set match
                tokens_a = set(sig_a.split())
                tokens_b = set(sig_b.split())
                exact_match = sig_a == sig_b
                token_match = len(tokens_a) >= 2 and tokens_a == tokens_b
                ratio = SequenceMatcher(None, sig_a, sig_b).ratio()

                if exact_match or token_match or (ratio > 0.90 and len(sig_a) > 8):
                    signals.append(
                        ForensicSignal(
                            forensic_type=ForensicType.BIDDER_TIE_IN,
                            signal_code="SHARED_SIGNATORY",
                            strength=SignalStrength.HIGH,
                            bidder_a_id=bid_a_id,
                            bidder_b_id=bid_b_id,
                            description=(
                                f"High-Risk Affiliation Indicator: Both competing bidders '{name_a}' and '{name_b}' "
                                f"are represented or signed by the identical authorized signatory '{sig_a.title()}'."
                            ),
                            matched_field="authorized_signatory",
                            evidence_value_a=sig_a.title(),
                            evidence_value_b=sig_b.title(),
                            confidence=0.94,
                            provenance_quotes=[f"Signatory: '{sig_a.title()}' evidenced in submissions for both bidders."],
                            metadata={"signatory": sig_a.title()},
                        )
                    )

        # 3. Shared Uncommon Phone Number (HIGH Signal)
        shared_phones = prof_a.phones.intersection(prof_b.phones)
        for phone in shared_phones:
            masked = f"...{phone[-4:]}"
            signals.append(
                ForensicSignal(
                    forensic_type=ForensicType.BIDDER_TIE_IN,
                    signal_code="SHARED_PHONE_NUMBER",
                    strength=SignalStrength.HIGH,
                    bidder_a_id=bid_a_id,
                    bidder_b_id=bid_b_id,
                    description=(
                        f"Contact Tie-In Detected: Competing bidders '{name_a}' and '{name_b}' share the identical "
                        f"contact phone number '{masked}'."
                    ),
                    matched_field="phone",
                    evidence_value_a=phone,
                    evidence_value_b=phone,
                    confidence=0.92,
                    provenance_quotes=[f"Phone number: '{masked}' shared between bidders."],
                    metadata={"phone_tail": masked},
                )
            )

        # 4. Shared Exact Non-Public Email Address (HIGH Signal)
        shared_emails = prof_a.emails.intersection(prof_b.emails)
        for email in shared_emails:
            signals.append(
                ForensicSignal(
                    forensic_type=ForensicType.BIDDER_TIE_IN,
                    signal_code="SHARED_EMAIL_ADDRESS",
                    strength=SignalStrength.HIGH,
                    bidder_a_id=bid_a_id,
                    bidder_b_id=bid_b_id,
                    description=(
                        f"Shared Contact Email: Competing bidders '{name_a}' and '{name_b}' share the identical "
                        f"contact email address '{email}'."
                    ),
                    matched_field="email",
                    evidence_value_a=email,
                    evidence_value_b=email,
                    confidence=0.95,
                    provenance_quotes=[f"Contact email: '{email}' registered by both entities."],
                    metadata={"email": email},
                )
            )

        # 5. Shared Proprietary/Corporate Email Domain (MEDIUM Signal)
        shared_domains = prof_a.domains.intersection(prof_b.domains)
        # Exclude if exact email already flagged
        if not shared_emails:
            for domain in shared_domains:
                signals.append(
                    ForensicSignal(
                        forensic_type=ForensicType.BIDDER_TIE_IN,
                        signal_code="SHARED_EMAIL_DOMAIN",
                        strength=SignalStrength.MEDIUM,
                        bidder_a_id=bid_a_id,
                        bidder_b_id=bid_b_id,
                        description=(
                            f"Corporate Domain Correlation: Both bidders use email addresses originating from the "
                            f"identical corporate/group domain '@{domain}'."
                        ),
                        matched_field="email_domain",
                        evidence_value_a=domain,
                        evidence_value_b=domain,
                        confidence=0.80,
                        provenance_quotes=[f"Shared corporate domain: '@{domain}'."],
                        metadata={"domain": domain},
                    )
                )

        # 6. Shared Registered Physical Address
        for addr_a in prof_a.addresses:
            for addr_b in prof_b.addresses:
                # Direct match without whitespace
                compact_a = re.sub(r"\s+", "", addr_a)
                compact_b = re.sub(r"\s+", "", addr_b)
                ratio = SequenceMatcher(None, compact_a, compact_b).ratio()

                # Strong signal: exact or near-identical address (> 0.85 similarity and >= 15 chars)
                if ratio > 0.85 and len(compact_a) >= 15:
                    signals.append(
                        ForensicSignal(
                            forensic_type=ForensicType.BIDDER_TIE_IN,
                            signal_code="SHARED_PHYSICAL_ADDRESS",
                            strength=SignalStrength.HIGH,
                            bidder_a_id=bid_a_id,
                            bidder_b_id=bid_b_id,
                            description=(
                                f"Shared Physical Premise: Competing bidders '{name_a}' and '{name_b}' register the "
                                f"identical physical address ('{addr_a[:50]}...')."
                            ),
                            matched_field="address",
                            evidence_value_a=addr_a,
                            evidence_value_b=addr_b,
                            confidence=0.88,
                            provenance_quotes=[f"Address match: '{addr_a}' vs '{addr_b}'"],
                            metadata={"similarity": round(ratio, 2)},
                        )
                    )

        # 7. Common Corporate Group / CIN Identification (RELATED_ENTITY finding)
        shared_cins = prof_a.cins.intersection(prof_b.cins)
        for cin in shared_cins:
            signals.append(
                ForensicSignal(
                    forensic_type=ForensicType.BIDDER_TIE_IN,
                    signal_code="RELATED_CORPORATE_ENTITY",
                    strength=SignalStrength.HIGH,
                    bidder_a_id=bid_a_id,
                    bidder_b_id=bid_b_id,
                    description=(
                        f"Related Corporate Entity Detected: Competing bidders '{name_a}' and '{name_b}' share the "
                        f"identical corporate registration number (CIN/LLPIN: '{cin}'). Classify as RELATED_ENTITY "
                        "subject to officer review rather than automatic collusion."
                    ),
                    matched_field="cin",
                    evidence_value_a=cin,
                    evidence_value_b=cin,
                    confidence=0.96,
                    provenance_quotes=[f"Corporate identifier (CIN/LLPIN): '{cin}' shared across bidders."],
                    metadata={"cin": cin, "classification": "RELATED_ENTITY"},
                )
            )

        # Deduplicate signals
        deduped: List[ForensicSignal] = []
        seen: Set[str] = set()
        for s in signals:
            if s.signal_code not in seen:
                seen.add(s.signal_code)
                deduped.append(s)

        return deduped
