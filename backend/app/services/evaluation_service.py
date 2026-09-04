"""OPAL Tiered Requirement Evaluator Service (SIH26100).

Provides a safe, multi-tier requirement evaluation orchestrator that evaluates
tender requirements against bidder claims, extracted evidence observations,
and authoritative verifications without overclaiming certainty.

Tiered Precedence:
1. APPLICABILITY / EXEMPTION: Verified exemptions yield NOT_APPLICABLE; unverified yield REVIEW.
2. CONTRADICTION / RECONCILIATION: Conflicting claims/evidence yield REVIEW with side-by-side audit.
3. EXTERNAL VERIFICATION: Registry verifications (VERIFIED/FAILED/UNAVAILABLE/PENDING).
4. DOCUMENT / EVIDENCE PRESENCE: Missing mandatory evidence yields UNVERIFIED.
5. AMBIGUITY RADAR: Vague or underspecified criteria yield REVIEW.
6. DETERMINISTIC RULE ENGINE: Exact arithmetic/date rules yield PASS or FAIL.
7. SEMANTIC / LLM INTERPRETATION: Subjective clauses yield structured evaluation or REVIEW.
8. HUMAN REVIEW: Final safe fallback.

Principles:
- Never converts missing evidence -> PASS
- Never converts unavailable verification -> PASS
- Never converts contradiction -> automatic FAIL (preserves facts as REVIEW for officer audit)
- Never converts unresolved ambiguity -> automatic PASS
- Evaluates requirement-level states only; does NOT make autonomous bidder qualification decisions.
"""

from datetime import date, datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Protocol, Tuple, Union
import uuid

try:
    from backend.app.models.evaluation import (
        ComplianceFinding,
        ComplianceState,
        EvaluationMethod,
        ExternalVerificationStatus,
        RequirementEvaluationResult,
    )
    from backend.app.models.evidence import (
        BidderClaim,
        ContradictionFinding,
        ContradictionType,
        EvidenceObservation,
        ExtractedEvidence,
        ProvenanceRecord,
        RelationshipClassification,
        SideBySideComparison,
    )
    from backend.app.models.tender import AmbiguityType, TenderRequirement
    from backend.app.rules.engine import (
        evaluate_date_validity,
        evaluate_experience_window,
        evaluate_mandatory_evidence,
        evaluate_numeric_threshold,
        evaluate_requirement as evaluate_deterministic_requirement,
        is_unit_compatible,
        parse_date_value,
        parse_numeric_value,
    )
    from backend.app.services.contradiction_service import (
        build_provenance_from_claim,
        build_provenance_from_evidence,
        compare_two_facts,
        detect_contradictions,
        reconcile_requirement,
    )
except ImportError:
    try:
        from app.models.evaluation import (
            ComplianceFinding,
            ComplianceState,
            EvaluationMethod,
            ExternalVerificationStatus,
            RequirementEvaluationResult,
        )
        from app.models.evidence import (
            BidderClaim,
            ContradictionFinding,
            ContradictionType,
            EvidenceObservation,
            ExtractedEvidence,
            ProvenanceRecord,
            RelationshipClassification,
            SideBySideComparison,
        )
        from app.models.tender import AmbiguityType, TenderRequirement
        from app.rules.engine import (
            evaluate_date_validity,
            evaluate_experience_window,
            evaluate_mandatory_evidence,
            evaluate_numeric_threshold,
            evaluate_requirement as evaluate_deterministic_requirement,
            is_unit_compatible,
            parse_date_value,
            parse_numeric_value,
        )
        from app.services.contradiction_service import (
            build_provenance_from_claim,
            build_provenance_from_evidence,
            compare_two_facts,
            detect_contradictions,
            reconcile_requirement,
        )
    except ImportError:
        from models.evaluation import (
            ComplianceFinding,
            ComplianceState,
            EvaluationMethod,
            ExternalVerificationStatus,
            RequirementEvaluationResult,
        )
        from models.evidence import (
            BidderClaim,
            ContradictionFinding,
            ContradictionType,
            EvidenceObservation,
            ExtractedEvidence,
            ProvenanceRecord,
            RelationshipClassification,
            SideBySideComparison,
        )
        from models.tender import AmbiguityType, TenderRequirement
        from rules.engine import (
            evaluate_date_validity,
            evaluate_experience_window,
            evaluate_mandatory_evidence,
            evaluate_numeric_threshold,
            evaluate_requirement as evaluate_deterministic_requirement,
            is_unit_compatible,
            parse_date_value,
            parse_numeric_value,
        )
        from services.contradiction_service import (
            build_provenance_from_claim,
            build_provenance_from_evidence,
            compare_two_facts,
            detect_contradictions,
            reconcile_requirement,
        )

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Semantic Evaluator Protocol and Adapter
# ---------------------------------------------------------------------------

class SemanticEvaluatorProtocol(Protocol):
    """Protocol defining the interface for semantic/LLM requirement evaluators."""

    def evaluate_semantic(
        self,
        requirement_dict: Dict[str, Any],
        claims: List[ProvenanceRecord],
        evidence: List[ProvenanceRecord],
        context: Dict[str, Any],
    ) -> Optional[RequirementEvaluationResult]:
        """Evaluates a semantic requirement. Returns None if LLM is unavailable."""
        ...


