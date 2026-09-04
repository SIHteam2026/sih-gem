"""Bidder Compliance Evaluation Models.

Defines Pydantic data models and enumerations for evaluation outcomes,
compliance states, risk levels, and audit reasoning traces.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ComplianceState(str, Enum):
    """Enumeration of bidder requirement compliance states.

    Canonical states:
        PASS: Evidence deterministically and unambiguously satisfies the requirement.
        FAIL: Clear violation, deficiency, debarment, or failure to meet criteria.
        REVIEW: Ambiguity, conflicting evidence, or borderline case requiring human review.
        UNVERIFIED: Evidence is missing, un-extracted, or incomplete without affirmative failure.
        NOT_APPLICABLE: Requirement is waived under an authorized exemption (e.g. MSE/Startup).

    Legacy aliases preserved for backwards compatibility:
        VERIFIED (= PASS)
        NON_COMPLIANT (= FAIL)
        REVIEW_REQUIRED (= REVIEW)
    """
    # Canonical modern states
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    UNVERIFIED = "UNVERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"

    # Legacy compatibility aliases
    VERIFIED = "VERIFIED"
    NON_COMPLIANT = "NON_COMPLIANT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class EvaluationMethod(str, Enum):
    """Enumeration of evaluation mechanisms used for auditability."""
    DETERMINISTIC = "DETERMINISTIC"
    CONTRADICTION_RECONCILIATION = "CONTRADICTION_RECONCILIATION"
    DOCUMENT_PRESENCE = "DOCUMENT_PRESENCE"
    EXTERNAL_VERIFICATION = "EXTERNAL_VERIFICATION"
    SEMANTIC_LLM = "SEMANTIC_LLM"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    APPLICABILITY_EXEMPTION = "APPLICABILITY_EXEMPTION"


class ExternalVerificationStatus(str, Enum):
    """Enumeration of authoritative external government verification states."""
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    PENDING = "PENDING"
    UNVERIFIED = "UNVERIFIED"


class ComplianceFinding(BaseModel):
    """Model representing an evaluation finding for a specific requirement."""
    requirement_id: str = Field(
        ...,
        description="The unique requirement identifier.",
    )
    state: ComplianceState = Field(
        ...,
        description="Compliance determination state: PASS, FAIL, REVIEW, UNVERIFIED, NOT_APPLICABLE (or legacy VERIFIED, NON_COMPLIANT, REVIEW_REQUIRED).",
    )
    risk_level: str = Field(
        default="NONE",
        description="Risk level associated with this finding: 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', or 'NONE'.",
    )
    reasoning_trace: str = Field(
        ...,
        description="A short explanation of exactly why this compliance decision was made.",
    )
    rule_type: str | None = Field(
        default=None,
        description="Category of rule evaluated (e.g., 'NUMERIC_THRESHOLD', 'DATE_VALIDITY', 'MANDATORY_EVIDENCE', 'APPLICABILITY_EXEMPTION').",
    )
    expected: dict | None = Field(
        default=None,
        description="Structured criteria or threshold expected by the requirement.",
    )
    observed: dict | None = Field(
        default=None,
        description="Structured observed values extracted from bidder submissions or claims.",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="List of referenced evidence IDs or source document identifiers.",
    )
    confidence: float | None = Field(
        default=1.0,
        description="Confidence score for this finding (1.0 for deterministic rules).",
    )


class RequirementEvaluationResult(BaseModel):
    """Structured evaluation result for a tender requirement under the tiered evaluation policy."""
    requirement_id: str = Field(..., description="Unique identifier of the evaluated requirement.")
    state: ComplianceState = Field(..., description="Compliance state (PASS, FAIL, REVIEW, UNVERIFIED, NOT_APPLICABLE).")
    risk_level: str = Field(default="NONE", description="Risk level: NONE, LOW, MEDIUM, HIGH, CRITICAL.")
    evaluation_method: EvaluationMethod = Field(..., description="Evaluation mechanism used.")
    reason: str = Field(..., description="Human-readable and audit-friendly explanation of the outcome.")
    expected_condition: Optional[Dict[str, Any]] = Field(default=None, description="Structured criteria expected.")
    observed_values: Optional[List[Any]] = Field(default_factory=list, description="List of observed values/claims.")
    supporting_evidence: List[Any] = Field(default_factory=list, description="Supporting provenance records or observations.")
    conflicting_evidence: List[Any] = Field(default_factory=list, description="Conflicting provenance records or observations.")
    review_required: bool = Field(default=False, description="Whether human procurement officer review is required.")
    provenance: List[Any] = Field(default_factory=list, description="Complete provenance audit chain for this requirement.")
    contradiction_findings: List[Any] = Field(default_factory=list, description="Contradiction findings if detected.")
    evaluator_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata on evaluator tier, timing, etc.")
    confidence: Optional[float] = Field(default=1.0, description="Confidence score.")

    def to_compliance_finding(self) -> ComplianceFinding:
        """Converts to standard ComplianceFinding for backwards compatibility."""
        ev_ids = []
        for p in self.provenance:
            if hasattr(p, "evidence_id") and p.evidence_id:
                ev_ids.append(str(p.evidence_id))
            elif hasattr(p, "claim_id") and p.claim_id:
                ev_ids.append(str(p.claim_id))
            elif isinstance(p, dict):
                if p.get("evidence_id"):
                    ev_ids.append(str(p["evidence_id"]))
                elif p.get("claim_id"):
                    ev_ids.append(str(p["claim_id"]))

        return ComplianceFinding(
            requirement_id=self.requirement_id,
            state=self.state,
            risk_level=self.risk_level,
            reasoning_trace=self.reason,
            rule_type=self.evaluation_method.value,
            expected=self.expected_condition,
            observed={"values": self.observed_values, "contradictions": len(self.contradiction_findings)},
            evidence_ids=list(set(ev_ids)),
            confidence=self.confidence or 1.0,
        )
