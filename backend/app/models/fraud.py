"""Fraud and Collusion Risk Analysis Models.

Defines Pydantic models for bidder trust scoring, anomaly detection,
metadata cross-verification, and collusion risk assessment.
"""

from typing import List
from pydantic import BaseModel, Field


class FraudAnalysisResult(BaseModel):
    """Model representing bidder fraud detection, trust scoring, and collusion risk analysis."""
    trust_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Overall bidder authenticity and trust score on a scale from 0 to 100.",
    )
    is_suspicious: bool = Field(
        ...,
        description="Indicates whether suspicious patterns, document tampering, or anomalies were detected.",
    )
    red_flags: List[str] = Field(
        default_factory=list,
        description="List of detected anomalies such as date mismatches, conflicting registrations, or metadata discrepancies.",
    )
    collusion_risk_level: str = Field(
        ...,
        description="Collusion risk level rating: 'HIGH', 'MEDIUM', 'LOW', or 'NONE'.",
    )