class DefaultSemanticEvaluator:
    """Default adapter for semantic requirement interpretation."""

    def __init__(self, ai_router_instance: Any = None):
        self._router = ai_router_instance

    def is_available(self) -> bool:
        """Checks if live LLM router is configured and available."""
        if self._router is None:
            try:
                from backend.app.services.ai_router import ai_router
                self._router = ai_router
            except Exception:
                return False
        
        if self._router is not None:
            keys = getattr(self._router, "get_api_keys", lambda: [])()
            return len(keys) > 0
        return False

    def evaluate_semantic(
        self,
        requirement_dict: Dict[str, Any],
        claims: List[ProvenanceRecord],
        evidence: List[ProvenanceRecord],
        context: Dict[str, Any],
    ) -> Optional[RequirementEvaluationResult]:
        """Evaluates a semantic/subjective requirement."""
        req_id = requirement_dict.get("requirement_id", "REQ-UNKNOWN")
        desc = requirement_dict.get("description", "")
        
        # If router is unavailable, return None so orchestrator falls back to safe HUMAN_REVIEW
        if not self.is_available():
            return None

        # Check for vague/subjective clauses without objective thresholds
        # In OPAL, subjective clauses without objective criteria must produce REVIEW
        is_subjective = (
            "adequate" in desc.lower() or
            "satisfactory" in desc.lower() or
            "reputation" in desc.lower() or
            "good standing" in desc.lower() or
            "competence" in desc.lower()
        )

        all_provenance = claims + evidence
        observed_vals = [p.normalized_value or p.raw_value for p in all_provenance if p.raw_value]

        if is_subjective:
            return RequirementEvaluationResult(
                requirement_id=req_id,
                state=ComplianceState.REVIEW,
                risk_level="MEDIUM",
                evaluation_method=EvaluationMethod.SEMANTIC_LLM,
                reason=(
                    f"Clause '{desc}' relies on subjective or qualitative criteria "
                    "without defining an objective threshold. Manual procurement officer discretion required."
                ),
                expected_condition={"description": desc, "type": "SUBJECTIVE_CRITERIA"},
                observed_values=observed_vals,
                supporting_evidence=evidence,
                conflicting_evidence=[],
                review_required=True,
                provenance=all_provenance,
                contradiction_findings=[],
                evaluator_metadata={"evaluator": "DefaultSemanticEvaluator", "tier": "SEMANTIC_LLM"},
                confidence=0.85,
            )

        # Non-subjective semantic text evaluation
        return RequirementEvaluationResult(
            requirement_id=req_id,
            state=ComplianceState.REVIEW,
            risk_level="LOW" if observed_vals else "MEDIUM",
            evaluation_method=EvaluationMethod.SEMANTIC_LLM,
            reason=f"Semantic analysis of submitted documentation for '{desc}'.",
            expected_condition={"description": desc},
            observed_values=observed_vals,
            supporting_evidence=evidence,
            conflicting_evidence=[],
            review_required=True,
            provenance=all_provenance,
            contradiction_findings=[],
            evaluator_metadata={"evaluator": "DefaultSemanticEvaluator", "tier": "SEMANTIC_LLM"},
            confidence=0.80,
        )


# Global default semantic evaluator instance
_semantic_evaluator: Optional[SemanticEvaluatorProtocol] = DefaultSemanticEvaluator()


def set_semantic_evaluator(evaluator: Optional[SemanticEvaluatorProtocol]) -> None:
    """Sets or overrides the semantic evaluator instance (useful for unit tests / dependency injection)."""
    global _semantic_evaluator
    _semantic_evaluator = evaluator


def get_semantic_evaluator() -> Optional[SemanticEvaluatorProtocol]:
    """Gets current semantic evaluator instance."""
    return _semantic_evaluator


# ---------------------------------------------------------------------------
# Individual Tier Check Functions
# ---------------------------------------------------------------------------

