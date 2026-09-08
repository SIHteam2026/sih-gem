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
from typing import Any, Dict, List, Optional

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
        logger.info(
            "Executing Layer 4: Anti-Collusion and Relatedness for procurement '%s' (bidders: %d, submissions: %d, documents: %d)",
            context.procurement_id or "unknown",
            len(context.bidders or []),
            len(context.submissions or []),
            len(context.documents or []),
        )

        return await self._aggregator.execute_forensics(context)
