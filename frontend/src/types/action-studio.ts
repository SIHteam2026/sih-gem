/**
 * Action Studio Domain Types and DTOs.
 *
 * Defines document types, statuses, evidence references, drafts, and entry readiness.
 */

export type ActionDocumentType =
  | 'NOTE_FOR_FILE'
  | 'EVALUATION_COMMITTEE_REPORT'
  | 'LETTER_OF_AWARD'
  | 'REJECTION_LETTER'
  | 'REGRET_LETTER';

export type ActionDocumentStatus =
  | 'DRAFT'
  | 'EDITED'
  | 'READY_FOR_APPROVAL'
  | 'APPROVED';

export interface EvidenceReference {
  requirement_id?: string;
  finding_id?: string;
  evaluation_id?: string;
  document_id?: string;
  document_name?: string;
  page_number?: number;
  quote?: string;
  provenance_summary?: string;
}

export interface ActionStudioDocument {
  id: string;
  procurement_id: string;
  document_type: ActionDocumentType;
  title: string;
  status: ActionDocumentStatus;
  created_at: string;
  updated_at: string;
  created_by: string;
  decision_authority: string;
  source_evaluation_references: Record<string, any>;
  content: string;
  evidence_references: EvidenceReference[];
  is_ai_generated: boolean;
  is_draft: boolean;
  version: number;
  target_bidder_id?: string;
  target_bidder_name?: string;
  approved_by?: string;
  approved_at?: string;
}

export interface ActionStudioDocumentSummary {
  id: string;
  procurement_id: string;
  document_type: ActionDocumentType;
  title: string;
  status: ActionDocumentStatus;
  version: number;
  created_by: string;
  target_bidder_id?: string;
  target_bidder_name?: string;
  created_at: string;
  updated_at: string;
  is_draft: boolean;
  approved_by?: string;
  approved_at?: string;
}

export interface ActionStudioDocumentVersion {
  id: string;
  document_id: string;
  version: number;
  content: string;
  status: ActionDocumentStatus;
  updated_by: string;
  updated_at: string;
  change_summary?: string;
}

export interface ActionStudioListResponse {
  procurement_id: string;
  total: number;
  documents: ActionStudioDocumentSummary[];
}

export interface ActionStudioReadinessResponse {
  procurement_id: string;
  is_unlocked: boolean;
  status: string;
  blocker_reason?: string;
  technical_freeze_completed: boolean;
  financial_evaluation_completed: boolean;
  has_l1_bidder: boolean;
}

export interface ActionStudioAuditEvent {
  id: string;
  event_type: string;
  procurement_id: string;
  document_id: string;
  document_type: ActionDocumentType;
  actor: string;
  timestamp: string;
  version: number;
  details: Record<string, any>;
}

export interface CreateDraftRequest {
  document_type: ActionDocumentType;
  target_bidder_id?: string;
  title?: string;
  created_by?: string;
}

export interface UpdateDraftRequest {
  content: string;
  updated_by?: string;
  change_summary?: string;
  mark_ready_for_approval?: boolean;
}

export interface ApproveDraftRequest {
  officer_actor: string;
  notes?: string;
}
