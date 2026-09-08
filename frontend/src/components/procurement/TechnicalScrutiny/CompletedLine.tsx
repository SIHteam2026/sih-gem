import React from 'react';
import { Check } from 'lucide-react';

interface CompletedLineProps {
  message: string;
}

export function CompletedLine({ message }: CompletedLineProps) {
  return (
    <div className="flex items-center gap-3 py-2 text-[#162333] transition-opacity duration-500 ease-in opacity-100">
      <Check className="w-4 h-4 text-[#059669]" />
      <span className="font-medium text-sm">{message}</span>
    </div>
  );
}
