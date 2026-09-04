import React from "react";
import { ProcurementStatus } from "@/types/procurement";

interface StatusBadgeProps {
  status: ProcurementStatus | string;
  size?: "sm" | "md";
  className?: string;
}

export default function StatusBadge({
  status,
  size = "md",
  className = "",
}: StatusBadgeProps) {
  const normalized = String(status || "").toUpperCase();

  // Distinct, accessible styles matching restrained enterprise aesthetic
  let badgeStyle = "bg-slate-100 text-slate-700 border-slate-300";
  let dotStyle = "bg-slate-400";
  const label = normalized || "UNKNOWN";

  switch (normalized) {
    case "READY":
    case "PROCESSED":
    case "EVALUATED":
      badgeStyle = "bg-emerald-50 text-emerald-800 border-emerald-300";
      dotStyle = "bg-emerald-600";
      break;
    case "PROCESSING":
    case "UNDER_REVIEW":
      badgeStyle = "bg-sky-50 text-sky-800 border-sky-300";
      dotStyle = "bg-sky-600 animate-pulse";
      break;
    case "IMPORTED":
    case "SUBMITTED":
    case "PENDING":
      badgeStyle = "bg-blue-50 text-blue-800 border-blue-200";
      dotStyle = "bg-blue-500";
      break;
    case "FAILED":
    case "REJECTED":
      badgeStyle = "bg-rose-50 text-rose-800 border-rose-300";
      dotStyle = "bg-rose-600";
      break;
    default:
      badgeStyle = "bg-stone-100 text-stone-700 border-stone-300";
      dotStyle = "bg-stone-400";
      break;
  }

  const padding = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium border rounded ${padding} ${badgeStyle} ${className}`}
      role="status"
      aria-label={`Status: ${label.replaceAll("_", " ")}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dotStyle}`} aria-hidden="true" />
      <span className="tracking-wide uppercase">{label.replaceAll("_", " ")}</span>
    </span>
  );
}
