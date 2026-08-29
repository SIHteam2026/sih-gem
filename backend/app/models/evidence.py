"""Bidder Document Evidence Extraction Models.

Defines Pydantic data models for structured evidence extraction, proof verification,
source grounding, and confidence scoring from bidder-submitted documents.
"""

from typing import Dict, Optional
from pydantic import BaseModel, Field


class ExtractedEvidence(BaseModel):
    """Structured evidence extracted from bidder documentation for a specific requirement."""
    requirement_id: str = Field(
        ...,
        description="The unique identifier of the requirement this evidence applies to.",
    )
    is_present: bool = Field(
        ...,
        description="Indicates whether the document contains evidence for this requirement.",
    )
    extracted_values: Dict[str, str] = Field(
        default_factory=dict,
        description="Key-value dictionary of extracted parameters (e.g. {'local_content_percentage': '27%'}).",
    )
    source_quote: Optional[str] = Field(
        default="",
        description="The exact verbatim sentence or clause from the document proving the claim.",
    )
    extraction_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence score for the extraction, ranging from 0.0 to 1.0.",
    )
