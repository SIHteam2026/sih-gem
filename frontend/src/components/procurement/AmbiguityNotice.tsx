import React from "react";
import { HelpCircle, AlertCircle, MessageSquare } from "lucide-react";

interface AmbiguityNoticeProps {
  reason?: string | null;
  ambiguityType?: string | null;
  suggestedClarification?: string | null;
  className?: string;
}

/**
 * AmbiguityNotice
 * 
 * Visually communicates tender clause ambiguities (e.g. "adequate experience and satisfactory reputation"
 * or "completed during the last five years" without defining benchmark date).
 * Shows backend-identified reason and recommended statutory clarification questions.
 */
export default function AmbiguityNotice({
  reason,
  ambiguityType,
  suggestedClarification,
  className = "",
}: AmbiguityNoticeProps) {
  return (
    <div
      className={`p-3.5 rounded border border-purple-200 bg-[#faf8fc] text-xs text-[#2c1a3e] space-y-2.5 ${className}`}
      role="region"
      aria-label="Tender Ambiguity Notice"
    >
      <div className="flex items-center justify-between border-b border-purple-100 pb-2">
        <div className="flex items-center gap-1.5 font-semibold text-purple-900">
          <HelpCircle className="w-3.5 h-3.5 text-purple-700 shrink-0" aria-hidden="true" />
          <span className="font-mono uppercase text-[11px] tracking-wider">
            Tender Ambiguity Identified
          </span>
        </div>
        {ambiguityType && (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-purple-100 text-purple-800 border border-purple-200">
            {ambiguityType.replaceAll("_", " ")}
          </span>
        )}
      </div>

      <div className="space-y-1 text-[#3b2752]">
        <p className="leading-relaxed">
          <strong>Ambiguity Analysis:</strong>{" "}
          {reason || "The tender clause lacks an unambiguous objective threshold or explicit cutoff date."}
        </p>
      </div>

      {suggestedClarification && (
        <div className="p-2.5 rounded bg-[#f3edf7] border border-purple-200 text-[11px] space-y-1 text-[#432d5c]">
          <div className="flex items-center gap-1.5 font-semibold text-purple-950">
            <MessageSquare className="w-3 h-3 text-purple-700" aria-hidden="true" />
            <span>Suggested Clarification to Bidder / Buyer</span>
          </div>
          <p className="italic leading-relaxed">&ldquo;{suggestedClarification}&rdquo;</p>
        </div>
      )}
    </div>
  );
}
