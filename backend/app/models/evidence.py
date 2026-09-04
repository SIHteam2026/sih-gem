"""Bidder Document Evidence Extraction Models.

Defines Pydantic data models for structured evidence extraction, proof verification,
source grounding, and confidence scoring from bidder-submitted documents.
"""

from typing import Any, Dict, Optional
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


class BidderClaim(BaseModel):
    """Model representing an explicit assertion or self-declaration made by a bidder."""
    claim_id: str = Field(..., description="Unique claim identifier.")
    requirement_id: str = Field(..., description="Target requirement identifier.")
    claimed_value: Any = Field(..., description="Value claimed by the bidder (e.g., 27.0 or 'Active').")
    unit: Optional[str] = Field(default=None, description="Unit of measurement (e.g., 'PERCENT', 'INR').")
    source_document: Optional[str] = Field(default=None, description="Document filename containing the declaration.")
    page_number: Optional[int] = Field(default=None, description="Page number where the claim appears.")
    raw_statement: Optional[str] = Field(default=None, description="Verbatim statement of the claim.")


class EvidenceObservation(BaseModel):
    """Model representing an observed metric or fact extracted from supporting proof documents."""
    evidence_id: str = Field(..., description="Unique evidence observation identifier.")
    requirement_id: str = Field(..., description="Target requirement identifier.")
    observed_value: Any = Field(..., description="Value verified from supporting evidence (e.g., 14.0 or '2027-03-31').")
    unit: Optional[str] = Field(default=None, description="Unit of measurement (e.g., 'PERCENT', 'INR').")
    is_authoritative: bool = Field(default=False, description="Whether from an authoritative 3rd party (e.g. CA / GSTN).")
    source_document: Optional[str] = Field(default=None, description="Document filename containing the evidence.")
    page_number: Optional[int] = Field(default=None, description="Page number where the evidence appears.")
    source_quote: Optional[str] = Field(default="", description="Verbatim proof excerpt from the document.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score.")

