import React, { useState } from 'react';
import { ArrowRight, CheckCircle, AlertCircle, Info } from 'lucide-react';
import { saveOfficerObservation } from '@/services/api/technical-review';

interface DecisionLogWidgetProps {
  procurementId: string;
  layerKey: string;
  layerTitle: string;
  onProceed: (observationText: string, persisted: boolean) => void;
}

type SaveState = 'idle' | 'saving' | 'persisted' | 'unavailable' | 'error';

/**
 * Officer Observation widget shown after all checks in a layer are revealed.
 *
 * Observation is OPTIONAL — the officer may proceed without recording one.
 * If an observation is entered, the canonical backend endpoint is called.
 * The true persistence state is always reported accurately:
 *   - "Saved to procurement record" — backend returned 200
 *   - "Backend unavailable — observation not persisted" — backend returned 404
 *   - Error message — any other backend error
 *
 * This widget never claims persistence when it did not occur.
 */
export function DecisionLogWidget({
  procurementId,
  layerKey,
  layerTitle,
  onProceed,
}: DecisionLogWidgetProps) {
  const [observation, setObservation] = useState('');
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDone, setIsDone] = useState(false);

  const handleProceed = async () => {
    const trimmed = observation.trim();

    if (trimmed) {
      // Attempt to persist the observation
      setSaveState('saving');
      setErrorMessage(null);
      try {
        const result = await saveOfficerObservation({
          procurementId,
          layerKey,
          observation: trimmed,
        });

        if (result === 'persisted') {
          setSaveState('persisted');
          setIsDone(true);
          setTimeout(() => onProceed(trimmed, true), 600);
        } else {
          // 'unavailable' — backend returned 404
          setSaveState('unavailable');
          // Still allow proceeding after a moment — observation is local-only
          setIsDone(true);
          setTimeout(() => onProceed(trimmed, false), 800);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setSaveState('error');
        setErrorMessage(msg);
        // Do NOT proceed automatically on backend error — officer must acknowledge
      }
    } else {
      // No observation entered — proceed without saving
      setIsDone(true);
      onProceed('', false);
    }
  };

  // Save-state feedback banner
  const SaveFeedback = () => {
    if (saveState === 'persisted') {
      return (
        <div className="flex items-center gap-2 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-2 rounded-md">
          <CheckCircle className="w-4 h-4 shrink-0" />
          <span className="font-medium">Saved to procurement record.</span>
        </div>
      );
    }
    if (saveState === 'unavailable') {
      return (
        <div className="flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 px-3 py-2 rounded-md">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>
            <span className="font-medium">Observation endpoint unavailable.</span>{' '}
            Your note is recorded locally but has not been persisted to the procurement record.
          </span>
        </div>
      );
    }
    if (saveState === 'error') {
      return (
        <div className="flex items-center gap-2 text-sm text-red-700 bg-red-50 border border-red-200 px-3 py-2 rounded-md">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>
            <span className="font-medium">Save failed:</span> {errorMessage}
          </span>
        </div>
      );
    }
    return null;
  };

  if (isDone && saveState !== 'error') {
    return null; // Collapsed — parent layer takes over
  }

  return (
    <div className="mt-8 space-y-4">
      {/* Divider */}
      <div className="flex items-center gap-3">
        <div className="flex-1 h-px bg-slate-100" />
        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
          Officer Observation — {layerTitle}
        </span>
        <div className="flex-1 h-px bg-slate-100" />
      </div>

      <div className="bg-slate-50 rounded-xl border border-slate-100 p-5">
        <div className="flex items-start gap-2 mb-3">
          <Info className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
          <p className="text-xs text-slate-400 leading-relaxed">
            Record an observation for this layer checkpoint. This is optional — you may
            proceed without entering a note. Observations are saved to the procurement
            record and visible in the audit trail.
          </p>
        </div>

        <textarea
          value={observation}
          onChange={(e) => setObservation(e.target.value)}
          placeholder="e.g. Document appears acceptable; retain for committee record."
          className="w-full text-sm p-3 border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-slate-300 focus:border-transparent min-h-[90px] resize-y placeholder:text-slate-300"
          disabled={saveState === 'saving'}
        />

        <SaveFeedback />

        {saveState === 'error' && (
          <p className="mt-2 text-xs text-slate-500">
            You can retry saving, or proceed without saving the observation.
          </p>
        )}
      </div>

      {/* Proceed button — always available, observation is optional */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleProceed}
          disabled={saveState === 'saving'}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0f172a] hover:bg-[#1e293b] text-white text-sm font-medium rounded-full transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saveState === 'saving' ? (
            'Saving observation…'
          ) : (
            <>
              Proceed to Next Scrutiny
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>

        {saveState === 'error' && (
          <button
            onClick={() => {
              setSaveState('idle');
              setErrorMessage(null);
            }}
            className="text-sm text-slate-500 underline hover:text-slate-700"
          >
            Proceed without saving
          </button>
        )}
      </div>
    </div>
  );
}
