"""Canonical Procurement Data Models.

Defines persistent Pydantic domain schemas for the OPAL procurement ingestion foundation:
Procurement -> Tender -> Bidder -> BidSubmission -> Documents.
"""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field

try:
    from backend.app.models.tender import TenderRequirement
except ImportError:
    try:
        from app.models.tender import TenderRequirement
    except ImportError:
        from models.tender import TenderRequirement


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
    """Tender with associated tender specification documents, bidder submissions, and requirements."""
    documents: List[Document] = Field(default_factory=list, description="Tender RFP/NIT specification documents.")
    submissions: List[BidSubmissionWithDetails] = Field(default_factory=list, description="Bidder submissions for this tender.")
    requirements: List[TenderRequirement] = Field(default_factory=list, description="Structured tender requirements extracted from intelligence analysis.")


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


# ---------------------------------------------------------------------------
# Ingestion Contract Models
# ---------------------------------------------------------------------------
class IngestionDocumentInput(BaseModel):
    """Input payload model for document metadata."""
    filename: str = Field(..., min_length=1, description="Original document filename.")
    document_type: Optional[DocumentType] = Field(None, description="Category of the document.")
    mime_type: str = Field(default="application/pdf", description="MIME type.")
    file_size: Optional[int] = Field(None, description="File size in bytes.")
    storage_path: Optional[str] = Field(None, description="Storage location reference or URL.")
    content_text: Optional[str] = Field(None, description="Extracted raw text content.")


class IngestionProcurementInfo(BaseModel):
    """Input payload model for top-level procurement details."""
    title: str = Field(..., min_length=1, description="Procurement workspace title.")
    organization: str = Field(..., min_length=1, description="Issuing government agency or department.")


class IngestionTenderInfo(BaseModel):
    """Input payload model for tender RFP details."""
    tender_reference: str = Field(..., min_length=1, description="Official tender reference number.")
    title: str = Field(..., min_length=1, description="Tender title or work description.")
    description: Optional[str] = Field(None, description="Scope of work or tender summary.")
    estimated_value: Optional[float] = Field(None, description="Estimated budget in INR.")
    category: Optional[str] = Field(None, description="Procurement category.")
    documents: List[IngestionDocumentInput] = Field(default_factory=list, description="Tender specification documents.")


class IngestionBidderInfo(BaseModel):
    """Input payload model for bidder profile details."""
    legal_name: str = Field(..., min_length=1, description="Registered legal name of the bidder.")
    gstin: Optional[str] = Field(None, description="15-character GSTIN identifier.")
    pan: Optional[str] = Field(None, description="10-character PAN identifier.")
    email: Optional[str] = Field(None, description="Contact email.")


class IngestionSubmissionInfo(BaseModel):
    """Input payload model for submission metadata."""
    external_submission_reference: Optional[str] = Field(None, description="External submission ID.")
    submitted_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Submission timestamp.")
    status: str = Field(default="SUBMITTED", description="Submission status.")


class IngestionBidderPackageInput(BaseModel):
    """Input payload model grouping a bidder, their submission, and attached proof documents."""
    bidder: IngestionBidderInfo = Field(..., description="Bidder entity profile.")
    submission: Optional[IngestionSubmissionInfo] = Field(default_factory=IngestionSubmissionInfo, description="Submission metadata.")
    documents: List[IngestionDocumentInput] = Field(default_factory=list, description="Attached evidence documents.")


class ProcurementIngestionPayload(BaseModel):
    """Canonical input payload contract for ingesting an external procurement package."""
    source_system: str = Field(..., min_length=1, description="Source system identifier (e.g., MOCK_GEM, REAL_GEM).")
    external_reference: str = Field(..., min_length=1, description="Unique external reference identifier.")
    procurement: IngestionProcurementInfo = Field(..., description="Procurement metadata.")
    tender: IngestionTenderInfo = Field(..., description="Tender metadata and RFP specification documents.")
    bidders: List[IngestionBidderPackageInput] = Field(default_factory=list, description="List of bidder packages.")


class ProcurementIngestionResult(BaseModel):
    """Result returned by the ingestion service."""
    procurement_id: str = Field(..., description="Internal UUID of the procurement workspace.")
    source_system: str = Field(..., description="Source system identifier.")
    external_reference: str = Field(..., description="External procurement reference ID.")
    tender_id: str = Field(..., description="Internal UUID of the created/resolved tender.")
    bidder_count: int = Field(default=0, description="Total bidders ingested.")
    submission_count: int = Field(default=0, description="Total submissions ingested.")
    document_count: int = Field(default=0, description="Total documents registered.")
    status: ProcurementStatus = Field(..., description="Final procurement status.")
    was_created: bool = Field(..., description="True if new procurement was created, False if existing record was matched.")
    message: str = Field(..., description="Human-readable execution outcome summary.")
    hierarchy: Optional[ProcurementHierarchy] = Field(None, description="Full canonical procurement hierarchy.")

