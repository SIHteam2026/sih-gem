"""Layer 4: Anti-Collusion and Relatedness Verifier.

Canonical 7-Layer Architecture - First-Layer Cross-Bidder Forensic Engine.

Integrates four comprehensive forensic checks across competing bidders:
1. DIGITAL METADATA COLLISIONS (machine/user profile, author, close timestamps, benign software filter)
2. BIDDER-TO-BIDDER TIE-INS (signatory, normalized phone, normalized address/PIN, non-public email/domain, CIN/LLPIN)
3. FINANCIAL INSTRUMENT OVERLAP (issuing branch, sequential instrument numbers, same-day issuance)
4. FORMATTING CLONES (tender-template exclusion index, standard boilerplate exclusion, identical narrative clauses, identical typos)

Aggregates pairwise and cluster-level signals for human procurement officer review.
Advisory under GeM Anti-Collusion and Related-Party Guidelines.
"""

import logging
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

try:
    from app.models.evaluation import ComplianceState
    from app.models.evidence import ProvenanceRecord
    from app.models.procurement import Document
    from app.models.verification import (
        FindingSeverity,
        VerificationContext,
        VerificationFinding,
        VerificationLayer,
    )
    from app.rules.layers.base import BaseVerifier
    from app.rules.forensics.aggregator import CrossBidderForensicAggregator
except ImportError:
    try:
        from app.models.evaluation import ComplianceState
        from app.models.evidence import ProvenanceRecord
        from app.models.procurement import Document
        from app.models.verification import (
            FindingSeverity,
            VerificationContext,
            VerificationFinding,
            VerificationLayer,
        )
        from app.rules.layers.base import BaseVerifier
        from app.rules.forensics.aggregator import CrossBidderForensicAggregator
    except ImportError:
        from models.evaluation import ComplianceState
        from models.evidence import ProvenanceRecord
        from models.procurement import Document
        from models.verification import (
            FindingSeverity,
            VerificationContext,
            VerificationFinding,
            VerificationLayer,
        )
        from rules.layers.base import BaseVerifier
        from rules.forensics.aggregator import CrossBidderForensicAggregator

logger = logging.getLogger(__name__)

# Heuristic confidence mapping for each signal type (0.0 to 1.0)
SIGNAL_CONFIDENCE: Dict[str, float] = {
    "SHARED_BANK_ACCOUNT": 1.0,
    "SHARED_PHONE_NUMBER": 0.9,
    "SHARED_EMAIL_ADDRESS": 0.8,
    "SHARED_PHYSICAL_ADDRESS": 0.7,
    "SHARED_DOCUMENT_AUTHOR": 0.6,
    "DEFAULT": 0.5,
}

# Common boilerplate phrases in CPCL BOQ documents that should be ignored for collusion detection
BOQ_BOILERPLATE_PHRASES = [
    "online multichannel water quality analyzer units",
    "boq",
    "specification",
    "description",
    "technical specifications",
]

class AntiCollusionVerifier(BaseVerifier):
    """Verifier for Layer 4: Anti-Collusion and Relatedness."""

    def __init__(self, aggregator: Optional[CrossBidderForensicAggregator] = None):
        self._aggregator = aggregator or CrossBidderForensicAggregator(verifier_id=self.verifier_id)

    @property
    def verifier_id(self) -> str:
        return "ANTI_COLLUSION_VERIFIER"

    @property
    def layer(self) -> VerificationLayer:
        return VerificationLayer.ANTI_COLLUSION_AND_RELATEDNESS

    async def verify(self, context: VerificationContext) -> List[VerificationFinding]:
        """Executes Level 4 cross-bidder forensic analysis."""
        return await self._aggregator.execute_forensics(context)