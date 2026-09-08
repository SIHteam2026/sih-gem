import React from 'react';
import type { CheckResult } from '@/types/technical-review';

interface ResultCardProps {
  check: CheckResult;
}

const statusMap = {
  PASS: { label: 'CLEARED', color: 'text-[#059669]', bg: 'bg-[#ecfdf5]', border: 'border-[#a7f3d0]' },
  FAIL: { label: 'ATTENTION', color: 'text-[#e11d48]', bg: 'bg-[#fff1f2]', border: 'border-[#fecdd3]' },
  REVIEW: { label: 'REVIEW', color: 'text-[#d97706]', bg: 'bg-[#fffbeb]', border: 'border-[#fde68a]' },
  UNVERIFIED: { label: 'UNVERIFIED', color: 'text-[#475569]', bg: 'bg-[#f1f5f9]', border: 'border-[#cbd5e1]' },
  NOT_APPLICABLE: { label: 'NOT APPLICABLE', color: 'text-[#64748b]', bg: 'bg-[#f8fafc]', border: 'border-[#e2e8f0]' },
};

export function ResultCard({ check }: ResultCardProps) {
  const style = statusMap[check.status] || statusMap.UNVERIFIED;

  return (
    <div className={`mt-3 ml-7 rounded-lg border ${style.border} ${style.bg} p-4 max-w-2xl`}>
      <div className="flex items-center justify-between mb-2">
        <span className={`text-[11px] font-bold tracking-wider ${style.color}`}>
          {style.label}
        </span>
      </div>
      <p className="text-sm text-[#334155] leading-relaxed">
        {check.synthesis || check.description}
      </p>
      
      {check.evidenceRefs && check.evidenceRefs.length > 0 && (
        <div className="mt-3 pt-3 border-t border-black/5">
          <h5 className="text-[10px] uppercase font-semibold text-[#64748b] mb-1.5">Evidence Provenance</h5>
          <ul className="space-y-1.5">
            {check.evidenceRefs.map((ref, idx) => (
              <li key={idx} className="text-xs text-[#475569] flex gap-2">
                <span className="opacity-50">↳</span>
                <span>
                  <span className="font-medium text-[#1e293b]">Doc: {ref.documentId}</span>
                  {ref.page !== undefined && <span className="ml-1 opacity-75">(Page {ref.page})</span>}
                  {ref.snippet && <span className="ml-2 italic text-[#64748b]">&quot;{ref.snippet}&quot;</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
