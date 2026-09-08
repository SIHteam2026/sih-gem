import React, { useState, useEffect } from 'react';
import type { TechnicalLayer } from '@/types/technical-review';
import { CheckItem } from './CheckItem';
import { DecisionLogWidget } from './DecisionLogWidget';

interface TechnicalLayerSectionProps {
  layer: TechnicalLayer;
  procurementId: string;
  isActive: boolean; // Is this the currently active layer in the scrutiny flow
  isCompleted: boolean; // Has this layer been fully completed and proceeded past
  onProceedToNext: () => void;
}

export function TechnicalLayerSection({ layer, procurementId, isActive, isCompleted, onProceedToNext }: TechnicalLayerSectionProps) {
  // Reveal state tracks how many checks have been revealed.
  const [revealedCount, setRevealedCount] = useState(isCompleted ? layer.checks.length : 0);
  
  // If we just became active, start revealing the first check.
  useEffect(() => {
    if (isActive && !isCompleted && revealedCount === 0 && layer.checks.length > 0) {
      // Small delay before starting
      const timer = setTimeout(() => {
        // Just trigger the first check revealing
        // The CheckItem component handles its own timing
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isActive, isCompleted, revealedCount, layer.checks.length]);

  const handleRevealComplete = () => {
    setRevealedCount(prev => prev + 1);
  };

  if (!isActive && !isCompleted) return null;

  const allChecksRevealed = revealedCount >= layer.checks.length;
  const showDecisionLog = isActive && !isCompleted && allChecksRevealed;

  return (
    <div className={`mb-16 transition-opacity duration-700 ${isCompleted ? 'opacity-80' : 'opacity-100'}`}>
      <div className="mb-6">
        <h3 className="text-2xl font-bold tracking-tight text-[#111827] mb-1">
          {layer.title}
        </h3>
        <p className="text-xs font-mono text-[#64748b] tracking-wider uppercase">
          {layer.key.replace(/_/g, ' ')}
        </p>
      </div>

      <div className="relative pl-2">
        {layer.checks.map((check, idx) => {
          const isCheckRevealing = isActive && !isCompleted && idx === revealedCount;
          const isCheckRevealed = idx < revealedCount;
          
          return (
            <CheckItem 
              key={check.id} 
              check={check} 
              isRevealing={isCheckRevealing}
              isRevealed={isCheckRevealed}
              onRevealComplete={handleRevealComplete}
            />
          );
        })}
      </div>

      {showDecisionLog && (
        <DecisionLogWidget 
          procurementId={procurementId}
          layerKey={layer.key}
          onProceed={onProceedToNext}
        />
      )}
      
      {/* Historical observation representation (stubbed here, actual data would come from backend) */}
      {isCompleted && (
        <div className="mt-6 flex items-center gap-2 text-sm text-[#64748b] py-2 border-t border-slate-100">
          <span className="w-1.5 h-1.5 rounded-full bg-[#cbd5e1]" />
          <span>Officer observation recorded for this stage</span>
        </div>
      )}
    </div>
  );
}
