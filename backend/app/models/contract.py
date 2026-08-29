"""Contract and Letter of Award (LOA) Models.

Defines Pydantic models for automated Letter of Award drafting,
contract reference generation, statutory terms, and legal covenant management.
"""

from typing import List
from pydantic import BaseModel, Field


class LetterOfAward(BaseModel):
    """Model representing an automated legal Letter of Award (LOA) / Contract Note."""
    contract_reference_number: str = Field(
        ...,
        description="Unique legal contract or LOA reference number (e.g., 'LOA/GEM/2026/08/4892').",
    )
    date_of_issue: str = Field(
        ...,
        description="Official ISO or formatted date of contract issuance (e.g., '2026-08-29').",
    )
    vendor_name: str = Field(
        ...,
        description="Full verified legal name of the awarded vendor or bidder.",
    )
    total_award_value: float = Field(
        ...,
        description="Total sanctioned contract value in INR.",
    )
    legal_clauses: List[str] = Field(
        default_factory=list,
        description="List of standard government terms like warranty, delivery timeline, performance security, and jurisdiction.",
    )
    full_contract_text: str = Field(
        ...,
        description="Complete drafted formal text of the Letter of Award.",
    )
