from pydantic import BaseModel, Field
from typing import List, Optional, Any


class TechnicalParameter(BaseModel):
    """Canonical representation of a technical requirement extracted from a tender.
    Linked to a Requirement via ``requirement_id``.
    """
    requirement_id: str = Field(..., description="Requirement identifier from the tender.")
    parameter: str = Field(..., description="Short name of the parameter (e.g., 'Warranty', 'Local Content').")
    requirement_text: str = Field(..., description="Full textual clause for the requirement.")
    required_value: Optional[Any] = Field(None, description="Numeric or categorical value required by the clause.")
    operator: Optional[str] = Field(None, description="Comparison operator (>=, <=, =, IN, etc.).")
    unit: Optional[str] = Field(None, description="Unit of measurement (PERCENT, MONTHS, INR, etc.).")
    mandatory: bool = Field(True, description="Whether the requirement is mandatory for qualification.")
    evidence_expected: List[str] = Field(default_factory=list, description="List of document types or attributes expected as evidence.")
    source_document: Optional[str] = Field(None, description="Document name where the requirement originated.")
    source_page: Optional[int] = Field(None, description="Page number of the source document.")
    ambiguity_flag: bool = Field(False, description="True if the clause contains ambiguous language.")


class TechnicalMatrix(BaseModel):
    """Container for all technical parameters of a tender.
    The matrix is built once per tender and referenced by ``requirement_id``.
    """
    tender_id: str = Field(..., description="Identifier of the tender this matrix belongs to.")
    parameters: List[TechnicalParameter] = Field(default_factory=list, description="All extracted technical parameters.")
