import React from "react";
import { Database } from "lucide-react";

interface SourceBadgeProps {
  source?: string | null;
  className?: string;
}

export default function SourceBadge({ source, className = "" }: SourceBadgeProps) {
  const raw = String(source || "EXTERNAL").trim();
  let displayName = raw;

  if (raw === "MOCK_GEM") {
    displayName = "Mock-GeM";
  } else if (raw === "REAL_GEM" || raw === "GEM") {
    displayName = "GeM";
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono font-medium border bg-[#fbfbf9] text-[#556370] border-[#d8dcda] ${className}`}
      title={`Data source: ${displayName}`}
    >
      <Database className="w-3 h-3 text-[#798894]" aria-hidden="true" />
      <span>Source · {displayName}</span>
    </span>
  );
}
