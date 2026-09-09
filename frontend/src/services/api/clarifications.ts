/**
 * API service layer for the Clarification / Shortfall & Representation workflow.
 *
 * All officer actions go through canonical backend endpoints.
 * The frontend never directly mutates PASS / FAIL / REVIEW / UNVERIFIED.
 * Only canonical re-evaluation through the backend can change a finding.
 */

import type {
  ClarificationRecord,
  ClarificationCreatePayload,
  ClarificationDraftRequest,
  ClarificationDraftResponse,
  ClarificationResponsePayload,
  ClarificationResolutionPayload,
  ClarificationDocument,
  AuditHistoryEntry,
} from '@/types/clarification';

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

// ---------------------------------------------------------------------------
// Raw → frontend mapping helpers
// ---------------------------------------------------------------------------

type RawRecord = Record<string, unknown>;

function mapDocument(d: RawRecord): ClarificationDocument {
  return {
    document_id: d.document_id as string | undefined,
    filename: (d.filename as string) || (d.name as string) || 'Document',
    storage_path: d.storage_path as string | undefined,
    document_type: d.document_type as string | undefined,
    created_at: d.created_at as string | undefined,
  };
}

function mapAuditEntry(e: RawRecord): AuditHistoryEntry {
  return {
    event: (e.event as string) || (e.action as string) || 'EVENT',
    actor: e.actor as string | undefined,
    timestamp: (e.timestamp as string) || (e.created_at as string) || new Date().toISOString(),
    detail: (e.detail as string) || (e.notes as string) || undefined,
  };
}

function mapRecord(raw: RawRecord): ClarificationRecord {
  const rawDocs = ((raw.response_documents ?? []) as RawRecord[]).map(mapDocument);
  const rawAudit = ((raw.audit_history ?? []) as RawRecord[]).map(mapAuditEntry);

  return {
    id: (raw.id as string) || '',
    procurementId: (raw.procurement_id as string) || '',
    tenderId: (raw.tender_id as string) || '',
    bidderId: (raw.bidder_id as string) || '',
    submissionId: (raw.submission_id as string) || '',
    requirementId: (raw.requirement_id as string) || '',
    originatingFindingId: raw.originating_finding_id as string | undefined,
    question: (raw.question as string) || '',
    status: (raw.status as ClarificationRecord['status']) || 'OPEN',
    createdAt: (raw.created_at as string) || new Date().toISOString(),
    createdBy: raw.created_by as string | undefined,
    dueAt: raw.due_at as string | undefined,
    responseText: raw.response_text as string | undefined,
    responseDocuments: rawDocs,
    respondedAt: raw.responded_at as string | undefined,
    respondedBy: raw.responded_by as string | undefined,
    reEvaluationStatus: raw.re_evaluation_status as string | undefined,
    resultingFinding: raw.resulting_finding as Record<string, unknown> | undefined,
    auditHistory: rawAudit,
  };
}

