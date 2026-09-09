/**
 * Frontend types for the Clarification / Shortfall & Representation lifecycle.
 * 
 * Maps the canonical backend ClarificationRecord and related models.
 * Officer actions trigger backend state transitions — the UI never
 * directly mutates PASS / FAIL / REVIEW / UNVERIFIED / NOT_APPLICABLE.
 */

export type ClarificationStatus =
  | 'OPEN'
  | 'RESPONDED'
  | 'UNDER_REVIEW'
  | 'RESOLVED'
  | 'REQUIRES_FURTHER_CLARIFICATION'
  | 'EXPIRED'
  | 'CANCELLED'
  | 'REJECTED';

export interface ClarificationDocument {
  document_id?: string;
  filename: string;
  storage_path?: string;
  document_type?: string;
  created_at?: string;
}

export interface AuditHistoryEntry {
  event: string;
  actor?: string;
  timestamp: string;
  detail?: string;
}

/**
 * Canonical clarification lifecycle record.
 * Maps backend ClarificationRecord.
 */
export interface ClarificationRecord {
  id: string;
  procurementId: string;
  tenderId: string;
  bidderId: string;
  submissionId: string;
  requirementId: string;
  originatingFindingId?: string;
  question: string;
  status: ClarificationStatus;
  createdAt: string;
  createdBy?: string;
  dueAt?: string;
  responseText?: string;
  responseDocuments: ClarificationDocument[];
  respondedAt?: string;
  respondedBy?: string;
  reEvaluationStatus?: string;
  /** The canonical re-evaluated finding result — only set after backend re-evaluation */
  resultingFinding?: Record<string, unknown>;
  auditHistory: AuditHistoryEntry[];
}

/**
 * Payload to create a clarification request through the canonical backend endpoint.
 */
export interface ClarificationCreatePayload {
  submissionId: string;
  requirementId: string;
  originatingFindingId?: string;
  question: string;
  dueAt?: string;
}

/**
 * Payload for the AI-assisted draft request.
 * The draft is editable by the officer before sending.
 */
export interface ClarificationDraftRequest {
  procurementId: string;
  submissionId: string;
  requirementId: string;
  originatingFindingId?: string;
  customInstruction?: string;
}

/**
 * AI-generated draft clarification notice for officer review and editing.
 * Not a decision — always marked is_draft = true.
 */
export interface ClarificationDraftResponse {
  subject: string;
  recipientBidder: string;
  tenderReference: string;
  requirementId: string;
  requirementTitle: string;
  observedShortfall: string;
  requestedClarification: string;
  suggestedDeadlineDays?: number;
  supportingEvidenceReferences: string[];
  isDraft: true;
  decisionAuthority: string;
}

/**
 * Payload for submitting a bidder response to an open clarification.
 */
export interface ClarificationResponsePayload {
  responseText: string;
  respondedBy?: string;
}

/**
 * Payload for explicitly resolving a clarification lifecycle.
 * Maps to ClarificationResolutionRequest.
 */
export interface ClarificationResolutionPayload {
  resolutionStatus: 'RESOLVED' | 'REQUIRES_FURTHER_CLARIFICATION' | 'REJECTED' | 'CANCELLED';
  resolutionNotes?: string;
}

/**
 * A clarification event recorded in the Decision Log.
 */
export interface ClarificationLogEvent {
  type:
    | 'CLARIFICATION_CREATED'
    | 'RESPONSE_RECEIVED'
    | 'RE_EVALUATION_REQUESTED'
    | 'RE_EVALUATION_COMPLETED'
    | 'CLARIFICATION_RESOLVED'
    | 'CLARIFICATION_REJECTED'
    | 'FURTHER_CLARIFICATION_REQUIRED';
  clarificationId: string;
  bidderId?: string;
  bidderName?: string;
  requirementId?: string;
  resultingStatus?: string;
  timestamp: string;
  notes?: string;
}