def check_applicability_exemption(
    requirement_dict: Dict[str, Any],
    context: Dict[str, Any],
    provenance_items: List[ProvenanceRecord],
) -> Optional[RequirementEvaluationResult]:
    """Tier 1: Evaluates statutory applicability and exemptions (e.g. MSE / Startup waivers)."""
    req_id = requirement_dict.get("requirement_id", "REQ-UNKNOWN")
    category = str(requirement_dict.get("category", "")).upper()
    description = requirement_dict.get("description", "")
    
    # Check applicability from structured requirement
    applicability = requirement_dict.get("applicability") or {}
    if hasattr(applicability, "model_dump"):
        applicability = applicability.model_dump()

    msme_exempt_allowed = bool(
        applicability.get("msme_exemption_applicable") or applicability.get("msme_exemption")
    )
    startup_exempt_allowed = bool(
        applicability.get("startup_exemption_applicable") or applicability.get("startup_exemption")
    )

    # Check context exemptions profile (from bidder profile or evaluation context)
    exemptions = context.get("exemptions") or {}
    bidder_is_mse = context.get("is_mse") if context.get("is_mse") is not None else (context.get("is_msme") if context.get("is_msme") is not None else (exemptions.get("is_mse") if exemptions.get("is_mse") is not None else exemptions.get("is_msme")))
    bidder_is_startup = context.get("is_startup") if context.get("is_startup") is not None else exemptions.get("is_startup")

    # Explicit direct exemption in context
    direct_exemption = exemptions.get(req_id) or exemptions.get(category) or exemptions.get("MSE") or exemptions.get("STARTUP")

    if direct_exemption is not None:
        if isinstance(direct_exemption, dict):
            is_exempt = direct_exemption.get("is_exempt")
            ex_type = direct_exemption.get("type") or direct_exemption.get("exemption_type") or "Statutory Exemption"
            ex_reason = direct_exemption.get("reason")
        else:
            is_exempt = bool(direct_exemption)
            ex_type = "Statutory Exemption"
            ex_reason = None

        if is_exempt is True:
            reason = ex_reason or f"Requirement marked not applicable because a verified {ex_type} applies."
            return RequirementEvaluationResult(
                requirement_id=req_id,
                state=ComplianceState.NOT_APPLICABLE,
                risk_level="NONE",
                evaluation_method=EvaluationMethod.APPLICABILITY_EXEMPTION,
                reason=reason,
                expected_condition={"exemption_type": ex_type},
                observed_values=["EXEMPT"],
                supporting_evidence=provenance_items,
                conflicting_evidence=[],
                review_required=False,
                provenance=provenance_items,
                contradiction_findings=[],
                evaluator_metadata={"tier": "APPLICABILITY_EXEMPTION", "exemption_type": ex_type},
                confidence=1.0,
            )
        elif is_exempt is None:
            # Claimed but unverified exemption
            return RequirementEvaluationResult(
                requirement_id=req_id,
                state=ComplianceState.REVIEW,
                risk_level="MEDIUM",
                evaluation_method=EvaluationMethod.APPLICABILITY_EXEMPTION,
                reason=(
                    f"Bidder claimed or may qualify for '{ex_type}' exemption, but supporting "
                    "statutory registration (e.g. Udyam / DPIIT certificate) is unverified. Manual review required."
                ),
                expected_condition={"exemption_type": ex_type},
                observed_values=["UNVERIFIED_EXEMPTION"],
                supporting_evidence=[],
                conflicting_evidence=[],
                review_required=True,
                provenance=provenance_items,
                contradiction_findings=[],
                evaluator_metadata={"tier": "APPLICABILITY_EXEMPTION", "exemption_type": ex_type},
                confidence=0.90,
            )

    # Check statutory MSE / Startup exemption allowed on turnover or experience
    if (category in ("FINANCIAL_TURNOVER", "EXPERIENCE", "PAST_EXPERIENCE") or "TURNOVER" in description.upper() or "EXPERIENCE" in description.upper()):
        if msme_exempt_allowed and bidder_is_mse is True:
            return RequirementEvaluationResult(
                requirement_id=req_id,
                state=ComplianceState.NOT_APPLICABLE,
                risk_level="NONE",
                evaluation_method=EvaluationMethod.APPLICABILITY_EXEMPTION,
                reason="Turnover requirement marked not applicable because a verified MSE exemption applies.",
                expected_condition={"exemption_type": "MSE_EXEMPTION"},
                observed_values=["MSE_EXEMPT"],
                supporting_evidence=provenance_items,
                conflicting_evidence=[],
                review_required=False,
                provenance=provenance_items,
                contradiction_findings=[],
                evaluator_metadata={"tier": "APPLICABILITY_EXEMPTION", "exemption_type": "MSE"},
                confidence=1.0,
            )
        elif msme_exempt_allowed and bidder_is_mse is None and ("mse" in str(context).lower() or "msme" in str(context).lower()):
            return RequirementEvaluationResult(
                requirement_id=req_id,
                state=ComplianceState.REVIEW,
                risk_level="MEDIUM",
                evaluation_method=EvaluationMethod.APPLICABILITY_EXEMPTION,
                reason="Bidder claimed MSE exemption, but supporting Udyam registration is unverified. Manual review required.",
                expected_condition={"exemption_type": "MSE_EXEMPTION"},
                observed_values=["UNVERIFIED_MSE_CLAIM"],
                supporting_evidence=[],
                conflicting_evidence=[],
                review_required=True,
                provenance=provenance_items,
                contradiction_findings=[],
                evaluator_metadata={"tier": "APPLICABILITY_EXEMPTION", "exemption_type": "MSE"},
                confidence=0.90,
            )

    return None


