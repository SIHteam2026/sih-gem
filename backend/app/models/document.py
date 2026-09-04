"""Document Classification Models.

Defines the data models and enums for document category classification
and extracted key identifier results.
"""

from enum import Enum
from typing import List
from pydantic import BaseModel, Field


class DocumentCategory(str, Enum):
    """Enumeration of recognized document categories."""
    GST_CERTIFICATE = "GST_CERTIFICATE"
    PAN_CARD = "PAN_CARD"
    UDYAM_CERTIFICATE = "UDYAM_CERTIFICATE"
    OEM_AUTHORIZATION = "OEM_AUTHORIZATION"
    EXPERIENCE_CERTIFICATE = "EXPERIENCE_CERTIFICATE"
    UNKNOWN = "UNKNOWN"


class DocumentClassificationResult(BaseModel):
    """Model representing document classification and detected identifiers."""
    category: DocumentCategory = Field(
        ...,
        description="Classified document category.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Classification confidence score from 0.0 to 1.0.",
    )
    key_identifiers: List[str] = Field(
        default_factory=list,
        description="List of key identifiers detected in the document (e.g. GSTIN, PAN, Udyam registration).",
    )


class ExtractedDocumentContent(BaseModel):
    """Standardized extraction payload across all document formats in OPAL."""
    filename: str = Field(..., description="Source filename.")
    file_format: str = Field(..., description="Detected file format (pdf, csv, docx, xlsx, txt).")
    raw_text: str = Field(default="", description="Aggregated text extracted from the document.")
    page_count: int = Field(default=1, description="Page or sheet count.")
    pages: List[dict] = Field(default_factory=list, description="Per-page or per-unit text chunks [{'page': int, 'text': str}].")
    sections: List[dict] = Field(default_factory=list, description="Extracted sections or headings.")
    tables: List[dict] = Field(default_factory=list, description="Extracted structured tables [{'sheet': str, 'headers': list, 'rows': list}].")
    source_locations: List[dict] = Field(default_factory=list, description="Detailed format-specific provenance locations.")
    file_size: int = Field(default=0, description="File size in bytes.")
    metadata: dict = Field(default_factory=dict, description="Format-specific extraction metadata.")

    def __getitem__(self, item: str):
        return getattr(self, item)

    def get(self, item: str, default=None):
        return getattr(self, item, default)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item)

    def keys(self):
        return self.__dict__.keys()

    def __iter__(self):
        return iter(self.__dict__)
