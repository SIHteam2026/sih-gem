import React from "react";
import { ArrowRightLeft, AlertTriangle, CheckCircle2, HelpCircle, FileText, Info } from "lucide-react";
import { SideBySideComparison, RelationshipClassification, ProvenanceRecord } from "@/types/procurement";

interface EvidenceComparisonProps {
  comparison?: SideBySideComparison | null;
  left?: ProvenanceRecord | null;
  right?: ProvenanceRecord | null;
  relationship?: RelationshipClassification | string;
  explanation?: string;
  onInspect?: (record: ProvenanceRecord) => void;
  className?: string;
}

/**
 * EvidenceComparison
 * 
 * Side-by-side juxtaposition of competing or supporting claims and evidence observations.
 * For contradictions (e.g. 27% bidder declaration vs. 14% CA certificate):
 * - Displays both sources with respective provenance, quotes, and values
 * - Clearly signals relationship (CONTRADICTS, SUPPORTS, etc.)
 * - Communicates that contradiction leads to REVIEW, without arbitrarily choosing a winner.
 */
export default function EvidenceComparison({
  comparison,
  left: propLeft,
  right: propRight,
  relationship: propRel,
  explanation: propExp,
  onInspect,
  className = "",
}: EvidenceComparisonProps) {
  const left = comparison?.left || propLeft;
  const right = comparison?.right || propRight;
  const relationship = (comparison?.relationship || propRel || "REVIEW_REQUIRED").toUpperCase();
  const explanation = comparison?.discrepancy_description || propExp || "Discrepancy identified between submitted evidence sources.";

  if (!left || !right) return null;

  const isContradiction =
    relationship === "CONTRADICTS" ||
    relationship === "UNSUPPORTED" ||
    relationship === "REVIEW_REQUIRED";

  return (
    <div
      className={`rounded border p-4 space-y-3.5 text-xs ${
        isContradiction
          ? "border-amber-300 bg-[#fffcf5] text-[#2e2617]"
          : "border-[#ccdbe4] bg-[#f5f9fc] text-[#1e3447]"
      } ${className}`}
      role="region"
      aria-label="Side-by-side evidence comparison"
    >
      {/* Header / Relationship Indicator */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-amber-200/70 pb-2.5">
        <div className="flex items-center gap-2 font-semibold">
          {isContradiction ? (
            <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" aria-hidden="true" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" aria-hidden="true" />
          )}
          <span className="uppercase font-mono text-[11px] tracking-wider text-amber-950">
            {isContradiction ? "Evidence Contradiction Identified" : "Cross-Document Reconciliation"}
          </span>
        </div>

        <span
          className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase ${
            isContradiction
              ? "bg-amber-100 text-amber-900 border border-amber-300"
              : "bg-emerald-100 text-emerald-900 border border-emerald-300"
          }`}
        >
          {relationship.replaceAll("_", " ")}
        </span>
      </div>

      {/* Side-by-Side Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 items-stretch">
        {/* Source A (Left: typically Bidder Claim) */}
        <div className="p-3.5 rounded border border-[#d6ded6] bg-[#fffefa] flex flex-col justify-between space-y-2">
          <div className="space-y-1">
            <span className="text-[10px] uppercase font-bold text-[#627482] tracking-wider block">
              Source A: {left.source_type || "Bidder Declaration"}
            </span>

            <div className="flex items-baseline gap-2 pt-1">
              <span className="font-mono text-base font-bold text-[#163a5f]">
                {String(left.normalized_value ?? left.raw_value ?? "Value not parsed")}
                {left.unit ? ` ${left.unit}` : ""}
              </span>
            </div>

            <div className="text-[11px] text-[#4d5e6c] font-medium flex items-center gap-1.5 pt-0.5">
              <FileText className="w-3.5 h-3.5 text-[#163a5f]" aria-hidden="true" />
              <span>{left.document_name || "Document A"}</span>
              {left.page_number !== undefined && left.page_number !== null && (
                <span className="font-mono text-[10px] text-[#718290]">
                  (Page {left.page_number})
                </span>
              )}
            </div>
          </div>

          {left.quote && (
            <blockquote className="mt-2 pl-2.5 border-l-2 border-[#163a5f]/40 font-serif text-[11px] text-[#3d5060] italic leading-relaxed">
              &ldquo;{left.quote}&rdquo;
            </blockquote>
          )}

          {onInspect && (
            <div className="pt-2 border-t border-[#edf0ee] flex justify-end">
              <button
                type="button"
                onClick={() => onInspect(left)}
                className="text-[11px] font-semibold text-[#163a5f] hover:underline focus-ring"
              >
                Inspect Source A →
              </button>
            </div>
          )}
        </div>

        {/* Source B (Right: typically Supporting Certificate) */}
        <div className="p-3.5 rounded border border-[#d6ded6] bg-[#fffefa] flex flex-col justify-between space-y-2">
          <div className="space-y-1">
            <span className="text-[10px] uppercase font-bold text-[#627482] tracking-wider block">
              Source B: {right.source_type || "Supporting Certificate"}
            </span>

            <div className="flex items-baseline gap-2 pt-1">
              <span className="font-mono text-base font-bold text-[#163a5f]">
                {String(right.normalized_value ?? right.raw_value ?? "Value not parsed")}
                {right.unit ? ` ${right.unit}` : ""}
              </span>
            </div>

            <div className="text-[11px] text-[#4d5e6c] font-medium flex items-center gap-1.5 pt-0.5">
              <FileText className="w-3.5 h-3.5 text-[#163a5f]" aria-hidden="true" />
              <span>{right.document_name || "Document B"}</span>
              {right.page_number !== undefined && right.page_number !== null && (
                <span className="font-mono text-[10px] text-[#718290]">
                  (Page {right.page_number})
                </span>
              )}
            </div>
          </div>

          {right.quote && (
            <blockquote className="mt-2 pl-2.5 border-l-2 border-[#163a5f]/40 font-serif text-[11px] text-[#3d5060] italic leading-relaxed">
              &ldquo;{right.quote}&rdquo;
            </blockquote>
          )}

          {onInspect && (
            <div className="pt-2 border-t border-[#edf0ee] flex justify-end">
              <button
                type="button"
                onClick={() => onInspect(right)}
                className="text-[11px] font-semibold text-[#163a5f] hover:underline focus-ring"
              >
                Inspect Source B →
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Discrepancy Explanation & Decision Boundary Notice */}
      <div className="p-3 rounded bg-[#fff8eb] border border-amber-200/80 space-y-1 text-[11px] text-[#4d3d22]">
        <p className="font-medium text-[#2d2210]">
          <strong>Conflict Detail:</strong> {explanation}
        </p>
        <p className="text-[#695536] italic">
          <strong>Review Policy:</strong> OPAL identifies the divergence between the declaration and the supporting proof. The requirement is marked for <strong>Officer Review</strong> for authoritative reconciliation or 48-hour clarification notice.
        </p>
      </div>
    </div>
  );
}
