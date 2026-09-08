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
    from app.rules.engine import parse_numeric_value, parse_date_value, is_unit_compatible
    from app.rules.layers.base import BaseVerifier
    from app.models.technical_matrix import TechnicalMatrix, TechnicalParameter
    from app.services.adversarial_prompt_service import adversarial_gemini_client
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
        from app.models.technical_matrix import TechnicalMatrix, TechnicalParameter
        from app.services.adversarial_prompt_service import adversarial_gemini_client
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
        from models.technical_matrix import TechnicalMatrix, TechnicalParameter
        from services.adversarial_prompt_service import adversarial_gemini_client

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
        
    @classmethod
    def _resolve_source_doc(
        cls,
        ref: str,
        claims: List[BidderClaim],
        observations: List[EvidenceObservation],
    ) -> Optional[str]:
        ref_lower = ref.lower().strip()
        for o in observations:
            if o.source_quote and ref_lower in o.source_quote.lower():
                return o.source_document
            if o.observed_value and ref_lower in str(o.observed_value).lower():
                return o.source_document
        for c in claims:
            if c.raw_statement and ref_lower in c.raw_statement.lower():
                return c.source_document
            if c.claimed_value and ref_lower in str(c.claimed_value).lower():
                return c.source_document
        for o in observations:
            if o.source_document:
                return o.source_document
        for c in claims:
            if c.source_document:
                return c.source_document
        return "SUBMISSION_DOCUMENT"

    @classmethod
    def _resolve_source_page(
        cls,
        ref: str,
        claims: List[BidderClaim],
        observations: List[EvidenceObservation],
    ) -> Optional[int]:
        ref_lower = ref.lower().strip()
        for o in observations:
            if o.source_quote and ref_lower in o.source_quote.lower():
                return o.page_number
            if o.observed_value and ref_lower in str(o.observed_value).lower():
                return o.page_number
        for c in claims:
            if c.raw_statement and ref_lower in c.raw_statement.lower():
                return c.page_number
            if c.claimed_value and ref_lower in str(c.claimed_value).lower():
                return c.page_number
        for o in observations:
            if o.page_number is not None:
                return o.page_number
        for c in claims:
            if c.page_number is not None:
                return c.page_number
        return None

    def _extract_technical_matrix(self, requirements: List[RequirementEvaluationContract], tender_id: str) -> TechnicalMatrix:
        """Dynamically extracts a technical matrix from canonical requirements deterministically."""
        parameters = []
        for req in requirements:
            # Check if this is a technical requirement, SLA or quantifiable parameter
            is_tech = (
                req.is_quantifiable
                or req.threshold_value is not None
                or req.category in [
                    "TECHNICAL_SPECIFICATION",
                    "DELIVERY_AND_SLA",
                    "WARRANTY",
                    "LOCAL_CONTENT_MII",
                    "FINANCIAL_TURNOVER",
                    "PAST_EXPERIENCE",
                ]
                or str(req.evaluation_field or "").lower() in [
                    "warranty_months",
                    "local_content_percentage",
                    "annual_turnover",
                    "average_annual_turnover",
                    "executed_contracts_count",
                    "oem_authorization",
                ]
            )
            if is_tech:
                param_name = (
                    req.evaluation_field.value if hasattr(req.evaluation_field, "value")
                    else str(req.evaluation_field) if req.evaluation_field
                    else req.category.value if hasattr(req.category, "value")
                    else str(req.category) if req.category
                    else "TECHNICAL_REQ"
                )
                source_doc = req.provenance.document_id if hasattr(req, "provenance") and req.provenance else None
                source_pg = req.provenance.page_number if hasattr(req, "provenance") and req.provenance else None
                is_ambig = req.ambiguity.is_ambiguous if hasattr(req, "ambiguity") and req.ambiguity else False

                param = TechnicalParameter(
                    requirement_id=req.requirement_id,
                    parameter=param_name,
                    requirement_text=req.description or req.title,
                    required_value=req.threshold_value,
                    operator=req.operator,
                    unit=req.threshold_unit,
                    mandatory=req.mandatory,
                    evidence_expected=[e.document_description for e in req.evidence_contracts] if req.evidence_contracts else [],
                    source_document=source_doc,
                    source_page=source_pg,
                    ambiguity_flag=is_ambig,
                )
                parameters.append(param)
        return TechnicalMatrix(tender_id=tender_id, parameters=parameters)

    async def verify(self, context: VerificationContext) -> List[VerificationFinding]:
        findings: List[VerificationFinding] = []
        requirements = context.requirements or []
        claims = context.claims or []
        observations = context.observations or []

        # Reset LLM call budget for this verification pass
        adversarial_gemini_client.reset_call_count()

        # Generate technical matrix dynamically based on deterministic logic
        tender_id = context.tender_id or context.procurement_id or "UNKNOWN_TENDER"
        tech_matrix = self._extract_technical_matrix(requirements, tender_id)

        # Map requirements by ID
        req_map: Dict[str, RequirementEvaluationContract] = {r.requirement_id: r for r in requirements}

        # Collect all active bidder IDs
        bidder_ids = set()
        if context.bidders:
            for b in context.bidders:
                bid_id = b.get("id") if isinstance(b, dict) else getattr(b, "id", None)
                if not bid_id and isinstance(b, dict):
                    bid_id = b.get("bidder_id")
                if bid_id:
                    bidder_ids.add(str(bid_id))
        if context.submissions:
            for s in context.submissions:
                bid_id = s.get("bidder_id") if isinstance(s, dict) else getattr(s, "bidder_id", None)
                if bid_id:
                    bidder_ids.add(str(bid_id))
        for c in claims:
            if c.bidder_id:
                bidder_ids.add(str(c.bidder_id))
        for o in observations:
            if o.bidder_id:
                bidder_ids.add(str(o.bidder_id))
        if not bidder_ids:
            bidder_ids = {None}

        # 1-4. Check claims for adversarial wording patterns (Deterministic)
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
                        metadata={"matched_phrase": matched_phrase, "statement": statement, "decision_authority": "HUMAN_PROCUREMENT_OFFICER"},
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
                        metadata={"matched_phrase": matched_phrase, "statement": statement, "decision_authority": "HUMAN_PROCUREMENT_OFFICER"},
                    )
                )

            # 3. Evasive Technical Statement Check (Deterministic fallback before LLM)
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
                        metadata={"matched_phrase": matched_phrase, "statement": statement, "decision_authority": "HUMAN_PROCUREMENT_OFFICER"},
                    )
                )

            # 4. "Will comply" promise without supporting evidence (Requirement-aware)
            if WILL_COMPLY_PROMISE_REGEX.search(statement) and req_contract:
                req_desc_upper = (req_contract.description or "").upper()
                needs_proof = bool(req_contract.evidence_contracts) or any(
                    w in req_desc_upper for w in ("CERTIFICATE", "TEST REPORT", "NABL", "AUTHORIZATION", "ATTACH", "SUBMIT", "PROOF")
                )
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
                            metadata={"requirement_id": req_id, "statement": statement, "decision_authority": "HUMAN_PROCUREMENT_OFFICER"},
                        )
                    )

        # 5. Deterministic Contradiction & Compliance Analysis (Per Bidder, Per Requirement)
        for req_id, req in req_map.items():
            for b_id in bidder_ids:
                b_claims = [c for c in claims if c.requirement_id == req_id and c.bidder_id == b_id]
                b_obs = [o for o in observations if o.requirement_id == req_id and o.bidder_id == b_id]

                # Pairwise comparison across (claims vs obs), (obs vs obs), and (claims vs claims)
                fact_pairs = []
                # Claims vs Observations
                for c in b_claims:
                    for o in b_obs:
                        fact_pairs.append((c.claimed_value, o.observed_value, c.source_document, o.source_document, c.page_number, o.page_number, c.raw_statement, o.source_quote, "CLAIM_VS_OBSERVATION"))
                # Observation vs Observation (e.g. self-declaration vs CA auditor certificate)
                for i in range(len(b_obs)):
                    for j in range(i + 1, len(b_obs)):
                        o1 = b_obs[i]
                        o2 = b_obs[j]
                        fact_pairs.append((o1.observed_value, o2.observed_value, o1.source_document, o2.source_document, o1.page_number, o2.page_number, o1.source_quote, o2.source_quote, "OBSERVATION_VS_OBSERVATION"))
                # Claim vs Claim
                for i in range(len(b_claims)):
                    for j in range(i + 1, len(b_claims)):
                        c1 = b_claims[i]
                        c2 = b_claims[j]
                        fact_pairs.append((c1.claimed_value, c2.claimed_value, c1.source_document, c2.source_document, c1.page_number, c2.page_number, c1.raw_statement, c2.raw_statement, "CLAIM_VS_CLAIM"))

                for val1, val2, doc1, doc2, pg1, pg2, quote1, quote2, pair_type in fact_pairs:
                    # A. Numeric Contradiction Check
                    n1, u1 = parse_numeric_value(val1)
                    n2, u2 = parse_numeric_value(val2)

                    if n1 is not None and n2 is not None:
                        # Consistent evidence if values match
                        if n1 == n2:
                            continue

                        # Check unit compatibility if both units present
                        if u1 and u2 and not is_unit_compatible(u1, u2):
                            continue

                        # Warranty contradiction
                        is_warranty = (
                            req.evaluation_field == CanonicalEvaluationField.WARRANTY_MONTHS
                            or "WARRANTY" in (req.description or "").upper()
                        )
                        if is_warranty:
                            findings.append(
                                VerificationFinding(
                                    verifier=self.verifier_id,
                                    verification_layer=self.layer,
                                    requirement_id=req_id,
                                    bidder_id=b_id,
                                    status=ComplianceState.REVIEW,
                                    severity=FindingSeverity.HIGH,
                                    claim={"warranty_declared": val1, "source": doc1},
                                    observation={"warranty_verified": val2, "source": doc2},
                                    reason=(
                                        f"Warranty Term Contradiction: Bidder documentation asserts {val1} warranty in '{doc1}', "
                                        f"but conflicting evidence in '{doc2}' specifies {val2} warranty."
                                    ),
                                    evidence=[
                                        ProvenanceRecord(document_name=doc1, page_number=pg1, quote=quote1 or str(val1), raw_value=val1),
                                        ProvenanceRecord(document_name=doc2, page_number=pg2, quote=quote2 or str(val2), raw_value=val2),
                                    ],
                                    confidence=0.95,
                                    machine_readable_flags=["WARRANTY_TERMS_CONTRADICTION", "EVIDENCE_CONTRADICTION_FLAG"],
                                    metadata={
                                        "declared_val": n1,
                                        "observed_val": n2,
                                        "variance": abs(n1 - n2),
                                        "decision_authority": "HUMAN_PROCUREMENT_OFFICER",
                                    },
                                )
                            )
                            continue

                        # Local Content discrepancy
                        is_lc = (
                            req.evaluation_field == CanonicalEvaluationField.LOCAL_CONTENT_PERCENTAGE
                            or "LOCAL CONTENT" in (req.description or "").upper()
                        )
                        if is_lc:
                            findings.append(
                                VerificationFinding(
                                    verifier=self.verifier_id,
                                    verification_layer=self.layer,
                                    requirement_id=req_id,
                                    bidder_id=b_id,
                                    status=ComplianceState.REVIEW,
                                    severity=FindingSeverity.HIGH,
                                    claim={"local_content_declared": f"{n1}%", "source": doc1},
                                    observation={"local_content_verified": f"{n2}%", "source": doc2},
                                    reason=(
                                        f"Local Content Percentage Discrepancy: Bidder self-declaration asserts {n1}% local content in '{doc1}', "
                                        f"while audit / verified documentation in '{doc2}' establishes {n2}%."
                                    ),
                                    evidence=[
                                        ProvenanceRecord(document_name=doc1, page_number=pg1, quote=quote1 or str(val1), raw_value=val1),
                                        ProvenanceRecord(document_name=doc2, page_number=pg2, quote=quote2 or str(val2), raw_value=val2),
                                    ],
                                    confidence=0.98,
                                    machine_readable_flags=["LOCAL_CONTENT_CONTRADICTION", "DISCREPANCY_FLAG"],
                                    metadata={
                                        "declared_pct": n1,
                                        "verified_pct": n2,
                                        "delta": abs(n1 - n2),
                                        "decision_authority": "HUMAN_PROCUREMENT_OFFICER",
                                    },
                                )
                            )
                            continue

                        # General Numeric Discrepancy
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                requirement_id=req_id,
                                bidder_id=b_id,
                                status=ComplianceState.REVIEW,
                                severity=FindingSeverity.HIGH,
                                claim={"value_1": val1, "source": doc1},
                                observation={"value_2": val2, "source": doc2},
                                reason=(
                                    f"Numeric Specification Discrepancy: Document '{doc1}' declares {val1}, "
                                    f"which conflicts with {val2} in '{doc2}'."
                                ),
                                evidence=[
                                    ProvenanceRecord(document_name=doc1, page_number=pg1, quote=quote1 or str(val1), raw_value=val1),
                                    ProvenanceRecord(document_name=doc2, page_number=pg2, quote=quote2 or str(val2), raw_value=val2),
                                ],
                                confidence=0.92,
                                machine_readable_flags=["NUMERIC_VALUE_CONTRADICTION", "DISCREPANCY_FLAG"],
                                metadata={
                                    "val1": n1,
                                    "val2": n2,
                                    "difference": abs(n1 - n2),
                                    "decision_authority": "HUMAN_PROCUREMENT_OFFICER",
                                },
                            )
                        )
                        continue

                    # B. Date Contradiction Check
                    d1 = parse_date_value(val1)
                    d2 = parse_date_value(val2)
                    if d1 and d2 and d1 != d2:
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                requirement_id=req_id,
                                bidder_id=b_id,
                                status=ComplianceState.REVIEW,
                                severity=FindingSeverity.HIGH,
                                claim={"date_1": str(d1), "source": doc1},
                                observation={"date_2": str(d2), "source": doc2},
                                reason=(
                                    f"Date Validity Contradiction: Document '{doc1}' specifies validity date {d1}, "
                                    f"contradicting date {d2} specified in '{doc2}'."
                                ),
                                evidence=[
                                    ProvenanceRecord(document_name=doc1, page_number=pg1, quote=quote1 or str(val1), raw_value=val1),
                                    ProvenanceRecord(document_name=doc2, page_number=pg2, quote=quote2 or str(val2), raw_value=val2),
                                ],
                                confidence=0.94,
                                machine_readable_flags=["DATE_VALIDITY_CONTRADICTION", "EVIDENCE_CONTRADICTION_FLAG"],
                                metadata={
                                    "date_1": str(d1),
                                    "date_2": str(d2),
                                    "decision_authority": "HUMAN_PROCUREMENT_OFFICER",
                                },
                            )
                        )
                        continue

                    # C. Qualitative / Spec Conflict
                    s1 = str(val1).strip().lower()
                    s2 = str(val2).strip().lower()
                    if s1 and s2 and s1 != s2 and len(s1) > 4 and len(s2) > 4:
                        mutually_exclusive_terms = [
                            ("titanium", "pvc"),
                            ("titanium", "plastic"),
                            ("submersible", "surface"),
                            ("ss316", "cast iron"),
                            ("online", "offline"),
                            ("optical", "galvanic"),
                        ]
                        has_spec_conflict = any(
                            (t1 in s1 and t2 in s2) or (t2 in s1 and t1 in s2)
                            for t1, t2 in mutually_exclusive_terms
                        )
                        if has_spec_conflict:
                            findings.append(
                                VerificationFinding(
                                    verifier=self.verifier_id,
                                    verification_layer=self.layer,
                                    requirement_id=req_id,
                                    bidder_id=b_id,
                                    status=ComplianceState.REVIEW,
                                    severity=FindingSeverity.HIGH,
                                    claim={"specification_declared": val1, "source": doc1},
                                    observation={"specification_observed": val2, "source": doc2},
                                    reason=(
                                        f"Technical Specification Contradiction: Specification '{val1}' in '{doc1}' "
                                        f"is mutually incompatible with '{val2}' in '{doc2}'."
                                    ),
                                    evidence=[
                                        ProvenanceRecord(document_name=doc1, page_number=pg1, quote=quote1 or str(val1), raw_value=val1),
                                        ProvenanceRecord(document_name=doc2, page_number=pg2, quote=quote2 or str(val2), raw_value=val2),
                                    ],
                                    confidence=0.90,
                                    machine_readable_flags=["TECHNICAL_SPECIFICATION_CONTRADICTION", "DISCREPANCY_FLAG"],
                                    metadata={"decision_authority": "HUMAN_PROCUREMENT_OFFICER"},
                                )
                            )

                # D. Deterministic Mandatory Failure Check (Independently Established)
                if req.mandatory and req.threshold_value is not None and b_obs:
                    req_thresh, _ = parse_numeric_value(req.threshold_value)
                    if req_thresh is not None:
                        for o in b_obs:
                            o_val, _ = parse_numeric_value(o.observed_value)
                            if o_val is not None:
                                op = req.operator or ">="
                                failed = False
                                if op in (">=", "=>") and o_val < req_thresh:
                                    failed = True
                                elif op in ("<=", "=<") and o_val > req_thresh:
                                    failed = True
                                elif op in ("==", "=") and o_val != req_thresh:
                                    failed = True

                                if failed:
                                    findings.append(
                                        VerificationFinding(
                                            verifier=self.verifier_id,
                                            verification_layer=self.layer,
                                            requirement_id=req_id,
                                            bidder_id=b_id,
                                            status=ComplianceState.FAIL,
                                            severity=FindingSeverity.CRITICAL,
                                            claim={"required_threshold": f"{op} {req_thresh}", "requirement": req.title},
                                            observation={"verified_value": o_val, "source": o.source_document},
                                            reason=(
                                                f"Mandatory Threshold Not Met: Verified value of {o_val} in '{o.source_document}' "
                                                f"fails to meet mandatory tender threshold of {op} {req_thresh} for '{req.title}'."
                                            ),
                                            evidence=[
                                                ProvenanceRecord(
                                                    document_name=o.source_document,
                                                    page_number=o.page_number,
                                                    quote=o.source_quote or str(o.observed_value),
                                                    raw_value=o.observed_value,
                                                )
                                            ],
                                            confidence=1.0,
                                            machine_readable_flags=["MANDATORY_THRESHOLD_NOT_MET", "DETERMINISTIC_MANDATORY_FAILURE"],
                                            metadata={
                                                "threshold": req_thresh,
                                                "verified_value": o_val,
                                                "operator": op,
                                                "decision_authority": "HUMAN_PROCUREMENT_OFFICER",
                                            },
                                        )
                                    )

                # E. Insufficient / Missing Evidence Check
                if req.mandatory and not b_obs:
                    if b_claims or (context.submissions and any(s.get("bidder_id") == b_id for s in context.submissions)):
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                requirement_id=req_id,
                                bidder_id=b_id,
                                status=ComplianceState.UNVERIFIED,
                                severity=FindingSeverity.MEDIUM,
                                claim={"requirement": req.title},
                                observation="No supporting evidence observation submitted.",
                                reason=(
                                    f"Missing Mandatory Evidence: Bidder submitted no documentary evidence observations for "
                                    f"mandatory requirement '{req.title}' (ID: {req_id})."
                                ),
                                evidence=[],
                                confidence=0.90,
                                machine_readable_flags=["INSUFFICIENT_EVIDENCE", "MANDATORY_PROOF_MISSING"],
                                metadata={
                                    "requirement_id": req_id,
                                    "decision_authority": "HUMAN_PROCUREMENT_OFFICER",
                                },
                            )
                        )

        # 6. LLM-Based Semantic Contradiction / Evasive Language Detection
        # Only run for remaining semantic/unresolved claims where deterministic logic has not already flagged the issue
        for req_id, req in req_map.items():
            for b_id in bidder_ids:
                # Skip if already flagged for this requirement and bidder
                if any(f.requirement_id == req_id and f.bidder_id == b_id for f in findings):
                    continue

                req_claims = [c for c in claims if c.requirement_id == req_id and c.bidder_id == b_id]
                req_obs = [o for o in observations if o.requirement_id == req_id and o.bidder_id == b_id]
                if not req_claims and not req_obs:
                    continue

                sub_id = req_claims[0].bid_submission_id if req_claims else (req_obs[0].bid_submission_id if req_obs else None)

                c_texts = [str(c.raw_statement or c.claimed_value) for c in req_claims]
                o_texts = [str(o.source_quote or o.observed_value) for o in req_obs]

                llm_result = adversarial_gemini_client.analyze_contradiction(
                    requirement_text=req.description or req.title,
                    bidder_claims=c_texts,
                    evidence_quotes=o_texts,
                    requirement_id=req_id,
                )

                if llm_result:
                    if llm_result.status == "CONTRADICTION":
                        for detail in llm_result.details:
                            findings.append(
                                VerificationFinding(
                                    verifier=self.verifier_id,
                                    verification_layer=self.layer,
                                    requirement_id=req_id,
                                    bidder_id=b_id,
                                    submission_id=sub_id,
                                    status=ComplianceState.REVIEW,
                                    severity=FindingSeverity.HIGH,
                                    claim=detail.statement,
                                    observation="LLM Identified Contradiction/Evasion",
                                    reason=detail.reason,
                                    evidence=[
                                        ProvenanceRecord(
                                            document_name=self._resolve_source_doc(ref, req_claims, req_obs),
                                            page_number=self._resolve_source_page(ref, req_claims, req_obs),
                                            source_type="ADVERSARIAL_SEMANTIC",
                                            quote=ref,
                                        ) for ref in detail.evidence_refs
                                    ],
                                    confidence=0.85,
                                    machine_readable_flags=[f"LLM_SEMANTIC_{llm_result.type or 'CONTRADICTION'}"],
                                    metadata={
                                        "llm_type": llm_result.type,
                                        "statement": detail.statement,
                                        "decision_authority": "HUMAN_PROCUREMENT_OFFICER",
                                    },
                                )
                            )
                    elif llm_result.status == "INSUFFICIENT_EVIDENCE":
                        if req.mandatory:
                            findings.append(
                                VerificationFinding(
                                    verifier=self.verifier_id,
                                    verification_layer=self.layer,
                                    requirement_id=req_id,
                                    bidder_id=b_id,
                                    submission_id=sub_id,
                                    status=ComplianceState.UNVERIFIED,
                                    severity=FindingSeverity.MEDIUM,
                                    claim="Various claims submitted",
                                    observation="Evidence insufficient",
                                    reason="Supplied evidence cannot establish the relationship to the claim.",
                                    evidence=[],
                                    confidence=0.80,
                                    machine_readable_flags=["LLM_INSUFFICIENT_EVIDENCE"],
                                    metadata={"decision_authority": "HUMAN_PROCUREMENT_OFFICER"},
                                )
                            )

        return findings
