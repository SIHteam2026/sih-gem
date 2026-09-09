import React from 'react';
import type { CheckResult, ComplianceStatus } from '@/types/technical-review';
import { AlertTriangle, HelpCircle, Info, MessageSquare, ExternalLink } from 'lucide-react';

interface FindingAttentionPanelProps {
  check: CheckResult;
  bidderName: string;
  procurementId: string;
  onSeekClarification: (check: CheckResult) => void;
  /** Whether an existing clarification is already open for this finding */
  existingClarificationId?: string;
  existingClarificationStatus?: string;
}

const STATUS_STYLES: Record<ComplianceStatus, { badge: string; icon: React.ReactNode; label: string }> = {
  PASS: {
    badge: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: null,
    label: 'PASS',
  },
  FAIL: {
    badge: 'bg-red-50 text-red-700 border-red-200',
    icon: <AlertTriangle className="w-3.5 h-3.5" />,
    label: 'FAIL',
  },
  REVIEW: {
    badge: 'bg-amber-50 text-amber-700 border-amber-200',
    icon: <AlertTriangle className="w-3.5 h-3.5" />,
    label: 'REVIEW',
  },
  UNVERIFIED: {
    badge: 'bg-slate-50 text-slate-600 border-slate-200',
    icon: <HelpCircle className="w-3.5 h-3.5" />,
    label: 'UNVERIFIED',
  },
  NOT_APPLICABLE: {
    badge: 'bg-slate-50 text-slate-400 border-slate-100',
    icon: null,
    label: 'NOT APPLICABLE',
  },
};

/**
 * Derives a deterministic "why this requires attention" explanation from the
 * canonical finding state. Does not create new compliance state.
 */
function whyAttention(check: CheckResult): string {
  if (check.finding) return check.finding;
  if (check.synthesis) return check.synthesis;
  if (check.status === 'FAIL') {
    return 'The verification engine established non-compliance against this requirement. Reliable evidence supports this finding.';
  }
  if (check.status === 'REVIEW') {
    return 'The evidence is conflicting or ambiguous. This finding requires officer review before a determination can be made.';
  }
  if (check.status === 'UNVERIFIED') {
    return 'Verification could not be completed — required evidence is missing or the external verification source was unavailable.';
  }
  return 'This finding has been flagged for officer review.';
}

/**
 * Determines whether the "Seek Clarification" action should be available.
 *
 * Eligibility rule:
 * - Strictly relies on canonical backend signal (requires_clarification = true).
 * - The UI does not independently decide eligibility based on PASS/FAIL/REVIEW/UNVERIFIED statuses.
 */
function canSeekClarification(check: CheckResult): boolean {
  return check.requiresClarification === true;
}

const CLARIFICATION_STATUS_LABELS: Record<string, { label: string; color: string }> = {
  OPEN:                          { label: 'Awaiting bidder response',       color: 'text-blue-600' },
  RESPONDED:                     { label: 'Bidder responded',                color: 'text-amber-600' },
  UNDER_REVIEW:                  { label: 'Officer reviewing response',      color: 'text-amber-700' },
  RESOLVED:                      { label: 'Clarification resolved',          color: 'text-emerald-600' },
  REQUIRES_FURTHER_CLARIFICATION:{ label: 'Further clarification requested', color: 'text-amber-700' },
  EXPIRED:                       { label: 'Response deadline expired',       color: 'text-red-600' },
  CANCELLED:                     { label: 'Clarification cancelled',         color: 'text-slate-500' },
  REJECTED:                      { label: 'Representation rejected',        color: 'text-red-700' },
};

/**
 * Finding Attention Panel — an evidence review sheet for a single finding
 * requiring officer action.
 *
 * Shows REQUIREMENT / ORIGINAL EVIDENCE / ORIGINAL FINDING / STATUS in a
 * structured layout, explains why the finding needs attention, and provides
 * a "Seek Clarification" entry point where the canonical workflow permits it.
 *
 * Does NOT modify compliance state directly.
 */