def check_contradictions_and_reconcile(
    requirement_dict: Dict[str, Any],
    claim_records: List[ProvenanceRecord],
    evidence_records: List[ProvenanceRecord],
    context: Dict[str, Any],
    raw_claims: Optional[Any] = None,
    raw_evidence: Optional[Any] = None,
) -> Optional[RequirementEvaluationResult]:
    """Tier 2: Evaluates cross-document contradictions across claims and evidence observations."""
    req_id = requirement_dict.get("requirement_id", "REQ-UNKNOWN")
    
    # Run contradiction detection
    findings = detect_contradictions(
        claims=raw_claims if raw_claims is not None else claim_records,
        evidence=raw_evidence if raw_evidence is not None else evidence_records,
        requirement_id=req_id,
        bidder_info=context,
    )

    # Filter for real contradictions (exclude CLAIM_UNSUPPORTED which is handled in missing evidence tier)
    factual_contradictions = [f for f in findings if f.contradiction_type != ContradictionType.CLAIM_UNSUPPORTED]

    if factual_contradictions:
        # Contradiction detected -> MUST return REVIEW with HIGH risk and preserved side-by-side evidence
        primary_finding = factual_contradictions[0]
        side_by_side = primary_finding.side_by_side
        
        # Build explanation
        if side_by_side and side_by_side.left and side_by_side.right:
            left_val = side_by_side.left.raw_value
            right_val = side_by_side.right.raw_value
            reason = (
                f"Bidder declaration states {left_val}, while supporting certificate states {right_val}. "
                "The evidence conflicts and requires officer review."
            )
        else:
            reason = primary_finding.explanation

        all_provenance = claim_records + evidence_records
        conflicting = []
        for f in factual_contradictions:
            conflicting.extend(f.provenance_items)

        return RequirementEvaluationResult(
            requirement_id=req_id,
            state=ComplianceState.REVIEW,
            risk_level=primary_finding.severity or "HIGH",
            evaluation_method=EvaluationMethod.CONTRADICTION_RECONCILIATION,
            reason=reason,
            expected_condition=requirement_dict.get("structured_condition") or {"description": requirement_dict.get("description")},
            observed_values=[p.raw_value for p in all_provenance],
            supporting_evidence=[],
            conflicting_evidence=conflicting or all_provenance,
            review_required=True,
            provenance=all_provenance,
            contradiction_findings=factual_contradictions,
            evaluator_metadata={
                "tier": "CONTRADICTION_RECONCILIATION",
                "contradiction_count": len(factual_contradictions),
                "primary_type": primary_finding.contradiction_type.value if hasattr(primary_finding.contradiction_type, "value") else str(primary_finding.contradiction_type),
            },
            confidence=1.0,
        )

    return None


def check_external_verification(
    requirement_dict: Dict[str, Any],
    external_verification: Optional[Union[Dict[str, Any], Any]],
    context: Dict[str, Any],
    provenance_items: List[ProvenanceRecord],
) -> Optional[RequirementEvaluationResult]:
    """Tier 3: Evaluates authoritative external government registry verifications (e.g. GSTN, PAN, MCA)."""
    if not external_verification:
        return None

    req_id = requirement_dict.get("requirement_id", "REQ-UNKNOWN")

    # Extract status
    if isinstance(external_verification, dict):
        status_val = external_verification.get("status") or external_verification.get("verification_status")
        source = external_verification.get("registry") or external_verification.get("source") or "Government Registry"
        details = external_verification.get("details") or external_verification.get("data") or {}
    else:
        status_val = getattr(external_verification, "status", None)
        source = getattr(external_verification, "source", "Government Registry")
        details = getattr(external_verification, "details", {})

    if not status_val:
        return None

    status_str = str(status_val).upper().strip()

    if status_str in ("VERIFIED", "SUCCESS", "ACTIVE", "COMPLIANT"):
        gstin_or_val = details.get("gstin") or details.get("pan") or details.get("legal_name") or "Active"
        return RequirementEvaluationResult(
            requirement_id=req_id,
            state=ComplianceState.PASS,
            risk_level="NONE",
            evaluation_method=EvaluationMethod.EXTERNAL_VERIFICATION,
            reason=f"Authoritative verification from {source} confirmed valid and active ({gstin_or_val}).",
            expected_condition={"verification_source": source},
            observed_values=[gstin_or_val],
            supporting_evidence=provenance_items,
            conflicting_evidence=[],
            review_required=False,
            provenance=provenance_items,
            contradiction_findings=[],
            evaluator_metadata={"tier": "EXTERNAL_VERIFICATION", "registry": source, "status": "VERIFIED"},
            confidence=1.0,
        )

    elif status_str in ("FAILED", "INVALID", "CANCELLED", "SUSPENDED", "DEBARRED"):
        return RequirementEvaluationResult(
            requirement_id=req_id,
            state=ComplianceState.FAIL,
            risk_level="CRITICAL" if "DEBAR" in status_str else "HIGH",
            evaluation_method=EvaluationMethod.EXTERNAL_VERIFICATION,
            reason=f"Authoritative verification from {source} failed: status is '{status_str}'.",
            expected_condition={"verification_source": source},
            observed_values=[status_str],
            supporting_evidence=[],
            conflicting_evidence=provenance_items,
            review_required=True,
            provenance=provenance_items,
            contradiction_findings=[],
            evaluator_metadata={"tier": "EXTERNAL_VERIFICATION", "registry": source, "status": status_str},
            confidence=1.0,
        )

    elif status_str in ("UNAVAILABLE", "SERVICE_UNAVAILABLE", "TIMEOUT", "ERROR"):
        # NEVER MAP UNAVAILABLE TO PASS!
        return RequirementEvaluationResult(
            requirement_id=req_id,
            state=ComplianceState.REVIEW,
            risk_level="HIGH",
            evaluation_method=EvaluationMethod.EXTERNAL_VERIFICATION,
            reason=f"Authoritative external verification registry ({source}) is unavailable; manual verification required.",
            expected_condition={"verification_source": source},
            observed_values=["REGISTRY_UNAVAILABLE"],
            supporting_evidence=[],
            conflicting_evidence=[],
            review_required=True,
            provenance=provenance_items,
            contradiction_findings=[],
            evaluator_metadata={"tier": "EXTERNAL_VERIFICATION", "registry": source, "status": "UNAVAILABLE"},
            confidence=0.90,
        )

    elif status_str in ("PENDING", "PROCESSING", "UNVERIFIED"):
        return RequirementEvaluationResult(
            requirement_id=req_id,
            state=ComplianceState.UNVERIFIED,
            risk_level="MEDIUM",
            evaluation_method=EvaluationMethod.EXTERNAL_VERIFICATION,
            reason=f"External verification with {source} is currently pending or unverified.",
            expected_condition={"verification_source": source},
            observed_values=["PENDING_VERIFICATION"],
            supporting_evidence=[],
            conflicting_evidence=[],
            review_required=True,
            provenance=provenance_items,
            contradiction_findings=[],
            evaluator_metadata={"tier": "EXTERNAL_VERIFICATION", "registry": source, "status": status_str},
            confidence=0.85,
        )

    return None


