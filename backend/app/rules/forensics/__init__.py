"""Forensics package for Level 4 Anti-Collusion and Relatedness."""

from app.rules.forensics.models import (
    ForensicSignal,
    ForensicType,
    SignalStrength,
    normalize_address,
    normalize_cin,
    normalize_email,
    normalize_phone,
    normalize_signatory,
    parse_document_timestamp,
)
from app.rules.forensics.metadata_collision import (
    DigitalMetadataCollisionChecker,
    extract_metadata_from_document,
)
from app.rules.forensics.bidder_tie_in import (
    BidderTieInChecker,
    extract_bidder_identity_profile,
)
from app.rules.forensics.financial_overlap import (
    FinancialInstrumentOverlapChecker,
    FinancialInstrumentRecord,
)
from app.rules.forensics.formatting_clones import (
    FormattingCloneChecker,
    LayoutVisualComparisonHook,
    TenderTemplateExclusionIndex,
)
from app.rules.forensics.aggregator import CrossBidderForensicAggregator

__all__ = [
    "ForensicSignal",
    "ForensicType",
    "SignalStrength",
    "normalize_phone",
    "normalize_address",
    "normalize_signatory",
    "normalize_email",
    "normalize_cin",
    "parse_document_timestamp",
    "DigitalMetadataCollisionChecker",
    "extract_metadata_from_document",
    "BidderTieInChecker",
    "extract_bidder_identity_profile",
    "FinancialInstrumentOverlapChecker",
    "FinancialInstrumentRecord",
    "FormattingCloneChecker",
    "LayoutVisualComparisonHook",
    "TenderTemplateExclusionIndex",
    "CrossBidderForensicAggregator",
]
