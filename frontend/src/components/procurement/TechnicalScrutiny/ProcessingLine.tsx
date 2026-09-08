import React from 'react';
import { Loader2 } from 'lucide-react';

interface ProcessingLineProps {
  message: string;
}

export function ProcessingLine({ message }: ProcessingLineProps) {
  return (
    <div className="flex items-center gap-3 text-[#64748b] text-sm animate-pulse py-2">
      <Loader2 className="w-4 h-4 animate-spin text-[#94a3b8]" />
      <span className="font-medium tracking-wide">{message}</span>
    </div>
  );
}
