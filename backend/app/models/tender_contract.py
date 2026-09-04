"""Tender Requirement Evaluation Contract Models.

Defines the downstream semantic evaluation contract for Tender Intelligence output.
Provides typed, unambiguous metadata for:
- Person 3: Document/evidence matching
- Person 4: Deterministic compliance rule execution & contradiction detection
- Person 5: Officer review interface & explainability traces
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

try:
    from backend.app.models.tender import (
        AmbiguitySpec,
        AmbiguityType,
        ApplicabilitySpec,
        EvidenceSpec,
        RequirementCategory,
        SourceProvenance,
        StructuredCondition,
        TenderRequirement,
    )
except ImportError:
    try:
        from app.models.tender import (
            AmbiguitySpec,
            AmbiguityType,
            ApplicabilitySpec,
            EvidenceSpec,
            RequirementCategory,
            SourceProvenance,
            StructuredCondition,
            TenderRequirement,
        )
    except ImportError:
        from models.tender import (
            AmbiguitySpec,
            AmbiguityType,
            ApplicabilitySpec,
            EvidenceSpec,
            RequirementCategory,
            SourceProvenance,
            StructuredCondition,
            TenderRequirement,
        )


class EvaluationMode(str, Enum):
    """Primary mode of compliance evaluation for a tender requirement."""
    DETERMINISTIC = "DETERMINISTIC"                  # Exact arithmetic/threshold comparison (e.g. turnover >= 5Cr)
    DOCUMENT_PRESENCE = "DOCUMENT_PRESENCE"          # Mandatory document certificate attachment check
    EXTERNAL_VERIFICATION = "EXTERNAL_VERIFICATION"  # Authoritative external registry validation (GSTIN, PAN, Debarment)
    SEMANTIC = "SEMANTIC"                            # Semantic content matching (e.g. OEM MAF authorization scope)
    HUMAN_REVIEW = "HUMAN_REVIEW"                    # Subjective, vague, or ambiguous clause requiring officer discretion


class CanonicalEvaluationField(str, Enum):
    """Standardized field identifiers for downstream automated compliance evaluation."""
    AVERAGE_ANNUAL_TURNOVER = "average_annual_turnover"
    LOCAL_CONTENT_PERCENTAGE = "local_content_percentage"
    WARRANTY_MONTHS = "warranty_months"
    SIMILAR_CONTRACT_COUNT = "similar_contract_count"
    GST_STATUS = "gst_status"
    PAN_VALIDITY = "pan_validity"
    OEM_AUTHORIZATION = "oem_authorization"
    DEBARMENT_STATUS = "debarment_status"
    TECHNICAL_SPECIFICATION = "technical_specification"
    GENERAL_EXPERIENCE = "general_experience"
    EMD_SECURITY_DEPOSIT = "emd_security_deposit"
    DELIVERY_TIMELINE_DAYS = "delivery_timeline_days"
    COMMERCIAL_PRICE = "commercial_price"
    OTHER = "other"


class ApplicabilityContract(BaseModel):
    """Downstream contract for requirement applicability and statutory exemptions."""
    applies_to_all: bool = Field(default=True, description="True if requirement applies universally to all bidders.")
    exemption_possible: bool = Field(default=False, description="True if legal exemptions (MSE/Startup/Consortium) exist.")
    exemption_type: Optional[str] = Field(default=None, description="Type of statutory exemption (e.g., 'MSE_STARTUP', 'OEM_DIRECT').")
    exemption_basis: Optional[str] = Field(default=None, description="Statutory rule or clause basis for exemption.")
    applicability_notes: Optional[str] = Field(default=None, description="Detailed instructions regarding applicability.")
    msme_exemption: bool = Field(default=False, description="Whether MSME bidders registered under Udyam are exempt.")
    startup_exemption: bool = Field(default=False, description="Whether DPIIT-recognized Startups are exempt.")


class EvidenceContract(BaseModel):
    """Downstream contract detailing expected documentary evidence."""
    document_type: Optional[str] = Field(default=None, description="Standardized document category code.")
    document_description: str = Field(..., description="Factual description of proof document required.")
    mandatory: bool = Field(default=True, description="Whether submission of this evidence is strictly mandatory.")
    issuing_authority: Optional[str] = Field(default=None, description="Expected issuing authority (e.g. 'Practicing Chartered Accountant', 'OEM').")
    expected_attributes: List[str] = Field(default_factory=list, description="Key attributes to look for in the document (e.g., 'UDIN', 'Turnover Value', 'GSTIN').")
    validity_requirement: Optional[str] = Field(default=None, description="Validity or date constraint (e.g. 'Within last 3 financial years').")


class ProvenanceContract(BaseModel):
    """Downstream contract detailing source document location."""
    document_id: Optional[str] = Field(default=None, description="UUID or filename of the source tender document.")
    page_number: Optional[int] = Field(default=None, description="1-indexed page number in the tender PDF.")
    clause_number: Optional[str] = Field(default=None, description="Clause reference number (e.g., 'Clause 2.1').")
    section_title: Optional[str] = Field(default=None, description="Section heading in the RFP.")
    verbatim_quote: Optional[str] = Field(default=None, description="Exact snippet extracted verbatim from the tender text.")


class AmbiguityContract(BaseModel):
    """Downstream contract detailing ambiguity status, classification, and recommended human review questions."""
    is_ambiguous: bool = Field(default=False, description="True if clause contains vague terms, missing thresholds, or contradictory timelines.")
    ambiguity_type: AmbiguityType = Field(default=AmbiguityType.NONE, description="Classification of ambiguity.")
    ambiguity_reason: Optional[str] = Field(default=None, description="Detailed explanation of what is missing or ambiguous.")
    affected_field: Optional[str] = Field(default=None, description="The specific parameter or condition affected by ambiguity.")
    suggested_review_question: Optional[str] = Field(default=None, description="Suggested clarification question for procurement officer.")


class RequirementEvaluationContract(BaseModel):
    """Canonical, downstream-safe evaluation contract for an individual tender requirement.
    
    Provides everything Person 3 (Document Matching), Person 4 (Deterministic Engine),
    and Person 5 (Review UI) need to process compliance without parsing raw text.
    """
    requirement_id: str = Field(..., description="Stable requirement identifier (e.g., 'REQ-001').")
    tender_id: Optional[str] = Field(default=None, description="Canonical tender UUID or reference string.")
    category: RequirementCategory = Field(..., description="Requirement domain category.")
    title: str = Field(..., description="Human-readable title of the requirement.")
    description: str = Field(..., description="Factual description of the requirement clause.")
    mandatory: bool = Field(default=True, description="Whether failure to meet this requirement leads to rejection.")
    
    # Evaluation routing
    evaluation_mode: EvaluationMode = Field(..., description="Primary evaluation mode for downstream execution routing.")
    secondary_evaluation_modes: List[EvaluationMode] = Field(
        default_factory=list,
        description="Secondary evaluation modes (e.g., DOCUMENT_PRESENCE alongside DETERMINISTIC).",
    )
    
    # Deterministic condition fields
    evaluation_field: Optional[str] = Field(default=None, description="Canonical standardized field name (e.g. 'average_annual_turnover').")
    operator: Optional[str] = Field(default=None, description="Comparison operator ('>=', '<=', '==', 'IN', 'EXISTS').")
    threshold_value: Optional[Any] = Field(default=None, description="Standardized numeric or categorical threshold.")
    threshold_unit: Optional[str] = Field(default=None, description="Unit of measurement ('INR', 'PERCENT', 'COUNT', 'MONTHS').")
    allowed_values: Optional[List[Any]] = Field(default=None, description="Set of allowed categorical values if applicable.")
    time_period_years: Optional[float] = Field(default=None, description="Evaluation timeframe in years (e.g. 3.0, 5.0).")
    time_period_description: Optional[str] = Field(default=None, description="Verbatim timeframe description from tender.")
    is_quantifiable: bool = Field(default=True, description="Whether requirement is objectively measurable.")
    
    # Rich contracts
    applicability: ApplicabilityContract = Field(default_factory=ApplicabilityContract, description="Entity applicability & exemption rules.")
    evidence_contracts: List[EvidenceContract] = Field(default_factory=list, description="Expected proof documents and attributes.")
    evidence_required: List[str] = Field(default_factory=list, description="Legacy list of evidence strings.")
    provenance: ProvenanceContract = Field(default_factory=ProvenanceContract, description="Source page and clause citations.")
    ambiguity: AmbiguityContract = Field(default_factory=AmbiguityContract, description="Ambiguity radar metadata.")
    
    # Officer and audit instructions
    review_instructions: Optional[str] = Field(default=None, description="Specific instructions for human review if flagged.")
    raw_requirement: Optional[Any] = Field(default=None, description="Reference to the underlying TenderRequirement.")


class TenderEvaluationContract(BaseModel):
    """Complete evaluation contract package for an entire tender notice / RFP."""
    tender_id: str = Field(..., description="Canonical tender UUID or reference ID.")
    tender_reference: Optional[str] = Field(default=None, description="Official tender reference number or GeM bid number.")
    tender_title: Optional[str] = Field(default=None, description="Official title of the tender.")
    requirements_count: int = Field(default=0, description="Total extracted requirements.")
    deterministic_count: int = Field(default=0, description="Count of requirements evaluated via deterministic rules.")
    external_verification_count: int = Field(default=0, description="Count of requirements requiring external API verification.")
    document_presence_count: int = Field(default=0, description="Count of requirements checked via document presence.")
    semantic_count: int = Field(default=0, description="Count of requirements requiring semantic LLM matching.")
    human_review_count: int = Field(default=0, description="Count of requirements flagged for human officer review.")
    ambiguous_count: int = Field(default=0, description="Count of requirements with detected ambiguity.")
    requirements: List[RequirementEvaluationContract] = Field(default_factory=list, description="Ordered list of requirement contracts.")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of contract generation.")
