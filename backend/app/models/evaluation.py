"""Bidder Compliance Evaluation Models.

Defines Pydantic data models and enumerations for evaluation outcomes,
compliance states, risk levels, and audit reasoning traces.
"""

from enum import Enum
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

