import React, { useState, useEffect, useCallback } from 'react';
import type { TechnicalLayer } from '@/types/technical-review';
import { CheckItem } from './CheckItem';
import { DecisionLogWidget } from './DecisionLogWidget';

interface TechnicalLayerSectionProps {
  layer: TechnicalLayer;
  procurementId: string;
  /** Layer is actively showing its checks (sequential reveal in progress or complete) */
  isActive: boolean;
  /** Layer has been completed and officer has proceeded past it */
  isCompleted: boolean;
  onProceedToNext: (observationText: string, persisted: boolean) => void;
}

/**
 * Renders a single technical layer in the sequential scrutiny flow.
 *
 * Active state: reveals checks one-by-one (presentation effect — batch results
 * from backend, not separate backend calls), then shows synthesis + officer
 * observation input before the Proceed button.
 *
 * Completed state: shows a collapsed summary of what was reviewed.
 */
export function TechnicalLayerSection({
  layer,
  procurementId,
  isActive,
  isCompleted,
  onProceedToNext,
}: TechnicalLayerSectionProps) {
  const [revealedCount, setRevealedCount] = useState(isCompleted ? layer.checks.length : 0);

  // Reset when newly activated
  useEffect(() => {
    if (isActive && !isCompleted) {
      setRevealedCount(0);
    }
  }, [isActive, isCompleted]);

  const handleRevealComplete = useCallback(() => {
    setRevealedCount((prev) => prev + 1);
  }, []);

  // Do not render layers that are neither active nor completed
  if (!isActive && !isCompleted) return null;

  const allChecksRevealed = revealedCount >= layer.checks.length;
  const showObservation = isActive && !isCompleted && allChecksRevealed;

  // Counts for the completed summary
  const pass = layer.checks.filter((c) => c.status === 'PASS').length;
  const fail = layer.checks.filter((c) => c.status === 'FAIL').length;
  const review = layer.checks.filter((c) => c.status === 'REVIEW').length;
  const unverified = layer.checks.filter((c) => c.status === 'UNVERIFIED').length;

  // ---------------------------------------------------------------------------
  // Completed (collapsed) view
  // ---------------------------------------------------------------------------
  if (isCompleted) {
    return (
      <div className="mb-10 pb-10 border-b border-slate-100 opacity-70">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-base font-bold text-slate-600">{layer.title}</h3>
          <span className="text-xs text-slate-400 font-medium">Complete</span>
        </div>
        <div className="flex items-center gap-4 text-xs text-slate-400">
          {pass > 0 && <span className="text-emerald-600 font-medium">{pass} PASS</span>}
          {fail > 0 && <span className="text-red-600 font-medium">{fail} FAIL</span>}
          {review > 0 && <span className="text-amber-600 font-medium">{review} REVIEW</span>}
          {unverified > 0 && <span className="text-slate-500 font-medium">{unverified} UNVERIFIED</span>}
          {layer.checks.length === 0 && <span className="italic">No findings recorded</span>}
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Active view — full layer detail
  // ---------------------------------------------------------------------------
  return (
    <div className="mb-16">
      {/* Layer header */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold tracking-tight text-[#0f172a]">
          {layer.title}
        </h2>
        <p className="mt-1 text-xs font-mono text-slate-400 tracking-wider uppercase">
          {layer.key.replace(/_/g, ' ')}
        </p>
        {layer.checks.length === 0 && (
          <p className="mt-3 text-sm text-slate-400 italic">
            No findings recorded for this layer in the current evaluation.
          </p>
        )}
      </div>

      {/* Checks — sequential presentation of batch backend results */}
      <div className="space-y-1 pl-1">
        {layer.checks.map((check, idx) => {
          // Stagger delay for natural feel (800–1400ms, not uniform)
          const delay = 800 + (idx % 3) * 200;
          return (
            <CheckItem
              key={check.id}
              check={check}
              isRevealing={isActive && !isCompleted && idx === revealedCount}
              isRevealed={idx < revealedCount}
              onRevealComplete={handleRevealComplete}
              revealDelay={delay}
            />
          );
        })}
      </div>

      {/* Layer synthesis — shown after all checks revealed, before observation */}
      {allChecksRevealed && layer.synthesis && (
        <div className="mt-8 p-4 bg-slate-50 border border-slate-100 rounded-lg max-w-2xl animate-in fade-in duration-500">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
            Layer Summary
          </p>
          <p className="text-sm text-slate-600 leading-relaxed">{layer.synthesis}</p>
          <p className="mt-2 text-[10px] text-slate-400 italic">
            This summary is derived from the findings above and does not constitute a qualification decision.
          </p>
        </div>
      )}

      {/* Officer observation + Proceed — rendered once all checks revealed */}
      {showObservation && (
        <DecisionLogWidget
          procurementId={procurementId}
          layerKey={layer.key}
          layerTitle={layer.title}
          onProceed={onProceedToNext}
        />
      )}
    </div>
  );
}
