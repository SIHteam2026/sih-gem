"""Canonical Procurement Data Models.

Defines persistent Pydantic domain schemas for the OPAL procurement ingestion foundation:
Procurement -> Tender -> Bidder -> BidSubmission -> Documents.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

try:
    from app.models.tender import TenderRequirement
except ImportError:
    from models.tender import TenderRequirement


class ProcurementStatus(str, Enum):
    """Enumeration of canonical procurement lifecycle statuses."""
    IMPORTED = "IMPORTED"
    READY_FOR_TECHNICAL_SCRUTINY = "READY_FOR_TECHNICAL_SCRUTINY"
    TECHNICAL_SCRUTINY_RUNNING = "TECHNICAL_SCRUTINY_RUNNING"
    TECHNICAL_REVIEW = "TECHNICAL_REVIEW"
    CLARIFICATION_OPEN = "CLARIFICATION_OPEN"
    RE_EVALUATION_RUNNING = "RE_EVALUATION_RUNNING"
    TECHNICAL_FREEZE = "TECHNICAL_FREEZE"
    COVER_2_READY = "COVER_2_READY"
    FINANCIAL_EVALUATION_RUNNING = "FINANCIAL_EVALUATION_RUNNING"
    FINANCIAL_REVIEW = "FINANCIAL_REVIEW"
    L1_DETERMINED = "L1_DETERMINED"
    FAILED = "FAILED"

    # Backward compatibility aliases
    READY = "READY"
    PROCESSING = "PROCESSING"


class ProcessingStage(str, Enum):
    """Enumeration of processing pipeline stages."""
    TENDER_INTELLIGENCE = "TENDER_INTELLIGENCE"
    DOCUMENT_INTELLIGENCE = "DOCUMENT_INTELLIGENCE"
    EVIDENCE_EXTRACTION = "EVIDENCE_EXTRACTION"
    COMPLIANCE_EVALUATION = "COMPLIANCE_EVALUATION"


class DocumentType(str, Enum):
    """Enumeration of recognized document types across tenders and submissions."""
    TENDER_SPECIFICATION = "TENDER_SPECIFICATION"
    GST_CERTIFICATE = "GST_CERTIFICATE"
    OEM_AUTHORIZATION = "OEM_AUTHORIZATION"
    TURNOVER_CERTIFICATE = "TURNOVER_CERTIFICATE"
    LOCAL_CONTENT_CERTIFICATE = "LOCAL_CONTENT_CERTIFICATE"
    PAN_CARD = "PAN_CARD"
    EXPERIENCE_CERTIFICATE = "EXPERIENCE_CERTIFICATE"
    EMD_PROOF = "EMD_PROOF"
    TECHNICAL_BID = "TECHNICAL_BID"
    FINANCIAL_BOQ = "FINANCIAL_BOQ"
    OTHER = "OTHER"


class TechnicalFreezeStatus(str, Enum):
    """Enumeration of Technical Freeze (Cover 1) evaluation statuses."""
    NOT_FROZEN = "NOT_FROZEN"
    FROZEN = "FROZEN"
    TECHNICAL_REVIEW_REQUIRED = "TECHNICAL_REVIEW_REQUIRED"
    TECHNICALLY_QUALIFIED = "TECHNICALLY_QUALIFIED"
    TECHNICALLY_DISQUALIFIED = "TECHNICALLY_DISQUALIFIED"


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
    processing_status: str = Field(default="PENDING", description="Document intelligence processing status.")


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
    technical_freeze_status: TechnicalFreezeStatus = Field(default=TechnicalFreezeStatus.NOT_FROZEN, description="Technical Freeze lifecycle status.")
    is_locked: bool = Field(default=False, description="Whether the submission is locked against further evidence mutation.")
    frozen_at: Optional[datetime] = Field(None, description="Timestamp when technical freeze was applied.")
    frozen_by: Optional[str] = Field(None, description="Officer/system identifier that applied technical freeze.")
    freeze_reason: Optional[str] = Field(None, description="Operational rationale or context for freeze.")


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
    requirements: List[Any] = Field(default_factory=list, description="Structured tender requirements extracted from intelligence analysis.")



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


# ---------------------------------------------------------------------------
# Procurement Read API DTO Models
# ---------------------------------------------------------------------------
class DocumentMetadataResponse(BaseModel):
    """Clean document metadata response DTO without heavy extracted text payloads."""
    id: str = Field(..., description="Document UUID.")
    procurement_id: str = Field(..., description="Associated procurement ID.")
    tender_id: Optional[str] = Field(None, description="Associated tender ID.")
    bid_submission_id: Optional[str] = Field(None, description="Associated bid submission ID.")
    filename: str = Field(..., description="Original filename.")
    document_type: Optional[str] = Field(None, description="Category of the document.")
    mime_type: str = Field(default="application/pdf", description="MIME content type.")
    file_size: Optional[int] = Field(None, description="File size in bytes.")
    storage_path: Optional[str] = Field(None, description="Storage location reference or key.")
    processing_status: str = Field(default="PENDING", description="Document intelligence processing status.")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class BidderSummaryResponse(BaseModel):
    """Bidder identity summary DTO."""
    id: str = Field(..., description="Bidder UUID.")
    legal_name: str = Field(..., description="Registered corporate legal name.")
    gstin: Optional[str] = Field(None, description="15-character GSTIN identifier.")
    pan: Optional[str] = Field(None, description="10-character PAN identifier.")
    email: Optional[str] = Field(None, description="Primary contact email address.")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class SubmissionSummaryResponse(BaseModel):
    """Bid submission workspace summary DTO."""
    id: str = Field(..., description="Bid submission UUID.")
    tender_id: str = Field(..., description="Associated tender ID.")
    bidder_id: str = Field(..., description="Associated bidder ID.")
    external_submission_reference: Optional[str] = Field(None, description="External submission reference.")
    submitted_at: Optional[datetime] = Field(None, description="Submission timestamp.")
    status: str = Field(default="SUBMITTED", description="Submission status.")
    technical_freeze_status: TechnicalFreezeStatus = Field(default=TechnicalFreezeStatus.NOT_FROZEN, description="Technical Freeze lifecycle status.")
    is_locked: bool = Field(default=False, description="Whether the submission is locked against further evidence mutation.")
    frozen_at: Optional[datetime] = Field(None, description="Timestamp when technical freeze was applied.")
    frozen_by: Optional[str] = Field(None, description="Officer/system identifier that applied technical freeze.")
    freeze_reason: Optional[str] = Field(None, description="Operational rationale or context for freeze.")
    bidder: Optional[BidderSummaryResponse] = Field(None, description="Associated bidder profile.")
    documents: List[DocumentMetadataResponse] = Field(default_factory=list, description="Attached evidence document metadata.")
    document_count: int = Field(default=0, description="Total documents attached.")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class TenderSummaryResponse(BaseModel):
    """Tender workspace summary DTO."""
    id: str = Field(..., description="Tender UUID.")
    procurement_id: str = Field(..., description="Associated procurement ID.")
    tender_reference: str = Field(..., description="Tender reference number.")
    title: str = Field(..., description="Tender title.")
    description: Optional[str] = Field(None, description="Scope of work or summary.")
    estimated_value: Optional[float] = Field(None, description="Estimated budget in INR.")
    category: Optional[str] = Field(None, description="Procurement category.")
    status: str = Field(default="READY", description="Tender status.")
    requirement_count: int = Field(default=0, description="Extracted requirement criteria count.")
    document_count: int = Field(default=0, description="Tender specification document count.")
    bidder_count: int = Field(default=0, description="Participating bidder count.")
    documents: List[DocumentMetadataResponse] = Field(default_factory=list, description="Tender specification documents.")
    submissions: List[SubmissionSummaryResponse] = Field(default_factory=list, description="Bidder submissions for this tender.")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ProcurementSummaryItem(BaseModel):
    """Summary item for procurement list queries."""
    procurement_id: str = Field(..., description="Procurement UUID.")
    id: str = Field(..., description="Procurement UUID (alias for compatibility).")
    external_reference: str = Field(..., description="External procurement reference ID.")
    title: str = Field(..., description="Procurement workspace title.")
    organization: str = Field(..., description="Issuing government organization.")
    source_system: str = Field(..., description="Source system identifier (e.g., MOCK_GEM, REAL_GEM).")
    status: ProcurementStatus = Field(..., description="Procurement lifecycle status.")
    tender_count: int = Field(default=0, description="Total tenders in this procurement.")
    bidder_count: int = Field(default=0, description="Total unique participating bidders.")
    document_count: int = Field(default=0, description="Total documents registered.")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ProcurementListResponse(BaseModel):
    """Paginated list response for procurement list query."""
    total: int = Field(..., description="Total matching procurements.")
    limit: int = Field(..., description="Query limit.")
    offset: int = Field(..., description="Query offset.")
    procurements: List[ProcurementSummaryItem] = Field(default_factory=list, description="Procurement summaries.")


class ProcurementDetailResponse(BaseModel):
    """Full detail summary for procurement workspace."""
    id: str = Field(..., description="Procurement UUID.")
    external_reference: str = Field(..., description="External reference ID.")
    title: str = Field(..., description="Procurement workspace title.")
    organization: str = Field(..., description="Issuing government department.")
    source_system: str = Field(..., description="Source system identifier.")
    status: ProcurementStatus = Field(..., description="Procurement status.")
    tenders: List[TenderSummaryResponse] = Field(default_factory=list, description="Associated tenders.")
    documents: List[DocumentMetadataResponse] = Field(default_factory=list, description="Top-level procurement documents.")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class TenderWorkspaceDetailResponse(BaseModel):
    """Detailed workspace response for opening a specific tender."""
    id: str = Field(..., description="Tender UUID.")
    procurement_id: str = Field(..., description="Parent procurement UUID.")
    procurement_title: Optional[str] = Field(None, description="Parent procurement title.")
    procurement_external_reference: Optional[str] = Field(None, description="Parent procurement external reference.")
    source_system: Optional[str] = Field(None, description="Source system identifier.")
    tender_reference: str = Field(..., description="Tender reference number.")
    title: str = Field(..., description="Tender title.")
    description: Optional[str] = Field(None, description="Tender description.")
    estimated_value: Optional[float] = Field(None, description="Estimated budget in INR.")
    category: Optional[str] = Field(None, description="Procurement category.")
    status: str = Field(default="READY", description="Processing status.")
    requirement_count: int = Field(default=0, description="Total requirement criteria.")
    document_count: int = Field(default=0, description="Tender specification documents.")
    bidder_count: int = Field(default=0, description="Participating bidders.")
    documents: List[DocumentMetadataResponse] = Field(default_factory=list, description="Tender specification documents.")
    submissions: List[SubmissionSummaryResponse] = Field(default_factory=list, description="Bidder submissions.")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Procurement Processing Lifecycle Models
# ---------------------------------------------------------------------------
class ProcessingStageResult(BaseModel):
    """Result status from executing a single processing pipeline stage."""
    stage: ProcessingStage = Field(..., description="Stage enum identifier.")
    success: bool = Field(..., description="Whether the stage completed successfully.")
    error_code: Optional[str] = Field(None, description="Structured error code if stage failed.")
    error_message: Optional[str] = Field(None, description="Human-readable safe error message.")
    execution_time_ms: float = Field(default=0.0, description="Stage execution time in milliseconds.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Stage-specific execution metadata.")


class ProcurementProcessingStatusResponse(BaseModel):
    """Detailed response for checking procurement processing status."""
    procurement_id: str = Field(..., description="Target procurement UUID.")
    status: ProcurementStatus = Field(..., description="Current procurement processing status.")
    current_stage: Optional[ProcessingStage] = Field(None, description="Active stage being executed.")
    completed_stages: List[ProcessingStage] = Field(default_factory=list, description="Stages successfully executed.")
    failed_stage: Optional[ProcessingStage] = Field(None, description="Stage that failed execution.")
    stage_results: List[ProcessingStageResult] = Field(default_factory=list, description="Detailed stage results.")
    retry_count: int = Field(default=0, description="Total processing retry count.")
    last_error_code: Optional[str] = Field(None, description="Error code of last failure.")
    last_error_message: Optional[str] = Field(None, description="Safe error message of last failure.")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class StartProcessingResponse(BaseModel):
    """Response returned when triggering procurement processing."""
    procurement_id: str = Field(..., description="Target procurement UUID.")
    status: ProcurementStatus = Field(..., description="Updated procurement status.")
    message: str = Field(..., description="Status summary message.")
    already_completed: bool = Field(default=False, description="True if processing was already READY and skipped without force.")
    already_in_progress: bool = Field(default=False, description="True if processing is currently ongoing.")


class ProcessingContext(BaseModel):
    """Context object passed to processing stages during execution."""
    procurement_id: str = Field(..., description="Procurement UUID being processed.")
    procurement: Any = Field(..., description="Procurement domain entity.")
    force: bool = Field(default=False, description="Force re-processing flag.")
    retry_count: int = Field(default=0, description="Current retry attempt number.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Shared contextual metadata.")


# ---------------------------------------------------------------------------
# Technical Scrutiny & Review Lifecycle Models
# ---------------------------------------------------------------------------
class TechnicalScrutinyRunRequest(BaseModel):
    """Request payload for initiating full Technical Scrutiny."""
    force: bool = Field(default=False, description="Force re-execution even if already completed.")
    actor: Optional[str] = Field(default="PROCUREMENT_OFFICER", description="Initiator of the scrutiny run.")
    notes: Optional[str] = Field(default=None, description="Optional operational notes or rationale.")


class TechnicalScrutinyRunResponse(BaseModel):
    """Authoritative response from executing full Technical Scrutiny (L1-L7)."""
    procurement_id: str = Field(..., description="Target procurement UUID.")
    status: ProcurementStatus = Field(..., description="Updated procurement status (e.g. TECHNICAL_REVIEW).")
    executed_layers: List[str] = Field(default_factory=list, description="Verification layers executed (L1-L7).")
    bidders_evaluated: int = Field(default=0, description="Total bidders evaluated.")
    disqualified_count: int = Field(default=0, description="Total bidders with failed mandatory criteria.")
    review_count: int = Field(default=0, description="Total bidders requiring officer review.")
    qualified_count: int = Field(default=0, description="Total bidders meeting pass criteria.")
    open_clarifications_count: int = Field(default=0, description="Total unresolved clarification requests.")
    execution_time_ms: float = Field(default=0.0, description="Execution duration in milliseconds.")
    message: str = Field(..., description="Summary message.")


class OfficerBidderTechnicalSummary(BaseModel):
    """Officer-facing summary for a single participating bidder."""
    bidder_id: str = Field(..., description="Bidder UUID.")
    legal_name: str = Field(..., description="Corporate registered name.")
    submission_id: str = Field(..., description="Bid submission UUID.")
    technical_freeze_status: TechnicalFreezeStatus = Field(default=TechnicalFreezeStatus.NOT_FROZEN, description="Technical Freeze status.")
    compliance_status: str = Field(..., description="Overall compliance recommendation: PASS, FAIL, REVIEW, UNVERIFIED, NOT_APPLICABLE.")
    passed_requirements_count: int = Field(default=0, description="Number of passed requirements.")
    failed_requirements_count: int = Field(default=0, description="Number of failed requirements.")
    review_requirements_count: int = Field(default=0, description="Number of requirements needing review.")
    findings_count: int = Field(default=0, description="Total forensic findings associated with bidder.")
    has_open_clarifications: bool = Field(default=False, description="Whether bidder has pending/unresolved clarifications.")
    is_technically_eligible: bool = Field(default=False, description="Whether bidder currently qualifies technically.")
    is_blocking: bool = Field(default=False, description="Whether this bidder has blocking issues preventing qualification.")
    officer_action_required: bool = Field(default=False, description="Whether officer action is required to resolve bidder findings.")
    blockers: List[str] = Field(default_factory=list, description="List of concrete blocker descriptions for this bidder.")
    unresolved_clarifications: List[str] = Field(default_factory=list, description="IDs of active/open clarifications for this bidder.")
    pending_re_evaluation: bool = Field(default=False, description="Whether a clarification response is awaiting re-evaluation.")
    summary_notes: Optional[str] = Field(default=None, description="Key takeaway notes for the officer.")


class OfficerRequirementSummary(BaseModel):
    """Officer-facing summary for a tender requirement across bidders."""
    requirement_id: str = Field(..., description="Requirement UUID or code.")
    category: str = Field(..., description="Requirement category (e.g., GST, OEM, TURNOVER).")
    title: str = Field(..., description="Requirement title / description.")
    description: Optional[str] = Field(default=None, description="Detailed requirement text.")
    is_mandatory: bool = Field(default=True, description="Whether requirement is mandatory for qualification.")
    compliance_by_bidder: Dict[str, str] = Field(default_factory=dict, description="Compliance status keyed by bidder ID.")


class OfficerFindingSummary(BaseModel):
    """Officer-facing actionable finding from multi-layer forensics."""
    finding_id: Optional[str] = Field(default=None, description="Finding UUID if present.")
    bidder_id: str = Field(..., description="Associated bidder UUID.")
    bidder_name: str = Field(..., description="Associated bidder legal name.")
    layer: str = Field(..., description="Verification layer that raised the finding.")
    severity: str = Field(..., description="Severity level: INFO, WARNING, CRITICAL, FATAL.")
    title: str = Field(..., description="Short finding headline.")
    detail: str = Field(..., description="Detailed explanation.")
    evidence_pointer: Optional[str] = Field(default=None, description="Document/page pointer if available.")
    source_reference: Optional[str] = Field(default=None, description="Tender clause / external reference.")
    requires_clarification: bool = Field(default=False, description="Whether this finding warrants a clarification.")
    is_blocking: bool = Field(default=False, description="Whether this finding represents a mandatory qualification blocker.")
    clarification_id: Optional[str] = Field(default=None, description="Associated clarification UUID if opened.")
    clarification_status: Optional[str] = Field(default=None, description="Status of associated clarification.")


class OfficerClarificationSummary(BaseModel):
    """Officer-facing clarification status record."""
    clarification_id: str = Field(..., description="Clarification UUID.")
    bidder_id: str = Field(..., description="Associated bidder UUID.")
    bidder_name: str = Field(..., description="Associated bidder legal name.")
    requirement_id: Optional[str] = Field(default=None, description="Targeted requirement UUID.")
    subject: str = Field(..., description="Clarification question / subject.")
    status: str = Field(..., description="Clarification status: OPEN, RESPONDED, RESOLVED, CANCELLED.")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp.")


class OfficerFreezeSummary(BaseModel):
    """Officer-facing technical freeze state summary."""
    is_frozen: bool = Field(default=False, description="Whether all submissions are technically frozen.")
    frozen_at: Optional[datetime] = Field(default=None, description="When freeze was applied.")
    frozen_by: Optional[str] = Field(default=None, description="Officer/system identifier.")
    freeze_reason: Optional[str] = Field(default=None, description="Rationale for freeze.")
    qualified_bidders: List[str] = Field(default_factory=list, description="Bidder names/IDs considered qualified.")
    disqualified_bidders: List[str] = Field(default_factory=list, description="Bidder names/IDs considered disqualified.")


class Cover2ReadinessSummary(BaseModel):
    """Audit readiness summary for unlocking Cover 2 Financial Opening."""
    is_ready: bool = Field(default=False, description="Whether Cover 2 Financial Opening is permissible.")
    blockers: List[str] = Field(default_factory=list, description="Hard gating blockers preventing Cover 2 opening.")
    warnings: List[str] = Field(default_factory=list, description="Advisory warnings for the officer.")
    eligible_bidder_count: int = Field(default=0, description="Total bidders eligible for Cover 2.")
    eligible_bidders: List[str] = Field(default_factory=list, description="Names/IDs of eligible bidders.")
    technical_freeze_enforced: bool = Field(default=False, description="Whether Technical Freeze is fully enforced.")
    open_clarifications_count: int = Field(default=0, description="Count of unresolved clarifications.")


class Cover2ReadinessResponse(BaseModel):
    """Full officer response for Cover 2 Readiness evaluation."""
    procurement_id: str = Field(..., description="Target procurement UUID.")
    status: ProcurementStatus = Field(..., description="Procurement status.")
    cover2_readiness: Cover2ReadinessSummary = Field(..., description="Detailed Cover 2 gating breakdown.")
    decision_authority: str = Field(default="HUMAN_PROCUREMENT_OFFICER", description="Governance boundary authority.")
    evaluated_at: datetime = Field(default_factory=datetime.utcnow, description="Evaluation timestamp.")


class ProcurementTechnicalReviewResponse(BaseModel):
    """Authoritative Officer-facing Technical Review representation."""
    procurement_id: str = Field(..., description="Procurement UUID.")
    external_reference: str = Field(..., description="External procurement reference.")
    title: str = Field(..., description="Procurement workspace title.")
    status: ProcurementStatus = Field(..., description="Current procurement lifecycle status.")
    total_bidders: int = Field(default=0, description="Total participating bidders.")
    qualified_bidders_count: int = Field(default=0, description="Number of technically qualified bidders.")
    excluded_bidders_count: int = Field(default=0, description="Number of technically excluded bidders.")
    review_required_bidders_count: int = Field(default=0, description="Number of bidders requiring officer review.")
    unresolved_blockers: List[str] = Field(default_factory=list, description="Procurement-level technical blockers.")
    can_freeze: bool = Field(default=False, description="Whether procurement satisfies technical prerequisites to freeze.")
    can_open_cover2: bool = Field(default=False, description="Whether procurement meets prerequisites for Cover 2 opening.")
    bidders: List[OfficerBidderTechnicalSummary] = Field(default_factory=list, description="Bidder compliance summaries.")
    requirements: List[OfficerRequirementSummary] = Field(default_factory=list, description="Requirement matrix summaries.")
    key_findings: List[OfficerFindingSummary] = Field(default_factory=list, description="Consolidated multi-layer forensic findings.")
    clarifications: List[OfficerClarificationSummary] = Field(default_factory=list, description="Associated clarification lifecycles.")
    freeze_status: OfficerFreezeSummary = Field(default_factory=OfficerFreezeSummary, description="Technical Freeze state.")
    cover2_readiness: Cover2ReadinessSummary = Field(default_factory=Cover2ReadinessSummary, description="Cover 2 financial gate readiness.")
    decision_authority: str = Field(default="HUMAN_PROCUREMENT_OFFICER", description="Governance boundary authority.")
    last_evaluated_at: Optional[datetime] = Field(default=None, description="Timestamp of last scrutiny run.")




