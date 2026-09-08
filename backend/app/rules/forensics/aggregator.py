"""Cross-Bidder Forensic Aggregator and Canonical Finding Generator.

Coordinates pairwise comparison across:
1. DIGITAL METADATA COLLISIONS
2. BIDDER-TO-BIDDER TIE-INS
3. FINANCIAL INSTRUMENT OVERLAP
4. FORMATTING CLONES

Performs multi-signal reinforcement, cluster/cartel ring detection,
and produces canonical VerificationFinding instances.
"""

from collections import defaultdict
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

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

from app.rules.forensics.models import (
    ForensicSignal,
    ForensicType,
    SignalStrength,
)
from app.rules.forensics.metadata_collision import DigitalMetadataCollisionChecker
from app.rules.forensics.bidder_tie_in import BidderTieInChecker
from app.rules.forensics.financial_overlap import FinancialInstrumentOverlapChecker
from app.rules.forensics.formatting_clones import (
    FormattingCloneChecker,
    TenderTemplateExclusionIndex,
)

logger = logging.getLogger(__name__)


class CrossBidderForensicAggregator:
    """Master aggregator orchestrating all 4 forensic checks and generating canonical findings."""

    def __init__(self, verifier_id: str = "ANTI_COLLUSION_VERIFIER"):
        self.verifier_id = verifier_id
        self.layer = VerificationLayer.ANTI_COLLUSION_AND_RELATEDNESS

    async def execute_forensics(self, context: VerificationContext) -> List[VerificationFinding]:
        findings: List[VerificationFinding] = []
        bidders = context.bidders or []
        submissions = context.submissions or []
        documents = context.documents or []
        claims = context.claims or []
        observations = context.observations or []
        tender_metadata = context.tender_metadata or {}
        requirements = context.requirements or []

        # If fewer than 2 bidders, cross-bidder collusion is not applicable
        if len(bidders) < 2 and len(submissions) < 2:
            return findings

        # Bidder map: id -> bidder dict
        bidder_map: Dict[str, Dict[str, Any]] = {}
        for b in bidders:
            bid_id = str(b.get("id") or b.get("bidder_id") or "")
            if bid_id:
                bidder_map[bid_id] = b

        # Submission to Bidder map
        sub_to_bidder: Dict[str, str] = {}
        for s in submissions:
            sub_id = str(s.get("id") or "")
            b_id = str(s.get("bidder_id") or "")
            if sub_id and b_id:
                sub_to_bidder[sub_id] = b_id

        # Bidder to Documents map
        docs_by_bidder: Dict[str, List[Document]] = defaultdict(list)
        tender_docs: List[Document] = []

        for d in documents:
            if getattr(d, "document_type", None) == "TENDER_SPECIFICATION" or not d.bid_submission_id:
                tender_docs.append(d)
                continue

            b_id = sub_to_bidder.get(d.bid_submission_id)
            if not b_id and bidders:
                # If document filename contains bidder identifier
                fname_lower = (d.filename or "").lower()
                for bid_cand in bidder_map.keys():
                    if bid_cand.lower() in fname_lower:
                        b_id = bid_cand
                        break
            if b_id:
                docs_by_bidder[b_id].append(d)

        # Claims & Observations by Bidder
        claims_by_bidder: Dict[str, List[Any]] = defaultdict(list)
        for c in claims:
            if c.bidder_id:
                claims_by_bidder[c.bidder_id].append(c)

        obs_by_bidder: Dict[str, List[Any]] = defaultdict(list)
        for o in observations:
            if o.bidder_id:
                obs_by_bidder[o.bidder_id].append(o)

        all_bidder_ids = sorted(list(bidder_map.keys()))
        if len(all_bidder_ids) < 2:
            # Fallback: extract from submissions
            all_bidder_ids = sorted(list({str(s.get("bidder_id")) for s in submissions if s.get("bidder_id")}))
            for bid_id in all_bidder_ids:
                if bid_id not in bidder_map:
                    bidder_map[bid_id] = {"id": bid_id, "legal_name": f"Bidder-{bid_id}"}

        if len(all_bidder_ids) < 2:
            return findings

        # Build Tender Template Exclusion Index once
        tender_index = TenderTemplateExclusionIndex(
            tender_metadata=tender_metadata,
            requirements=requirements,
            tender_documents=tender_docs,
        )

        # Track pairwise signals between (bidder_a, bidder_b)
        pairwise_signals: Dict[Tuple[str, str], List[ForensicSignal]] = defaultdict(list)
        any_financial_instruments_found = False

        # Execute Pairwise Comparison Matrix (A ↔ B, A ↔ C, B ↔ C)
        for i in range(len(all_bidder_ids)):
            for j in range(i + 1, len(all_bidder_ids)):
                bid_a = all_bidder_ids[i]
                bid_b = all_bidder_ids[j]
                pair = (bid_a, bid_b)

                b_dict_a = bidder_map.get(bid_a, {"id": bid_a, "legal_name": bid_a})
                b_dict_b = bidder_map.get(bid_b, {"id": bid_b, "legal_name": bid_b})
                docs_a = docs_by_bidder.get(bid_a, [])
                docs_b = docs_by_bidder.get(bid_b, [])
                c_a = claims_by_bidder.get(bid_a, [])
                c_b = claims_by_bidder.get(bid_b, [])
                o_a = obs_by_bidder.get(bid_a, [])
                o_b = obs_by_bidder.get(bid_b, [])

                # Check 1: Digital Metadata Collisions
                meta_signals = DigitalMetadataCollisionChecker.analyze_bidder_pair(
                    bidder_a_id=bid_a,
                    bidder_b_id=bid_b,
                    docs_a=docs_a,
                    docs_b=docs_b,
                )
                pairwise_signals[pair].extend(meta_signals)

                # Check 2: Bidder-to-Bidder Tie-Ins
                tie_signals = BidderTieInChecker.analyze_bidder_pair(
                    bidder_a=b_dict_a,
                    bidder_b=b_dict_b,
                    docs_a=docs_a,
                    docs_b=docs_b,
                    claims_a=c_a,
                    claims_b=c_b,
                    obs_a=o_a,
                    obs_b=o_b,
                )
                pairwise_signals[pair].extend(tie_signals)

                # Check 3: Financial Instrument Overlap
                fin_signals, fin_has_evidence = FinancialInstrumentOverlapChecker.analyze_bidder_pair(
                    bidder_a_id=bid_a,
                    bidder_b_id=bid_b,
                    docs_a=docs_a,
                    docs_b=docs_b,
                    obs_a=o_a,
                    obs_b=o_b,
                )
                pairwise_signals[pair].extend(fin_signals)
                if fin_has_evidence:
                    any_financial_instruments_found = True

                # Check 4: Formatting Clones
                format_signals = FormattingCloneChecker.analyze_bidder_pair(
                    bidder_a_id=bid_a,
                    bidder_b_id=bid_b,
                    docs_a=docs_a,
                    docs_b=docs_b,
                    tender_index=tender_index,
                )
                pairwise_signals[pair].extend(format_signals)

        # Detect Bidder Cartel Clusters (Connected Components)
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        for (b_a, b_b), sigs in pairwise_signals.items():
            if any(s.strength in (SignalStrength.CRITICAL, SignalStrength.HIGH, SignalStrength.MEDIUM) for s in sigs):
                adjacency[b_a].add(b_b)
                adjacency[b_b].add(b_a)

        visited: Set[str] = set()
        clusters: List[List[str]] = []
        for b_id in all_bidder_ids:
            if b_id not in visited and b_id in adjacency:
                cluster = []
                queue = [b_id]
                visited.add(b_id)
                while queue:
                    curr = queue.pop(0)
                    cluster.append(curr)
                    for neighbor in adjacency.get(curr, []):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                if len(cluster) > 1:
                    clusters.append(cluster)

        # Convert Pairwise Signals into Canonical Verification Findings
        for (bid_a, bid_b), sigs in pairwise_signals.items():
            if not sigs:
                continue

            name_a = bidder_map.get(bid_a, {}).get("legal_name", bid_a)
            name_b = bidder_map.get(bid_b, {}).get("legal_name", bid_b)

            signal_types = list({s.forensic_type.value for s in sigs})
            signal_codes = [s.signal_code for s in sigs]
            has_critical = any(s.strength == SignalStrength.CRITICAL for s in sigs)
            has_high = any(s.strength == SignalStrength.HIGH for s in sigs)
            has_medium = any(s.strength == SignalStrength.MEDIUM for s in sigs)

            # Severity and Confidence Calibration with Multi-Signal Reinforcement
            # Note: Confidence is calibrated as an expert heuristic alignment score [0.0 - 1.0]
            # reflecting signal strength and cross-category convergence, NOT a mathematically validated probability.
            if has_critical or len(signal_types) >= 3 or (has_high and len(sigs) >= 3):
                severity = FindingSeverity.CRITICAL
                confidence = 0.95
            elif has_high or len(signal_types) >= 2 or len(sigs) >= 2:
                severity = FindingSeverity.HIGH
                confidence = 0.88
            elif has_medium:
                severity = FindingSeverity.MEDIUM
                confidence = 0.78
            else:
                severity = FindingSeverity.LOW
                confidence = 0.65

            # Determine whether this is primarily a related-entity disclosure
            is_related_entity = "RELATED_CORPORATE_ENTITY" in signal_codes and len(sigs) == 1

            reasons = [s.description for s in sigs]
            category_names = ", ".join(signal_types)
            explanation = (
                f"Cross-Bidder Forensic Link Detected between '{name_a}' and '{name_b}': "
                f"Identified {len(sigs)} reinforcing signal(s) across [{category_names}]: {'; '.join(reasons)}. "
                "Advisory finding for human procurement officer review under GeM Anti-Collusion Guidelines."
            )

            provenance_records = []
            for s in sigs:
                for q in s.provenance_quotes:
                    provenance_records.append(
                        ProvenanceRecord(
                            quote=q,
                            source_type=f"FORENSIC_{s.forensic_type.value}",
                            source_document=", ".join(s.documents_a + s.documents_b) or "procurement_submission",
                        )
                    )

            matched_docs = sorted(list({d for s in sigs for d in (s.documents_a + s.documents_b)}))
            matched_fields = sorted(list({s.matched_field for s in sigs}))

            cluster_context = next((c for c in clusters if bid_a in c and bid_b in c), [bid_a, bid_b])

            finding = VerificationFinding(
                verifier=self.verifier_id,
                verification_layer=self.layer,
                bidder_id=bid_a,
                status=ComplianceState.REVIEW,
                severity=severity,
                claim={"involved_bidders": [bid_a, bid_b], "bidder_names": [name_a, name_b]},
                observation={
                    "matched_signal_codes": signal_codes,
                    "signal_count": len(sigs),
                    "categories": signal_types,
                    "matched_fields": matched_fields,
                    "cluster_size": len(cluster_context),
                },
                reason=explanation,
                evidence=provenance_records,
                confidence=confidence,
                machine_readable_flags=signal_codes + [
                    "COLLUSION_RISK_FLAG",
                    "MULTI_BIDDER_REVIEW_REQUIRED",
                    "RELATED_ENTITY" if is_related_entity else "FORENSIC_COLLUSION_SIGNAL",
                ],
                metadata={
                    "forensic_type": signal_types[0] if len(signal_types) == 1 else "MULTI_CATEGORY_FORENSIC",
                    "forensic_categories": signal_types,
                    "classification": "RELATED_ENTITY" if is_related_entity else "COLLUSION_SIGNAL",
                    "bidder_ids": [bid_a, bid_b],
                    "bidder_names": [name_a, name_b],
                    "compared_documents": matched_docs,
                    "matched_fields": matched_fields,
                    "confidence": confidence,
                    "confidence_basis": "HEURISTIC_SIGNAL_CONVERGENCE",
                    "calibration_notice": "Confidence represents an expert heuristic indicator alignment score, not a frequentist statistical probability.",
                    "signals": [s.model_dump() for s in sigs],
                    "cluster_bidders": cluster_context,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "decision_authority": "HUMAN_PROCUREMENT_OFFICER",
                },
            )
            findings.append(finding)

        # If financial instrument evidence was completely absent across the procurement:
        if not any_financial_instruments_found and len(all_bidder_ids) >= 2:
            findings.append(
                VerificationFinding(
                    verifier=self.verifier_id,
                    verification_layer=self.layer,
                    status=ComplianceState.UNVERIFIED,
                    severity=FindingSeverity.INFO,
                    claim={"check": "FINANCIAL_INSTRUMENT_OVERLAP"},
                    observation="No EMD or Bank Guarantee instrument documents or serial numbers were submitted.",
                    reason=(
                        "Financial Instrument Overlap: No conclusive financial instrument evidence (EMD / BG) was "
                        "submitted in the bidder documentation for cross-bidder issuing branch or serial verification."
                    ),
                    confidence=1.0,
                    machine_readable_flags=["FINANCIAL_INSTRUMENT_EVIDENCE_ABSENT", "NO_CONCLUSIVE_EVIDENCE"],
                    metadata={
                        "forensic_type": "FINANCIAL_INSTRUMENT_OVERLAP",
                        "bidder_count": len(all_bidder_ids),
                        "status": "NO_CONCLUSIVE_EVIDENCE",
                    },
                )
            )

        # If multiple bidders evaluated and NO collusion signals were detected, emit clear audit PASS finding
        active_review_findings = [f for f in findings if f.status == ComplianceState.REVIEW]
        if not active_review_findings and len(all_bidder_ids) >= 2:
            findings.append(
                VerificationFinding(
                    verifier=self.verifier_id,
                    verification_layer=self.layer,
                    status=ComplianceState.PASS,
                    severity=FindingSeverity.INFO,
                    claim={"bidder_count": len(all_bidder_ids)},
                    observation="No cross-bidder metadata, contact, address, banking, or formatting linkages detected.",
                    reason=(
                        f"Multi-bidder cross-forensic screening clear across {len(all_bidder_ids)} competing submissions: "
                        "no suspicious linkages detected across digital metadata, corporate identity, financial instruments, or narrative formatting."
                    ),
                    confidence=1.0,
                    machine_readable_flags=[
                        "NO_COLLUSION_DETECTED",
                        "NO_SUSPICIOUS_LINKAGE_DETECTED",
                        "FORENSIC_SCREENING_CLEAR",
                    ],
                    metadata={
                        "bidders_screened": all_bidder_ids,
                        "checks_evaluated": [
                            "DIGITAL_METADATA_COLLISIONS",
                            "BIDDER_TO_BIDDER_TIE_INS",
                            "FINANCIAL_INSTRUMENT_OVERLAP",
                            "FORMATTING_CLONES",
                        ],
                    },
                )
            )

        return findings
