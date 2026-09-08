"""Canonical Clarification Lifecycle and Technical Freeze Data Models.

Defines Pydantic models for managing clarification requests, bidder responses,
attached clarification evidence proofs, targeted requirement re-evaluation,
and technical freeze locks.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

try:
    from app.models.procurement import Document, IngestionDocumentInput, TechnicalFreezeStatus
except ImportError:
    from models.procurement import Document, IngestionDocumentInput, TechnicalFreezeStatus


class ClarificationStatus(str, Enum):
    """Enumeration of clarification lifecycle statuses."""
    OPEN = "OPEN"
    RESPONDED = "RESPONDED"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    REQUIRES_FURTHER_CLARIFICATION = "REQUIRES_FURTHER_CLARIFICATION"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class ClarificationDraftRequest(BaseModel):
    """Request payload for generating an AI-drafted clarification / shortfall notice."""
    procurement_id: str = Field(..., description="Procurement workspace UUID.")
    submission_id: str = Field(..., description="Bid submission UUID.")
    requirement_id: str = Field(..., description="Target tender requirement ID.")
    originating_finding_id: Optional[str] = Field(None, description="Optional originating finding UUID.")
    custom_instruction: Optional[str] = Field(None, description="Optional guidance or operational notes from the officer.")


class ClarificationDraftResponse(BaseModel):
    """Structured AI-generated draft clarification notice for officer review and editing."""
    subject: str = Field(..., description="Formal notice subject line.")
    recipient_bidder: str = Field(..., description="Name or corporate identity of the recipient bidder.")
    tender_reference: str = Field(..., description="Tender identifier / reference number.")
    requirement_id: str = Field(..., description="Target tender requirement code.")
    requirement_title: str = Field(..., description="Human-readable requirement title.")
    observed_shortfall: str = Field(..., description="Clear explanation of the observed shortfall, ambiguity, or missing proof.")
    requested_clarification: str = Field(..., description="Specific evidentiary documents or clarifications requested.")
    suggested_deadline_days: Optional[int] = Field(None, description="Optional suggested timeframe in days if derived from domain rules.")
    supporting_evidence_references: List[str] = Field(default_factory=list, description="Relevant cited document references or page numbers.")
    is_draft: bool = Field(default=True, description="Strictly marked as a draft notice.")
    decision_authority: str = Field(default="HUMAN_PROCUREMENT_OFFICER", description="Decision authority boundary.")


class ClarificationResolutionRequest(BaseModel):
    """Request payload for explicitly resolving or advancing a clarification status."""
    resolution_status: ClarificationStatus = Field(..., description="Target status: RESOLVED, REQUIRES_FURTHER_CLARIFICATION, REJECTED, or CANCELLED.")
    resolution_notes: Optional[str] = Field(None, description="Officer notes explaining the resolution.")
    officer_id: Optional[str] = Field(default="OFFICER", description="Procurement officer taking the resolution action.")


# ---------------------------------------------------------------------------
# Technical Freeze Models
# ---------------------------------------------------------------------------
class TechnicalFreezeRequest(BaseModel):
    """Request payload for applying or modifying technical freeze on a submission."""
    freeze: bool = Field(default=True, description="True to freeze/lock, False to unfreeze/unlock.")
    freeze_reason: Optional[str] = Field(None, description="Operational justification or rationale for freezing.")
    officer_id: Optional[str] = Field(default="OFFICER", description="Procurement officer or system actor applying the freeze.")


class TechnicalFreezeResponse(BaseModel):
    """Response payload detailing the technical freeze state of a submission."""
    submission_id: str = Field(..., description="Unique submission UUID.")
    technical_freeze_status: TechnicalFreezeStatus = Field(..., description="Current technical freeze status.")
    is_locked: bool = Field(..., description="Whether the submission is locked against further mutations.")
    frozen_at: Optional[datetime] = Field(None, description="Timestamp when freeze was applied.")
    frozen_by: Optional[str] = Field(None, description="Officer/system identifier that applied the freeze.")
    freeze_reason: Optional[str] = Field(None, description="Operational rationale or note for freeze.")
    message: str = Field(..., description="Status summary message.")


# ---------------------------------------------------------------------------
# Clarification Request Models
# ---------------------------------------------------------------------------
class ClarificationCreate(BaseModel):
    """Payload to create a formal clarification / shortfall request for a submission finding."""
    procurement_id: Optional[str] = Field(None, description="Procurement workspace UUID (inferred if omitted).")
    tender_id: Optional[str] = Field(None, description="Tender UUID (inferred if omitted).")
    bidder_id: Optional[str] = Field(None, description="Bidder UUID (inferred if omitted).")
    submission_id: str = Field(..., description="Target bid submission UUID.")
    requirement_id: str = Field(..., description="Identifier of the requirement needing clarification/proof.")
    originating_finding_id: Optional[str] = Field(None, description="UUID of the finding that prompted this clarification.")
    question: str = Field(..., min_length=5, description="Formal clarification question or shortfall notice to bidder.")
    due_at: Optional[datetime] = Field(None, description="Deadline timestamp for bidder response.")
    created_by: Optional[str] = Field(default="OFFICER", description="Officer/system identifier initiating clarification.")


class ClarificationResponseInput(BaseModel):
    """Payload for submitting a response to an open clarification request."""
    response_text: str = Field(..., min_length=1, description="Textual explanation or statement from the bidder.")
    documents: List[IngestionDocumentInput] = Field(
        default_factory=list,
        description="Newly attached certificate or evidence documents submitted in response to the clarification.",
    )
    responded_by: Optional[str] = Field(default="BIDDER", description="Actor providing the response.")


class ClarificationRecord(BaseModel):
    """Canonical persistent record representing a clarification lifecycle instance."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique clarification request UUID.")
    procurement_id: str = Field(..., description="Associated procurement workspace UUID.")
    tender_id: str = Field(..., description="Associated tender UUID.")
    bidder_id: str = Field(..., description="Target bidder UUID.")
    submission_id: str = Field(..., description="Associated bid submission UUID.")
    requirement_id: str = Field(..., description="Target requirement identifier.")
    originating_finding_id: Optional[str] = Field(None, description="Originating finding ID.")
    question: str = Field(..., description="Clarification question / shortfall requirement text.")
    status: ClarificationStatus = Field(default=ClarificationStatus.OPEN, description="Clarification status.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp.")
    created_by: Optional[str] = Field(None, description="Officer who created the clarification.")
    due_at: Optional[datetime] = Field(None, description="Response due timestamp.")
    response_text: Optional[str] = Field(None, description="Bidder response explanation.")
    response_documents: List[Document] = Field(default_factory=list, description="Documents attached as part of response.")
    responded_at: Optional[datetime] = Field(None, description="Timestamp when response was submitted.")
    responded_by: Optional[str] = Field(None, description="Actor who submitted response.")
    re_evaluation_status: Optional[str] = Field(None, description="Re-evaluation outcome status.")
    resulting_finding: Optional[Dict[str, Any]] = Field(None, description="Targeted re-evaluated requirement finding dictionary.")
    audit_history: List[Dict[str, Any]] = Field(default_factory=list, description="Traceable chronological audit events.")

    class Config:
        from_attributes = True


class ClarificationListResponse(BaseModel):
    """Paginated or filtered list of clarification records."""
    total: int = Field(..., description="Total matching clarification records.")
    clarifications: List[ClarificationRecord] = Field(default_factory=list, description="List of clarification records.")
