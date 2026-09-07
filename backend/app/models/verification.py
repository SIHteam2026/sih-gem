"""Canonical Verification Engine Models (SIH26100).

Defines standard contracts, schemas, enumerations, and diagnostic models
for the 7-layer canonical verification engine in OPAL.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

try:
    from app.models.evaluation import ComplianceState
    from app.models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
    from app.models.procurement import Document
    from app.models.tender_contract import RequirementEvaluationContract
except ImportError:
    try:
        from app.models.evaluation import ComplianceState
        from app.models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
        from app.models.procurement import Document
        from app.models.tender_contract import RequirementEvaluationContract
    except ImportError:
        from models.evaluation import ComplianceState
        from models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
        from models.procurement import Document
        from models.tender_contract import RequirementEvaluationContract


class VerificationLayer(str, Enum):
    """Explicit named verification layers in the canonical conceptual stack."""
    INGESTION_AND_DOCUMENT_INTEGRITY = "INGESTION_AND_DOCUMENT_INTEGRITY"
    ADMINISTRATIVE_AND_IDENTITY = "ADMINISTRATIVE_AND_IDENTITY"
    CORPORATE_EXISTENCE_AND_RISK = "CORPORATE_EXISTENCE_AND_RISK"
    ANTI_COLLUSION_AND_RELATEDNESS = "ANTI_COLLUSION_AND_RELATEDNESS"
    ADVERSARIAL_TECHNICAL = "ADVERSARIAL_TECHNICAL"
    PAST_PERFORMANCE_AND_CAPACITY = "PAST_PERFORMANCE_AND_CAPACITY"
    FINANCIAL_AND_COMMERCIAL = "FINANCIAL_AND_COMMERCIAL"

    # Numeric compatibility aliases
    LAYER_1 = "INGESTION_AND_DOCUMENT_INTEGRITY"
    LAYER_2 = "ADMINISTRATIVE_AND_IDENTITY"
    LAYER_3 = "CORPORATE_EXISTENCE_AND_RISK"
    LAYER_4 = "ANTI_COLLUSION_AND_RELATEDNESS"
    LAYER_5 = "ADVERSARIAL_TECHNICAL"
    LAYER_6 = "PAST_PERFORMANCE_AND_CAPACITY"
    LAYER_7 = "FINANCIAL_AND_COMMERCIAL"


class FindingSeverity(str, Enum):
    """Severity / attention priority for verification findings.
    
    Decoupled from compliance status (e.g. an UNVERIFIED finding can be HIGH severity,
    while a PASS finding is INFO).
    """
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IdentityVerificationStatus(str, Enum):
    """Standardized statuses for identity and registration verification."""
    FORMAT_VALID = "FORMAT_VALID"
    EXTERNALLY_VERIFIED = "EXTERNALLY_VERIFIED"
    INVALID = "INVALID"
    UNVERIFIED = "UNVERIFIED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class VerificationFinding(BaseModel):
    """Standard structured finding returned by any verification layer module."""
    verifier: str = Field(..., description="Unique verifier module identifier.")
    verification_layer: VerificationLayer = Field(..., description="Canonical named verification layer.")
    requirement_id: Optional[str] = Field(default=None, description="Tender requirement ID if finding is requirement-linked.")
    bidder_id: Optional[str] = Field(default=None, description="Bidder identifier if finding is bidder-specific.")
    submission_id: Optional[str] = Field(default=None, description="Bid submission identifier if applicable.")
    document_id: Optional[str] = Field(default=None, description="Document identifier if finding is document-specific.")
    status: ComplianceState = Field(..., description="Compliance outcome state (PASS, FAIL, REVIEW, UNVERIFIED, NOT_APPLICABLE).")
    severity: FindingSeverity = Field(default=FindingSeverity.INFO, description="Finding attention severity.")
    claim: Optional[Any] = Field(default=None, description="The claimed assertion or parameter evaluated.")
    observation: Optional[Any] = Field(default=None, description="The observed evidence fact or metric.")
    reason: str = Field(..., description="Clear human-auditable reason explaining the finding.")
    evidence: List[ProvenanceRecord] = Field(default_factory=list, description="Traceable provenance records supporting this finding.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score (1.0 for deterministic rules).")
    machine_readable_flags: List[str] = Field(default_factory=list, description="Diagnostic and rule trigger tags.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of finding generation.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional verifier-specific diagnostic attributes.")


class VerificationContext(BaseModel):
    """Execution context provided to verification layer modules."""
    procurement_id: Optional[str] = Field(default=None, description="Procurement workspace ID.")
    tender_id: Optional[str] = Field(default=None, description="Tender reference or ID.")
    tender_metadata: Dict[str, Any] = Field(default_factory=dict, description="Tender metadata (title, category, estimated_value, etc.).")
    requirements: List[RequirementEvaluationContract] = Field(default_factory=list, description="Canonical tender requirement contracts.")
    bidders: List[Dict[str, Any]] = Field(default_factory=list, description="List of bidder profiles in the procurement case.")
    submissions: List[Dict[str, Any]] = Field(default_factory=list, description="List of bid submissions in the procurement case.")
    documents: List[Document] = Field(default_factory=list, description="All registered documents for the case.")
    claims: List[BidderClaim] = Field(default_factory=list, description="Extracted bidder claims across submissions.")
    observations: List[EvidenceObservation] = Field(default_factory=list, description="Extracted evidence observations across documents.")
    provenance_records: List[ProvenanceRecord] = Field(default_factory=list, description="Extracted provenance records.")
    external_verifications: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="External verification payload cache.")
    previous_findings: List[VerificationFinding] = Field(default_factory=list, description="Findings from previously executed layers.")
    extra_context: Dict[str, Any] = Field(default_factory=dict, description="Custom contextual parameters.")


class VerificationEngineReport(BaseModel):
    """Aggregate execution report of the Canonical Verification Engine."""
    procurement_id: Optional[str] = Field(default=None, description="Procurement case UUID.")
    tender_id: Optional[str] = Field(default=None, description="Tender identifier.")
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Execution timestamp.")
    total_findings: int = Field(default=0, description="Total findings produced across all layers.")
    findings_by_layer: Dict[str, List[VerificationFinding]] = Field(default_factory=dict, description="Findings grouped by named verification layer.")
    findings_by_bidder: Dict[str, List[VerificationFinding]] = Field(default_factory=dict, description="Findings grouped by bidder ID.")
    findings_by_requirement: Dict[str, List[VerificationFinding]] = Field(default_factory=dict, description="Findings grouped by requirement ID.")
    collusion_findings: List[VerificationFinding] = Field(default_factory=list, description="Case-level collusion / relatedness findings.")
    system_errors: List[VerificationFinding] = Field(default_factory=list, description="Execution errors recorded for fault isolation.")
    summary_by_state: Dict[str, int] = Field(default_factory=dict, description="Finding count by ComplianceState.")
    summary_by_severity: Dict[str, int] = Field(default_factory=dict, description="Finding count by FindingSeverity.")
    review_required: bool = Field(default=False, description="True if any REVIEW or CRITICAL/HIGH risk finding requires officer review.")
