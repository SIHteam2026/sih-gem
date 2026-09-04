import React from "react";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  MinusCircle,
} from "lucide-react";
import { ComplianceState } from "@/types/procurement";

interface ComplianceStateBadgeProps {
  state: ComplianceState | string;
  size?: "sm" | "md" | "lg";
  className?: string;
  showIcon?: boolean;
}

/**
 * Canonical ComplianceStateBadge
 * 
 * Accurately displays the canonical backend compliance outcome states:
 * - PASS: Criteria met deterministically & unambiguously
 * - FAIL: Deterministic criteria failure or violation
 * - REVIEW: Ambiguity, contradiction, or threshold needing human officer judgment
 * - UNVERIFIED: Missing, unextracted, or unconfirmed proof (distinct from FAIL)
 * - NOT_APPLICABLE: Authorized exemption (e.g. MSE / Startup waiver)
 */
export default function ComplianceStateBadge({
  state,
  size = "md",
  className = "",
  showIcon = true,
}: ComplianceStateBadgeProps) {
  let normalized = String(state || "").toUpperCase().trim();

  // Normalize legacy aliases
  if (normalized === "VERIFIED" || normalized === "COMPLIANT") {
    normalized = "PASS";
  } else if (normalized === "NON_COMPLIANT" || normalized === "REJECTED") {
    normalized = "FAIL";
  } else if (normalized === "REVIEW_REQUIRED" || normalized === "NEEDS_REVIEW") {
    normalized = "REVIEW";
  }

  let badgeStyle = "bg-stone-100 text-stone-700 border-stone-300";
  let label = normalized || "UNSPECIFIED";
  let IconComponent = HelpCircle;

  switch (normalized) {
    case "PASS":
      badgeStyle = "bg-emerald-50 text-emerald-900 border-emerald-300 font-semibold";
      label = "PASS";
      IconComponent = CheckCircle2;
      break;
    case "FAIL":
      badgeStyle = "bg-rose-50 text-rose-900 border-rose-300 font-semibold";
      label = "FAIL";
      IconComponent = XCircle;
      break;
    case "REVIEW":
      badgeStyle = "bg-amber-50 text-amber-950 border-amber-400 font-semibold";
      label = "REVIEW";
      IconComponent = AlertTriangle;
      break;
    case "UNVERIFIED":
      // Distinct dashed border and muted stone styling - clearly distinguished from FAIL
      badgeStyle = "bg-stone-50 text-stone-700 border-stone-400 border-dashed font-medium";
      label = "UNVERIFIED";
      IconComponent = HelpCircle;
      break;
    case "NOT_APPLICABLE":
      badgeStyle = "bg-slate-50 text-slate-700 border-slate-300 font-medium";
      label = "NOT APPLICABLE";
      IconComponent = MinusCircle;
      break;
    default:
      badgeStyle = "bg-stone-100 text-stone-700 border-stone-300 font-medium";
      label = normalized.replaceAll("_", " ");
      IconComponent = HelpCircle;
      break;
  }

  const padding =
    size === "sm"
      ? "px-2 py-0.5 text-[11px]"
      : size === "lg"
      ? "px-3.5 py-1.5 text-xs tracking-wide"
      : "px-2.5 py-1 text-xs";

  const iconSize =
    size === "sm" ? "w-3 h-3" : size === "lg" ? "w-4 h-4" : "w-3.5 h-3.5";

  return (
    <span
      className={`inline-flex items-center gap-1.5 border rounded ${padding} ${badgeStyle} ${className}`}
      role="status"
      aria-label={`Compliance State: ${label}`}
    >
      {showIcon && <IconComponent className={`${iconSize} shrink-0`} aria-hidden="true" />}
      <span className="tracking-wide uppercase font-mono">{label}</span>
    </span>
  );
}
