"""Bidder Compliance Evaluation Models.

Defines Pydantic data models and enumerations for evaluation outcomes,
compliance states, risk levels, and audit reasoning traces.
"""

from enum import Enum
from pydantic import BaseModel, Field


class ComplianceState(str, Enum):
    """Enumeration of bidder requirement compliance states."""
    VERIFIED = "VERIFIED"
    NON_COMPLIANT = "NON_COMPLIANT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNVERIFIED = "UNVERIFIED"


class ComplianceFinding(BaseModel):
    """Model representing an evaluation finding for a specific requirement."""
    requirement_id: str = Field(
        ...,
        description="The unique requirement identifier.",
    )
    state: ComplianceState = Field(
        ...,
        description="Compliance determination state: VERIFIED, NON_COMPLIANT, REVIEW_REQUIRED, or UNVERIFIED.",
    )
    risk_level: str = Field(
        ...,
        description="Risk level associated with this finding: 'HIGH', 'MEDIUM', 'LOW', or 'NONE'.",
    )
    reasoning_trace: str = Field(
        ...,
        description="A short explanation of exactly why this compliance decision was made.",
    )
