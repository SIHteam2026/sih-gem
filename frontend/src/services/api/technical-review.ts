/**
 * API client for Technical Scrutiny / Technical Review endpoints.
 *
 * Compliance state is derived ONLY from backend data.
 * This client maps the backend schema to the frontend presentation schema
 * without altering PASS / FAIL / REVIEW / UNVERIFIED / NOT_APPLICABLE values.
 *
 * Sequential animation on the frontend is a presentation effect only.
 * The backend returns a completed batch result; no per-check backend calls occur.
 */

import type {
  TechnicalReviewResponse,
  TechnicalLayer,
  CheckResult,
  OfficerObservationPayload,
  BidderSummary,
  Cover2Readiness,
  ObservationRecord,
  ComplianceStatus,
} from '@/types/technical-review';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

/** Canonical display titles for the six technical layers. */
const LAYER_TITLES: Record<string, string> = {
  'INGESTION_AND_DOCUMENT_INTEGRITY':  '01 — Document & Evidence Integrity',
  'ADMINISTRATIVE_AND_IDENTITY':       '02 — Administrative & Identity',
  'CORPORATE_EXISTENCE_AND_RISK':      '03 — Corporate Existence & Risk',
  'ANTI_COLLUSION_AND_RELATEDNESS':    '04 — Anti-Collusion Forensics',
  'ADVERSARIAL_TECHNICAL':             '05 — Adversarial Technical Review',
  'PAST_PERFORMANCE_AND_CAPACITY':     '06 — Past Performance & Capacity',
};

/** The six canonical technical layer keys in display order. Layer 7 (FINANCIAL) is excluded. */
const CANONICAL_LAYERS = Object.keys(LAYER_TITLES);

// ---------------------------------------------------------------------------
// Severity → canonical ComplianceStatus mapping
// ---------------------------------------------------------------------------

/**
 * Maps backend severity to canonical frontend status.
 * The result is display-only context and must not alter the underlying finding.
 */
