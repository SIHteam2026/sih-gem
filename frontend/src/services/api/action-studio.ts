/**
 * API service layer for Action Studio governance workspace.
 *
 * Interacts with canonical Action Studio backend endpoints for readiness,
 * draft creation, editing, versioning, regeneration, human approval,
 * context fetching, and audit history.
 */

import type {
  ActionStudioDocument,
  ActionStudioDocumentVersion,
  ActionStudioListResponse,
  ActionStudioReadinessResponse,
  ActionStudioAuditEvent,
  CreateDraftRequest,
  UpdateDraftRequest,
  ApproveDraftRequest,
} from '@/types/action-studio';

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

async function handleError(resp: Response, context: string): Promise<never> {
  let detail = '';
  try {
    const body = await resp.json();
    detail = body.detail || body.message || '';
  } catch (_) {}
  throw new Error(`${context}: ${resp.status}${detail ? ` — ${detail}` : ''}`);
}

/**
 * Checks whether Action Studio is unlocked for a procurement workspace based on backend state.
 */
export async function checkActionStudioReadiness(
  procurementId: string
): Promise<ActionStudioReadinessResponse> {
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/action-studio/readiness`
  );
  if (!resp.ok) await handleError(resp, 'Check Action Studio readiness');
  return await resp.json();
}

/**
 * Retrieves complete canonical evidence context for Action Studio workspace.
 */
export async function getActionStudioContext(
  procurementId: string
): Promise<Record<string, any>> {
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/action-studio/context`
  );
  if (!resp.ok) await handleError(resp, 'Fetch Action Studio context');
  return await resp.json();
}

/**
 * Lists all Action Studio drafts for a procurement workspace.
 */
export async function listActionStudioDrafts(
  procurementId: string
): Promise<ActionStudioListResponse> {
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/action-studio`
  );
  if (!resp.ok) await handleError(resp, 'List Action Studio drafts');
  return await resp.json();
}

/**
 * Creates a new Action Studio document draft grounded in canonical evidence context.
 */
export async function createActionStudioDraft(
  procurementId: string,
  payload: CreateDraftRequest
): Promise<ActionStudioDocument> {
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/action-studio/drafts`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }
  );
  if (!resp.ok) await handleError(resp, 'Create Action Studio draft');
  return await resp.json();
}

/**
 * Retrieves a single Action Studio draft detail by ID.
 */
export async function getActionStudioDraftDetail(
  draftId: string
): Promise<ActionStudioDocument> {
  const resp = await fetch(
    `${API_BASE}/api/action-studio/drafts/${encodeURIComponent(draftId)}`
  );
  if (!resp.ok) await handleError(resp, 'Get Action Studio draft detail');
  return await resp.json();
}

/**
 * Updates Action Studio draft content (officer editing).
 */
export async function updateActionStudioDraft(
  draftId: string,
  payload: UpdateDraftRequest
): Promise<ActionStudioDocument> {
  const resp = await fetch(
    `${API_BASE}/api/action-studio/drafts/${encodeURIComponent(draftId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }
  );
  if (!resp.ok) await handleError(resp, 'Update Action Studio draft');
  return await resp.json();
}

/**
 * Regenerates an existing Action Studio draft from canonical evidence.
 */
export async function regenerateActionStudioDraft(
  draftId: string
): Promise<ActionStudioDocument> {
  const resp = await fetch(
    `${API_BASE}/api/action-studio/drafts/${encodeURIComponent(draftId)}/regenerate`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }
  );
  if (!resp.ok) await handleError(resp, 'Regenerate Action Studio draft');
  return await resp.json();
}

/**
 * Lists version history for a draft document.
 */
export async function listActionStudioVersions(
  draftId: string
): Promise<ActionStudioDocumentVersion[]> {
  const resp = await fetch(
    `${API_BASE}/api/action-studio/drafts/${encodeURIComponent(draftId)}/versions`
  );
  if (!resp.ok) await handleError(resp, 'List Action Studio draft versions');
  return await resp.json();
}

/**
 * Formally approves an Action Studio draft document under human officer authority.
 */
export async function approveActionStudioDraft(
  draftId: string,
  payload: ApproveDraftRequest
): Promise<ActionStudioDocument> {
  const resp = await fetch(
    `${API_BASE}/api/action-studio/drafts/${encodeURIComponent(draftId)}/approve`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }
  );
  if (!resp.ok) await handleError(resp, 'Approve Action Studio draft');
  return await resp.json();
}

/**
 * Lists audit trail events for a procurement workspace.
 */
export async function listActionStudioAuditEvents(
  procurementId: string
): Promise<ActionStudioAuditEvent[]> {
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/action-studio/audit`
  );
  if (!resp.ok) await handleError(resp, 'List Action Studio audit events');
  return await resp.json();
}
