import React, { useState } from 'react';
import { ArrowRight, Check } from 'lucide-react';
import { saveOfficerObservation } from '@/services/api/technical-review';

interface DecisionLogWidgetProps {
  procurementId: string;
  layerKey: string;
  onProceed: () => void;
}

export function DecisionLogWidget({ procurementId, layerKey, onProceed }: DecisionLogWidgetProps) {
  const [observation, setObservation] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleProceed = async () => {
    setIsSaving(true);
    setError(null);
    try {
      await saveOfficerObservation({
        procurementId,
        layerKey,
        observation: observation.trim()
      });
      setIsSaved(true);
      // Give a brief moment to show saved state before transitioning
      setTimeout(() => {
        onProceed();
      }, 600);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save observation. Backend endpoint may not be ready.';
      setError(message);
      setIsSaving(false);
    }
  };

  if (isSaved) {
    return (
      <div className="flex items-center gap-2 text-sm text-[#059669] py-3 bg-[#ecfdf5] px-4 rounded-md border border-[#a7f3d0] mt-4 ml-auto w-full lg:w-80">
        <Check className="w-4 h-4" />
        <span className="font-medium">Officer observation saved</span>
      </div>
    );
  }

  return (
    <div className="mt-8 flex flex-col items-end">
      {/* 
        On large screens: this widget can float to the right side of the main content column.
        We achieve this using layout techniques in the parent. Here we just set max-w.
      */}
      <div className="w-full lg:w-96 bg-white border border-[#e2e8f0] shadow-sm rounded-xl p-5 relative lg:-mr-16 xl:-mr-32">
        <h4 className="text-xs font-semibold tracking-wider text-[#64748b] mb-3 uppercase">
          Officer Observation
        </h4>
        <textarea
          value={observation}
          onChange={(e) => setObservation(e.target.value)}
          placeholder="Enter observation or notes for this level..."
          className="w-full text-sm p-3 border border-[#cbd5e1] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#94a3b8] focus:border-transparent min-h-[100px] resize-y mb-4"
          disabled={isSaving}
        />
        {error && (
          <div className="text-xs text-red-600 mb-3 bg-red-50 p-2 rounded">
            {error}
          </div>
        )}
      </div>
      
      <div className="w-full mt-4 flex justify-start">
        <button
          onClick={handleProceed}
          disabled={isSaving || !observation.trim()}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#162333] hover:bg-[#2b3a4a] text-white text-sm font-medium rounded-full transition-colors disabled:opacity-50"
        >
          {isSaving ? 'Saving...' : 'Proceed to Next Scrutiny'}
          {!isSaving && <ArrowRight className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}
