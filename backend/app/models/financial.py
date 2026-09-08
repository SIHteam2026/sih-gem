"""Financial and Commercial Bid Evaluation Models.

Defines Pydantic models for arithmetic auditing, line-item summation validation,
abnormally low bid (ALB) detection, Cover 2 gatekeeping, BOQ parity, and L1 ranking.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class TechnicalEligibilityState(str, Enum):
    """Evaluation state of bidder at the Cover 2 Gate."""
    TECHNICALLY_ELIGIBLE = "TECHNICALLY_ELIGIBLE"
    TECHNICAL_REVIEW_REQUIRED = "TECHNICAL_REVIEW_REQUIRED"
    TECHNICALLY_FAILED = "TECHNICALLY_FAILED"


class CommercialEvaluationStatus(str, Enum):
    """Commercial evaluation status for a submission."""
    EVALUATED = "EVALUATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    DISQUALIFIED = "DISQUALIFIED"
    NOT_EVALUATED = "NOT_EVALUATED"


class Cover2State(str, Enum):
    """Lifecycle state of Cover 2 Commercial Opening."""
    LOCKED = "LOCKED"
    UNLOCKED = "UNLOCKED"
    EVALUATED = "EVALUATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class BOQItemEvaluation(BaseModel):
    """Evaluation result for an individual BOQ line item."""
    item_number: Union[int, str] = Field(..., description="Line item index or code.")
    description: str = Field(..., description="Item description or work component.")
    quantity: float = Field(..., description="Quoted quantity.")
    unit: str = Field(default="units", description="Unit of measurement (e.g., units, sets, lot).")
    unit_rate: float = Field(..., description="Base unit rate in specified currency.")
    total_price: float = Field(..., description="Calculated or quoted item total.")
    taxes: Optional[float] = Field(default=0.0, description="Applicable tax or GST amount.")
    is_arithmetic_valid: bool = Field(default=True, description="Whether quantity * unit_rate equals total_price.")
    discrepancy_note: Optional[str] = Field(default=None, description="Explanation of any arithmetic or unit mismatch.")
    provenance: Optional[Dict[str, Any]] = Field(default=None, description="Page number, snippet, and source document reference.")


class CommercialFinding(BaseModel):
    """Commercial compliance finding or discrepancy."""
    finding_type: str = Field(..., description="Category: MISSING_ITEM, EXTRA_ITEM, QUANTITY_MISMATCH, UNIT_MISMATCH, LINE_TOTAL_MISMATCH, SUBTOTAL_MISMATCH, GRAND_TOTAL_MISMATCH, NORMALIZATION_FAILURE, ARITHMETIC_ERROR.")
    severity: str = Field(default="WARNING", description="Severity: CRITICAL, WARNING, INFO.")
    message: str = Field(..., description="Audit explanation of the finding.")
    expected: Optional[Any] = Field(default=None, description="Expected value or structure from RFP.")
    observed: Optional[Any] = Field(default=None, description="Observed value from bidder submission.")
    source_provenance: Optional[Dict[str, Any]] = Field(default=None, description="Provenance link to source document.")


class FinancialAnomalySignal(BaseModel):
    """Comparative pricing anomaly signal across peer bids."""
    signal_type: str = Field(..., description="Signal code: UNUSUALLY_LOW_BID, UNUSUALLY_HIGH_BID, BID_CLUSTERING, BENCHMARK_VARIANCE, PRICING_MULTIPLIER_DETECTED, IDENTICAL_PRICING_PATTERN, HIGH_VECTOR_CORRELATION, SHARED_ROUNDING_ANOMALY, ENGINEER_ESTIMATE_UNAVAILABLE, RAW_MATERIAL_FLOOR_BREACH, RAW_MATERIAL_BASELINE_UNAVAILABLE, PEER_GROUP_VARIANCE.")
    severity: str = Field(default="INFO", description="Severity level: INFO, WARNING, CRITICAL.")
    description: str = Field(..., description="Human-readable audit explanation.")
    metric_name: str = Field(..., description="Statistical metric calculated.")
    metric_value: float = Field(..., description="Calculated value.")
    threshold: Optional[float] = Field(default=None, description="Reference threshold triggering the signal.")
    requires_officer_review: bool = Field(default=True, description="Indicates flag requires officer determination.")
    bidders_involved: List[str] = Field(default_factory=list, description="Names or IDs of bidders involved in the anomaly.")
    details: Dict[str, Any] = Field(default_factory=dict, description="Detailed forensic metrics, line item indices, multipliers, correlations.")
    source_documents: List[str] = Field(default_factory=list, description="Source documents or BOQs referenced.")
    calculation_basis: Optional[str] = Field(default=None, description="Detailed explanation of the calculation/formula used.")
    decision_authority: str = Field(default="HUMAN_PROCUREMENT_OFFICER", description="Authority responsible for final determination.")
    generated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc), description="Signal timestamp.")


class BidderFinancialEvaluation(BaseModel):
    """Canonical commercial evaluation record for a single bidder."""
    procurement_id: str = Field(..., description="Procurement UUID.")
    tender_id: str = Field(..., description="Tender UUID.")
    bidder_id: str = Field(..., description="Bidder UUID.")
    bidder_name: str = Field(..., description="Bidder corporate name.")
    submission_id: str = Field(..., description="Submission UUID.")
    technical_eligibility_status: TechnicalEligibilityState = Field(..., description="Gatekeeper status.")
    is_cover2_unlocked: bool = Field(..., description="Whether Cover 2 was unlocked for this bidder.")
    exclusion_reason: Optional[str] = Field(default=None, description="Reason if excluded from Cover 2.")
    currency: str = Field(default="INR", description="Currency code.")
    quoted_amount: Optional[float] = Field(default=None, description="Raw quoted amount from bid.")
    subtotal: Optional[float] = Field(default=None, description="Normalized base subtotal.")
    tax_amount: Optional[float] = Field(default=0.0, description="Normalized tax/GST amount.")
    freight_amount: Optional[float] = Field(default=0.0, description="Normalized freight and insurance.")
    discount_amount: Optional[float] = Field(default=0.0, description="Normalized discount applied.")
    evaluated_amount: Optional[float] = Field(default=None, description="Total comparable evaluated amount.")
    commercial_status: CommercialEvaluationStatus = Field(default=CommercialEvaluationStatus.NOT_EVALUATED, description="Commercial evaluation outcome.")
    rank: Optional[int] = Field(default=None, description="Commercial rank (1 = L1).")
    is_l1: bool = Field(default=False, description="True if bidder is lowest evaluated compliant bidder.")
    line_items: List[BOQItemEvaluation] = Field(default_factory=list, description="Evaluated BOQ line items.")
    commercial_findings: List[CommercialFinding] = Field(default_factory=list, description="Identified commercial issues.")
    anomalies: List[FinancialAnomalySignal] = Field(default_factory=list, description="Bidder-specific anomaly signals.")
    provenance: List[Dict[str, Any]] = Field(default_factory=list, description="Supporting document citations.")
    evaluated_at: Optional[datetime] = Field(default=None, description="Evaluation timestamp.")


class ProcurementFinancialEvaluationResponse(BaseModel):
    """Canonical API response for procurement-level Cover 2 financial evaluation."""
    procurement_id: str = Field(..., description="Procurement workspace UUID.")
    tender_id: str = Field(..., description="Tender UUID.")
    cover2_status: Cover2State = Field(..., description="Cover 2 evaluation state.")
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Evaluation timestamp.")
    evaluator_version: str = Field(default="opal-cover2-v1.0", description="Evaluator version.")
    currency: str = Field(default="INR", description="Currency code.")
    estimated_tender_value: Optional[float] = Field(default=None, description="Official estimated tender value.")
    total_bidders: int = Field(default=0, description="Total participating bidders.")
    eligible_bidders_count: int = Field(default=0, description="Bidders qualified through Cover 2 Gate.")
    excluded_bidders_count: int = Field(default=0, description="Bidders excluded at Cover 2 Gate.")
    l1_bidder_id: Optional[str] = Field(default=None, description="UUID of L1 bidder.")
    l1_bidder_name: Optional[str] = Field(default=None, description="Name of L1 bidder.")
    l1_evaluated_amount: Optional[float] = Field(default=None, description="Lowest evaluated bid amount.")
    bidder_evaluations: List[BidderFinancialEvaluation] = Field(default_factory=list, description="Individual bidder commercial evaluations.")
    comparative_signals: List[FinancialAnomalySignal] = Field(default_factory=list, description="Cross-bidder comparative pricing signals.")
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list, description="Audit log of Cover 2 execution.")


class FinancialEvaluationResult(BaseModel):
    """Model representing commercial bid financial evaluation and arithmetic audit results (backward compatibility)."""
    total_bid_value: float = Field(
        ...,
        description="The calculated or verified total commercial bid value in currency units.",
    )
    math_errors_found: bool = Field(
        ...,
        description="Indicates whether calculation mismatches, unit price errors, or summation issues were detected.",
    )
    abnormally_low_bid: bool = Field(
        ...,
        description="Indicates whether the bid is flagged as abnormally low compared to benchmark/estimate.",
    )
    audit_notes: List[str] = Field(
        default_factory=list,
        description="Detailed notes explaining calculation mismatches, incorrect summations, or missing tax components.",
    )
    # Optional extensions for modern pipeline compatibility
    currency: str = Field(default="INR", description="Currency code.")
    subtotal: Optional[float] = Field(default=None, description="Base subtotal before taxes/freight.")
    tax_amount: Optional[float] = Field(default=0.0, description="Taxes.")
    freight_amount: Optional[float] = Field(default=0.0, description="Freight.")
    discount_amount: Optional[float] = Field(default=0.0, description="Discounts.")
    rank: Optional[int] = Field(default=None, description="Commercial rank.")
    is_l1: bool = Field(default=False, description="Is L1 flag.")
    line_items: List[BOQItemEvaluation] = Field(default_factory=list, description="BOQ line items.")


class Cover2RunRequest(BaseModel):
    """Request payload for initiating Cover 2 Financial Opening & Evaluation."""
    force: bool = Field(default=False, description="Force re-execution even if already evaluated.")
    actor: Optional[str] = Field(default="PROCUREMENT_OFFICER", description="Initiator of the financial opening.")
    notes: Optional[str] = Field(default=None, description="Operational notes or rationale.")

