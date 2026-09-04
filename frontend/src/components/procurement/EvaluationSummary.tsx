import React from "react";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  MinusCircle,
  BarChart3,
  Layers,
} from "lucide-react";
import { ComplianceState } from "@/types/procurement";

interface EvaluationSummaryProps {
  totalRequirements: number;
  stateCounts: Record<string, number>;
  reviewRequired: boolean;
  reviewRequiredCount?: number;
  unresolvedContradictions?: number;
  unverifiedCount?: number;
  selectedFilter?: string | null;
  onFilterSelect?: (state: string | null) => void;
}

/**
 * EvaluationSummary
 * 
 * Non-authoritative machine evaluation summary displaying requirement outcome distribution.
 * Preserves the core product principle: It presents facts and counts without asserting
 * autonomous "Bidder Qualified" or "Bidder Rejected" decisions.
 */
export default function EvaluationSummary({
  totalRequirements,
  stateCounts,
  reviewRequired,
  reviewRequiredCount = 0,
  unresolvedContradictions = 0,
  unverifiedCount = 0,
  selectedFilter = null,
  onFilterSelect,
}: EvaluationSummaryProps) {
  const passCount =
    (stateCounts["PASS"] || 0) + (stateCounts["VERIFIED"] || 0) + (stateCounts["COMPLIANT"] || 0);
  const failCount =
    (stateCounts["FAIL"] || 0) + (stateCounts["NON_COMPLIANT"] || 0) + (stateCounts["REJECTED"] || 0);
  const reviewCount =
    (stateCounts["REVIEW"] || 0) + (stateCounts["REVIEW_REQUIRED"] || 0);
  const unverifiedTotal =
    (stateCounts["UNVERIFIED"] || 0) || unverifiedCount;
  const notApplicableCount = stateCounts["NOT_APPLICABLE"] || 0;

  const cards = [
    {
      key: "PASS",
      label: "PASS",
      count: passCount,
      icon: CheckCircle2,
      textColor: "text-emerald-900",
      bgColor: "bg-emerald-50/70",
      borderColor: "border-emerald-300",
      activeStyle: "ring-2 ring-emerald-600 bg-emerald-100",
      desc: "Met criteria",
    },
    {
      key: "FAIL",
      label: "FAIL",
      count: failCount,
      icon: XCircle,
      textColor: "text-rose-900",
      bgColor: "bg-rose-50/70",
      borderColor: "border-rose-300",
      activeStyle: "ring-2 ring-rose-600 bg-rose-100",
      desc: "Violations / deficits",
    },
    {
      key: "REVIEW",
      label: "REVIEW",
      count: reviewCount,
      icon: AlertTriangle,
      textColor: "text-amber-950",
      bgColor: "bg-amber-50/80",
      borderColor: "border-amber-400",
      activeStyle: "ring-2 ring-amber-600 bg-amber-100",
      desc: "Officer review needed",
    },
    {
      key: "UNVERIFIED",
      label: "UNVERIFIED",
      count: unverifiedTotal,
      icon: HelpCircle,
      textColor: "text-stone-800",
      bgColor: "bg-stone-50/80",
      borderColor: "border-stone-400 border-dashed",
      activeStyle: "ring-2 ring-stone-600 bg-stone-100",
      desc: "Evidence missing",
    },
    {
      key: "NOT_APPLICABLE",
      label: "NOT APPLICABLE",
      count: notApplicableCount,
      icon: MinusCircle,
      textColor: "text-slate-800",
      bgColor: "bg-slate-50/70",
      borderColor: "border-slate-300",
      activeStyle: "ring-2 ring-slate-600 bg-slate-100",
      desc: "Exemption waived",
    },
  ];

  return (
    <div className="space-y-4" aria-label="Evaluation Summary Breakdown">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#d9ddd9] pb-3">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-[#163a5f]" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-[#162333]">
            Evaluation Findings Summary
          </h2>
        </div>
        <div className="flex items-center gap-3 text-xs text-[#5a6a77] font-mono">
          <span>{totalRequirements} Requirements Evaluated</span>
          {unresolvedContradictions > 0 && (
            <>
              <span>•</span>
              <span className="text-amber-800 font-semibold">
                {unresolvedContradictions} Contradiction{unresolvedContradictions === 1 ? "" : "s"}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Metric Cards Grid with Interactive Filtering */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {cards.map((card) => {
          const Icon = card.icon;
          const isSelected = selectedFilter === card.key;
          return (
            <button
              key={card.key}
              type="button"
              onClick={() => {
                if (onFilterSelect) {
                  onFilterSelect(isSelected ? null : card.key);
                }
              }}
              className={`p-3.5 rounded border text-left transition-all ${card.bgColor} ${
                card.borderColor
              } ${isSelected ? card.activeStyle : "hover:border-slate-400"} ${
                onFilterSelect ? "cursor-pointer" : "cursor-default"
              }`}
              aria-pressed={isSelected}
              aria-label={`Filter by ${card.label}: ${card.count} items`}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] uppercase font-bold font-mono tracking-wider text-[#556675]">
                  {card.label}
                </span>
                <Icon className={`w-3.5 h-3.5 ${card.textColor}`} aria-hidden="true" />
              </div>
              <div className="mt-2 flex items-baseline gap-1.5">
                <span className={`text-2xl font-bold font-mono ${card.textColor}`}>
                  {card.count}
                </span>
                <span className="text-[10px] text-[#6b7b8a]">/ {totalRequirements}</span>
              </div>
              <p className="text-[10px] text-[#556677] mt-0.5 truncate">{card.desc}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
