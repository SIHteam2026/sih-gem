import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import type { TechnicalReviewResponse, DecisionLogEntry, ComplianceStatus } from '@/types/technical-review';
import { TechnicalLayerSection } from './TechnicalLayerSection';
import { PersistentDecisionLog } from './PersistentDecisionLog';
import { AlertTriangle, CheckCircle2, Clock, Users, ShieldCheck, XCircle } from 'lucide-react';

interface TechnicalScrutinyViewProps {
  data: TechnicalReviewResponse;
  /** Full procurement detail for richer context (org, status, etc.) */
  procurementOrganization?: string;
}

// Canonical status badge colors for the completion summary
const BIDDER_STATUS_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  PASS:           { bg: 'bg-emerald-50',  text: 'text-emerald-700', border: 'border-emerald-200' },
  FAIL:           { bg: 'bg-red-50',      text: 'text-red-700',     border: 'border-red-200' },
  REVIEW:         { bg: 'bg-amber-50',    text: 'text-amber-700',   border: 'border-amber-200' },
  UNVERIFIED:     { bg: 'bg-slate-50',    text: 'text-slate-600',   border: 'border-slate-200' },
  NOT_APPLICABLE: { bg: 'bg-slate-50',    text: 'text-slate-500',   border: 'border-slate-100' },
};

