/**
 * Canonical Procurement Workspace TypeScript Data Models.
 * 
 * Maps directly to backend Pydantic schemas in backend/app/models/procurement.py
 * and backend/app/models/tender.py.
 */

export type ProcurementStatus = 'IMPORTED' | 'PROCESSING' | 'READY' | 'FAILED' | string;

export type DocumentType =
  | 'TENDER_SPECIFICATION'
  | 'GST_CERTIFICATE'
  | 'OEM_AUTHORIZATION'
  | 'TURNOVER_CERTIFICATE'
  | 'TECHNICAL_BID'
  | 'FINANCIAL_BOQ'
  | 'OTHER'
  | string;

export interface DocumentMetadata {
  id: string;
  procurement_id: string;
  tender_id?: string | null;
  bid_submission_id?: string | null;
  filename: string;
  document_type?: DocumentType | null;
  mime_type?: string;
  file_size?: number | null;
  storage_path?: string | null;
  processing_status?: string;
  created_at?: string;
  updated_at?: string;
}

export interface BidderSummary {
  id: string;
  legal_name: string;
  gstin?: string | null;
  pan?: string | null;
  email?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface SubmissionSummary {
  id: string;
  tender_id: string;
  bidder_id: string;
  external_submission_reference?: string | null;
  submitted_at?: string | null;
  status: string;
  bidder?: BidderSummary | null;
  documents: DocumentMetadata[];
  document_count: number;
  created_at?: string;
  updated_at?: string;
}

export interface TenderSummary {
  id: string;
  procurement_id: string;
  tender_reference: string;
  title: string;
  description?: string | null;
  estimated_value?: number | null;
  category?: string | null;
  status: string;
  requirement_count: number;
  document_count: number;
  bidder_count: number;
  documents?: DocumentMetadata[];
  submissions?: SubmissionSummary[];
  requirements?: TenderRequirement[];
  created_at?: string;
  updated_at?: string;
}

export interface TenderWorkspaceDetail extends TenderSummary {
  procurement_title?: string | null;
  procurement_external_reference?: string | null;
  source_system?: string | null;
}

export interface ProcurementSummaryItem {
  id: string;
  procurement_id?: string;
  external_reference: string;
  title: string;
  organization: string;
  source_system: string;
  status: ProcurementStatus;
  tender_count: number;
  bidder_count: number;
  document_count: number;
  created_at?: string;
  updated_at?: string;
}

export interface ProcurementListResponse {
  total: number;
  limit: number;
  offset: number;
  procurements: ProcurementSummaryItem[];
}

export interface ProcurementDetail {
  id: string;
  external_reference: string;
  title: string;
  organization: string;
  source_system: string;
  status: ProcurementStatus;
  tenders: TenderSummary[];
  documents: DocumentMetadata[];
  created_at?: string;
  updated_at?: string;
}

export interface StructuredCondition {
  metric?: string | null;
  field_name?: string | null;
  operator?: string | null;
  threshold_value?: number | string | (string | number)[] | null;
  unit?: string | null;
  currency?: string | null;
  period_years?: number | null;
  period_description?: string | null;
  is_quantifiable?: boolean;
}

export interface SourceProvenance {
  page_number?: number | null;
  clause_number?: string | null;
  section_title?: string | null;
  verbatim_quote?: string | null;
}

export interface AmbiguitySpec {
  is_ambiguous: boolean;
  ambiguity_type?: string | null;
  ambiguity_reason?: string | null;
}

export interface EvidenceSpec {
  document_type?: string | null;
  description: string;
  mandatory?: boolean;
  issuing_authority?: string | null;
}

export interface TenderRequirement {
  id?: string | null;
  tender_id?: string | null;
  requirement_id: string;
  title?: string | null;
  category: string;
  description: string;
  mandatory: boolean;
  evidence_required?: string[];
  is_ambiguous?: boolean;
  ambiguity_reason?: string | null;
  raw_statement?: string | null;
  structured_condition?: StructuredCondition | null;
  source_provenance?: SourceProvenance | null;
  ambiguity?: AmbiguitySpec | null;
  evidence_specs?: EvidenceSpec[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TenderEvaluationContract {
  tender_id: string;
  tender_reference?: string | null;
  tender_title?: string | null;
  requirements_count: number;
  deterministic_count: number;
  external_verification_count: number;
  document_presence_count: number;
  semantic_count: number;
  human_review_count: number;
  ambiguous_count: number;
}

// ---------------------------------------------------------------------------
// Canonical Evaluation & Review Data Models
// ---------------------------------------------------------------------------

export type ComplianceState =
  | 'PASS'
  | 'FAIL'
  | 'REVIEW'
  | 'UNVERIFIED'
  | 'NOT_APPLICABLE'
  // Legacy aliases
  | 'VERIFIED'
  | 'NON_COMPLIANT'
  | 'REVIEW_REQUIRED'
  | string;

export type EvaluationMethod =
  | 'DETERMINISTIC'
  | 'CONTRADICTION_RECONCILIATION'
  | 'DOCUMENT_PRESENCE'
  | 'EXTERNAL_VERIFICATION'
  | 'SEMANTIC_LLM'
  | 'HUMAN_REVIEW'
  | 'APPLICABILITY_EXEMPTION'
  | string;

export type RiskLevel = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | string;

export type ContradictionType =
  | 'NUMERIC_CONFLICT'
  | 'DATE_CONFLICT'
  | 'IDENTITY_CONFLICT'
  | 'STATUS_CONFLICT'
  | 'ATTRIBUTE_CONFLICT'
  | 'CLAIM_UNSUPPORTED'
  | 'EVIDENCE_DISAGREEMENT'
  | 'INCOMPATIBLE_UNITS'
  | string;

export type RelationshipClassification =
  | 'CONSISTENT'
  | 'SUPPORTS'
  | 'CONTRADICTS'
  | 'UNSUPPORTED'
  | 'INSUFFICIENT_DATA'
  | 'REVIEW_REQUIRED'
  | string;

export type ProcessingStage =
  | 'TENDER_INTELLIGENCE'
  | 'DOCUMENT_INTELLIGENCE'
  | 'EVIDENCE_EXTRACTION'
  | 'COMPLIANCE_EVALUATION'
  | string;

export interface ProcessingStageResult {
  stage: ProcessingStage;
  success: boolean;
  error_code?: string | null;
  error_message?: string | null;
  execution_time_ms?: number;
  metadata?: Record<string, any>;
}

export interface ProcurementProcessingStatusResponse {
  procurement_id: string;
  status: ProcurementStatus;
  current_stage?: ProcessingStage | null;
  completed_stages: ProcessingStage[];
  failed_stage?: ProcessingStage | null;
  stage_results: ProcessingStageResult[];
  retry_count: number;
  last_error_code?: string | null;
  last_error_message?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface StartProcessingResponse {
  procurement_id: string;
  status: ProcurementStatus;
  message: string;
  already_completed?: boolean;
  already_in_progress?: boolean;
}

export interface ProvenanceRecord {
  document_id?: string | null;
  document_name?: string | null;
  page_number?: number | null;
  sheet_name?: string | null;
  row_number?: number | null;
  cell_reference?: string | null;
  section_context?: string | null;
  source_type?: string | null;
  quote?: string | null;
  extraction_confidence?: number | null;
  raw_value?: any;
  normalized_value?: any;
  unit?: string | null;
  claim_id?: string | null;
  evidence_id?: string | null;
}

export interface SideBySideComparison {
  left: ProvenanceRecord;
  right: ProvenanceRecord;
  comparison_type: ContradictionType;
  relationship: RelationshipClassification;
  discrepancy_description: string;
  delta_value?: any;
}

export interface ContradictionFinding {
  finding_id: string;
  bidder_id?: string | null;
  bidder_name?: string | null;
  submission_id?: string | null;
  requirement_id: string;
  contradiction_type: ContradictionType;
  severity?: string;
  relationship_status: RelationshipClassification;
  explanation: string;
  side_by_side?: SideBySideComparison | null;
  claim_references?: string[];
  evidence_references?: string[];
  provenance_items?: ProvenanceRecord[];
  detected_at?: string | null;
}

export interface RequirementEvaluationResult {
  requirement_id: string;
  state: ComplianceState;
  risk_level: RiskLevel;
  evaluation_method: EvaluationMethod;
  reason: string;
  expected_condition?: Record<string, any> | null;
  observed_values?: any[];
  supporting_evidence?: any[];
  conflicting_evidence?: any[];
  review_required: boolean;
  provenance?: ProvenanceRecord[];
  contradiction_findings?: ContradictionFinding[];
  evaluator_metadata?: Record<string, any> | null;
  confidence?: number | null;
  // Optional requirement metadata if joined
  title?: string | null;
  category?: string | null;
  mandatory?: boolean;
  description?: string | null;
  is_ambiguous?: boolean;
  ambiguity_reason?: string | null;
}

export interface SubmissionEvaluationResult {
  tender_id: string;
  bidder_name?: string | null;
  evaluation_timestamp?: string | null;
  requirement_results: RequirementEvaluationResult[];
  machine_review_summary: Record<string, number>;
  review_required: boolean;
  review_required_count: number;
  unresolved_contradiction_count: number;
  unverified_count: number;
  deterministic_checks?: any;
  compliance_findings?: any[];
}

