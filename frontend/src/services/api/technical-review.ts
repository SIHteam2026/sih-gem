import type { TechnicalReviewResponse, OfficerObservationPayload } from '@/types/technical-review';

/**
 * Fetch the technical review data for a procurement.
 * The backend returns the final results for all six layers.
 */
export async function fetchTechnicalReview(procurementId: string): Promise<TechnicalReviewResponse> {
  const resp = await fetch(`/api/technical-review/${encodeURIComponent(procurementId)}`);
  if (!resp.ok) {
    throw new Error(`Failed to load technical review: ${resp.status}`);
  }
  return (await resp.json()) as TechnicalReviewResponse;
}

/**
 * Persist an officer observation for a specific layer.
 * This function is an adapter – the concrete backend endpoint may differ.
 * If the endpoint is not implemented, the promise will reject, signalling a missing backend dependency.
 */
export async function saveOfficerObservation(payload: OfficerObservationPayload): Promise<void> {
  // NOTE: The exact backend contract is expected to be /api/technical-review/observation.
  // We deliberately do not implement a stub; we forward the request and let the backend respond.
  // The UI MUST handle this gracefully if the backend is not yet fully implemented, 
  // treating it as a real canonical persistence attempt.
  const resp = await fetch('/api/technical-review/observation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`saveOfficerObservation failed: ${resp.status} ${err}`);
  }
}
