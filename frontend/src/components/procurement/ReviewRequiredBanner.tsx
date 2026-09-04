import React from "react";
import { ShieldCheck, AlertCircle, Info } from "lucide-react";

interface ReviewRequiredBannerProps {
  reviewRequired: boolean;
  reviewCount: number;
  totalEvaluated: number;
  contradictionCount?: number;
  unverifiedCount?: number;
}

/**
 * ReviewRequiredBanner
 * 
 * Formal human-in-the-loop review boundary banner.
 * Clearly articulates that OPAL's machine evaluation is a decision-support layer,
 * and highlights items requiring procurement officer scrutiny.
 * Deliberately contains NO automatic qualification or award decision buttons.
 */
export default function ReviewRequiredBanner({
  reviewRequired,
  reviewCount,
  totalEvaluated,
  contradictionCount = 0,
  unverifiedCount = 0,
}: ReviewRequiredBannerProps) {
  if (reviewRequired || reviewCount > 0 || contradictionCount > 0) {
    return (
      <div
        className="p-5 rounded border border-amber-300 bg-[#fffdf7] text-xs text-[#2b2618] space-y-3"
        role="region"
        aria-label="Officer Review Notice"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-amber-200/80 pb-3">
          <div className="flex items-center gap-2 font-semibold text-amber-950 text-sm">
            <AlertCircle className="w-4 h-4 text-amber-700 shrink-0" aria-hidden="true" />
            <span>Procurement Officer Review Required</span>
          </div>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-900 border border-amber-300">
            {reviewCount} item{reviewCount === 1 ? "" : "s"} need attention
          </span>
        </div>

        <p className="leading-relaxed text-[#4a3f28]">
          Automated evaluation has identified{" "}
          <strong>
            {reviewCount} requirement{reviewCount === 1 ? "" : "s"}
          </strong>{" "}
          with ambiguous tender clauses, conflicting evidence documents, or borderline conditions.
          {contradictionCount > 0 && (
            <span>
              {" "}
              Additionally, <strong>{contradictionCount} evidence contradiction{contradictionCount === 1 ? "" : "s"}</strong>{" "}
              warrant scrutiny.
            </span>
          )}
        </p>

        <div className="flex items-start gap-2 pt-1 text-[11px] text-[#6b5c3e]">
          <Info className="w-3.5 h-3.5 text-amber-700 shrink-0 mt-0.5" aria-hidden="true" />
          <span>
            <strong>Decision-Support Notice:</strong> OPAL provides deterministic rule evaluation and contradiction reconciliation to assist the procurement officer. The officer retains full statutory authority to inspect evidence provenance and record the official qualification determination.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      className="p-4 rounded border border-[#ccdbe4] bg-[#f2f7fa] text-xs text-[#203a52] space-y-2"
      role="region"
      aria-label="Evaluation Completed Notice"
    >
      <div className="flex items-center gap-2 font-semibold text-[#163a5f] text-sm">
        <ShieldCheck className="w-4 h-4 text-[#163a5f] shrink-0" aria-hidden="true" />
        <span>Machine Analysis Complete — All {totalEvaluated} Requirements Evaluated</span>
      </div>
      <p className="leading-relaxed text-[#445b70]">
        Deterministic verification and evidence extraction completed without unresolved contradictions.
        {unverifiedCount > 0 && (
          <span> Note: {unverifiedCount} requirement(s) remain unverified due to missing evidence.</span>
        )}
      </p>
    </div>
  );
}
