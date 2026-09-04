"""Canonical Procurement Data Models.

Defines persistent Pydantic domain schemas for the OPAL procurement ingestion foundation:
Procurement -> Tender -> Bidder -> BidSubmission -> Documents.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ProcurementStatus(str, Enum):
    """Enumeration of procurement lifecycle statuses."""
    IMPORTED = "IMPORTED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class DocumentType(str, Enum):
    """Enumeration of recognized document types across tenders and submissions."""
    TENDER_SPECIFICATION = "TENDER_SPECIFICATION"
    GST_CERTIFICATE = "GST_CERTIFICATE"
    OEM_AUTHORIZATION = "OEM_AUTHORIZATION"
    TURNOVER_CERTIFICATE = "TURNOVER_CERTIFICATE"
    TECHNICAL_BID = "TECHNICAL_BID"
    FINANCIAL_BOQ = "FINANCIAL_BOQ"
    OTHER = "OTHER"


# ---------------------------------------------------------------------------
# Document Models
# ---------------------------------------------------------------------------
class DocumentBase(BaseModel):
    """Base schema for document metadata."""
    filename: str = Field(..., description="Original filename of the uploaded/ingested document.")
    document_type: Optional[DocumentType] = Field(None, description="Category of the document.")
    mime_type: str = Field(default="application/pdf", description="MIME content type.")
    file_size: Optional[int] = Field(None, description="File size in bytes.")
    storage_path: Optional[str] = Field(None, description="Path or object key in cloud/local storage.")
    content_text: Optional[str] = Field(None, description="Extracted raw text content of the document.")


class DocumentCreate(DocumentBase):
    """Schema for creating a document entity."""
    procurement_id: str = Field(..., description="Associated procurement ID.")
    tender_id: Optional[str] = Field(None, description="Associated tender ID (if tender-level document).")
    bid_submission_id: Optional[str] = Field(None, description="Associated bid submission ID (if bidder document).")


class Document(DocumentBase):
    """Canonical persistent Document model."""
    id: str = Field(..., description="Unique document UUID.")
    procurement_id: str = Field(..., description="Associated procurement ID.")
    tender_id: Optional[str] = Field(None, description="Associated tender ID.")
    bid_submission_id: Optional[str] = Field(None, description="Associated bid submission ID.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Bidder Models
# ---------------------------------------------------------------------------
class BidderBase(BaseModel):
    """Base schema for corporate bidder identity."""
    legal_name: str = Field(..., description="Registered corporate legal name.")
    gstin: Optional[str] = Field(None, description="15-character Goods and Services Tax Identification Number.")
    pan: Optional[str] = Field(None, description="10-character Permanent Account Number.")
    email: Optional[str] = Field(None, description="Primary contact email address.")


class BidderCreate(BidderBase):
    """Schema for creating a new bidder entity."""
    pass


class Bidder(BidderBase):
    """Canonical persistent Bidder model."""
    id: str = Field(..., description="Unique bidder UUID.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Bid Submission Models
# ---------------------------------------------------------------------------
class BidSubmissionBase(BaseModel):
    """Base schema for a bidder's submission to a tender."""
    external_submission_reference: Optional[str] = Field(None, description="External source submission reference.")
    submitted_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Submission timestamp.")
    status: str = Field(default="SUBMITTED", description="Submission status (e.g. SUBMITTED, UNDER_REVIEW, EVALUATED).")


class BidSubmissionCreate(BidSubmissionBase):
    """Schema for creating a bid submission."""
    tender_id: str = Field(..., description="Associated tender ID.")
    bidder_id: str = Field(..., description="Associated bidder ID.")


class BidSubmission(BidSubmissionBase):
    """Canonical persistent BidSubmission model."""
    id: str = Field(..., description="Unique bid submission UUID.")
    tender_id: str = Field(..., description="Associated tender ID.")
    bidder_id: str = Field(..., description="Associated bidder ID.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class BidSubmissionWithDetails(BidSubmission):
    """Bid submission with embedded bidder profile and attached document proofs."""
    bidder: Optional[Bidder] = Field(None, description="Associated bidder profile.")
    documents: List[Document] = Field(default_factory=list, description="Attached evidence documents.")


# ---------------------------------------------------------------------------
# Tender Models
# ---------------------------------------------------------------------------
class TenderBase(BaseModel):
    """Base schema for a tender notice / RFP."""
    tender_reference: str = Field(..., description="Tender reference number (e.g., 'GEM/2026/B/894120').")
    title: str = Field(..., description="Tender title or work description.")
    description: Optional[str] = Field(None, description="Detailed RFP summary or scope of work.")
    estimated_value: Optional[float] = Field(None, description="Benchmark budget / estimated value in INR.")
    category: Optional[str] = Field(None, description="Procurement category (e.g. IT_INFRASTRUCTURE, GOODS, SERVICES).")


class TenderCreate(TenderBase):
    """Schema for creating a tender."""
    procurement_id: str = Field(..., description="Associated procurement ID.")


class Tender(TenderBase):
    """Canonical persistent Tender model."""
    id: str = Field(..., description="Unique tender UUID.")
    procurement_id: str = Field(..., description="Associated procurement ID.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class TenderWithDetails(Tender):
    """Tender with associated tender specification documents and bidder submissions."""
    documents: List[Document] = Field(default_factory=list, description="Tender RFP/NIT specification documents.")
    submissions: List[BidSubmissionWithDetails] = Field(default_factory=list, description="Bidder submissions for this tender.")


# ---------------------------------------------------------------------------
# Procurement Models
# ---------------------------------------------------------------------------
class ProcurementBase(BaseModel):
    """Base schema for top-level procurement workspace."""
    source_system: str = Field(default="MOCK_GEM", description="External source system (e.g. MOCK_GEM, REAL_GEM).")
    external_reference: str = Field(..., description="External procurement reference ID.")
    title: str = Field(..., description="Overall procurement title.")
    organization: str = Field(..., description="Issuing government department or agency.")
    status: ProcurementStatus = Field(default=ProcurementStatus.IMPORTED, description="Ingestion/processing status.")


class ProcurementCreate(ProcurementBase):
    """Schema for creating a procurement workspace."""
    pass


class Procurement(ProcurementBase):
    """Canonical persistent Procurement model."""
    id: str = Field(..., description="Unique procurement UUID.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ProcurementHierarchy(Procurement):
    """Full canonical procurement hierarchy: Procurement -> Tenders -> Submissions -> Documents."""
    tenders: List[TenderWithDetails] = Field(default_factory=list, description="Associated tenders in this procurement.")
    documents: List[Document] = Field(default_factory=list, description="Top-level procurement documents.")
