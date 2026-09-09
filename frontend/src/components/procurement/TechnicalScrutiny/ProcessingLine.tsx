import React from 'react';
import { Loader2 } from 'lucide-react';

interface ProcessingLineProps {
  message: string;
}

/**
 * Transient processing indicator shown during sequential check reveal.
 *
 * This is a presentation effect for batch results returned by the backend.
 * It does NOT represent a live backend call in progress.
 */
export function ProcessingLine({ message }: ProcessingLineProps) {
  return (
    <div className="flex items-center gap-3 text-[#64748b] text-sm py-2.5">
      <Loader2 className="w-4 h-4 animate-spin text-[#94a3b8] shrink-0" />
      <span className="font-medium tracking-wide">{message}</span>
    </div>
  );
}
