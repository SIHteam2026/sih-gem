/**
 * API service layer for the Cover 2 and Financial Scrutiny workflow.
 *
 * Exposes canonical backend endpoints for opening Cover 2 and running
 * commercial evaluation. Does not calculate compliance independently.
 */

import type {
  ProcurementFinancialEvaluationResponse,
} from '@/types/financial';

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
 * Open Cover 2 and explicitly transition the canonical lifecycle.
 */
export async function openCover2(
  procurementId: string
): Promise<ProcurementFinancialEvaluationResponse> {
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/cover2/open`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor: 'PROCUREMENT_OFFICER' }),
    }
  );
  if (!resp.ok) await handleError(resp, 'Open Cover 2');
  return await resp.json();
}

/**
 * Trigger the canonical commercial evaluation pipeline.
 */
export async function runFinancialEvaluation(
  procurementId: string,
  force: boolean = false
): Promise<ProcurementFinancialEvaluationResponse> {
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/financial-evaluation`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor: 'PROCUREMENT_OFFICER', force }),
    }
  );
  if (!resp.ok) await handleError(resp, 'Run financial evaluation');
  return await resp.json();
}

/**
 * Retrieve the current canonical financial evaluation representation.
 */
export async function getFinancialReview(
  procurementId: string
): Promise<ProcurementFinancialEvaluationResponse> {
  const resp = await fetch(
    `${API_BASE}/api/procurements/${encodeURIComponent(procurementId)}/financial-review`
  );
  if (!resp.ok) await handleError(resp, 'Get financial review');
  return await resp.json();
}