function severityToStatus(severity?: string): ComplianceStatus {
  switch ((severity ?? '').toUpperCase()) {
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

// ---------------------------------------------------------------------------
// Backend → frontend mapping helpers
// ---------------------------------------------------------------------------

type RawFinding = Record<string, unknown>;
type RawCheck = Record<string, unknown>;
type RawLayer = Record<string, unknown>;

function mapFindingToCheck(f: RawFinding, idx: number): CheckResult {
  const status = f.state
    ? (String(f.state) as ComplianceStatus)
    : severityToStatus(f.severity as string | undefined);

  const evidenceRefs = f.evidence_pointer
    ? [{ documentId: String(f.evidence_pointer), snippet: f.evidence_snippet as string | undefined }]
    : undefined;

  return {
    id: (f.finding_id as string) || (f.check_id as string) || `finding-${idx}`,
    description: (f.title as string) || (f.check_title as string) || 'Requirement Check',
    status,
    severity: f.severity as string | undefined,
    requirement: f.requirement_text as string | undefined,
    evidence: f.evidence_summary as string | undefined,
    finding: (f.detail as string) || (f.finding_detail as string) || undefined,
    bidderName: (f.bidder_name as string) || undefined,
    synthesis: (f.detail as string) || undefined,
    evidenceRefs,
    sourceReference: (f.source_reference as string) || undefined,
  };
}

function mapPresentationCheck(c: RawCheck, idx: number): CheckResult {
  const status = c.status
    ? (String(c.status) as ComplianceStatus)
    : severityToStatus(c.severity as string | undefined);

  const rawBidders = c.bidders as Record<string, string> | undefined;
  const firstBidderStatus = rawBidders ? Object.values(rawBidders)[0] : undefined;
  // If there's a clear bidder-level status, use it; otherwise keep layer check status
  const effectiveStatus = firstBidderStatus
    ? (firstBidderStatus as ComplianceStatus)
    : status;

  const evidenceRefs = (c.evidence_references as string[] | undefined)?.map((r) => ({
    documentId: r,
  }));

  return {
    id: (c.check_id as string) || `check-${idx}`,
    description: (c.title as string) || 'Check',
    status: effectiveStatus,
    severity: c.severity as string | undefined,
    requirement: c.requirement_text as string | undefined,
    evidence: c.evidence_summary as string | undefined,
    finding: c.explanation as string | undefined,
    synthesis: c.explanation as string | undefined,
    evidenceRefs: evidenceRefs?.length ? evidenceRefs : undefined,
    sourceReference: c.source_reference as string | undefined,
  };
}

/**
 * Build the six canonical layers from backend data.
 * Uses presentation_layers (richer, per-layer) as primary source.
 * Falls back to bucketing key_findings by layer.
 */
function buildLayers(rawData: Record<string, unknown>): TechnicalLayer[] {
  const rawPresentationLayers = (rawData.presentation_layers ?? []) as RawLayer[];
  const rawKeyFindings = (rawData.key_findings ?? []) as RawFinding[];

  // Build a lookup from presentation_layers
  const presentationByKey: Record<string, RawLayer> = {};
  for (const pl of rawPresentationLayers) {
    const key = (pl.layer_key as string) || (pl.key as string);
    if (key) presentationByKey[key] = pl;
  }

  return CANONICAL_LAYERS.map((layerKey) => {
    let checks: CheckResult[] = [];
    let synthesis: string | undefined;

    const pl = presentationByKey[layerKey];
    if (pl) {
      const rawChecks = (pl.checks ?? []) as RawCheck[];
      checks = rawChecks.map((c, i) => mapPresentationCheck(c, i));
      synthesis = pl.synthesis as string | undefined;
    }

    // Supplement or fall back with key_findings for this layer
    const layerFindings = rawKeyFindings.filter(
      (f) => (f.layer as string) === layerKey
    );
    if (layerFindings.length > 0 && checks.length === 0) {
      checks = layerFindings.map((f, i) => mapFindingToCheck(f, i));
    } else if (layerFindings.length > 0) {
      // Merge: add any finding that doesn't already have a matching check
      const existingIds = new Set(checks.map((c) => c.id));
      for (let i = 0; i < layerFindings.length; i++) {
        const f = layerFindings[i];
        const fid = (f.finding_id as string) || `finding-${i}`;
        if (!existingIds.has(fid)) {
          checks.push(mapFindingToCheck(f, checks.length));
        }
      }
    }

    // Derive a deterministic synthesis from checks if none provided by backend
    if (!synthesis && checks.length > 0) {
      synthesis = deriveLayerSynthesis(layerKey, checks);
    }

    return {
      key: layerKey,
      title: LAYER_TITLES[layerKey],
      checks,
      synthesis,
    };
  });
}

/**
 * Derives a deterministic synthesis string from completed checks.
 * This is a presentation summary only — it does not create new compliance state.
 */
function deriveLayerSynthesis(layerKey: string, checks: CheckResult[]): string {
  if (checks.length === 0) return 'No findings recorded for this layer.';

  const pass = checks.filter((c) => c.status === 'PASS').length;
  const fail = checks.filter((c) => c.status === 'FAIL').length;
  const review = checks.filter((c) => c.status === 'REVIEW').length;
  const unverified = checks.filter((c) => c.status === 'UNVERIFIED').length;
  const total = checks.length;

  const parts: string[] = [];
  if (pass > 0) parts.push(`${pass} check${pass > 1 ? 's' : ''} cleared`);
  if (fail > 0) parts.push(`${fail} non-compliance finding${fail > 1 ? 's' : ''} identified`);
  if (review > 0) parts.push(`${review} requiring officer review`);
  if (unverified > 0) parts.push(`${unverified} verification${unverified > 1 ? 's' : ''} could not be completed`);

  const layerShortNames: Record<string, string> = {
    'INGESTION_AND_DOCUMENT_INTEGRITY': 'Document integrity checks',
    'ADMINISTRATIVE_AND_IDENTITY':       'Administrative identity checks',
    'CORPORATE_EXISTENCE_AND_RISK':      'Corporate existence checks',
    'ANTI_COLLUSION_AND_RELATEDNESS':    'Anti-collusion forensics',
    'ADVERSARIAL_TECHNICAL':             'Technical specification review',
    'PAST_PERFORMANCE_AND_CAPACITY':     'Past performance review',
  };

  const prefix = layerShortNames[layerKey] ?? 'Layer checks';
  return `${prefix} complete. ${parts.join(', ')}.`;
}

function mapBidders(rawBidders: RawFinding[]): BidderSummary[] {
  return rawBidders.map((b) => ({
    bidderId: (b.bidder_id as string) || '',
    legalName: (b.legal_name as string) || 'Unknown Bidder',
    submissionId: (b.submission_id as string) || '',
    complianceStatus: (b.compliance_status as ComplianceStatus) || 'UNVERIFIED',
    passedCount: (b.passed_requirements_count as number) || 0,
    failedCount: (b.failed_requirements_count as number) || 0,
    reviewCount: (b.review_requirements_count as number) || 0,
    findingsCount: (b.findings_count as number) || 0,
    hasOpenClarifications: (b.has_open_clarifications as boolean) || false,
    freezeStatus: (b.technical_freeze_status as string) || 'NOT_FROZEN',
  }));
}

function mapCover2Readiness(rawCover2: Record<string, unknown>): Cover2Readiness {
  return {
    isReady: (rawCover2.is_ready as boolean) || false,
    blockers: (rawCover2.blockers as string[]) || [],
    warnings: (rawCover2.warnings as string[]) || [],
    eligibleBidderCount: (rawCover2.eligible_bidder_count as number) || 0,
    eligibleBidders: (rawCover2.eligible_bidders as string[]) || [],
    technicalFreezeEnforced: (rawCover2.technical_freeze_enforced as boolean) || false,
    openClarificationsCount: (rawCover2.open_clarifications_count as number) || 0,
  };
}

function mapObservations(rawObs: RawFinding[]): ObservationRecord[] {
  return rawObs.map((o) => ({
    observationId: (o.observation_id as string) || '',
    procurementId: (o.procurement_id as string) || '',
    layer: (o.layer as string) || '',
    actor: (o.actor as string) || 'HUMAN_PROCUREMENT_OFFICER',
    observation: (o.observation as string) || '',
    createdAt: (o.created_at as string) || new Date().toISOString(),
  }));
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Fetch the technical review representation from the canonical backend endpoint.
 * Maps the full ProcurementTechnicalReviewResponse to the frontend type.
 */
export async function fetchTechnicalReview(procurementId: string): Promise<TechnicalReviewResponse> {
  const resp = await fetch(
    `${API_BASE_URL}/api/procurements/${encodeURIComponent(procurementId)}/technical-review`
  );

  if (!resp.ok) {
    let detail = '';
    try {
      const errBody = await resp.json();
      detail = errBody.detail || errBody.message || '';
    } catch (_) {}
    throw new Error(`Failed to load technical review: ${resp.status}${detail ? ` — ${detail}` : ''}`);
  }

  const raw = await resp.json() as Record<string, unknown>;

  const layers = buildLayers(raw);
  const rawBidders = ((raw.bidders ?? []) as RawFinding[]);
  const rawCover2 = (raw.cover2_readiness ?? {}) as Record<string, unknown>;
  const rawObs = ((raw.observations ?? []) as RawFinding[]);

  return {
    procurementId: (raw.procurement_id as string) || procurementId,
    externalReference: (raw.external_reference as string) || '',
    procurementTitle: (raw.title as string) || 'Procurement Workspace',
    status: (raw.status as string) || '',
    totalBidders: (raw.total_bidders as number) || 0,
    qualifiedBidders: (raw.qualified_bidders_count as number) || 0,
    excludedBidders: (raw.excluded_bidders_count as number) || 0,
    reviewRequiredBidders: (raw.review_required_bidders_count as number) || 0,
    lastEvaluatedAt: (raw.last_evaluated_at as string) || undefined,
    layers,
    bidders: mapBidders(rawBidders),
    unresolvedBlockers: (raw.unresolved_blockers as string[]) || [],
    canFreeze: (raw.can_freeze as boolean) || false,
    canOpenCover2: rawCover2.is_ready === true,
    cover2Readiness: mapCover2Readiness(rawCover2),
    observations: mapObservations(rawObs),
    decisionAuthority: (raw.decision_authority as string) || 'HUMAN_PROCUREMENT_OFFICER',
    _raw: raw,
  };
}

/**
 * Persist an officer observation via the canonical backend endpoint.
 * Returns 'persisted' if successful, 'unavailable' if endpoint returned 404,
 * or throws with the backend error message for other failures.
 */
export async function saveOfficerObservation(
  payload: OfficerObservationPayload
): Promise<'persisted' | 'unavailable'> {
  const resp = await fetch(
    `${API_BASE_URL}/api/procurements/${encodeURIComponent(payload.procurementId)}/observations`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        layer: payload.layerKey,
        observation: payload.observation,
      }),
    }
  );

  if (resp.ok) return 'persisted';
  if (resp.status === 404) return 'unavailable';

  let detail = '';
  try {
    const errBody = await resp.json();
    detail = errBody.detail || errBody.message || '';
  } catch (_) {}
  throw new Error(`Observation save failed: ${resp.status}${detail ? ` — ${detail}` : ''}`);
}

/**
 * Invoke the canonical technical scrutiny pipeline via POST.
 * The backend enforces deadline gate and lifecycle state.
 * Returns the run response or throws with the backend error detail.
 */
export async function runTechnicalScrutiny(procurementId: string): Promise<unknown> {
  const resp = await fetch(
    `${API_BASE_URL}/api/procurements/${encodeURIComponent(procurementId)}/technical-scrutiny/run`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor: 'PROCUREMENT_OFFICER' }),
    }
  );

  if (!resp.ok) {
    let errMsg = `Failed to run technical scrutiny: ${resp.status}`;
    try {
      const errBody = await resp.json();
      errMsg = errBody.detail || errBody.message || errMsg;
    } catch (_) {}
    throw new Error(errMsg);
  }

  return resp.json();
}
