import type { TechnicalReviewResponse, TechnicalLayer, CheckResult, OfficerObservationPayload } from '@/types/technical-review';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

const LAYER_TITLES: Record<string, string> = {
  'INGESTION_AND_DOCUMENT_INTEGRITY': '01 — DOCUMENT & EVIDENCE INTEGRITY',
  'ADMINISTRATIVE_AND_IDENTITY': '02 — ADMINISTRATIVE & IDENTITY',
  'CORPORATE_EXISTENCE_AND_RISK': '03 — CORPORATE EXISTENCE & RISK',
  'ANTI_COLLUSION_AND_RELATEDNESS': '04 — ANTI-COLLUSION FORENSICS',
  'ADVERSARIAL_TECHNICAL': '05 — ADVERSARIAL TECHNICAL REVIEW',
  'PAST_PERFORMANCE_AND_CAPACITY': '06 — PAST PERFORMANCE & CAPACITY',
};

const CANONICAL_LAYERS = [
  'INGESTION_AND_DOCUMENT_INTEGRITY',
  'ADMINISTRATIVE_AND_IDENTITY',
  'CORPORATE_EXISTENCE_AND_RISK',
  'ANTI_COLLUSION_AND_RELATEDNESS',
  'ADVERSARIAL_TECHNICAL',
  'PAST_PERFORMANCE_AND_CAPACITY'
];

/**
 * Fetch the technical review data using the canonical backend endpoint.
 * Maps the backend schema to the frontend presentation schema.
 */
export async function fetchTechnicalReview(procurementId: string): Promise<TechnicalReviewResponse> {
  const resp = await fetch(`${API_BASE_URL}/api/procurements/${encodeURIComponent(procurementId)}/technical-review`);
  if (!resp.ok) {
    throw new Error(`Failed to load technical review: ${resp.status}`);
  }
  
  const rawData = await resp.json();
  
  // Normalize key_findings and requirements into layer checks
  const findings = rawData.key_findings || [];
  const layers: TechnicalLayer[] = CANONICAL_LAYERS.map(layerKey => {
    const layerFindings = findings.filter((f: Record<string, unknown>) => f.layer === layerKey);
    const checks: CheckResult[] = layerFindings.map((f: Record<string, unknown>) => ({
      id: (f.finding_id as string) || Math.random().toString(),
      description: (f.title as string) || 'Requirement Check',
      status: mapSeverityToStatus(f.severity as string),
      synthesis: f.detail as string,
      evidenceRefs: f.evidence_pointer ? [{ documentId: f.evidence_pointer as string }] : undefined
    }));
    
    // We can also map requirements into the applicable layer if we have category logic.
    // For now, if there's no layer checks at all, we do NOT fabricate them, per instructions.

    return {
      key: layerKey,
      title: LAYER_TITLES[layerKey] || layerKey,
      checks
    };
  });

  return {
    procurementId: rawData.procurement_id || procurementId,
    layers,
    freezeReady: rawData.can_freeze || false,
    canOpenCover2: rawData.can_open_cover2 || false,
    rawBackendData: rawData
  };
}

function mapSeverityToStatus(severity: string): CheckResult['status'] {
  switch (severity?.toUpperCase()) {
    case 'FATAL':
    case 'CRITICAL':
      return 'FAIL';
    case 'WARNING':
      return 'REVIEW';
    case 'INFO':
      return 'PASS';
    default:
      return 'UNVERIFIED';
  }
}

/**
 * Adapter for persisting officer observation.
 * The endpoint `/api/procurements/{procurementId}/observations` is not yet available in the backend.
 * This adapter makes the call, handles the 404 cleanly, and rejects so the UI knows it's not persisted.
 */
export async function saveOfficerObservation(payload: OfficerObservationPayload): Promise<void> {
  const resp = await fetch(`${API_BASE_URL}/api/procurements/${encodeURIComponent(payload.procurementId)}/observations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ layer: payload.layerKey, observation: payload.observation }),
  });
  
  if (!resp.ok) {
    if (resp.status === 404) {
      throw new Error('NOT_IMPLEMENTED');
    }
    const err = await resp.text();
    throw new Error(`Persistence failed: ${resp.status} ${err}`);
  }
}