export function TechnicalScrutinyView({
  data,
  procurementOrganization,
}: TechnicalScrutinyViewProps) {
  const router = useRouter();
  const [activeLayerIndex, setActiveLayerIndex] = useState(0);
  const [isFullyComplete, setIsFullyComplete] = useState(false);
  const [logEntries, setLogEntries] = useState<DecisionLogEntry[]>([]);

  const handleProceedToNext = (observationText: string, persisted: boolean) => {
    const layer = data.layers[activeLayerIndex];
    if (!layer) return;

    // Count findings for this layer
    const findingsSummary = {
      pass:       layer.checks.filter((c) => c.status === 'PASS').length,
      fail:       layer.checks.filter((c) => c.status === 'FAIL').length,
      review:     layer.checks.filter((c) => c.status === 'REVIEW').length,
      unverified: layer.checks.filter((c) => c.status === 'UNVERIFIED').length,
    };

    // Add entry to the persistent Decision Log
    const newEntry: DecisionLogEntry = {
      layerKey: layer.key,
      layerTitle: layer.title,
      observationText: observationText || undefined,
      observationPersisted: persisted,
      recordedAt: new Date().toISOString(),
      findingsSummary,
    };
    setLogEntries((prev) => [...prev, newEntry]);

    if (activeLayerIndex < data.layers.length - 1) {
      setActiveLayerIndex((prev) => prev + 1);
    } else {
      setIsFullyComplete(true);
    }
  };

  const formattedDate = data.lastEvaluatedAt
    ? new Date(data.lastEvaluatedAt).toLocaleString([], {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : null;

  return (
    <div className="min-h-screen bg-white text-[#0f172a] font-sans">
      {/* ----------------------------------------------------------------- */}
      {/* Procurement identity header — restrained, not a dashboard */}
      {/* ----------------------------------------------------------------- */}
      <header className="sticky top-0 z-20 bg-white/95 backdrop-blur-md border-b border-slate-100 py-4 px-8">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-start justify-between gap-6">
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest bg-slate-100 text-slate-500 uppercase">
                  {data.externalReference || data.procurementId}
                </span>
                <span className="text-xs text-slate-400 font-medium tracking-wider uppercase">
                  Technical Scrutiny · Cover 1
                </span>
                {data.status && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-600 border border-blue-100 uppercase tracking-wider">
                    {data.status.replace(/_/g, ' ')}
                  </span>
                )}
              </div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#0f172a] truncate">
                {data.procurementTitle}
              </h1>
              <div className="flex items-center gap-4 mt-1 flex-wrap">
                {procurementOrganization && (
                  <span className="text-xs text-slate-400">{procurementOrganization}</span>
                )}
                {data.totalBidders > 0 && (
                  <span className="flex items-center gap-1 text-xs text-slate-400">
                    <Users className="w-3 h-3" />
                    {data.totalBidders} bidder{data.totalBidders !== 1 ? 's' : ''}
                  </span>
                )}
                {formattedDate && (
                  <span className="flex items-center gap-1 text-xs text-slate-400">
                    <Clock className="w-3 h-3" />
                    Evaluated {formattedDate}
                  </span>
                )}
              </div>
            </div>

            {/* Decision authority note */}
            <div className="shrink-0 hidden sm:flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 border border-slate-100 rounded-full">
              <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
              <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">
                {data.decisionAuthority === 'HUMAN_PROCUREMENT_OFFICER'
                  ? 'Officer Decision Required'
                  : data.decisionAuthority}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* ----------------------------------------------------------------- */}
      {/* Main two-column layout */}
      {/* Left: layer content  |  Right: persistent Decision Log */}
      {/* ----------------------------------------------------------------- */}
      <div className="max-w-7xl mx-auto px-6 sm:px-8 py-10">
        <div className="flex gap-10 items-start">

          {/* ============================================================= */}
          {/* LEFT — Layer content (2/3 width on large screens) */}
          {/* ============================================================= */}
          <main className="flex-1 min-w-0">
            {/* Unresolved blockers warning */}
            {data.unresolvedBlockers.length > 0 && (
              <div className="mb-8 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  <span className="text-sm font-bold text-amber-800">Unresolved Blockers</span>
                </div>
                <ul className="space-y-1">
                  {data.unresolvedBlockers.map((b, i) => (
                    <li key={i} className="text-sm text-amber-700">· {b}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Six canonical layers in order */}
            <div className="relative">
              {data.layers.map((layer, idx) => (
                <TechnicalLayerSection
                  key={layer.key}
                  layer={layer}
                  procurementId={data.procurementId}
                  isActive={idx === activeLayerIndex && !isFullyComplete}
                  isCompleted={idx < activeLayerIndex || isFullyComplete}
                  onProceedToNext={handleProceedToNext}
                />
              ))}
            </div>

            {/* ============================================================= */}
            {/* Technical Completion — shown after all 6 layers are done */}
            {/* ============================================================= */}
            {isFullyComplete && (
              <div className="mt-10 pt-10 border-t border-slate-200 animate-in fade-in slide-in-from-bottom-4 duration-700">
                <div className="flex items-center gap-3 mb-6">
                  <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                  <h3 className="text-xl font-bold text-[#0f172a]">
                    Technical Scrutiny Complete
                  </h3>
                </div>

                {/* Bidder-level outcomes */}
                {data.bidders.length > 0 && (
                  <div className="mb-8">
                    <h4 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4">
                      Bidder Outcomes
                    </h4>
                    <div className="space-y-3">
                      {data.bidders.map((b) => {
                        const cfg =
                          BIDDER_STATUS_COLORS[b.complianceStatus] ??
                          BIDDER_STATUS_COLORS.UNVERIFIED;
                        return (
                          <div
                            key={b.bidderId}
                            className={`flex items-center justify-between p-4 rounded-lg border ${cfg.border} ${cfg.bg}`}
                          >
                            <div>
                              <p className="text-sm font-bold text-slate-800">{b.legalName}</p>
                              <p className="text-xs text-slate-500 mt-0.5">
                                {b.passedCount}P · {b.failedCount}F · {b.reviewCount}R ·{' '}
                                {b.findingsCount} finding{b.findingsCount !== 1 ? 's' : ''}
                                {b.hasOpenClarifications && ' · Open clarifications'}
                              </p>
                            </div>
                            <span
                              className={`text-[11px] font-bold tracking-wider px-2.5 py-1 rounded-full border ${cfg.border} ${cfg.text} ${cfg.bg}`}
                            >
                              {b.complianceStatus}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Cover-2 Gate — driven by backend cover2_readiness */}
                <div className="mt-8 p-5 bg-slate-50 border border-slate-200 rounded-xl">
                  <h4 className="text-sm font-bold text-slate-700 mb-3">
                    Cover 2 — Financial Scrutiny Gate
                  </h4>

                  {data.canOpenCover2 ? (
                    <div className="space-y-4">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                        <p className="text-sm text-slate-700">
                          {data.cover2Readiness.eligibleBidderCount} eligible bidder
                          {data.cover2Readiness.eligibleBidderCount !== 1 ? 's' : ''} cleared
                          for financial evaluation.
                        </p>
                      </div>
                      {data.cover2Readiness.warnings.length > 0 && (
                        <ul className="space-y-1">
                          {data.cover2Readiness.warnings.map((w, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-amber-700">
                              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                              {w}
                            </li>
                          ))}
                        </ul>
                      )}
                      <button
                        onClick={() =>
                          router.push(
                            `/procurements/${data.procurementId}/financial-evaluation`
                          )
                        }
                        className="inline-flex items-center gap-2 px-6 py-3 bg-[#0f172a] hover:bg-[#1e293b] text-white text-sm font-medium rounded-full transition-colors"
                      >
                        Proceed to Financial Scrutiny
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center gap-2">
                        <XCircle className="w-4 h-4 text-red-500" />
                        <p className="text-sm text-slate-700">
                          Financial scrutiny cannot be opened yet.
                        </p>
                      </div>
                      {data.cover2Readiness.blockers.length > 0 && (
                        <ul className="space-y-1.5">
                          {data.cover2Readiness.blockers.map((b, i) => (
                            <li
                              key={i}
                              className="text-sm text-red-700 flex items-start gap-2"
                            >
                              <span className="text-red-400 mt-0.5">·</span>
                              {b}
                            </li>
                          ))}
                        </ul>
                      )}
                      <button
                        disabled
                        className="inline-flex items-center gap-2 px-6 py-3 bg-slate-200 text-slate-400 text-sm font-medium rounded-full cursor-not-allowed"
                      >
                        Proceed to Financial Scrutiny (Blocked)
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </main>

          {/* ============================================================= */}
          {/* RIGHT — Persistent Decision Log (hidden on narrow screens) */}
          {/* ============================================================= */}
          <aside className="hidden lg:block w-72 xl:w-80 shrink-0">
            <div className="sticky top-28">
              <div className="bg-slate-50 border border-slate-100 rounded-xl p-5 min-h-[400px] flex flex-col">
                <PersistentDecisionLog entries={logEntries} />
              </div>
            </div>
          </aside>
        </div>

        {/* Narrow-screen Decision Log — stacks below main content */}
        {logEntries.length > 0 && (
          <div className="lg:hidden mt-10 pt-10 border-t border-slate-100">
            <div className="bg-slate-50 border border-slate-100 rounded-xl p-5">
              <PersistentDecisionLog entries={logEntries} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