async function handleError(resp: Response, context: string): Promise<never> {
  let detail = '';
  try {
    const body = await resp.json();
    detail = body.detail || body.message || '';
  } catch (_) {}
  throw new Error(`${context}: ${resp.status}${detail ? ` — ${detail}` : ''}`);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Create a formal clarification request for a specific finding.
 * This persists through the canonical backend; no frontend-only state is created.
 */
export async function createClarification(
  procurementId: string,
  payload: ClarificationCreatePayload
): Promise<ClarificationRecord> {
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/clarifications`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        submission_id: payload.submissionId,
        requirement_id: payload.requirementId,
        originating_finding_id: payload.originatingFindingId,
        question: payload.question,
        due_at: payload.dueAt,
        created_by: 'OFFICER',
      }),
    }
  );
  if (!resp.ok) await handleError(resp, 'Create clarification');
  return mapRecord(await resp.json());
}

/**
 * Request an AI-assisted draft clarification notice.
 * The result is always editable — the officer remains the author.
 */
export async function getDraftClarification(
  procurementId: string,
  payload: ClarificationDraftRequest
): Promise<ClarificationDraftResponse> {
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/clarifications/draft`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        procurement_id: payload.procurementId,
        submission_id: payload.submissionId,
        requirement_id: payload.requirementId,
        originating_finding_id: payload.originatingFindingId,
        custom_instruction: payload.customInstruction,
      }),
    }
  );
  if (!resp.ok) await handleError(resp, 'Get clarification draft');
  const raw = await resp.json() as RawRecord;
  return {
    subject: (raw.subject as string) || '',
    recipientBidder: (raw.recipient_bidder as string) || '',
    tenderReference: (raw.tender_reference as string) || '',
    requirementId: (raw.requirement_id as string) || '',
    requirementTitle: (raw.requirement_title as string) || '',
    observedShortfall: (raw.observed_shortfall as string) || '',
    requestedClarification: (raw.requested_clarification as string) || '',
    suggestedDeadlineDays: raw.suggested_deadline_days as number | undefined,
    supportingEvidenceReferences: (raw.supporting_evidence_references as string[]) || [],
    isDraft: true,
    decisionAuthority: (raw.decision_authority as string) || 'HUMAN_PROCUREMENT_OFFICER',
  };
}

/**
 * Retrieve a single clarification record by ID.
 */
export async function getClarification(
  procurementId: string,
  clarificationId: string
): Promise<ClarificationRecord> {
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/clarifications/${encodeURIComponent(clarificationId)}`
  );
  if (!resp.ok) await handleError(resp, 'Get clarification');
  return mapRecord(await resp.json());
}

/**
 * List clarifications for a procurement, optionally filtered by submission.
 */
export async function listClarifications(
  procurementId: string,
  submissionId?: string
): Promise<ClarificationRecord[]> {
  const params = new URLSearchParams();
  if (submissionId) params.set('submission_id', submissionId);
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/clarifications?${params}`
  );
  if (!resp.ok) await handleError(resp, 'List clarifications');
  const raw = await resp.json() as RawRecord;
  const list = ((raw.clarifications ?? raw) as RawRecord[]);
  return Array.isArray(list) ? list.map(mapRecord) : [];
}

/**
 * Submit a bidder response to an open clarification.
 */
export async function respondToClarification(
  procurementId: string,
  clarificationId: string,
  payload: ClarificationResponsePayload
): Promise<ClarificationRecord> {
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/clarifications/${encodeURIComponent(clarificationId)}/respond`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        response_text: payload.responseText,
        documents: [],
        responded_by: payload.respondedBy || 'BIDDER',
      }),
    }
  );
  if (!resp.ok) await handleError(resp, 'Submit clarification response');
  return mapRecord(await resp.json());
}

/**
 * Trigger canonical targeted re-evaluation of the requirement.
 * This is the ONLY path that can change the underlying technical finding.
 * Officer action → backend evaluator → new canonical finding → persisted state.
 */
export async function reEvaluateClarification(
  procurementId: string,
  clarificationId: string
): Promise<ClarificationRecord> {
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/clarifications/${encodeURIComponent(clarificationId)}/re-evaluate`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }
  );
  if (!resp.ok) await handleError(resp, 'Re-evaluate clarification');
  return mapRecord(await resp.json());
}

/**
 * Explicitly resolve, reject, or require further clarification.
 * Maps to ClarificationResolutionRequest.
 */
export async function resolveClarification(
  procurementId: string,
  clarificationId: string,
  payload: ClarificationResolutionPayload
): Promise<ClarificationRecord> {
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/clarifications/${encodeURIComponent(clarificationId)}/resolve`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resolution_status: payload.resolutionStatus,
        resolution_notes: payload.resolutionNotes,
        officer_id: 'OFFICER',
      }),
    }
  );
  if (!resp.ok) await handleError(resp, 'Resolve clarification');
  return mapRecord(await resp.json());
}
