from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

try:
    from backend.app.models.evaluation import ComplianceState
except ImportError:
    try:
        from app.models.evaluation import ComplianceState
    except ImportError:
        from models.evaluation import ComplianceState


class ContradictionType(str, Enum):
    """Enumeration of contradiction and evidence conflict types."""
    NUMERIC_CONFLICT = "NUMERIC_CONFLICT"
    DATE_CONFLICT = "DATE_CONFLICT"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    STATUS_CONFLICT = "STATUS_CONFLICT"
    ATTRIBUTE_CONFLICT = "ATTRIBUTE_CONFLICT"
    CLAIM_UNSUPPORTED = "CLAIM_UNSUPPORTED"
    EVIDENCE_DISAGREEMENT = "EVIDENCE_DISAGREEMENT"
    INCOMPATIBLE_UNITS = "INCOMPATIBLE_UNITS"


class RelationshipClassification(str, Enum):
    """Enumeration of relational classifications between claims and evidence."""
    CONSISTENT = "CONSISTENT"
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    UNSUPPORTED = "UNSUPPORTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ExtractedEvidence(BaseModel):
    """Structured evidence extracted from bidder documentation for a specific requirement."""
    requirement_id: str = Field(
        ...,
        description="The unique identifier of the requirement this evidence applies to.",
    )
    document_id: Optional[str] = Field(
        None,
        description="The canonical UUID of the source document.",
    )
    bid_submission_id: Optional[str] = Field(
        None,
        description="The canonical UUID of the bid submission.",
    )
    bidder_id: Optional[str] = Field(
        None,
        description="The canonical UUID of the bidder.",
    )
    page_number: Optional[int] = Field(
        None,
        description="The 1-indexed page number where the claim was found.",
    )
    sheet_name: Optional[str] = Field(
        None,
        description="The sheet name where the evidence was found for spreadsheet formats.",
    )
    row_number: Optional[int] = Field(
        None,
        description="The 1-indexed row number where the evidence was found for tabular formats.",
    )
    location_context: Optional[str] = Field(
        None,
        description="Human-readable provenance location context (e.g. Sheet: Data, Row: 5).",
    )
    source_format: Optional[str] = Field(
        None,
        description="Original source file format (PDF, CSV, DOCX, XLSX, TXT).",
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
    bidder_id: Optional[str] = Field(default=None, description="Bidder canonical UUID.")
    bid_submission_id: Optional[str] = Field(default=None, description="Bid Submission canonical UUID.")
    requirement_id: str = Field(..., description="Target requirement identifier.")
    claimed_value: Any = Field(..., description="Value claimed by the bidder (e.g., 27.0 or 'Active').")
    unit: Optional[str] = Field(default=None, description="Unit of measurement (e.g., 'PERCENT', 'INR').")
    source_document: Optional[str] = Field(default=None, description="Document filename containing the declaration.")
    page_number: Optional[int] = Field(default=None, description="Page number where the claim appears.")
    sheet_name: Optional[str] = Field(default=None, description="Sheet name if source is spreadsheet.")
    row_number: Optional[int] = Field(default=None, description="Row number if source is structured table/spreadsheet/CSV.")
    location_context: Optional[str] = Field(default=None, description="Detailed location context.")
    source_format: Optional[str] = Field(default=None, description="Source format (PDF, XLSX, CSV, DOCX, TXT).")
    raw_statement: Optional[str] = Field(default=None, description="Verbatim statement of the claim.")
    source_type: Optional[str] = Field(default="BIDDER_DECLARATION", description="Source classification.")
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score.")
    document_id: Optional[str] = Field(default=None, description="Document canonical UUID.")


class EvidenceObservation(BaseModel):
    """Model representing an observed metric or fact extracted from supporting proof documents."""
    evidence_id: str = Field(..., description="Unique evidence observation identifier.")
    bidder_id: Optional[str] = Field(default=None, description="Bidder canonical UUID.")
    bid_submission_id: Optional[str] = Field(default=None, description="Bid Submission canonical UUID.")
    requirement_id: str = Field(..., description="Target requirement identifier.")
    observed_value: Any = Field(..., description="Value verified from supporting evidence (e.g., 14.0 or '2027-03-31').")
    unit: Optional[str] = Field(default=None, description="Unit of measurement (e.g., 'PERCENT', 'INR').")
    is_authoritative: bool = Field(default=False, description="Whether from an authoritative 3rd party (e.g. CA / GSTN).")
    source_document: Optional[str] = Field(default=None, description="Document filename containing the evidence.")
    page_number: Optional[int] = Field(default=None, description="Page number where the evidence appears.")
    sheet_name: Optional[str] = Field(default=None, description="Sheet name if source is spreadsheet.")
    row_number: Optional[int] = Field(default=None, description="Row number if source is structured table/spreadsheet/CSV.")
    location_context: Optional[str] = Field(default=None, description="Detailed location context.")
    source_format: Optional[str] = Field(default=None, description="Source format (PDF, XLSX, CSV, DOCX, TXT).")
    source_quote: Optional[str] = Field(default="", description="Verbatim proof excerpt from the document.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score.")
    source_type: Optional[str] = Field(default="SUPPORTING_DOCUMENT", description="Source classification (e.g. 'CA_CERTIFICATE', 'OEM_MAF').")
    document_id: Optional[str] = Field(default=None, description="Document canonical UUID.")


class ProvenanceRecord(BaseModel):
    """Traceable provenance detailing where a specific fact, claim, or evidence originated."""
    document_id: Optional[str] = Field(default=None, description="Document UUID or database identifier.")
    document_name: Optional[str] = Field(default=None, description="Filename or title of source document.")
    page_number: Optional[int] = Field(default=None, description="Page number in source document.")
    sheet_name: Optional[str] = Field(default=None, description="Sheet name if source is spreadsheet.")
    row_number: Optional[int] = Field(default=None, description="Row number if source is structured table/spreadsheet/CSV.")
    location_context: Optional[str] = Field(default=None, description="Detailed location context.")
    source_format: Optional[str] = Field(default=None, description="Source format (PDF, XLSX, CSV, DOCX, TXT).")
    source_type: Optional[str] = Field(default=None, description="Source classification (e.g. 'Bidder Self-Declaration', 'CA Certificate').")
    quote: Optional[str] = Field(default=None, description="Verbatim excerpt or citation quote.")
    extraction_confidence: Optional[float] = Field(default=1.0, description="Extraction confidence score (0.0 to 1.0).")
    raw_value: Optional[Any] = Field(default=None, description="Original unparsed string or value.")
    normalized_value: Optional[Any] = Field(default=None, description="Parsed canonical float, date, or string.")
    unit: Optional[str] = Field(default=None, description="Unit of measurement (e.g. 'PERCENT', 'INR').")
    claim_id: Optional[str] = Field(default=None, description="Referenced claim identifier if applicable.")
    evidence_id: Optional[str] = Field(default=None, description="Referenced evidence observation identifier if applicable.")


class SideBySideComparison(BaseModel):
    """Side-by-side juxtaposition of two competing or supporting claims/evidence items."""
    left: ProvenanceRecord = Field(..., description="Baseline claim or first evidence observation.")
    right: ProvenanceRecord = Field(..., description="Comparing claim or second evidence observation.")
    comparison_type: ContradictionType = Field(..., description="Type of discrepancy or comparison.")
    relationship: RelationshipClassification = Field(..., description="Relational classification (SUPPORTS, CONTRADICTS, etc.).")
    discrepancy_description: str = Field(..., description="Human-readable explanation of the comparison or variance.")
    delta_value: Optional[Any] = Field(default=None, description="Mathematical difference or variance if numeric.")


class ContradictionFinding(BaseModel):
    """Model representing an identified conflict, contradiction, or unsupported claim."""
    finding_id: str = Field(..., description="Unique contradiction finding identifier.")
    bidder_id: Optional[str] = Field(default=None, description="Bidder identifier if available.")
    bidder_name: Optional[str] = Field(default=None, description="Bidder company name.")
    submission_id: Optional[str] = Field(default=None, description="Bid submission identifier.")
    requirement_id: str = Field(..., description="Target requirement identifier.")
    contradiction_type: ContradictionType = Field(..., description="Specific contradiction classification.")
    severity: str = Field(default="HIGH", description="Severity level: 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', or 'NONE'.")
    relationship_status: RelationshipClassification = Field(..., description="Overall relational status.")
    explanation: str = Field(..., description="Comprehensive explanation of the conflict.")
    side_by_side: Optional[SideBySideComparison] = Field(default=None, description="Direct side-by-side evidence comparison.")
    claim_references: List[str] = Field(default_factory=list, description="List of claim IDs involved.")
    evidence_references: List[str] = Field(default_factory=list, description="List of evidence IDs involved.")
    provenance_items: List[ProvenanceRecord] = Field(default_factory=list, description="Exhaustive provenance list for all compared sources.")
    detected_at: Optional[str] = Field(default=None, description="ISO 8601 detection timestamp.")


class RequirementReconciliationResult(BaseModel):
    """Comprehensive reconciliation result summarizing claims, evidence, and contradictions for a requirement."""
    requirement_id: str = Field(..., description="Target requirement identifier.")
    overall_status: ComplianceState = Field(..., description="Compliance recommendation state (PASS, FAIL, REVIEW, UNVERIFIED, NOT_APPLICABLE).")
    contradiction_count: int = Field(default=0, description="Total number of contradictions identified.")
    relationships: List[RelationshipClassification] = Field(default_factory=list, description="List of observed relationships.")
    findings: List[ContradictionFinding] = Field(default_factory=list, description="List of specific contradiction findings.")
    unresolved_conflicts: List[str] = Field(default_factory=list, description="Human-readable list of unresolved conflicts.")
    supporting_evidence_count: int = Field(default=0, description="Count of supporting evidence observations.")
    conflicting_evidence_count: int = Field(default=0, description="Count of conflicting evidence observations.")
    missing_evidence_count: int = Field(default=0, description="Count of missing mandatory evidence items.")
    review_required: bool = Field(default=False, description="Whether human review is required to resolve conflicting evidence.")
    reconciliation_summary: str = Field(..., description="Summary of evidence reconciliation findings.")


