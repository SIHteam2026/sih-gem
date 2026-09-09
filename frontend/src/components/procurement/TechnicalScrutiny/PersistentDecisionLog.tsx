import React from 'react';
import type { DecisionLogEntry, ComplianceStatus } from '@/types/technical-review';
import { CheckCircle, AlertCircle, Clock, BookOpen } from 'lucide-react';

interface PersistentDecisionLogProps {
  entries: DecisionLogEntry[];
}

const STATUS_DOT: Record<ComplianceStatus, string> = {
  PASS: 'bg-emerald-400',
  FAIL: 'bg-red-400',
  REVIEW: 'bg-amber-400',
  UNVERIFIED: 'bg-slate-400',
  NOT_APPLICABLE: 'bg-slate-300',
};

function FindingsTally({ summary }: { summary: DecisionLogEntry['findingsSummary'] }) {
  const parts: { label: string; count: number; color: string }[] = [
    { label: 'P', count: summary.pass, color: 'text-emerald-600' },
    { label: 'F', count: summary.fail, color: 'text-red-600' },
    { label: 'R', count: summary.review, color: 'text-amber-600' },
    { label: 'U', count: summary.unverified, color: 'text-slate-500' },
  ].filter((p) => p.count > 0);

  if (parts.length === 0) return <span className="text-[10px] text-slate-400 italic">No findings</span>;

  return (
    <span className="inline-flex items-center gap-1.5">
      {parts.map((p) => (
        <span key={p.label} className={`text-[10px] font-bold ${p.color}`}>
          {p.label}:{p.count}
        </span>
      ))}
    </span>
  );
}

/**
 * Persistent right-side Decision Log ledger.
 *
 * Records officer review history as layers are completed.
 * This is a read-only record panel — it does NOT make compliance decisions.
 * Observations are shown with their true persistence state.
 */
export function PersistentDecisionLog({ entries }: PersistentDecisionLogProps) {
  if (entries.length === 0) {
    return (
      <div className="h-full flex flex-col">
        <div className="flex items-center gap-2 mb-4">
          <BookOpen className="w-4 h-4 text-slate-400" />
          <h3 className="text-xs font-bold tracking-widest text-slate-400 uppercase">
            Decision Log
          </h3>
        </div>
        <div className="flex-1 flex items-start pt-4">
          <p className="text-xs text-slate-300 italic leading-relaxed">
            Review history will appear here as you progress through each layer.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 mb-5">
        <BookOpen className="w-4 h-4 text-slate-500" />
        <h3 className="text-xs font-bold tracking-widest text-slate-500 uppercase">
          Decision Log
        </h3>
        <span className="ml-auto text-[10px] text-slate-400 font-medium">
          {entries.length} layer{entries.length > 1 ? 's' : ''} reviewed
        </span>
      </div>

      <div className="space-y-4 overflow-y-auto flex-1 pr-1">
        {entries.map((entry, idx) => (
          <div
            key={`${entry.layerKey}-${idx}`}
            className="border border-slate-100 rounded-lg p-3 bg-white/60"
          >
            {/* Layer header */}
            <div className="flex items-start justify-between gap-2 mb-2">
              <span className="text-[11px] font-bold text-slate-700 leading-tight">
                {entry.layerTitle}
              </span>
              <CheckCircle className="w-3.5 h-3.5 text-slate-300 shrink-0 mt-0.5" />
            </div>

            {/* Findings summary */}
            <div className="mb-2">
              <FindingsTally summary={entry.findingsSummary} />
            </div>

            {/* Officer observation */}
            {entry.observationText ? (
              <div className="mt-2 pt-2 border-t border-slate-100">
                <p className="text-[11px] text-slate-600 italic leading-snug">
                  &ldquo;{entry.observationText}&rdquo;
                </p>
                <div className="flex items-center gap-1.5 mt-1.5">
                  {entry.observationPersisted ? (
                    <CheckCircle className="w-3 h-3 text-emerald-500" />
                  ) : (
                    <AlertCircle className="w-3 h-3 text-amber-500" />
                  )}
                  <span
                    className={`text-[10px] font-medium ${
                      entry.observationPersisted ? 'text-emerald-600' : 'text-amber-600'
                    }`}
                  >
                    {entry.observationPersisted
                      ? 'Saved to procurement record'
                      : 'Local only — not persisted'}
                  </span>
                </div>
              </div>
            ) : (
              <div className="mt-2 pt-2 border-t border-slate-100">
                <span className="text-[10px] text-slate-300 italic">No observation recorded</span>
              </div>
            )}

            {/* Timestamp */}
            <div className="flex items-center gap-1 mt-2">
              <Clock className="w-3 h-3 text-slate-300" />
              <span className="text-[10px] text-slate-400">
                {new Date(entry.recordedAt).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Governance boundary reminder */}
      <div className="mt-4 pt-3 border-t border-slate-100">
        <p className="text-[10px] text-slate-300 leading-relaxed">
          This log records review context and officer observations.
          Final qualification decisions rest with the procurement officer.
        </p>
      </div>
    </div>
  );
}
