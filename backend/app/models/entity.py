"""Entity Matching Models.

Defines the data models for entity name matching, normalization,
and compliance verification confidence scoring.
"""

from pydantic import BaseModel, Field


class EntityMatchResult(BaseModel):
    """Model representing the result of fuzzy entity name resolution and comparison."""
    entity_name_1: str = Field(
        ...,
        description="First entity/company name as provided in the source.",
    )
    entity_name_2: str = Field(
        ...,
        description="Second entity/company name to compare against.",
    )
    normalized_1: str = Field(
        ...,
        description="Normalized representation of entity_name_1.",
    )
    normalized_2: str = Field(
        ...,
        description="Normalized representation of entity_name_2.",
    )
    match_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fuzzy match similarity score ranging from 0.0 to 1.0.",
    )
    is_match: bool = Field(
        ...,
        description="Flag indicating if the entities match based on threshold criteria.",
    )
    requires_human_review: bool = Field(
        ...,
        description="Flag indicating if the match score falls within the borderline threshold requiring manual review.",
    )
