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
