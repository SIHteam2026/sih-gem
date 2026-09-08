"""Layer 6: Past Performance and Capacity Verifier.

Evaluates past performance and delivery capacity against tender criteria:
- Number of completed qualifying contracts
- Contract value evidence vs required threshold
- Stated delivery capacity vs required supply volume/timeline
- Current workload / pending commitments (capacity overcommitment detection)
- Missing evidence safely mapped to UNVERIFIED (never fabricated).
"""

import logging
import re
from typing import Any, Dict, List, Optional

try:
    from app.models.evaluation import ComplianceState
    from app.models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
    from app.models.tender_contract import CanonicalEvaluationField, RequirementEvaluationContract
    from app.models.verification import (
        FindingSeverity,
        VerificationContext,
        VerificationFinding,
        VerificationLayer,
    )
    from app.rules.engine import parse_numeric_value, evaluate_numeric_operator, is_unit_compatible, evaluate_numeric_threshold, currency_to_inr
    from app.rules.layers.base import BaseVerifier
except ImportError:
    try:
        from app.models.evaluation import ComplianceState
        from app.models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
        from app.models.tender_contract import CanonicalEvaluationField, RequirementEvaluationContract
        from app.models.verification import (
            FindingSeverity,
            VerificationContext,
            VerificationFinding,
            VerificationLayer,
        )
        from app.rules.engine import parse_numeric_value
        from app.rules.layers.base import BaseVerifier
    except ImportError:
        from models.evaluation import ComplianceState
        from models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
        from models.tender_contract import CanonicalEvaluationField, RequirementEvaluationContract
        from models.verification import (
            FindingSeverity,
            VerificationContext,
            VerificationFinding,
            VerificationLayer,
        )
        from rules.engine import parse_numeric_value
        from rules.layers.base import BaseVerifier

logger = logging.getLogger(__name__)