export function FindingAttentionPanel({
  check,
  bidderName,
  procurementId: _procurementId,
  onSeekClarification,
  existingClarificationId,
  existingClarificationStatus,
}: FindingAttentionPanelProps) {
  const statusCfg = STATUS_STYLES[check.status] ?? STATUS_STYLES.UNVERIFIED;
  const showClarification = canSeekClarification(check);
  const hasExistingClarification = !!existingClarificationId;

  const existingStatusInfo = existingClarificationStatus
    ? CLARIFICATION_STATUS_LABELS[existingClarificationStatus]
    : null;

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden bg-white">
      {/* Finding header */}
      <div className="px-5 py-4 border-b border-slate-100 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">
            {bidderName}
          </p>
          <h4 className="text-sm font-bold text-slate-800">{check.description}</h4>
        </div>
        <span
          className={`shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold tracking-wider border ${statusCfg.badge}`}
        >
          {statusCfg.icon}
          {statusCfg.label}
        </span>
      </div>

      {/* Structured fields */}
      <div className="px-5 py-4 space-y-4">
        {/* REQUIREMENT */}
        {check.requirement && (
          <div>
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">
              Requirement
            </p>
            <p className="text-sm text-slate-700 leading-relaxed">{check.requirement}</p>
          </div>
        )}

        {/* ORIGINAL EVIDENCE */}
        {check.evidence && (
          <div>
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">
              Original Evidence
            </p>
            <p className="text-sm text-slate-700 leading-relaxed">{check.evidence}</p>
          </div>
        )}

        {/* ORIGINAL FINDING / WHY THIS REQUIRES ATTENTION */}
        <div>
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">
            Why This Requires Attention
          </p>
          <div className="p-3 bg-slate-50 border border-slate-100 rounded-lg">
            <p className="text-sm text-slate-700 leading-relaxed">{whyAttention(check)}</p>
          </div>
        </div>

        {/* Evidence provenance */}
        {check.evidenceRefs && check.evidenceRefs.length > 0 && (
          <div>
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">
              Evidence References
            </p>
            <ul className="space-y-1">
              {check.evidenceRefs.map((ref, i) => (
                <li key={i} className="text-xs text-slate-500 flex gap-2">
                  <span className="text-slate-300">↳</span>
                  <span>
                    {ref.documentName || ref.documentId}
                    {ref.page !== undefined && <span className="ml-1 text-slate-400">· Page {ref.page}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Officer Action */}
      <div className="px-5 py-4 border-t border-slate-100 bg-slate-50/50">
        {hasExistingClarification ? (
          /* Existing clarification state */
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-slate-400" />
              <span className="text-sm text-slate-600">
                Clarification{' '}
                <span className={`font-semibold ${existingStatusInfo?.color ?? 'text-slate-700'}`}>
                  {existingStatusInfo?.label ?? existingClarificationStatus}
                </span>
              </span>
            </div>
            <button
              onClick={() => onSeekClarification(check)}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-800"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              View Clarification
            </button>
          </div>
        ) : showClarification ? (
          /* Seek Clarification entry point */
          <div className="flex items-start gap-3">
            <div className="flex-1">
              <div className="flex items-center gap-1.5 mb-1">
                <Info className="w-3.5 h-3.5 text-slate-400" />
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  A clarification request will be created through the canonical procurement record.
                  Only re-evaluation through the backend can change the underlying finding.
                </p>
              </div>
            </div>
            <button
              onClick={() => onSeekClarification(check)}
              className="shrink-0 inline-flex items-center gap-2 px-4 py-2 bg-[#0f172a] hover:bg-[#1e293b] text-white text-xs font-semibold rounded-full transition-colors"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Seek Clarification
            </button>
          </div>
        ) : (
          /* No clarification applicable */
          <p className="text-xs text-slate-400 italic">
            {check.status === 'PASS' || check.status === 'NOT_APPLICABLE'
              ? 'No clarification action required for this finding.'
              : 'Clarification is not available for this finding type through the current workflow.'}
          </p>
        )}
      </div>
    </div>
  );
}
