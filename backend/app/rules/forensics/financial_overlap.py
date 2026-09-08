"""Check 3: Financial Instrument Overlap Forensics.

Evaluates EMD / Bank Guarantee / FDR / Demand Draft evidence actually present
in bidder submissions. Detects:
- Exact same issuing bank branch
- Suspiciously sequential instrument serial numbers
- Correlated instrument metadata (same-day issuance)
- Distinguishes benign common bank selection from suspicious branch & serial linkages.
- Produces NO_CONCLUSIVE_EVIDENCE / UNVERIFIED when financial instrument evidence is absent.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models.procurement import Document
from app.models.evidence import EvidenceObservation
from app.rules.forensics.models import (
    ForensicSignal,
    ForensicType,
    SignalStrength,
    parse_document_timestamp,
)

logger = logging.getLogger(__name__)

# Pattern for Bank Guarantee / EMD / FDR / DD Instrument identification
INSTRUMENT_NUM_REGEX = re.compile(
    r"(?:(?:Bank\s+Guarantee|BG|EMD|FDR|DD|Demand\s+Draft|Challan)\s*(?:No\.?|Number|#)?)\s*[:\-]?\s*([A-Za-z0-9\/\-_]{5,30})",
    re.IGNORECASE,
)

ISSUING_BANK_REGEX = re.compile(
    r"(?:Issuing\s+Bank|Bank\s+Name|Name\s+of\s+Bank)\s*[:\-]?\s*([A-Za-z\s&]{3,40}(?:Bank|Corporation|Ltd))",
    re.IGNORECASE,
)

BRANCH_REGEX = re.compile(
    r"(?:Branch(?:\s+Name)?|IFSC(?:\s+Code)?)\s*[:\-]?\s*([A-Za-z0-9\s,\.\-]{3,40})",
    re.IGNORECASE,
)

DATE_REGEX = re.compile(
    r"(?:Date\s+of\s+Issue|Issue\s+Date|Dated)\s*[:\-]?\s*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-][0-9]{2}[\/\-][0-9]{2})",
    re.IGNORECASE,
)


class FinancialInstrumentRecord:
    """Represents an extracted financial instrument (EMD / Bank Guarantee)."""

    def __init__(
        self,
        bidder_id: str,
        document_filename: str,
        instrument_type: str,
        instrument_number: Optional[str] = None,
        bank_name: Optional[str] = None,
        branch: Optional[str] = None,
        issue_date: Optional[str] = None,
        amount: Optional[str] = None,
        beneficiary: Optional[str] = None,
        raw_quote: str = "",
    ):
        self.bidder_id = bidder_id
        self.document_filename = document_filename
        self.instrument_type = instrument_type
        self.instrument_number = instrument_number.strip() if instrument_number else None
        self.bank_name = bank_name.strip() if bank_name else None
        self.branch = branch.strip() if branch else None
        self.issue_date = issue_date.strip() if issue_date else None
        self.amount = amount.strip() if amount else None
        self.beneficiary = beneficiary.strip() if beneficiary else None
        self.raw_quote = raw_quote

    @property
    def numeric_serial(self) -> Optional[int]:
        """Extracts the numeric sequence suffix from an instrument number (e.g. BG/2026/10452 -> 10452)."""
        if not self.instrument_number:
            return None
        nums = re.findall(r"\d+", self.instrument_number)
        if nums:
            # Prefer the longest or last numeric component as the sequence number
            return int(nums[-1])
        return None

    @property
    def normalized_branch(self) -> Optional[str]:
        if not self.branch:
            return None
        return re.sub(r"[\s,\.\-]+", " ", self.branch).strip().lower()

    @property
    def normalized_bank(self) -> Optional[str]:
        if not self.bank_name:
            return None
        return re.sub(r"[\s,\.\-]+", " ", self.bank_name).strip().lower()


def extract_financial_instruments_from_documents(
    bidder_id: str,
    documents: List[Document],
    observations: List[EvidenceObservation],
) -> List[FinancialInstrumentRecord]:
    """Extracts genuine financial instrument records without hallucinating values."""
    records: List[FinancialInstrumentRecord] = []

    for doc in documents:
        text = doc.content_text or ""
        doc_name_upper = (doc.filename or "").upper()
        doc_type_upper = str(getattr(doc, "document_type", "")).upper()
        is_emd_doc = "EMD" in doc_name_upper or "GUARANTEE" in doc_name_upper or "BG" in doc_name_upper or "EMD_PROOF" in doc_type_upper

        # Only examine if document is EMD/BG or contains explicit guarantee keywords
        if not is_emd_doc and not any(k in text.upper() for k in ("BANK GUARANTEE", "EARNEST MONEY DEPOSIT", "EMD NO", "BG NO")):
            continue

        inst_match = INSTRUMENT_NUM_REGEX.search(text)
        bank_match = ISSUING_BANK_REGEX.search(text)
        branch_match = BRANCH_REGEX.search(text)
        date_match = DATE_REGEX.search(text)

        inst_num = inst_match.group(1) if inst_match else None
        bank_val = bank_match.group(1) if bank_match else None
        branch_val = branch_match.group(1) if branch_match else None
        date_val = date_match.group(1) if date_match else None

        if inst_num or bank_val or branch_val:
            records.append(
                FinancialInstrumentRecord(
                    bidder_id=bidder_id,
                    document_filename=doc.filename or "unknown_doc.pdf",
                    instrument_type="BANK_GUARANTEE" if "BG" in text.upper() or "GUARANTEE" in text.upper() else "EMD",
                    instrument_number=inst_num,
                    bank_name=bank_val,
                    branch=branch_val,
                    issue_date=date_val,
                    raw_quote=inst_match.group(0) if inst_match else (bank_match.group(0) if bank_match else ""),
                )
            )

    return records


class FinancialInstrumentOverlapChecker:
    """Forensic engine for Check 3: Financial Instrument Overlap."""

    @classmethod
    def analyze_bidder_pair(
        cls,
        bidder_a_id: str,
        bidder_b_id: str,
        docs_a: List[Document],
        docs_b: List[Document],
        obs_a: List[EvidenceObservation],
        obs_b: List[EvidenceObservation],
    ) -> Tuple[List[ForensicSignal], bool]:
        """Cross-checks financial instruments between two competing bidders.
        
        Returns:
            Tuple[List[ForensicSignal], has_conclusive_evidence]
        """
        signals: List[ForensicSignal] = []

        inst_a = extract_financial_instruments_from_documents(bidder_a_id, docs_a, obs_a)
        inst_b = extract_financial_instruments_from_documents(bidder_b_id, docs_b, obs_b)

        # If either bidder did not submit or have financial instrument evidence extracted:
        if not inst_a or not inst_b:
            return signals, False

        for rec_a in inst_a:
            for rec_b in inst_b:
                bank_a = rec_a.normalized_bank
                bank_b = rec_b.normalized_bank
                branch_a = rec_a.normalized_branch
                branch_b = rec_b.normalized_branch
                serial_a = rec_a.numeric_serial
                serial_b = rec_b.numeric_serial

                # Rule 1: Same bank alone is NOT collusion failure
                same_bank = bool(bank_a and bank_b and bank_a == bank_b)
                same_branch = bool(branch_a and branch_b and branch_a == branch_b)

                if same_branch:
                    # 1a. Sequential serial numbers from same branch (CRITICAL Signal)
                    if serial_a is not None and serial_b is not None:
                        diff = abs(serial_a - serial_b)
                        if 1 <= diff <= 5:
                            signals.append(
                                ForensicSignal(
                                    forensic_type=ForensicType.FINANCIAL_INSTRUMENT_OVERLAP,
                                    signal_code="SEQUENTIAL_FINANCIAL_INSTRUMENTS",
                                    strength=SignalStrength.CRITICAL,
                                    bidder_a_id=bidder_a_id,
                                    bidder_b_id=bidder_b_id,
                                    description=(
                                        f"Critical Financial Cartel Indicator: Competing bidders submitted sequentially "
                                        f"numbered financial instruments ({rec_a.instrument_number} vs {rec_b.instrument_number}, "
                                        f"serial difference: {diff}) issued by the exact same branch '{rec_a.branch}' of '{rec_a.bank_name}'."
                                    ),
                                    matched_field="instrument_serial_number",
                                    evidence_value_a=rec_a.instrument_number,
                                    evidence_value_b=rec_b.instrument_number,
                                    documents_a=[rec_a.document_filename],
                                    documents_b=[rec_b.document_filename],
                                    confidence=0.98,
                                    provenance_quotes=[
                                        f"Bidder A: '{rec_a.instrument_number}' from '{rec_a.branch}'",
                                        f"Bidder B: '{rec_b.instrument_number}' from '{rec_b.branch}'",
                                    ],
                                    metadata={
                                        "serial_a": serial_a,
                                        "serial_b": serial_b,
                                        "serial_difference": diff,
                                        "issuing_branch": rec_a.branch,
                                    },
                                )
                            )

                    # 1b. Same branch + same issuance date (HIGH Signal)
                    if rec_a.issue_date and rec_b.issue_date and rec_a.issue_date == rec_b.issue_date:
                        signals.append(
                            ForensicSignal(
                                forensic_type=ForensicType.FINANCIAL_INSTRUMENT_OVERLAP,
                                signal_code="SHARED_ISSUING_BRANCH_SAME_DAY",
                                strength=SignalStrength.HIGH,
                                bidder_a_id=bidder_a_id,
                                bidder_b_id=bidder_b_id,
                                description=(
                                    f"Coordinated Financial Issuance: Both bidders obtained financial guarantees from the "
                                    f"exact same branch '{rec_a.branch}' on the same date ({rec_a.issue_date})."
                                ),
                                matched_field="issuing_branch_and_date",
                                evidence_value_a=f"{rec_a.branch} ({rec_a.issue_date})",
                                evidence_value_b=f"{rec_b.branch} ({rec_b.issue_date})",
                                documents_a=[rec_a.document_filename],
                                documents_b=[rec_b.document_filename],
                                confidence=0.88,
                                provenance_quotes=[f"Branch '{rec_a.branch}', Date '{rec_a.issue_date}'"],
                                metadata={"branch": rec_a.branch, "issue_date": rec_a.issue_date},
                            )
                        )
                    else:
                        # 1c. Same issuing branch alone (MEDIUM Signal)
                        signals.append(
                            ForensicSignal(
                                forensic_type=ForensicType.FINANCIAL_INSTRUMENT_OVERLAP,
                                signal_code="SHARED_ISSUING_BRANCH",
                                strength=SignalStrength.MEDIUM,
                                bidder_a_id=bidder_a_id,
                                bidder_b_id=bidder_b_id,
                                description=(
                                    f"Shared Financial Issuing Branch: Both bidders obtained guarantees from the identical "
                                    f"bank branch '{rec_a.branch}' ('{rec_a.bank_name}')."
                                ),
                                matched_field="issuing_branch",
                                evidence_value_a=rec_a.branch,
                                evidence_value_b=rec_b.branch,
                                documents_a=[rec_a.document_filename],
                                documents_b=[rec_b.document_filename],
                                confidence=0.75,
                                provenance_quotes=[f"Issuing branch: '{rec_a.branch}'"],
                                metadata={"branch": rec_a.branch, "bank": rec_a.bank_name},
                            )
                        )

        return signals, True
