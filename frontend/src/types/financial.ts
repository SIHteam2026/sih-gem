/**
 * Types for the Cover 2 and Financial Scrutiny workflow.
 * Maps to backend models.financial
 */

export type TechnicalEligibilityState =
  | 'TECHNICALLY_ELIGIBLE'
  | 'TECHNICAL_REVIEW_REQUIRED'
  | 'TECHNICALLY_FAILED';

export type CommercialEvaluationStatus =
  | 'EVALUATED'
  | 'REVIEW_REQUIRED'
  | 'DISQUALIFIED'
  | 'NOT_EVALUATED';

export type Cover2State =
  | 'LOCKED'
  | 'UNLOCKED'
  | 'EVALUATED'
  | 'REVIEW_REQUIRED';

export interface BOQItemEvaluation {
  item_number: string | number;
  description: string;
  quantity: number;
  unit: string;
  unit_rate: number;
  total_price: number;
  taxes?: number;
  is_arithmetic_valid: boolean;
  discrepancy_note?: string;
  provenance?: Record<string, unknown>;
}

export interface CommercialFinding {
  finding_type: string;
  severity: string;
  message: string;
  expected?: unknown;
  observed?: unknown;
  source_provenance?: Record<string, unknown>;
}

export interface FinancialAnomalySignal {
  signal_type: string;
  severity: string;
  description: string;
  metric_name: string;
  metric_value: number;
  threshold?: number;
  requires_officer_review: boolean;
  bidders_involved: string[];
  details: Record<string, unknown>;
  source_documents: string[];
  calculation_basis?: string;
  decision_authority: string;
  generated_at?: string;
}

export interface BidderFinancialEvaluation {
  procurement_id: string;
  tender_id: string;
  bidder_id: string;
  bidder_name: string;
  submission_id: string;
  technical_eligibility_status: TechnicalEligibilityState;
  is_cover2_unlocked: boolean;
  exclusion_reason?: string;
  currency: string;
  quoted_amount?: number;
  subtotal?: number;
  tax_amount?: number;
  freight_amount?: number;
  discount_amount?: number;
  evaluated_amount?: number;
  commercial_status: CommercialEvaluationStatus;
  rank?: number;
  is_l1: boolean;
  line_items: BOQItemEvaluation[];
  commercial_findings: CommercialFinding[];
  anomalies: FinancialAnomalySignal[];
  provenance: Record<string, unknown>[];
  evaluated_at?: string;
}

export interface ProcurementFinancialEvaluationResponse {
  procurement_id: string;
  tender_id: string;
  cover2_status: Cover2State;
  evaluated_at: string;
  evaluator_version: string;
  currency: string;
  estimated_tender_value?: number;
  total_bidders: number;
  eligible_bidders_count: number;
  excluded_bidders_count: number;
  l1_bidder_id?: string;
  l1_bidder_name?: string;
  l1_evaluated_amount?: number;
  bidder_evaluations: BidderFinancialEvaluation[];
  comparative_signals: FinancialAnomalySignal[];
  audit_trail: Record<string, unknown>[];
}