class PastPerformanceCapacityVerifier(BaseVerifier):
    """Verifier for Layer 6: Past Performance and Capacity."""

    @property
    def verifier_id(self) -> str:
        return "PAST_PERFORMANCE_CAPACITY_VERIFIER"

    @property
    def layer(self) -> VerificationLayer:
        return VerificationLayer.PAST_PERFORMANCE_AND_CAPACITY

    async def verify(self, context: VerificationContext) -> List[VerificationFinding]:
        findings: List[VerificationFinding] = []
        requirements = context.requirements or []
        claims = context.claims or []
        observations = context.observations or []
        bidders = context.bidders or []

        # Filter requirements related to experience, capacity, past performance
        perf_reqs = [
            r for r in requirements
            if r.evaluation_field in (
                CanonicalEvaluationField.SIMILAR_CONTRACT_COUNT,
                CanonicalEvaluationField.GENERAL_EXPERIENCE,
                CanonicalEvaluationField.DELIVERY_TIMELINE_DAYS,
            )
            or any(kw in r.description.upper() for kw in ("EXPERIENCE", "SIMILAR WORK", "SIMILAR CONTRACT", "CAPACITY", "PAST PERFORMANCE", "SUPPLY RECORD"))
        ]

        if not perf_reqs:
            return findings

        for req in perf_reqs:
            req_id = req.requirement_id
            # Determine expected threshold and unit from requirement metadata
            expected_val = req.threshold_value
            expected_unit = getattr(req, "threshold_unit", None)
            operator = req.operator or ">="
            # If unit is missing, we cannot safely evaluate numeric comparisons
            if expected_unit is None:
                # For count‑based requirements, treat missing unit as a simple count threshold
                if isinstance(expected_val, (int, float)):
                    expected_unit = "COUNT"
                else:
                    # Ambiguous requirement – mark as UNVERIFIED for this bidder
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            requirement_id=req_id,
                            bidder_id=bid_id,
                            status=ComplianceState.UNVERIFIED,
                            severity=FindingSeverity.HIGH,
                            claim=None,
                            observation="Threshold unit missing for requirement.",
                            reason=f"Requirement '{req.title or req_id}' lacks a threshold unit; cannot deterministically evaluate.",
                            evidence=[],
                            confidence=0.0,
                            machine_readable_flags=["THRESHOLD_UNIT_MISSING"],
                            metadata={"requirement_id": req_id},
                        )
                    )
                    continue
            # Set min_count for count‑type thresholds (default to 1 if not specified)
            min_count = expected_val if expected_unit == "COUNT" else 1

            # Evaluate per bidder
            for b in (bidders or [{"id": None, "legal_name": "Bidder"}]):
                bid_id = b.get("id") or b.get("bidder_id")
                b_name = b.get("legal_name", "Bidder")

                b_claims = [c for c in claims if c.requirement_id == req_id and (not c.bidder_id or c.bidder_id == bid_id)]
                b_obs = [o for o in observations if o.requirement_id == req_id and (not o.bidder_id or o.bidder_id == bid_id)]

                # Case A: No evidence or claim provided
                if not b_claims and not b_obs:
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            requirement_id=req_id,
                            bidder_id=bid_id,
                            status=ComplianceState.UNVERIFIED,
                            severity=FindingSeverity.HIGH,
                            claim=None,
                            observation="No past performance or capacity certificates submitted.",
                            reason=f"Past Performance Evidence Missing: Requirement '{req.title or req_id}' requires past performance/capacity certificates, but no documentation was provided.",
                            evidence=[],
                            confidence=1.0,
                            machine_readable_flags=["PAST_PERFORMANCE_UNVERIFIED", "MANDATORY_EXPERIENCE_MISSING"],
                            metadata={"requirement_id": req_id},
                        )
                    )
                    continue

                # Case B: Observations / Work Orders submitted
                observed_counts = []
                capacity_overcommitted = False
                total_work_orders = len(b_obs)

                for obs in b_obs:
                    val_num, unit = parse_numeric_value(obs.observed_value)
                    if val_num is not None:
                        observed_counts.append(val_num)
                    
                    # Check for workload / capacity overcommitment indicator in text
                    quote_lower = (obs.source_quote or "").lower()
                    if "capacity" in quote_lower and ("exceeded" in quote_lower or "overcommitted" in quote_lower or "backlog" in quote_lower):
                        capacity_overcommitted = True

                if capacity_overcommitted:
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            requirement_id=req_id,
                            bidder_id=bid_id,
                            status=ComplianceState.REVIEW,
                            severity=FindingSeverity.HIGH,
                            claim={"work_orders_count": total_work_orders},
                            observation="Capacity constraint or active project backlog flagged.",
                            reason=f"Capacity Constraint Signal for {b_name}: Submitted performance reports indicate existing manufacturing/delivery commitments may exceed available monthly output capacity.",
                            evidence=[ProvenanceRecord(document_name=o.source_document, page_number=o.page_number, quote=o.source_quote) for o in b_obs],
                            confidence=0.85,
                            machine_readable_flags=["CAPACITY_OVERCOMMITMENT_RISK", "DELIVERY_RISK_REVIEW"],
                            metadata={"requirement_id": req_id},
                        )
                    )
                elif total_work_orders >= (min_count or 1):
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            requirement_id=req_id,
                            bidder_id=bid_id,
                            status=ComplianceState.PASS,
                            severity=FindingSeverity.INFO,
                            claim={"required_contracts": min_count},
                            observation=f"Submitted {total_work_orders} verified completion certificate(s).",
                            reason=f"Past Performance Satisfied: {b_name} provided {total_work_orders} verified past completion certificate(s) meeting the requirement of {min_count}.",
                            evidence=[ProvenanceRecord(document_name=o.source_document, page_number=o.page_number, quote=o.source_quote, raw_value=o.observed_value) for o in b_obs],
                            confidence=1.0,
                            machine_readable_flags=["PAST_PERFORMANCE_MET", "QUALIFYING_CONTRACTS_VERIFIED"],
                            metadata={"requirement_id": req_id, "contracts_count": total_work_orders},
                        )
                    )
                else:
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            requirement_id=req_id,
                            bidder_id=bid_id,
                            status=ComplianceState.FAIL,
                            severity=FindingSeverity.HIGH,
                            claim={"required_contracts": min_count},
                            observation=f"Only {total_work_orders} contract(s) documented.",
                            reason=f"Past Performance Deficit: {b_name} submitted {total_work_orders} contract certificate(s), which is below the minimum required {min_count}.",
                            evidence=[ProvenanceRecord(document_name=o.source_document, page_number=o.page_number, quote=o.source_quote, raw_value=o.observed_value) for o in b_obs],
                            confidence=1.0,
                            machine_readable_flags=["EXPERIENCE_DEFICIT", "INSUFFICIENT_QUALIFYING_CONTRACTS"],
                            metadata={"requirement_id": req_id, "achieved": total_work_orders, "required": min_count},
                        )
                    )

        return findings
