import React from "react";
import { AlertCircle, FileSearch, Sparkles } from "lucide-react";
import { TenderRequirement, StructuredCondition } from "@/types/procurement";

interface RequirementCardProps {
  requirement: TenderRequirement;
  index?: number;
  className?: string;
}

function formatCondition(condition?: StructuredCondition | null): string | null {
  if (!condition) return null;

  const parts: string[] = [];

  // Formatted operator and threshold
  const op = condition.operator;
  const val = condition.threshold_value;
  const unit = condition.unit || "";
  const curr = condition.currency;

  let valueFormatted = "";
  if (val !== undefined && val !== null) {
    if (typeof val === "number") {
      if (curr === "INR" || condition.metric?.includes("TURNOVER") || condition.metric?.includes("VALUE")) {
        valueFormatted = `₹${val.toLocaleString("en-IN")}`;
      } else if (unit === "PERCENT" || unit === "%") {
        valueFormatted = `${val}%`;
      } else {
        valueFormatted = `${val}${unit ? " " + unit : ""}`;
      }
    } else {
      valueFormatted = String(val);
      if (unit && !valueFormatted.includes(unit)) {
        valueFormatted += ` ${unit}`;
      }
    }
  }

  let label = "";
  if (op === ">=" || op === ">") {
    label = "Minimum:";
  } else if (op === "<=" || op === "<") {
    label = "Maximum:";
  } else if (op === "==" || op === "=") {
    label = "Required:";
  } else if (op) {
    label = `${op}:`;
  }

  if (label && valueFormatted) {
    parts.push(`${label} ${valueFormatted}`);
  } else if (valueFormatted) {
    parts.push(`Threshold: ${valueFormatted}`);
  }

  if (condition.period_description) {
    parts.push(`(${condition.period_description})`);
  } else if (condition.period_years) {
    parts.push(`(over past ${condition.period_years} years)`);
  }

  return parts.length > 0 ? parts.join(" ") : null;
}

function formatCategory(category: string): string {
  return category
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function RequirementCard({
  requirement,
  index,
  className = "",
}: RequirementCardProps) {
  const reqId = requirement.requirement_id || `REQ-${(index ?? 0) + 1}`;
  const title = requirement.title || formatCategory(requirement.category);
  const conditionText = formatCondition(requirement.structured_condition);

  // Provenance formatting
  const prov = requirement.source_provenance;
  const provItems: string[] = [];
  if (prov?.page_number) provItems.push(`Page ${prov.page_number}`);
  if (prov?.clause_number) provItems.push(prov.clause_number);
  if (prov?.section_title) provItems.push(prov.section_title);
  const provenanceText = provItems.join(" · ");

  // Ambiguity flag
  const isAmbiguous = Boolean(requirement.is_ambiguous || requirement.ambiguity?.is_ambiguous);
  const ambiguityReason = requirement.ambiguity_reason || requirement.ambiguity?.ambiguity_reason;
  const ambiguityType = requirement.ambiguity?.ambiguity_type;

  return (
    <article
      className={`p-5 rounded border border-[#d9ddd9] bg-[#fffefa] hover:border-[#b8c6d1] transition-all space-y-3.5 ${className}`}
      aria-labelledby={`req-title-${reqId}`}
    >
      {/* Header: ID, Category & Mandatory status */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#e7eae7] pb-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-[#163a5f] text-white">
            {reqId}
          </span>
          <span className="text-xs font-semibold text-[#445564] uppercase tracking-wider">
            {formatCategory(requirement.category)}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {requirement.mandatory ? (
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-amber-50 text-amber-900 border border-amber-200">
              Mandatory
            </span>
          ) : (
            <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-slate-50 text-slate-700 border border-slate-200">
              Optional / Desirable
            </span>
          )}
        </div>
      </div>

      {/* Title & Description */}
      <div>
        <h3 id={`req-title-${reqId}`} className="text-sm font-semibold text-[#162333]">
          {title}
        </h3>
        <p className="mt-1 text-xs leading-relaxed text-[#51616e]">
          {requirement.description}
        </p>
      </div>

      {/* Structured Condition Badge (Formatted, non-JSON) */}
      {conditionText && (
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded bg-[#f4f7f9] border border-[#d3dfe7] text-xs font-medium text-[#1c3f60]">
          <Sparkles className="w-3.5 h-3.5 text-[#20517d]" aria-hidden="true" />
          <span>{conditionText}</span>
        </div>
      )}

      {/* Provenance Tag */}
      {provenanceText && (
        <div className="flex items-start gap-1.5 text-[11px] text-[#697885] pt-1">
          <FileSearch className="w-3.5 h-3.5 text-[#7c8b98] shrink-0 mt-0.5" aria-hidden="true" />
          <span>
            Source: <strong className="font-medium text-[#3b4b59]">{provenanceText}</strong>
          </span>
        </div>
      )}

      {/* Ambiguity Radar Alert */}
      {isAmbiguous && (
        <div className="p-3 rounded border border-[#efd6b8] bg-[#fffaf4] text-[#824b1f] text-xs space-y-1">
          <div className="flex items-center gap-1.5 font-semibold">
            <AlertCircle className="w-3.5 h-3.5 text-[#b06122]" aria-hidden="true" />
            <span>
              Ambiguity Radar
              {ambiguityType ? `: ${ambiguityType.replaceAll("_", " ")}` : ""}
            </span>
          </div>
          {ambiguityReason && (
            <p className="text-[11px] leading-relaxed text-[#915424] pl-5">
              {ambiguityReason}
            </p>
          )}
        </div>
      )}

      {/* Expected Evidence Specs */}
      {((requirement.evidence_specs && requirement.evidence_specs.length > 0) ||
        (requirement.evidence_required && requirement.evidence_required.length > 0)) && (
        <div className="border-t border-[#edf0ee] pt-2.5 text-[11px] text-[#60717e]">
          <span className="font-semibold text-[#3b4b59]">Expected Proof: </span>
          {requirement.evidence_specs && requirement.evidence_specs.length > 0 ? (
            <span>
              {requirement.evidence_specs.map((s) => s.description).join("; ")}
            </span>
          ) : (
            <span>{requirement.evidence_required?.join("; ")}</span>
          )}
        </div>
      )}
    </article>
  );
}
