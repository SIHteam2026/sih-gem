"""Financial and Commercial Bid Evaluation Models.

Defines Pydantic models for arithmetic auditing, line-item summation validation,
abnormally low bid (ALB) detection, and audit notes.
"""

from typing import List
from pydantic import BaseModel, Field


class FinancialEvaluationResult(BaseModel):
    """Model representing commercial bid financial evaluation and arithmetic audit results."""
    total_bid_value: float = Field(
        ...,
        description="The calculated or verified total commercial bid value in currency units.",
    )
    math_errors_found: bool = Field(
        ...,
        description="Indicates whether calculation mismatches, unit price errors, or summation issues were detected.",
    )
    abnormally_low_bid: bool = Field(
        ...,
        description="Indicates whether the bid is flagged as abnormally low compared to benchmark/estimate.",
    )
    audit_notes: List[str] = Field(
        default_factory=list,
        description="Detailed notes explaining calculation mismatches, incorrect summations, or missing tax components.",
    )
