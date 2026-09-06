/**
 * OPAL Officer Review & Verification Decisions Store.
 * 
 * Manages human officer compliance verification decisions across procurements and submissions:
 * - 'CONFIRMED': Officer reviewed evidence findings and confirmed statutory compliance.
 * - 'NEEDS_FURTHER_REVIEW': Officer flagged case for deeper analysis, clarifications, or second-tier review.
 */

export type OfficerDecisionType = 'CONFIRMED' | 'NEEDS_FURTHER_REVIEW';

export interface OfficerDecision {
  targetId: string;
  decision: OfficerDecisionType;
  title?: string;
  reference?: string;
  officerName?: string;
  timestamp: string;
  notes?: string;
}

const STORAGE_KEY = 'opal_officer_review_decisions_v1';
const EVENT_NAME = 'opal-review-decision-updated';

/**
 * Retrieve all saved officer review decisions.
 */
export function getOfficerDecisions(): Record<string, OfficerDecision> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

/**
 * Get officer decision for a specific procurement or submission ID.
 */
export function getOfficerDecisionFor(targetId: string): OfficerDecision | null {
  if (!targetId) return null;
  const all = getOfficerDecisions();
  return all[targetId] || null;
}

/**
 * Save an officer decision and broadcast an update event.
 */
export function saveOfficerDecision(
  targetId: string,
  decision: OfficerDecisionType,
  metadata?: {
    title?: string;
    reference?: string;
    officerName?: string;
    notes?: string;
  }
): OfficerDecision {
  const all = getOfficerDecisions();
  const record: OfficerDecision = {
    targetId,
    decision,
    title: metadata?.title,
    reference: metadata?.reference,
    officerName: metadata?.officerName || 'Mr. Srivastav',
    timestamp: new Date().toISOString(),
    notes: metadata?.notes,
  };

  all[targetId] = record;

  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
      window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: record }));
    } catch (e) {
      console.error('Could not save officer decision to localStorage:', e);
    }
  }

  return record;
}

/**
 * Clear or reset decision for a target.
 */
export function clearOfficerDecision(targetId: string): void {
  const all = getOfficerDecisions();
  if (all[targetId]) {
    delete all[targetId];
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
        window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: { targetId, cleared: true } }));
      } catch (e) {
        console.error('Could not clear officer decision:', e);
      }
    }
  }
}

/**
 * Subscribe to review decision changes across components.
 */
export function subscribeToReviewDecisions(callback: () => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const handler = () => callback();
  window.addEventListener(EVENT_NAME, handler);
  window.addEventListener('storage', handler);
  return () => {
    window.removeEventListener(EVENT_NAME, handler);
    window.removeEventListener('storage', handler);
  };
}

/**
 * Compute breakdown stats for a list of procurements.
 */
export function computeReviewStats(
  procurements: Array<{ id: string; status?: string }>
): {
  totalProcessed: number;
  pendingCount: number;
  furtherReviewCount: number;
  confirmedCount: number;
} {
  const decisions = getOfficerDecisions();

  // Filter for completely processed procurements (status === 'READY')
  const processedCases = procurements.filter(
    (p) => (p.status || '').toUpperCase() === 'READY'
  );

  let pendingCount = 0;
  let furtherReviewCount = 0;
  let confirmedCount = 0;

  processedCases.forEach((p) => {
    const dec = decisions[p.id];
    if (dec?.decision === 'CONFIRMED') {
      confirmedCount += 1;
    } else if (dec?.decision === 'NEEDS_FURTHER_REVIEW') {
      furtherReviewCount += 1;
    } else {
      pendingCount += 1;
    }
  });

  return {
    totalProcessed: processedCases.length,
    pendingCount,
    furtherReviewCount,
    confirmedCount,
  };
}
