import React, { useEffect, useRef } from 'react';
import type { CheckResult } from '@/types/technical-review';
import { ProcessingLine } from './ProcessingLine';
import { CompletedLine } from './CompletedLine';
import { ResultCard } from './ResultCard';

interface CheckItemProps {
  check: CheckResult;
  isRevealing: boolean; // This check is currently being "examined" (presentation effect)
  isRevealed: boolean;  // This check result is fully shown
  onRevealComplete: () => void;
  /** Delay in ms before transitioning from processing → result (presentation only) */
  revealDelay?: number;
}

/**
 * Renders a single verification check with a two-phase presentation:
 *
 * Phase 1 — Processing (presentation effect only):
 *   Shows a spinner and a purposeful status message.
 *   This is a sequential reveal of batch results — NOT a separate backend call.
 *
 * Phase 2 — Revealed:
 *   Shows the permanent result with canonical status, structured fields,
 *   and evidence provenance from the backend.
 */
export function CheckItem({
  check,
  isRevealing,
  isRevealed,
  onRevealComplete,
  revealDelay = 1100,
}: CheckItemProps) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (isRevealing) {
      timerRef.current = setTimeout(() => {
        onRevealComplete();
      }, revealDelay);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isRevealing, revealDelay, onRevealComplete]);

  if (!isRevealing && !isRevealed) return null;

  // Build a purposeful processing message from the check description.
  // These are descriptive labels — not claims about live backend execution.
  const processingMessage = buildProcessingMessage(check.description);

  return (
    <div className="mb-5">
      {isRevealing ? (
        <ProcessingLine message={processingMessage} />
      ) : (
        <div className="animate-in fade-in slide-in-from-top-1 duration-300">
          <CompletedLine message={check.description} />
          <ResultCard check={check} />
        </div>
      )}
    </div>
  );
}

/**
 * Generates a contextually appropriate examining message.
 * These describe what Opal is doing conceptually, not implying separate API calls.
 */
function buildProcessingMessage(description: string): string {
  const desc = description.toLowerCase();

  if (desc.includes('gst') || desc.includes('tax') || desc.includes('registration')) {
    return 'Validating external registration record…';
  }
  if (desc.includes('document') || desc.includes('integrity') || desc.includes('hash')) {
    return 'Reading submitted evidence…';
  }
  if (desc.includes('pan') || desc.includes('identity') || desc.includes('director')) {
    return 'Cross-checking identity record…';
  }
  if (desc.includes('collusion') || desc.includes('related') || desc.includes('common')) {
    return 'Analysing bidder relationships…';
  }
  if (desc.includes('turnover') || desc.includes('financial') || desc.includes('balance')) {
    return 'Comparing financial evidence…';
  }
  if (desc.includes('experience') || desc.includes('past') || desc.includes('capacity')) {
    return 'Reviewing past performance evidence…';
  }
  if (desc.includes('blacklist') || desc.includes('debarment') || desc.includes('sanction')) {
    return 'Checking debarment registers…';
  }
  if (desc.includes('specification') || desc.includes('technical') || desc.includes('requirement')) {
    return 'Comparing requirement and evidence…';
  }

  return 'Examining submitted evidence…';
}
