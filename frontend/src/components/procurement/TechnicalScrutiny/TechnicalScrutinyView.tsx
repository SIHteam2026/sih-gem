import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import type { TechnicalReviewResponse } from '@/types/technical-review';
import { TechnicalLayerSection } from './TechnicalLayerSection';

interface TechnicalScrutinyViewProps {
  data: TechnicalReviewResponse;
  projectName: string;
  projectRef: string;
}

export function TechnicalScrutinyView({ data, projectName, projectRef }: TechnicalScrutinyViewProps) {
  const [activeLayerIndex, setActiveLayerIndex] = useState(0);
  const [isFullyComplete, setIsFullyComplete] = useState(false);

  const router = useRouter();

  const handleProceedToNext = () => {
    if (activeLayerIndex < data.layers.length - 1) {
      setActiveLayerIndex(prev => prev + 1);
    } else {
      setIsFullyComplete(true);
    }
  };

  return (
    <div className="min-h-screen bg-white text-[#162333] font-sans">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white/90 backdrop-blur-md border-b border-slate-100 py-6 px-8">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest bg-slate-100 text-slate-500 uppercase">
                {projectRef}
              </span>
              <span className="text-xs font-semibold text-slate-400 tracking-wider uppercase">
                Technical Scrutiny · Cover 1
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#0f172a]">
              {projectName}
            </h1>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-5xl mx-auto px-8 py-12">
        <div className="relative">
          {/* Vertical progress line hint (optional visual) */}
          <div className="absolute left-[13px] top-4 bottom-0 w-px bg-slate-100 -z-10" />
          
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

        {/* Completion Summary */}
        {isFullyComplete && (
          <div className="mt-16 border-t border-slate-200 pt-12 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <h3 className="text-lg font-bold mb-6">TECHNICAL SCRUTINY COMPLETE</h3>
            
            <div className="flex gap-4">
              {data.canOpenCover2 ? (
                <div className="space-y-4">
                  <p className="text-sm text-slate-600">
                    Technical evaluation frozen. Financial evaluation is ready for eligible bidders.
                  </p>
                  <button 
                    onClick={() => {
                      router.push(`/procurements/${data.procurementId}/financial-evaluation`);
                    }}
                    className="inline-flex items-center justify-center px-6 py-3 bg-[#0f172a] text-white text-sm font-medium rounded-full transition-colors hover:bg-black"
                  >
                    Open Cover 2
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  <p className="text-sm text-slate-600">
                    Technical scrutiny is complete, but Cover 2 cannot be opened yet.
                    {data.freezeReady === false && " Technical evaluation is not frozen due to pending blockers."}
                  </p>
                  <button disabled className="inline-flex items-center justify-center px-6 py-3 bg-slate-200 text-slate-400 text-sm font-medium rounded-full cursor-not-allowed">
                    Open Cover 2 (Blocked)
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
