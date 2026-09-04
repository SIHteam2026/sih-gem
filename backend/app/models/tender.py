"""Tender Intelligence Engine Pydantic Models.

Defines the core data models and enums for parsing, categorizing, and analyzing
tender requirements, structured conditions, applicability, expected evidence,
source provenance, and ambiguity radar.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class RequirementCategory(str, Enum):
    """Enumeration of tender requirement categories."""
    # Core statutory & identity
    GST = "GST"
    GST_AND_TAX = "GST_AND_TAX"
    PAN_IDENTITY = "PAN_IDENTITY"
    
    # Financial
    FINANCIAL_TURNOVER = "FINANCIAL_TURNOVER"
    
    # Technical & Experience
    EXPERIENCE = "EXPERIENCE"
    PAST_EXPERIENCE = "PAST_EXPERIENCE"
    OEM_AUTH = "OEM_AUTH"
    OEM_AUTHORIZATION = "OEM_AUTHORIZATION"
    LOCAL_CONTENT = "LOCAL_CONTENT"
    LOCAL_CONTENT_MII = "LOCAL_CONTENT_MII"
    TECHNICAL_SPECIFICATION = "TECHNICAL_SPECIFICATION"
    
    # Governance, Legal & SLA
    LEGAL_AND_DEBARMENT = "LEGAL_AND_DEBARMENT"
    EMD_AND_PBG = "EMD_AND_PBG"
    DELIVERY_AND_SLA = "DELIVERY_AND_SLA"
    COMMERCIAL = "COMMERCIAL"
    OTHER = "OTHER"


class AmbiguityType(str, Enum):
    """Enumeration of requirement ambiguity classifications."""
    NONE = "NONE"
    VAGUE_TERMINOLOGY = "VAGUE_TERMINOLOGY"
    THRESHOLD_MISSING = "THRESHOLD_MISSING"
    TIMEFRAME_MISSING = "TIMEFRAME_MISSING"
    SCOPE_UNCLEAR = "SCOPE_UNCLEAR"
    METRIC_UNCLEAR = "METRIC_UNCLEAR"
    EVIDENCE_UNCLEAR = "EVIDENCE_UNCLEAR"
    APPLICABILITY_UNCLEAR = "APPLICABILITY_UNCLEAR"
    DATE_DEFINITION_UNCLEAR = "DATE_DEFINITION_UNCLEAR"
    SUBJECTIVE_EVALUATION = "SUBJECTIVE_EVALUATION"
    OTHER = "OTHER"


class ApplicabilitySpec(BaseModel):
    """Model specifying which entity the requirement applies to and any explicit exemptions."""
    applies_to_all: bool = Field(
        default=True,
        description="True if requirement applies to all bidders universally.",
    )
    target_entity: str = Field(
        default="ALL_BIDDERS",
        description="Target entity (e.g., 'ALL_BIDDERS', 'OEM', 'AUTHORIZED_REPRESENTATIVE', 'STARTUP_MSME', 'CONSORTIUM_MEMBER').",
    )
    msme_exemption_applicable: bool = Field(
        default=False,
        description="True if tender explicitly exempts MSE/MSME bidders from this requirement.",
    )
    startup_exemption_applicable: bool = Field(
        default=False,
        description="True if tender explicitly exempts DPIIT recognized startups from this requirement.",
    )
    exemption_notes: Optional[str] = Field(
        default=None,
        description="Specific statutory exemption clauses or notes cited in the tender.",
    )
    notes: Optional[str] = Field(
        default=None,
        description="General applicability notes.",
    )


class StructuredCondition(BaseModel):
    """Model representing an executable, mathematically auditable parameter condition."""
    metric: Optional[str] = Field(
        default=None,
        description="Standardized metric name (e.g. 'AVERAGE_ANNUAL_TURNOVER', 'SIMILAR_CONTRACT_COUNT', 'LOCAL_CONTENT_PERCENTAGE', 'WARRANTY_MONTHS').",
    )
    field_name: Optional[str] = Field(
        default=None,
        description="Standardized field identifier alias.",
    )
    operator: Optional[str] = Field(
        default=None,
        description="Comparison operator: '>=', '<=', '==', '>', '<', 'IN', 'NOT_IN'.",
    )
    threshold_value: Optional[Union[float, int, str, List[Union[str, float, int]]]] = Field(
        default=None,
        description="Numeric or categorical threshold value (e.g., 50000000.0, 50, 'ACTIVE'). Null if not explicitly specified.",
    )
    unit: Optional[str] = Field(
        default=None,
        description="Unit of measurement (e.g., 'INR', 'PERCENT', 'COUNT', 'MONTHS', 'YEARS').",
    )
    currency: Optional[str] = Field(
        default=None,
        description="Currency code if monetary (e.g. 'INR', 'USD').",
    )
    period_years: Optional[float] = Field(
        default=None,
        description="Evaluation timeframe in years (e.g., 3.0, 5.0). Null if not stated.",
    )
    period_description: Optional[str] = Field(
        default=None,
        description="Verbatim description of the timeframe (e.g. 'last three completed financial years').",
    )
    is_quantifiable: bool = Field(
        default=True,
        description="Whether this condition contains objective numeric/boolean criteria versus subjective evaluation.",
    )


class EvidenceSpec(BaseModel):
    """Structured evidence specification defining what document/proof must be submitted."""
    document_type: Optional[str] = Field(
        default=None,
        description="Standardized document type code (e.g. 'CA_CERTIFICATE', 'GST_CERTIFICATE', 'OEM_AUTHORIZATION', 'COMPLETION_CERTIFICATE').",
    )
    description: str = Field(
        ...,
        description="Factual description of the required proof document as stated in the tender.",
    )
    mandatory: bool = Field(
        default=True,
        description="Whether submission of this specific evidence item is strictly mandatory.",
    )
    issuing_authority: Optional[str] = Field(
        default=None,
        description="Expected issuing authority (e.g., 'Practicing Chartered Accountant', 'OEM / Manufacturer', 'Client Nodal Officer').",
    )


class SourceProvenance(BaseModel):
    """Traceable provenance detailing where in the tender document the requirement originated."""
    page_number: Optional[int] = Field(
        default=None,
        description="1-indexed page number in the tender PDF where this requirement is located.",
    )
    clause_number: Optional[str] = Field(
        default=None,
        description="Official clause number or reference (e.g. 'Clause 4.2(b)', 'Section 3.1').",
    )
    section_title: Optional[str] = Field(
        default=None,
        description="Section header or title under which this clause falls.",
    )
    verbatim_quote: Optional[str] = Field(
        default=None,
        description="Exact snippet or sentence extracted verbatim from the tender text.",
    )


class AmbiguitySpec(BaseModel):
    """Ambiguity radar assessment for vague, subjective, or underspecified requirements."""
    is_ambiguous: bool = Field(
        default=False,
        description="True if the requirement lacks measurable metrics, thresholds, or clear definitions.",
    )
    ambiguity_type: Optional[AmbiguityType] = Field(
        default=None,
        description="Classification of the ambiguity (e.g. THRESHOLD_MISSING, SCOPE_UNCLEAR).",
    )
    ambiguity_reason: Optional[str] = Field(
        default=None,
        description="Explanation of what specific parameters or definitions are missing.",
    )


class TenderRequirement(BaseModel):
    """Model representing an individual requirement extracted from a tender.
    
    Preserves full backward compatibility with legacy top-level fields while
    providing rich additive structured condition, applicability, evidence,
    provenance, ambiguity, and persistence models.
    """
    # Persistence identifiers (Optional for in-flight extraction, populated on DB persistence)
    id: Optional[str] = Field(default=None, description="Unique UUID of the persisted requirement record.")
    tender_id: Optional[str] = Field(default=None, description="Associated canonical tender ID or reference.")

    # Legacy top-level fields (Maintained for full backward compatibility)
    requirement_id: str = Field(..., description="Unique identifier for the requirement.")
    category: RequirementCategory = Field(..., description="Category of the requirement.")
    description: str = Field(..., description="Detailed description of the requirement.")
    mandatory: bool = Field(default=True, description="Indicates if the requirement is mandatory.")
    evidence_required: List[str] = Field(
        default_factory=list,
        description="List of required evidence documents or proofs.",
    )
    is_ambiguous: bool = Field(
        default=False,
        description="Flag indicating if the requirement contains vague or underspecified criteria.",
    )
    ambiguity_reason: Optional[str] = Field(
        default=None,
        description="Explanation of missing metrics or ambiguity in the clause.",
    )

    # Additive structured fields
    title: Optional[str] = Field(
        default=None,
        description="Short human-readable title for the requirement (e.g., 'Annual Financial Turnover').",
    )
    raw_statement: Optional[str] = Field(
        default=None,
        description="Exact verbatim or reconstructed requirement statement from the tender.",
    )
    applicability: Optional[ApplicabilitySpec] = Field(
        default_factory=ApplicabilitySpec,
        description="Target entity and statutory exemption criteria.",
    )
    structured_condition: Optional[StructuredCondition] = Field(
        default=None,
        description="Executable parameter condition with metric, operator, threshold, unit, and period.",
    )
    evidence_specs: List[EvidenceSpec] = Field(
        default_factory=list,
        description="Detailed structured evidence specifications with document types and issuing authorities.",
    )
    source_provenance: Optional[SourceProvenance] = Field(
        default=None,
        description="Document page, clause, section, and verbatim quote provenance.",
    )
    ambiguity: Optional[AmbiguitySpec] = Field(
        default=None,
        description="Structured ambiguity classification and rationale.",
    )
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp.")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp.")


class TenderAnalysisResult(BaseModel):
    """Model representing the full analysis result for a tender document."""
    tender_id: str = Field(..., description="Unique identifier for the tender.")
    tender_title: Optional[str] = Field(default=None, description="Official title or scope of the tender.")
    issuing_authority: Optional[str] = Field(default=None, description="Issuing department, ministry, or PSU.")
    estimated_value: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Estimated tender budget / value object (e.g. {'amount': 15000000.0, 'currency': 'INR'}).",
    )
    page_count: Optional[int] = Field(default=None, description="Total number of pages in the tender document.")
    requirements: List[TenderRequirement] = Field(
        default_factory=list,
        description="List of extracted, categorized, and structured tender requirements.",
    )