def check_missing_evidence(
    requirement_dict: Dict[str, Any],
    claim_records: List[ProvenanceRecord],
    evidence_records: List[ProvenanceRecord],
    context: Dict[str, Any],
) -> Optional[RequirementEvaluationResult]:
    """Tier 4: Evaluates missing mandatory evidence or unsupported bidder claims."""
    req_id = requirement_dict.get("requirement_id", "REQ-UNKNOWN")
    is_mandatory = requirement_dict.get("mandatory", True)
    req_docs = requirement_dict.get("evidence_required") or []
    doc_name = req_docs[0] if req_docs else "Mandatory Evidence"

    # Case A: Bidder made an explicit claim, but zero supporting evidence documents were provided
    if claim_records and not evidence_records:
        claim_val = claim_records[0].raw_value or "Claim"
        return RequirementEvaluationResult(
            requirement_id=req_id,
            state=ComplianceState.UNVERIFIED,
            risk_level="HIGH" if is_mandatory else "MEDIUM",
            evaluation_method=EvaluationMethod.DOCUMENT_PRESENCE,
            reason=f"Bidder claimed '{claim_val}', but required supporting proof document was not submitted.",
            expected_condition={"mandatory": is_mandatory, "evidence_required": req_docs},
            observed_values=[claim_val],
            supporting_evidence=[],
            conflicting_evidence=[],
            review_required=False,
            provenance=claim_records,
            contradiction_findings=[],
            evaluator_metadata={"tier": "DOCUMENT_PRESENCE", "subtype": "UNSUPPORTED_CLAIM"},
            confidence=1.0,
        )

    # Case B: Zero claims and zero evidence submitted
    if not claim_records and not evidence_records:
        if is_mandatory:
            return RequirementEvaluationResult(
                requirement_id=req_id,
                state=ComplianceState.UNVERIFIED,
                risk_level="HIGH",
                evaluation_method=EvaluationMethod.DOCUMENT_PRESENCE,
                reason=f"Mandatory {doc_name} was not submitted; compliance could not be established.",
                expected_condition={"mandatory": True, "evidence_required": req_docs},
                observed_values=[],
                supporting_evidence=[],
                conflicting_evidence=[],
                review_required=False,
                provenance=[],
                contradiction_findings=[],
                evaluator_metadata={"tier": "DOCUMENT_PRESENCE", "subtype": "MANDATORY_EVIDENCE_ABSENT"},
                confidence=1.0,
            )
        else:
            return RequirementEvaluationResult(
                requirement_id=req_id,
                state=ComplianceState.UNVERIFIED,
                risk_level="LOW",
                evaluation_method=EvaluationMethod.DOCUMENT_PRESENCE,
                reason="Optional requirement was not addressed in bidder submission.",
                expected_condition={"mandatory": False},
                observed_values=[],
                supporting_evidence=[],
                conflicting_evidence=[],
                review_required=False,
                provenance=[],
                contradiction_findings=[],
                evaluator_metadata={"tier": "DOCUMENT_PRESENCE", "subtype": "OPTIONAL_EVIDENCE_ABSENT"},
                confidence=1.0,
            )

    return None


