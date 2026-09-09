/**
 * Frontend types for Technical Scrutiny / Technical Review.
 *
 * These map the backend's ProcurementTechnicalReviewResponse to
 * the officer-facing presentation layer. Compliance state (PASS / FAIL /
 * REVIEW / UNVERIFIED / NOT_APPLICABLE) is derived ONLY from backend data.
 * Presentation logic must never mutate these values.
 */

export type ComplianceStatus =
  | 'PASS'
  | 'FAIL'
  | 'REVIEW'
  | 'UNVERIFIED'
  | 'NOT_APPLICABLE';

export interface EvidenceRef {
  documentId: string;
  documentName?: string;
  page?: number;
  snippet?: string;
  sourceType?: string;
  retrievedAt?: string;
}

/**
 * A single verification check within a technical layer.
 * Requirement / Evidence / Finding / Status are the four canonical fields.
 */
export interface CheckResult {
  id: string;
  /** Short title for the check (e.g. "GST Registration Validity") */
  description: string;
  /** Canonical compliance status — never renamed or overridden by UI logic. */
  status: ComplianceStatus;
  /** What the tender/regulation requires */
  requirement?: string;
  /** What the bidder submitted or what was retrieved */
  evidence?: string;
  /** What the verification engine established */
  finding?: string;
  /** Bidder this finding belongs to (where applicable) */
  bidderName?: string;
  /** Severity from backend (INFO / WARNING / CRITICAL / FATAL) — informational only */
  severity?: string;
  /** Evidence provenance references */
  evidenceRefs?: EvidenceRef[];
  /** Source reference (tender clause / external ref) */
  sourceReference?: string;
  /**
   * Human-readable synthesis — derived deterministically from findings.
   * Must not conflict with the canonical status.
   */
  synthesis?: string;
}

export interface TechnicalLayer {
  /** Backend canonical key e.g. 'INGESTION_AND_DOCUMENT_INTEGRITY' */
  key: string;
  /** Display title e.g. '01 — DOCUMENT & EVIDENCE INTEGRITY' */
  title: string;
  checks: CheckResult[];
  /**
   * Deterministic synthesis for this layer — derived from existing findings.
   * Not a new compliance decision.
   */
  synthesis?: string;
}

export interface BidderSummary {
  bidderId: string;
  legalName: string;
  submissionId: string;
  complianceStatus: ComplianceStatus;
  passedCount: number;
  failedCount: number;
  reviewCount: number;
  findingsCount: number;
  hasOpenClarifications: boolean;
  freezeStatus: string;
}

export interface Cover2Readiness {
  isReady: boolean;
  blockers: string[];
  warnings: string[];
  eligibleBidderCount: number;
  eligibleBidders: string[];
  technicalFreezeEnforced: boolean;
  openClarificationsCount: number;
}

export interface ObservationRecord {
  observationId: string;
  procurementId: string;
  layer: string;
  actor: string;
  observation: string;
  createdAt: string;
}

export interface TechnicalReviewResponse {
  procurementId: string;
  externalReference: string;
  procurementTitle: string;
  organization?: string;
  status: string;
  totalBidders: number;
  qualifiedBidders: number;
  excludedBidders: number;
  reviewRequiredBidders: number;
  lastEvaluatedAt?: string;
  layers: TechnicalLayer[];
  bidders: BidderSummary[];
  unresolvedBlockers: string[];
  canFreeze: boolean;
  canOpenCover2: boolean;
  cover2Readiness: Cover2Readiness;
  observations: ObservationRecord[];
  decisionAuthority: string;
  /** Raw backend payload preserved for debugging — not used by UI logic */
  _raw?: unknown;
}

export interface OfficerObservationPayload {
  procurementId: string;
  layerKey: string;
  observation: string;
}

/** Entry in the persistent Decision Log */
export interface DecisionLogEntry {
  layerKey: string;
  layerTitle: string;
  observationText?: string;
  observationPersisted: boolean;
  /** ISO timestamp */
  recordedAt: string;
  findingsSummary: {
    pass: number;
    fail: number;
    review: number;
    unverified: number;
  };
}
