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
        
        findings: List[VerificationFinding] = []
        bidders = context.bidders or []
        submissions = context.submissions or []
        documents = context.documents or []
        
        logger.info(
            "Executing Layer 4: Anti-Collusion and Relatedness for procurement '%s' (bidders: %d, submissions: %d, documents: %d)",
            context.procurement_id or "unknown",
            len(bidders),
            len(submissions),
            len(documents),
        )

        # If single bidder, no cross-bidder collusion is possible
        if len(bidders) < 2 and len(submissions) < 2:
            return findings

        # Bidder ID to details mapping
        bidder_map: Dict[str, Dict[str, Any]] = {}
        for b in bidders:
            bid_id = str(b.get("id") or b.get("bidder_id") or "")
            if bid_id:
                bidder_map[bid_id] = b

        # Submission to Bidder ID mapping
        sub_to_bidder: Dict[str, str] = {}
        for s in submissions:
            sub_id = str(s.get("id") or "")
            b_id = str(s.get("bidder_id") or "")
            if sub_id and b_id:
                sub_to_bidder[sub_id] = b_id

        # Document to Bidder ID mapping
        doc_to_bidder: Dict[str, str] = {}
        for d in documents:
            if d.bid_submission_id and d.bid_submission_id in sub_to_bidder:
                doc_to_bidder[d.id] = sub_to_bidder[d.bid_submission_id]

        # Structure to track pairwise collusion signals between (bidder_a, bidder_b)
        pairwise_signals: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)

        # 1. Shared Contact Details (Phone numbers & Specific Non-Public Emails)
        phones: Dict[str, List[str]] = defaultdict(list)
        emails: Dict[str, List[str]] = defaultdict(list)

        for bid_id, b in bidder_map.items():
            phone = b.get("phone") or b.get("mobile") or b.get("contact_number")
            if phone:
                clean_phone = re.sub(r"[^0-9]", "", str(phone))
                if len(clean_phone) >= 10:
                    phones[clean_phone[-10:]].append(bid_id)

            email = b.get("email") or b.get("contact_email")
            if email:
                clean_email = str(email).strip().lower()
                # Exclude generic public domains for domain check, but check exact email match
                emails[clean_email].append(bid_id)

        for phone_num, b_list in phones.items():
            unique_bids = sorted(list(set(b_list)))
            if len(unique_bids) > 1:
                for i in range(len(unique_bids)):
                    for j in range(i + 1, len(unique_bids)):
                        pair = (unique_bids[i], unique_bids[j])
                        pairwise_signals[pair].append({
                            "signal": "SHARED_PHONE_NUMBER",
                            "description": f"Both bidders share identical contact phone number '...{phone_num[-4:]}'.",
                            "evidence": f"Phone: {phone_num}",
                        })

        for email_addr, b_list in emails.items():
            unique_bids = sorted(list(set(b_list)))
            if len(unique_bids) > 1:
                for i in range(len(unique_bids)):
                    for j in range(i + 1, len(unique_bids)):
                        pair = (unique_bids[i], unique_bids[j])
                        pairwise_signals[pair].append({
                            "signal": "SHARED_EMAIL_ADDRESS",
                            "description": f"Both bidders share identical contact email '{email_addr}'.",
                            "evidence": f"Email: {email_addr}",
                        })

        # 2. Shared Physical Address
        addresses: Dict[str, List[str]] = defaultdict(list)
        for bid_id, b in bidder_map.items():
            addr = b.get("address") or b.get("registered_office")
            if addr:
                clean_addr = re.sub(r"[\s,.-]", "", str(addr).upper())
                if len(clean_addr) > 15:
                    addresses[clean_addr].append(bid_id)

        for addr_str, b_list in addresses.items():
            unique_bids = sorted(list(set(b_list)))
            if len(unique_bids) > 1:
                for i in range(len(unique_bids)):
                    for j in range(i + 1, len(unique_bids)):
                        pair = (unique_bids[i], unique_bids[j])
                        pairwise_signals[pair].append({
                            "signal": "SHARED_PHYSICAL_ADDRESS",
                            "description": "Both bidders list identical registered physical address.",
                            "evidence": f"Address hash match ({len(addr_str)} chars)",
                        })

        # 3. Shared Bank Details (Account / IFSC)
        bank_accounts: Dict[str, List[str]] = defaultdict(list)
        for bid_id, b in bidder_map.items():
            acc = b.get("bank_account") or b.get("account_number")
            if acc:
                clean_acc = re.sub(r"[^0-9A-Za-z]", "", str(acc))
                if len(clean_acc) >= 8:
                    bank_accounts[clean_acc].append(bid_id)

        for acc_num, b_list in bank_accounts.items():
            unique_bids = sorted(list(set(b_list)))
            if len(unique_bids) > 1:
                for i in range(len(unique_bids)):
                    for j in range(i + 1, len(unique_bids)):
                        pair = (unique_bids[i], unique_bids[j])
                        pairwise_signals[pair].append({
                            "signal": "SHARED_BANK_ACCOUNT",
                            "description": f"Critical Collusion Indicator: Competing bidders declare identical bank account '...{acc_num[-4:]}'.",
                            "evidence": f"Bank Account: {acc_num}",
                        })

        # 4. Document Metadata Fingerprints (PDF Author / Producer / Tool & Creation Times)
        authors: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        for d in documents:
            b_id = doc_to_bidder.get(d.id)
            if not b_id:
                continue
            # Check for author tag in content or extra context
            text = d.content_text or ""
            author_match = re.search(r"(?:Author|Creator|Producer)\s*[:\-]\s*([^\n\r]+)", text, re.IGNORECASE)
            if author_match:
                author_val = author_match.group(1).strip().lower()
                if len(author_val) > 3 and author_val not in ("microsoft word", "adobe acrobat", "unknown", "pdf generator"):
                    authors[author_val].append((b_id, d.filename))

        for author_name, items in authors.items():
            b_ids = sorted(list({b_id for b_id, _ in items}))
            if len(b_ids) > 1:
                for i in range(len(b_ids)):
                    for j in range(i + 1, len(b_ids)):
                        pair = (b_ids[i], b_ids[j])
                        docs_involved = [fname for bid, fname in items if bid in pair]
                        pairwise_signals[pair].append({
                            "signal": "SHARED_DOCUMENT_AUTHOR",
                            "description": f"Competing bidder technical documents generated by identical author/machine user '{author_name}'.",
                            "evidence": f"Files: {', '.join(docs_involved)}",
                        })

        # 5. Aggregate Multi-Signal Pairwise Findings
        for (bid_a, bid_b), sigs in pairwise_signals.items():
            name_a = bidder_map.get(bid_a, {}).get("legal_name", bid_a)
            name_b = bidder_map.get(bid_b, {}).get("legal_name", bid_b)
            signal_names = [s["signal"] for s in sigs]
            has_bank = "SHARED_BANK_ACCOUNT" in signal_names
            
            # Calibrate severity based on signal convergence
            if has_bank or len(sigs) >= 3:
                severity = FindingSeverity.CRITICAL
            elif len(sigs) >= 2:
                severity = FindingSeverity.HIGH
            else:
                severity = FindingSeverity.MEDIUM

            # Compute heuristic confidence based on signal strengths
            # Use the highest confidence value among the involved signals
            signal_confidences = [SIGNAL_CONFIDENCE.get(sig, SIGNAL_CONFIDENCE["DEFAULT"]) for sig in signal_names]
            max_signal_conf = max(signal_confidences) if signal_confidences else SIGNAL_CONFIDENCE["DEFAULT"]
            # Apply a scaling factor to reflect overall assessment (e.g., 0.95)
            confidence = round(max_signal_conf * 0.95, 2)

            reasons = [s["description"] for s in sigs]
            explanation = (
                f"Potential Collusion / Affiliation Detected between Bidder A ('{name_a}') and Bidder B ('{name_b}'): "
                f"Identified {len(sigs)} matching structural signal(s): {'; '.join(reasons)}. "
                "Requires procurement officer review under GeM Anti-Collusion and Related-Party guidelines."
            )

            # Suppress boilerplate-only author overlap findings
            if len(sigs) == 1 and signal_names[0] == "SHARED_DOCUMENT_AUTHOR":
                desc = sigs[0].get("description", "").lower()
                if any(phrase in desc for phrase in BOQ_BOILERPLATE_PHRASES):
                    # Skip adding this finding as it's likely boilerplate overlap
                    continue

            findings.append(
                VerificationFinding(
                    verifier=self.verifier_id,
                    verification_layer=self.layer,
                    bidder_id=bid_a,
                    status=ComplianceState.REVIEW,
                    severity=severity,
                    claim={"involved_bidders": [bid_a, bid_b], "bidder_names": [name_a, name_b]},
                    observation={"matched_signals": signal_names, "signal_count": len(sigs)},
                    reason=explanation,
                    evidence=[ProvenanceRecord(
                        quote=s.get("evidence"),
                        source_type="COLLUSION_SIGNAL_EVIDENCE"
                    ) for s in sigs],
                    confidence=confidence,
                    machine_readable_flags=signal_names + ["COLLUSION_RISK_FLAG", "MULTI_BIDDER_REVIEW_REQUIRED"],
                    metadata={
                        "involved_bidders": [bid_a, bid_b],
                        "bidder_names": [name_a, name_b],
                        "signals": sigs,
                    },
                )
            )

        # 6. If multiple bidders evaluated and no collusion detected, record positive audit
        if not findings and len(bidders) >= 2:
            findings.append(
                VerificationFinding(
                    verifier=self.verifier_id,
                    verification_layer=self.layer,
                    status=ComplianceState.PASS,
                    severity=FindingSeverity.INFO,
                    claim={"bidder_count": len(bidders)},
                    observation="No cross-bidder metadata, contact, address, or banking linkage detected.",
                    reason=f"Multi-bidder anti-collusion screening clear across {len(bidders)} competing submissions.",
                    confidence=1.0,
                    machine_readable_flags=["NO_COLLUSION_DETECTED", "NO_SUSPICIOUS_LINKAGE_DETECTED"],
                    metadata={"bidders_screened": [b.get("id") for b in bidders]},
                )
            )

        # Extend with aggregator findings rather than returning twice
        aggregator_findings = await self._aggregator.execute_forensics(context)
        if aggregator_findings:
            findings.extend(aggregator_findings)

        return findings