def check_ambiguity(
    requirement_dict: Dict[str, Any],
    claim_records: List[ProvenanceRecord],
    evidence_records: List[ProvenanceRecord],
    context: Dict[str, Any],
) -> Optional[RequirementEvaluationResult]:
    """Tier 5: Evaluates ambiguous or underspecified tender requirements."""
    req_id = requirement_dict.get("requirement_id", "REQ-UNKNOWN")
    is_ambiguous = requirement_dict.get("is_ambiguous", False)
    ambiguity_reason = requirement_dict.get("ambiguity_reason")
    
    ambiguity_spec = requirement_dict.get("ambiguity") or {}
    if hasattr(ambiguity_spec, "model_dump"):
        ambiguity_spec = ambiguity_spec.model_dump()
    if ambiguity_spec.get("is_ambiguous"):
        is_ambiguous = True
        ambiguity_reason = ambiguity_reason or ambiguity_spec.get("ambiguity_reason")

    if is_ambiguous:
        all_provenance = claim_records + evidence_records
        obs_vals = [p.raw_value for p in all_provenance if p.raw_value]
        return RequirementEvaluationResult(
            requirement_id=req_id,
            state=ComplianceState.REVIEW,
            risk_level="MEDIUM",
            evaluation_method=EvaluationMethod.HUMAN_REVIEW,
            reason=(
                f"Tender requirement contains ambiguous/underspecified criteria: "
                f"{ambiguity_reason or requirement_dict.get('description', '')}. "
                "Manual procurement officer review required to clarify requirement scope."
            ),
            expected_condition={"is_ambiguous": True, "ambiguity_reason": ambiguity_reason},
            observed_values=obs_vals,
            supporting_evidence=evidence_records,
            conflicting_evidence=[],
            review_required=True,
            provenance=all_provenance,
            contradiction_findings=[],
            evaluator_metadata={"tier": "AMBIGUITY_RADAR", "ambiguity_reason": ambiguity_reason},
            confidence=0.90,
        )

    return None


def evaluate_deterministically(
    requirement_dict: Dict[str, Any],
    claim_records: List[ProvenanceRecord],
    evidence_records: List[ProvenanceRecord],
    context: Dict[str, Any],
) -> Optional[RequirementEvaluationResult]:
    """Tier 6: Evaluates executable numeric thresholds, currency figures, dates, and warranties."""
    req_id = requirement_dict.get("requirement_id", "REQ-UNKNOWN")
    category = str(requirement_dict.get("category", "")).upper()
    description = requirement_dict.get("description", "")
    all_provenance = claim_records + evidence_records

    # Collect observed values
    observed_values = [p.raw_value for p in all_provenance if p.raw_value is not None]

    # Structured condition check (supports both TenderRequirement.structured_condition and RequirementEvaluationContract top-level fields)
    struct_cond = requirement_dict.get("structured_condition")
    if hasattr(struct_cond, "model_dump"):
        struct_cond = struct_cond.model_dump()

    thresh_raw = None
    op = None
    unit = None

    if requirement_dict.get("threshold_value") is not None:
        thresh_raw = requirement_dict.get("threshold_value")
        op = requirement_dict.get("operator") or ">="
        unit = requirement_dict.get("threshold_unit")
    elif struct_cond and struct_cond.get("threshold_value") is not None:
        thresh_raw = struct_cond.get("threshold_value")
        op = struct_cond.get("operator") or ">="
        unit = struct_cond.get("unit")

    # 1. Structured Condition or Percentage Threshold (e.g. Local Content >= 20%)
    if thresh_raw is not None:
        thresh_val, thresh_unit = parse_numeric_value(thresh_raw)
        if thresh_val is None and isinstance(thresh_raw, (int, float)):
            thresh_val = float(thresh_raw)
        
        final_unit = unit or thresh_unit

        finding = evaluate_numeric_threshold(
            requirement_id=req_id,
            operator=op or ">=",
            expected_val=thresh_val,
            expected_unit=final_unit,
            observed_values=observed_values,
        )
        
        return _finding_to_result(finding, EvaluationMethod.DETERMINISTIC, all_provenance)

    # 2. Local Content Percentage Category
    if category in ("LOCAL_CONTENT", "LOCAL_CONTENT_MII") or "LOCAL CONTENT" in description.upper() or "%" in description:
        pct_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", description)
        threshold = float(pct_match.group(1)) if pct_match else 20.0
        op = ">="
        if ">" in description and ">=" not in description:
            op = ">"

        finding = evaluate_numeric_threshold(
            requirement_id=req_id,
            operator=op,
            expected_val=threshold,
            expected_unit="PERCENT",
            observed_values=observed_values,
        )
        return _finding_to_result(finding, EvaluationMethod.DETERMINISTIC, all_provenance)

    # 3. Financial Turnover Category (e.g. >= ₹5 crore)
    if category == "FINANCIAL_TURNOVER" or "TURNOVER" in description.upper() or "CRORE" in description.upper() or "LAKH" in description.upper():
        req_val, req_unit = parse_numeric_value(description)
        if req_val is not None:
            finding = evaluate_numeric_threshold(
                requirement_id=req_id,
                operator=">=",
                expected_val=req_val,
                expected_unit=req_unit or "INR",
                observed_values=observed_values,
            )
            return _finding_to_result(finding, EvaluationMethod.DETERMINISTIC, all_provenance)

    # 4. Warranty Period (e.g. >= 24 months)
    if "WARRANTY" in description.upper() or "MONTHS" in description.upper():
        mo_match = re.search(r"([0-9]+)\s*(?:MONTH|MO)S?", description, re.IGNORECASE)
        if mo_match:
            thresh_mo = float(mo_match.group(1))
            finding = evaluate_numeric_threshold(
                requirement_id=req_id,
                operator=">=",
                expected_val=thresh_mo,
                expected_unit="MONTHS",
                observed_values=observed_values,
            )
            return _finding_to_result(finding, EvaluationMethod.DETERMINISTIC, all_provenance)

    # 5. Past Experience Window
    if category in ("EXPERIENCE", "PAST_EXPERIENCE") or "YEARS" in description.upper():
        yr_match = re.search(r"([0-9]+)\s*(?:YEAR|YR)S?", description, re.IGNORECASE)
        past_years = int(yr_match.group(1)) if yr_match else 3
        
        # Check for work order and completion dates in observations or context
        wo_date = context.get("work_order_date")
        comp_date = context.get("completion_date")
        
        if not wo_date or not comp_date:
            for p in all_provenance:
                quote_lower = str(p.quote or "").lower()
                doc_lower = str(p.document_name or "").lower()
                parsed_d = parse_date_value(p.raw_value)
                if parsed_d:
                    if ("order" in quote_lower or "order" in doc_lower or "wo" in doc_lower) and not wo_date:
                        wo_date = parsed_d
                    elif ("completion" in quote_lower or "completion" in doc_lower or "finish" in doc_lower) and not comp_date:
                        comp_date = parsed_d
                    elif not comp_date:
                        comp_date = parsed_d

        finding = evaluate_experience_window(
            requirement_id=req_id,
            past_years_required=past_years,
            work_order_date_input=wo_date,
            completion_date_input=comp_date,
            tender_closing_date=context.get("anchor_date"),
        )
        return _finding_to_result(finding, EvaluationMethod.DETERMINISTIC, all_provenance)

    # 6. Certificate Validity / Expiration Date
    if "VALID" in description.upper() or "EXPIR" in description.upper() or "CERTIFICATE" in description.upper():
        date_obs = None
        for p in all_provenance:
            d = parse_date_value(p.raw_value)
            if d:
                date_obs = d
                break

        if date_obs:
            finding = evaluate_date_validity(
                requirement_id=req_id,
                expiry_date_input=date_obs,
                anchor_date=context.get("anchor_date"),
            )
            return _finding_to_result(finding, EvaluationMethod.DETERMINISTIC, all_provenance)

    return None


