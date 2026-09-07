"""Layer 5: Adversarial Technical Verifier.

Evaluates adversarial technical compliance beyond raw keyword matching:
- Direct contradictions with tender specifications
- Hidden exceptions ("we comply except for clause 4.2", "with exclusion of")
- Conditional compliance language ("will comply upon award", "subject to raw material availability")
- Evasive statements ("industry standard specifications apply")
- "Will comply" future assertions without required supporting evidence
- Technical parameter mismatches between declaration and datasheets
- SLA / Warranty term inconsistency (e.g. 5-year declaration vs 2-year OEM certificate)
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

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

# Adversarial language regex patterns
HIDDEN_EXCEPTION_REGEX = re.compile(
    r"\b(?:with\s+(?:the\s+)?exception\s+of|except\s+(?:for|clause|section|as\s+stated)|"
    r"subject\s+to\s+exclusions?|deviating\s+from|exclusion\s+of|not\s+applicable\s+to\s+our\s+scope|"
    r"unless\s+otherwise\s+agreed|not\s+included\s+in\s+our\s+offer)\b",
    re.IGNORECASE,
)

CONDITIONAL_COMPLIANCE_REGEX = re.compile(
    r"\b(?:will\s+comply\s+(?:upon|after|post)\s+(?:award|contract|order|po)|"
    r"subject\s+to\s+(?:raw\s+material\s+availability|price\s+revision|mutual\s+agreement|standard\s+terms|oem\s+confirmation)|"
    r"conditional\s+upon|shall\s+be\s+arranged\s+upon\s+award|to\s+be\s+submitted\s+later)\b",
    re.IGNORECASE,
)

EVASIVE_STATEMENT_REGEX = re.compile(
    r"\b(?:industry\s+standards?\s+apply|standard\s+market\s+specifications?|as\s+per\s+standard\s+catalogue|"
    r"details\s+available\s+on\s+request|refer\s+to\s+standard\s+brochure|substantially\s+equivalent)\b",
    re.IGNORECASE,
)

WILL_COMPLY_PROMISE_REGEX = re.compile(
    r"\b(?:we\s+(?:shall|will|agree\s+to)\s+comply|undertake\s+to\s+provide|committed\s+to\s+achieve)\b",
    re.IGNORECASE,
)


class AdversarialTechnicalVerifier(BaseVerifier):
    """Verifier for Layer 5: Adversarial Technical Analysis."""

    @property
    def verifier_id(self) -> str:
        return "ADVERSARIAL_TECHNICAL_VERIFIER"

    @property
    def layer(self) -> VerificationLayer:
        return VerificationLayer.ADVERSARIAL_TECHNICAL

    async def verify(self, context: VerificationContext) -> List[VerificationFinding]:
        findings: List[VerificationFinding] = []
        requirements = context.requirements or []
        claims = context.claims or []
        observations = context.observations or []

        # Map requirements by ID
        req_map: Dict[str, RequirementEvaluationContract] = {r.requirement_id: r for r in requirements}

        # Check all claims for adversarial wording patterns
        for claim in claims:
            statement = str(claim.raw_statement or claim.claimed_value or "")
            req_id = claim.requirement_id
            req_contract = req_map.get(req_id)
            bidder_id = claim.bidder_id
            submission_id = claim.bid_submission_id

            prov = [
                ProvenanceRecord(
                    document_name=claim.source_document,
                    page_number=claim.page_number,
                    source_type=claim.source_type or "BIDDER_CLAIM",
                    quote=statement,
                    raw_value=claim.claimed_value,
                )
            ]

            # 1. Hidden Exception Check
            exc_match = HIDDEN_EXCEPTION_REGEX.search(statement)
            if exc_match:
                matched_phrase = exc_match.group(0)
                findings.append(
                    VerificationFinding(
                        verifier=self.verifier_id,
                        verification_layer=self.layer,
                        requirement_id=req_id,
                        bidder_id=bidder_id,
                        submission_id=submission_id,
                        status=ComplianceState.REVIEW,
                        severity=FindingSeverity.HIGH,
                        claim=claim.claimed_value,
                        observation=f"Hidden Exception Detected: '{matched_phrase}'",
                        reason=(
                            f"Adversarial Clause Flag: Bidder statement contains an exception clause "
                            f"('{matched_phrase}') in quote: \"{statement}\". Requires review for unauthorized deviation."
                        ),
                        evidence=prov,
                        confidence=0.92,
                        machine_readable_flags=["HIDDEN_EXCEPTION_DETECTED", "TECHNICAL_DEVIATION_RISK"],
                        metadata={"matched_phrase": matched_phrase, "statement": statement},
                    )
                )

            # 2. Conditional Compliance Language Check
            cond_match = CONDITIONAL_COMPLIANCE_REGEX.search(statement)
            if cond_match:
                matched_phrase = cond_match.group(0)
                findings.append(
                    VerificationFinding(
                        verifier=self.verifier_id,
                        verification_layer=self.layer,
                        requirement_id=req_id,
                        bidder_id=bidder_id,
                        submission_id=submission_id,
                        status=ComplianceState.REVIEW,
                        severity=FindingSeverity.HIGH,
                        claim=claim.claimed_value,
                        observation=f"Conditional Compliance: '{matched_phrase}'",
                        reason=(
                            f"Conditional Compliance Flag: Bidder asserts qualification conditioned on future event "
                            f"('{matched_phrase}'). Procurement terms require immediate affirmative proof at bid submission."
                        ),
                        evidence=prov,
                        confidence=0.90,
                        machine_readable_flags=["CONDITIONAL_COMPLIANCE_DETECTED", "DEFERRED_OBLIGATION_RISK"],
                        metadata={"matched_phrase": matched_phrase, "statement": statement},
                    )
                )

            # 3. Evasive Technical Statement Check
            evasive_match = EVASIVE_STATEMENT_REGEX.search(statement)
            if evasive_match:
                matched_phrase = evasive_match.group(0)
                findings.append(
                    VerificationFinding(
                        verifier=self.verifier_id,
                        verification_layer=self.layer,
                        requirement_id=req_id,
                        bidder_id=bidder_id,
                        submission_id=submission_id,
                        status=ComplianceState.REVIEW,
                        severity=FindingSeverity.MEDIUM,
                        claim=claim.claimed_value,
                        observation=f"Evasive Statement: '{matched_phrase}'",
                        reason=(
                            f"Evasive Specification Flag: Bidder provides vague generic reference ('{matched_phrase}') "
                            "instead of concrete verifiable technical parameters."
                        ),
                        evidence=prov,
                        confidence=0.85,
                        machine_readable_flags=["EVASIVE_TECHNICAL_STATEMENT", "VAGUE_SPECIFICATION_RISK"],
                        metadata={"matched_phrase": matched_phrase, "statement": statement},
                    )
                )

            # 4. "Will comply" promise without supporting evidence
            if WILL_COMPLY_PROMISE_REGEX.search(statement) and req_contract:
                # Check if requirement specifically requires test certificate or authoritative proof
                req_desc_upper = req_contract.description.upper()
                needs_proof = any(w in req_desc_upper for w in ("CERTIFICATE", "TEST REPORT", "NABL", "AUTHORIZATION", "ATTACH", "SUBMIT"))
                
                # Check if matching observation exists
                matching_obs = [o for o in observations if o.requirement_id == req_id and (not o.bidder_id or o.bidder_id == bidder_id)]
                if needs_proof and not matching_obs:
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            requirement_id=req_id,
                            bidder_id=bidder_id,
                            submission_id=submission_id,
                            status=ComplianceState.REVIEW,
                            severity=FindingSeverity.HIGH,
                            claim=claim.claimed_value,
                            observation="Self-declaration promise without mandatory proof document attached.",
                            reason=(
                                f"Unsupported Future Promise: Bidder self-declares compliance ('{statement}'), but mandatory "
                                "test report / proof certificate required by tender clause was not provided in supporting evidence."
                            ),
                            evidence=prov,
                            confidence=0.88,
                            machine_readable_flags=["UNSUPPORTED_PROMISE", "MANDATORY_PROOF_MISSING"],
                            metadata={"requirement_id": req_id, "statement": statement},
                        )
                    )

        # 5. Technical Parameter & Warranty Contradiction Check
        # Cross-examine claims vs observations for the same requirement
        for req_id, req in req_map.items():
            req_claims = [c for c in claims if c.requirement_id == req_id]
            req_obs = [o for o in observations if o.requirement_id == req_id]

            for c in req_claims:
                for o in req_obs:
                    if c.bidder_id and o.bidder_id and c.bidder_id != o.bidder_id:
                        continue
                    
                    # Numeric comparison (e.g. Local Content % or Warranty duration)
                    c_num, c_unit = parse_numeric_value(c.claimed_value)
                    o_num, o_unit = parse_numeric_value(o.observed_value)

                    if c_num is not None and o_num is not None:
                        # Check warranty contradiction
                        is_warranty = req.evaluation_field == CanonicalEvaluationField.WARRANTY_MONTHS or "WARRANTY" in req.description.upper()
                        if is_warranty:
                            if c_num > o_num:
                                findings.append(
                                    VerificationFinding(
                                        verifier=self.verifier_id,
                                        verification_layer=self.layer,
                                        requirement_id=req_id,
                                        bidder_id=c.bidder_id,
                                        submission_id=c.bid_submission_id,
                                        status=ComplianceState.REVIEW,
                                        severity=FindingSeverity.HIGH,
                                        claim={"warranty_claimed": c.claimed_value, "source": c.source_document},
                                        observation={"warranty_verified": o.observed_value, "source": o.source_document},
                                        reason=(
                                            f"Warranty Term Contradiction: Bidder declaration claims {c.claimed_value} warranty in '{c.source_document}', "
                                            f"but supporting manufacturer / OEM certificate in '{o.source_document}' only provides {o.observed_value} warranty."
                                        ),
                                        evidence=[
                                            ProvenanceRecord(document_name=c.source_document, page_number=c.page_number, quote=c.raw_statement, raw_value=c.claimed_value),
                                            ProvenanceRecord(document_name=o.source_document, page_number=o.page_number, quote=o.source_quote, raw_value=o.observed_value),
                                        ],
                                        confidence=0.95,
                                        machine_readable_flags=["WARRANTY_TERMS_CONTRADICTION", "EVIDENCE_CONTRADICTION_FLAG"],
                                        metadata={"claimed_val": c_num, "observed_val": o_num, "variance": c_num - o_num},
                                    )
                                )

                        # Check local content percentage contradiction
                        is_lc = req.evaluation_field == CanonicalEvaluationField.LOCAL_CONTENT_PERCENTAGE or "LOCAL CONTENT" in req.description.upper()
                        if is_lc:
                            if c_num != o_num:
                                findings.append(
                                    VerificationFinding(
                                        verifier=self.verifier_id,
                                        verification_layer=self.layer,
                                        requirement_id=req_id,
                                        bidder_id=c.bidder_id,
                                        submission_id=c.bid_submission_id,
                                        status=ComplianceState.REVIEW,
                                        severity=FindingSeverity.HIGH,
                                        claim={"local_content_declared": f"{c_num}%", "source": c.source_document},
                                        observation={"local_content_verified": f"{o_num}%", "source": o.source_document},
                                        reason=(
                                            f"Local Content Percentage Discrepancy: Bidder self-declaration asserts {c_num}% local content in '{c.source_document}', "
                                            f"while CA audit certificate in '{o.source_document}' calculates {o_num}%."
                                        ),
                                        evidence=[
                                            ProvenanceRecord(document_name=c.source_document, page_number=c.page_number, quote=c.raw_statement, raw_value=c.claimed_value),
                                            ProvenanceRecord(document_name=o.source_document, page_number=o.page_number, quote=o.source_quote, raw_value=o.observed_value),
                                        ],
                                        confidence=0.98,
                                        machine_readable_flags=["LOCAL_CONTENT_CONTRADICTION", "DISCREPANCY_FLAG"],
                                        metadata={"declared_pct": c_num, "verified_pct": o_num, "delta": c_num - o_num},
                                    )
                                )

        return findings
