"""Tender Intelligence Engine Pydantic Models.

Defines the core data models and enums for parsing, categorizing, and analyzing
tender requirements and compliance criteria.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RequirementCategory(str, Enum):
    """Enumeration of tender requirement categories."""
    GST = "GST"
    OEM_AUTH = "OEM_AUTH"
    LOCAL_CONTENT = "LOCAL_CONTENT"
    EXPERIENCE = "EXPERIENCE"


class TenderRequirement(BaseModel):
    """Model representing an individual requirement extracted from a tender."""
    requirement_id: str = Field(..., description="Unique identifier for the requirement.")
    category: RequirementCategory = Field(..., description="Category of the requirement.")
    description: str = Field(..., description="Detailed description of the requirement.")
    mandatory: bool = Field(default=True, description="Indicates if the requirement is mandatory.")
    evidence_required: List[str] = Field(
        default_factory=list,
        description="List of required evidence documents or proofs.",
    )
    is_ambiguous: bool = Field(
        default=False,
        description="Flag indicating if the requirement contains vague or underspecified criteria.",
    )
    ambiguity_reason: Optional[str] = Field(
        default=None,
        description="Explanation of missing metrics or ambiguity in the clause.",
    )


class TenderAnalysisResult(BaseModel):
    """Model representing the full analysis result for a tender document."""
    tender_id: str = Field(..., description="Unique identifier for the tender.")
    requirements: List[TenderRequirement] = Field(
        default_factory=list,
        description="List of extracted and categorized tender requirements.",
    )