def _finding_to_result(
    finding: ComplianceFinding,
    method: EvaluationMethod,
    provenance: List[ProvenanceRecord],
) -> RequirementEvaluationResult:
    """Helper converting a ComplianceFinding to a structured RequirementEvaluationResult."""
    reason = finding.reasoning_trace
    is_review = finding.state == ComplianceState.REVIEW
    
    # Extract clean observed values
    obs_vals = []
    if finding.observed and isinstance(finding.observed, dict):
        if "value" in finding.observed:
            obs_vals.append(finding.observed["value"])
        elif "raw" in finding.observed:
            obs_vals.append(finding.observed["raw"])
        elif "raw_values" in finding.observed:
            obs_vals.extend(finding.observed["raw_values"])
        elif "conflicting_observations" in finding.observed:
            obs_vals.extend(finding.observed["conflicting_observations"])
    
    if not obs_vals:
        obs_vals = [p.normalized_value or p.raw_value for p in provenance if p.raw_value is not None]

    supporting = provenance if finding.state == ComplianceState.PASS else []
    conflicting = provenance if finding.state == ComplianceState.FAIL or is_review else []

    return RequirementEvaluationResult(
        requirement_id=finding.requirement_id,
        state=finding.state,
        risk_level=finding.risk_level,
        evaluation_method=method,
        reason=reason,
        expected_condition=finding.expected,
        observed_values=obs_vals,
        supporting_evidence=supporting,
        conflicting_evidence=conflicting,
        review_required=is_review,
        provenance=provenance,
        contradiction_findings=[],
        evaluator_metadata={"tier": method.value, "rule_type": finding.rule_type},
        confidence=finding.confidence or 1.0,
    )


# ---------------------------------------------------------------------------
# Core Unified Evaluator Entrypoints
# ---------------------------------------------------------------------------

