"""Executive Audit Report Models.

Defines Pydantic models for holistic tender audit reports, key compliance violations,
financial assessments, and final procurement recommendations.
"""

from typing import List
from pydantic import BaseModel, Field


class FinalAuditReport(BaseModel):
    """Holistic executive audit report aggregating technical, entity, and financial evaluations."""
    executive_summary: str = Field(
        ...,
        description="High-level narrative executive summary of the bidder evaluation and key findings.",
    )
    key_violations: List[str] = Field(
        default_factory=list,
        description="List of specific failed requirements, entity mismatches, missing documents, or BOQ arithmetic errors.",
    )
    financial_assessment: str = Field(
        ...,
        description="Comprehensive assessment of the commercial bid, price reasonableness, and abnormally low bid status.",
    )
    final_recommendation: str = Field(
        ...,
        description="Final procurement decision: 'ACCEPT', 'REJECT', or 'MANUAL_REVIEW'.",
    )
