export interface CheckResult {
  id: string;
  description: string;
  status: 'PASS' | 'FAIL' | 'REVIEW' | 'UNVERIFIED' | 'NOT_APPLICABLE';
  evidenceRefs?: Array<{
    documentId: string;
    page?: number;
    snippet?: string;
  }>;
  synthesis?: string; // optional human‑readable summary for this check
}

export interface TechnicalLayer {
  key: string; // backend identifier, e.g. 'INGESTION_AND_DOCUMENT_INTEGRITY'
  title: string; // e.g. '01 — DOCUMENT & EVIDENCE INTEGRITY'
  checks: CheckResult[];
}

export interface TechnicalReviewResponse {
  procurementId: string;
  layers: TechnicalLayer[]; // exactly six canonical layers in order
  freezeReady?: boolean;
  canOpenCover2?: boolean;
  [key: string]: unknown;
}

export interface OfficerObservationPayload {
  procurementId: string;
  layerKey: string; // matches TechnicalLayer.key
  observation: string;
  // timestamp can be added by backend; we omit here
}