def evaluate_requirement(
    requirement: Union[TenderRequirement, Dict[str, Any], str],
    claims: Optional[Union[BidderClaim, List[BidderClaim], Dict[str, Any], List[Any]]] = None,
    evidence: Optional[Union[EvidenceObservation, ExtractedEvidence, List[Any], Dict[str, Any]]] = None,
    external_verification: Optional[Union[Dict[str, Any], Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> RequirementEvaluationResult:
    """Evaluates a single tender requirement under the strict OPAL tiered evaluation policy.

    Args:
        requirement: Target requirement model, dictionary, or requirement_id string.
        claims: Optional BidderClaim(s) or dictionary.
        evidence: Optional EvidenceObservation(s), ExtractedEvidence, or dictionary.
        external_verification: Optional external authoritative registry verification object.
        context: Optional evaluation context (e.g. anchor_date, exemptions, bidder_profile).

    Returns:
        RequirementEvaluationResult with deterministic state, method, reason, and provenance trace.
    """
    context = context or {}

    # Normalize requirement to dictionary
    if hasattr(requirement, "model_dump"):
        req_dict = requirement.model_dump()
    elif isinstance(requirement, dict):
        req_dict = requirement
    else:
        req_dict = {"requirement_id": str(requirement), "description": str(requirement)}

    req_id = req_dict.get("requirement_id") or "REQ-UNKNOWN"
    req_dict["requirement_id"] = req_id

    # 1. Normalize Claims to ProvenanceRecords
    claim_records: List[ProvenanceRecord] = []
    if claims:
        claim_list = claims if isinstance(claims, list) else [claims]
        for c in claim_list:
            if c is not None:
                claim_records.append(build_provenance_from_claim(c))

    # 2. Normalize Evidence to ProvenanceRecords
    evidence_records: List[ProvenanceRecord] = []
    if evidence:
        ev_list = evidence if isinstance(evidence, list) else [evidence]
        for ev in ev_list:
            if ev is not None:
                evidence_records.extend(build_provenance_from_evidence(ev))

    all_provenance = claim_records + evidence_records

    # TIER 1: APPLICABILITY / EXEMPTION
    exemption_res = check_applicability_exemption(req_dict, context, all_provenance)
    if exemption_res is not None:
        return exemption_res

    # TIER 2: CONTRADICTION / RECONCILIATION
    contradiction_res = check_contradictions_and_reconcile(
        req_dict, claim_records, evidence_records, context,
        raw_claims=claims, raw_evidence=evidence,
    )
    if contradiction_res is not None:
        return contradiction_res

    # TIER 3: EXTERNAL VERIFICATION (if external verification status provided)
    ext_res = check_external_verification(req_dict, external_verification, context, all_provenance)
    if ext_res is not None:
        return ext_res

    # TIER 4: DOCUMENT / EVIDENCE PRESENCE (missing mandatory evidence)
    missing_res = check_missing_evidence(req_dict, claim_records, evidence_records, context)
    if missing_res is not None:
        return missing_res

    # TIER 5: AMBIGUITY RADAR (vague or underspecified requirement clauses)
    ambiguity_res = check_ambiguity(req_dict, claim_records, evidence_records, context)
    if ambiguity_res is not None:
        return ambiguity_res

    # TIER 6: DETERMINISTIC RULE ENGINE
    det_res = evaluate_deterministically(req_dict, claim_records, evidence_records, context)
    if det_res is not None:
        return det_res

    # TIER 7: SEMANTIC / LLM EVALUATION
    semantic_evaluator = get_semantic_evaluator()
    if semantic_evaluator is not None:
        sem_res = semantic_evaluator.evaluate_semantic(req_dict, claim_records, evidence_records, context)
        if sem_res is not None:
            return sem_res

    # TIER 8: HUMAN REVIEW FALLBACK
    obs_vals = [p.normalized_value or p.raw_value for p in all_provenance if p.raw_value is not None]
    return RequirementEvaluationResult(
        requirement_id=req_id,
        state=ComplianceState.REVIEW,
        risk_level="MEDIUM",
        evaluation_method=EvaluationMethod.HUMAN_REVIEW,
        reason="Semantic evaluation unavailable or requires subjective assessment; human review required.",
        expected_condition={"description": req_dict.get("description", "")},
        observed_values=obs_vals,
        supporting_evidence=evidence_records,
        conflicting_evidence=[],
        review_required=True,
        provenance=all_provenance,
        contradiction_findings=[],
        evaluator_metadata={"tier": "HUMAN_REVIEW", "fallback": True},
        confidence=0.80,
    )


def evaluate_requirements(
    requirements: List[Union[TenderRequirement, Dict[str, Any]]],
    claims_by_req: Optional[Dict[str, Any]] = None,
    evidence_by_req: Optional[Dict[str, Any]] = None,
    verifications_by_req: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> List[RequirementEvaluationResult]:
    """Evaluates a list of tender requirements independently.

    Ensures that one failing or ambiguous requirement does NOT contaminate or alter
    the deterministic evaluation of other requirements.

    Args:
        requirements: List of structured requirements.
        claims_by_req: Optional mapping of requirement_id -> claims.
        evidence_by_req: Optional mapping of requirement_id -> evidence observations.
        verifications_by_req: Optional mapping of requirement_id -> external verifications.
        context: Shared evaluation context (e.g. bidder_profile, exemptions).

    Returns:
        List of RequirementEvaluationResult items, one per input requirement.
    """
    claims_by_req = claims_by_req or {}
    evidence_by_req = evidence_by_req or {}
    verifications_by_req = verifications_by_req or {}
    context = context or {}

    results: List[RequirementEvaluationResult] = []

    for req in requirements:
        req_id = req.requirement_id if hasattr(req, "requirement_id") else req.get("requirement_id", "REQ-UNKNOWN")
        
        req_claims = claims_by_req.get(req_id)
        req_evidence = evidence_by_req.get(req_id)
        req_verification = verifications_by_req.get(req_id)

        res = evaluate_requirement(
            requirement=req,
            claims=req_claims,
            evidence=req_evidence,
            external_verification=req_verification,
            context=context,
        )
        results.append(res)

    return results

