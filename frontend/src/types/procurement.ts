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
