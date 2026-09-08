import React, { useEffect } from 'react';
import type { CheckResult } from '@/types/technical-review';
import { ProcessingLine } from './ProcessingLine';
import { CompletedLine } from './CompletedLine';
import { ResultCard } from './ResultCard';

interface CheckItemProps {
  check: CheckResult;
  isRevealing: boolean;
  isRevealed: boolean;
  onRevealComplete: () => void;
}

export function CheckItem({ check, isRevealing, isRevealed, onRevealComplete }: CheckItemProps) {
  useEffect(() => {
    if (isRevealing) {
      // Simulate presentation time for the "AI chat" effect
      const timer = setTimeout(() => {
        onRevealComplete();
      }, 1200); // 1.2s per check
      return () => clearTimeout(timer);
    }
  }, [isRevealing, onRevealComplete]);

  if (!isRevealing && !isRevealed) {
    return null; // Not reached yet
  }

  return (
    <div className="mb-4">
      {isRevealing ? (
        <ProcessingLine message={`Revealing ${check.description.toLowerCase()}...`} />
      ) : (
        <div className="animate-in fade-in slide-in-from-top-1 duration-300">
          <CompletedLine message={`${check.description}`} />
          <ResultCard check={check} />
        </div>
      )}
    </div>
  );
}
