"""Master Orchestrator Models.

Defines Pydantic models for end-to-end multi-agent evaluation orchestration,
aggregating deterministic checks, OCR parsing, RAG legal citations,
forensic trust scores, compliance findings, executive reports,
and automated contract or shortfall generation.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

from .contract import LetterOfAward
from .document import DocumentClassificationResult
from .entity import EntityMatchResult
from .evaluation import ComplianceFinding, RequirementEvaluationResult
from .evidence import BidderClaim, EvidenceObservation
from .tender_contract import RequirementEvaluationContract
from .financial import FinancialEvaluationResult
from .fraud import FraudAnalysisResult
from .report import FinalAuditReport
from .shortfall import ShortfallRequest
from .tender import TenderAnalysisResult
from .translation import TranslationResult


class RawDocumentItem(BaseModel):
    """Model representing an individual input document payload or reference."""
    filename: str = Field(..., description="Name or identifier of the document file.")
    text: Optional[str] = Field(None, description="Extracted raw text content of the document.")
    url: Optional[str] = Field(None, description="Direct URL to fetch the document from cloud storage.")
    document_type: Optional[str] = Field(None, description="Declared or assumed document category.")


class MasterEvaluationRequest(BaseModel):
    """Request model for full master evaluation orchestration."""
    tender_id: Optional[str] = Field(default=None, description="Unique tender reference identifier (e.g., 'GEM/2026/B/88219').")
    bidder_name: Optional[str] = Field(default=None, description="Legal company name of the bidder under evaluation.")
    document_urls: Optional[List[str]] = Field(
        default=None,
        description="List of downloadable document URLs stored in cloud storage.",
    )
    raw_documents: Optional[List[RawDocumentItem]] = Field(
        default=None,
        description="List of raw document items containing filenames and text content.",
    )
    tender_text: Optional[str] = Field(
        default=None,
        description="Raw or parsed text of the tender notice / RFP document.",
    )
    estimated_tender_value: Optional[float] = Field(
        default=None,
        description="Official benchmark or estimated budget value of the tender in INR.",
    )
    boq_data: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Structured bidder Bill of Quantities (BOQ) line items for financial evaluation.",
    )
    generate_contract_if_accepted: bool = Field(
        default=True,
        description="Whether to automatically generate a Letter of Award (LoA) if the final recommendation is ACCEPT.",
    )
    generate_shortfall_if_review: bool = Field(
        default=True,
        description="Whether to automatically draft a formal 48-hour shortfall notice if requirements need clarification.",
    )
    # Canonical requirement-level inputs.  These are additive so legacy callers
    # remain valid while canonical procurement flows avoid raw-text aggregation.
    bidder_id: Optional[str] = None
    submission_id: Optional[str] = None
    requirement_contracts: List[RequirementEvaluationContract] = Field(default_factory=list)
    bidder_claims: List[BidderClaim] = Field(default_factory=list)
    evidence_observations: List[EvidenceObservation] = Field(default_factory=list)
    external_verifications: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    evaluation_context: Dict[str, Any] = Field(default_factory=dict)


class DeterministicCheckSummary(BaseModel):
    """Aggregated summary of deterministic rule checks."""
    gst_verified: bool = Field(default=False, description="Whether GSTIN status is active and verified.")
    gstin: Optional[str] = Field(default=None, description="Verified GSTIN identifier.")
    taxpayer_name: Optional[str] = Field(default=None, description="Official taxpayer legal name from GST portal.")
    entity_match_score: float = Field(default=0.0, description="Normalized entity name match score (0-100).")
    entity_verified: bool = Field(default=False, description="Whether corporate identity matched with high confidence.")
    details: Dict[str, Any] = Field(default_factory=dict, description="Detailed attributes from deterministic checks.")


class LegalCitation(BaseModel):
    """Model representing a RAG-retrieved legal or procurement rule citation."""
    rule_source: str = Field(..., description="Statutory authority or rule manual (e.g., 'GFR 2017 Rule 144(xi)', 'GeM GTC Cl 4(a)', 'CVC Circular 02/05/2022').")
    clause_title: str = Field(..., description="Title or header of the legal clause.")
    relevance_summary: str = Field(..., description="Summary of how this rule applies to the evaluation findings.")
    mandatory_status: bool = Field(default=True, description="Whether compliance with this statutory clause is mandatory.")


class MasterEvaluationResponse(BaseModel):
    """Complete aggregated response from the multi-agent procurement evaluation orchestrator."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tender_id: str = Field(..., description="Tender identifier.")
    bidder_name: str = Field(..., description="Bidder corporate name.")
    evaluation_timestamp: str = Field(..., description="ISO 8601 evaluation timestamp.")
    
    # 1. Deterministic Rule Checks
    deterministic_checks: DeterministicCheckSummary = Field(
        default_factory=DeterministicCheckSummary,
        description="Summary of deterministic GST, PAN, and fuzzy entity matching checks.",
    )
    
    # 2. OCR & Document Classification
    classified_documents: List[Union[DocumentClassificationResult, Dict[str, Any], Any]] = Field(
        default_factory=list,
        description="Classified document inventory across the bidder submission.",
    )
    
    # 3. Multilingual Translations
    translations: List[Union[TranslationResult, Dict[str, Any], Any]] = Field(
        default_factory=list,
        description="Results of regional language detections and English legal normalizations.",
    )
    
    # 4. RAG Legal & Statutory Citations
    legal_citations: List[Union[LegalCitation, Dict[str, Any], Any]] = Field(
        default_factory=list,
        description="RAG-retrieved public procurement statutory rules and legal citations.",
    )
    
    # 5. Forensic Fraud & Trust Scoring
    fraud_analysis: Optional[Union[FraudAnalysisResult, Dict[str, Any], Any]] = Field(
        default=None,
        description="Forensic fraud risk assessment, date cross-verification, and trust score.",
    )
    
    # 6. Commercial & Financial BOQ Audit
    financial_evaluation: Optional[Union[FinancialEvaluationResult, Dict[str, Any], Any]] = Field(
        default=None,
        description="Mathematical BOQ audit, unit rate check, and abnormally low bid analysis.",
    )
    
    # 7. Compliance Findings & Contradiction Analysis
    compliance_findings: List[Union[ComplianceFinding, Dict[str, Any], Any]] = Field(
        default_factory=list,
        description="Requirement-by-requirement contradiction and compliance analysis findings.",
    )
    requirement_results: List[Union[RequirementEvaluationResult, Dict[str, Any], Any]] = Field(
        default_factory=list,
        description="Canonical requirement-level machine evaluation results; never a procurement decision.",
    )
    machine_review_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Non-authoritative counts by requirement state for officer review.",
    )
    review_required: bool = Field(default=False)
    review_required_count: int = Field(default=0)
    unresolved_contradiction_count: int = Field(default=0)
    unverified_count: int = Field(default=0)
    
    # 8. Executive Decision & Final Report
    final_report: Optional[Union[FinalAuditReport, Dict[str, Any], Any]] = Field(
        default=None,
        description="Executive summary, itemized violations, and final procurement recommendation.",
    )
    
    # 9. Automated Contract Generation (Optional)
    letter_of_award: Optional[Union[LetterOfAward, Dict[str, Any], Any]] = Field(
        default=None,
        description="Drafted Letter of Award (LoA) generated if bid is ACCEPT.",
    )
    
    # 10. Automated Shortfall Notice (Optional)
    shortfall_notice: Optional[Union[ShortfallRequest, Dict[str, Any], Any]] = Field(
        default=None,
        description="Drafted 48-hour shortfall clarification notice generated if discrepancies or missing proofs exist.",
    )
