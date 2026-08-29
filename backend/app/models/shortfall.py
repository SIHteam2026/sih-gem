"""Bidder Clarification and Document Shortfall Models.

Defines Pydantic models for automated shortfall detection,
ambiguity resolution, and formal communication drafting.
"""

from typing import List
from pydantic import BaseModel, Field


class ShortfallRequest(BaseModel):
    """Model representing bidder document shortfall assessment and formal clarification email draft."""
    requires_clarification: bool = Field(
        ...,
        description="Indicates whether document shortfalls, ambiguous evidence, or missing proofs require bidder clarification.",
    )
    missing_items: List[str] = Field(
        default_factory=list,
        description="List of specific missing certificates, ambiguous declarations, or incomplete proofs required from the bidder.",
    )
    clarification_email_draft: str = Field(
        ...,
        description="A fully written, formal bureaucratic clarification email draft addressed to the bidder citing tender clauses.",
    )
