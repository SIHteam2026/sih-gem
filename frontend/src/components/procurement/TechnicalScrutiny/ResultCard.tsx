import React, { useState } from 'react';
import type { CheckResult, ComplianceStatus } from '@/types/technical-review';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface ResultCardProps {
  check: CheckResult;
}

// ---------------------------------------------------------------------------
// Canonical status presentation
// Each status maps to a label, color, and brief friendly explanation.
// The canonical name (PASS / FAIL / REVIEW / UNVERIFIED / NOT_APPLICABLE)
// is ALWAYS shown — it must never be renamed to Approved, Rejected, etc.
// ---------------------------------------------------------------------------
const STATUS_CONFIG: Record<
  ComplianceStatus,
  {
    label: string;
    color: string;
    bg: string;
    border: string;
    dot: string;
    explainer: string;
  }
> = {
  PASS: {
    label: 'PASS',
    color: 'text-emerald-700',
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    dot: 'bg-emerald-500',
    explainer: 'Sufficient evidence establishes compliance.',
  },
  FAIL: {
    label: 'FAIL',
    color: 'text-red-700',
    bg: 'bg-red-50',
    border: 'border-red-200',
    dot: 'bg-red-500',
    explainer: 'Reliable evidence establishes non-compliance.',
  },
  REVIEW: {
    label: 'REVIEW',
    color: 'text-amber-700',
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    dot: 'bg-amber-500',
    explainer: 'Conflicting or ambiguous evidence — officer review required.',
  },
  UNVERIFIED: {
    label: 'UNVERIFIED',
    color: 'text-slate-600',
    bg: 'bg-slate-50',
    border: 'border-slate-200',
    dot: 'bg-slate-400',
    explainer: 'Verification could not be completed.',
  },
  NOT_APPLICABLE: {
    label: 'NOT APPLICABLE',
    color: 'text-slate-500',
    bg: 'bg-slate-50',
    border: 'border-slate-100',
    dot: 'bg-slate-300',
    explainer: 'This requirement does not apply to this bidder.',
  },
};

function StatusBadge({ status }: { status: ComplianceStatus }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.UNVERIFIED;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold tracking-wider ${cfg.color} ${cfg.bg} border ${cfg.border}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

export function ResultCard({ check }: ResultCardProps) {
  const [showEvidence, setShowEvidence] = useState(false);
  const cfg = STATUS_CONFIG[check.status] ?? STATUS_CONFIG.UNVERIFIED;

  const hasStructuredData = check.requirement || check.evidence || check.finding;
  const hasEvidenceRefs = check.evidenceRefs && check.evidenceRefs.length > 0;

  return (
    <div className={`mt-2 ml-7 rounded-lg border ${cfg.border} ${cfg.bg} overflow-hidden max-w-2xl`}>
      {/* Status header row */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-black/5">
        <StatusBadge status={check.status} />
        <span className="text-[11px] text-slate-400 italic">{cfg.explainer}</span>
      </div>

      {/* Bidder attribution */}
      {check.bidderName && (
        <div className="px-4 pt-2.5 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
          Bidder: <span className="text-slate-700 font-bold">{check.bidderName}</span>
        </div>
      )}

      {/* Structured fields: REQUIREMENT / EVIDENCE / FINDING */}
      {hasStructuredData ? (
        <div className="px-4 py-3 space-y-3">
          {check.requirement && (
            <div>
              <span className="text-[10px] font-bold tracking-widest text-slate-400 uppercase block mb-0.5">
                Requirement
              </span>
              <p className="text-sm text-slate-700 leading-relaxed">{check.requirement}</p>
            </div>
          )}
          {check.evidence && (
            <div>
              <span className="text-[10px] font-bold tracking-widest text-slate-400 uppercase block mb-0.5">
                Evidence
              </span>
              <p className="text-sm text-slate-700 leading-relaxed">{check.evidence}</p>
            </div>
          )}
          {check.finding && (
            <div>
              <span className="text-[10px] font-bold tracking-widest text-slate-400 uppercase block mb-0.5">
                Finding
              </span>
              <p className="text-sm text-slate-700 leading-relaxed">{check.finding}</p>
            </div>
          )}
        </div>
      ) : check.synthesis ? (
        /* Fallback: show synthesis when no structured fields available */
        <div className="px-4 py-3">
          <p className="text-sm text-slate-700 leading-relaxed">{check.synthesis}</p>
        </div>
      ) : null}

      {/* Source reference */}
      {check.sourceReference && (
        <div className="px-4 pb-2 text-xs text-slate-400">
          Source: {check.sourceReference}
        </div>
      )}

      {/* Evidence provenance toggle */}
      {hasEvidenceRefs && (
        <div className="border-t border-black/5">
          <button
            onClick={() => setShowEvidence((v) => !v)}
            className="w-full flex items-center justify-between px-4 py-2 text-[11px] text-slate-500 hover:text-slate-700 transition-colors"
          >
            <span className="font-semibold uppercase tracking-wider">
              Evidence Provenance ({check.evidenceRefs!.length})
            </span>
            {showEvidence ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </button>
          {showEvidence && (
            <ul className="px-4 pb-3 space-y-2">
              {check.evidenceRefs!.map((ref, idx) => (
                <li key={idx} className="text-xs text-slate-500 flex gap-2 items-start">
                  <span className="text-slate-300 mt-0.5">↳</span>
                  <span>
                    <span className="font-medium text-slate-700">
                      {ref.documentName || ref.documentId}
                    </span>
                    {ref.page !== undefined && (
                      <span className="ml-1.5 text-slate-400">· Page {ref.page}</span>
                    )}
                    {ref.sourceType && (
                      <span className="ml-1.5 text-slate-400">· {ref.sourceType}</span>
                    )}
                    {ref.retrievedAt && (
                      <span className="ml-1.5 text-slate-400">
                        · Retrieved {new Date(ref.retrievedAt).toLocaleString()}
                      </span>
                    )}
                    {ref.snippet && (
                      <span className="block mt-1 italic text-slate-500">
                        &ldquo;{ref.snippet}&rdquo;
                      </span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
