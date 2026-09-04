import React from "react";
import { FileText, ExternalLink, Quote, Bookmark } from "lucide-react";
import { ProvenanceRecord } from "@/types/procurement";

interface EvidenceReferenceProps {
  provenance: ProvenanceRecord;
  onInspect?: (record: ProvenanceRecord) => void;
  className?: string;
  isConflicting?: boolean;
}

/**
 * EvidenceReference
 * 
 * Displays an evidence reference with document label, page number, verbatim quote,
 * and extracted value. Internally keys evidence by canonical document_id.
 */
export default function EvidenceReference({
  provenance,
  onInspect,
  className = "",
  isConflicting = false,
}: EvidenceReferenceProps) {
  const docName = provenance.document_name || "Document";
  const pageLabel =
    provenance.page_number !== undefined && provenance.page_number !== null
      ? `Page ${provenance.page_number}`
      : null;
  const sourceType = provenance.source_type || "Evidence Proof";

  return (
    <div
      className={`p-3 rounded border text-xs transition-colors ${
        isConflicting
          ? "border-rose-200 bg-[#fffbfc] text-[#3d2325]"
          : "border-[#d8ded8] bg-[#fafbfa] text-[#1c2b38]"
      } ${className}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-1.5 font-medium">
            <span className="font-semibold text-[#162333] flex items-center gap-1">
              <FileText className="w-3.5 h-3.5 text-[#163a5f]" aria-hidden="true" />
              {docName}
            </span>
            {pageLabel && (
              <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-[#e9edf0] text-[#334b5c]">
                {pageLabel}
              </span>
            )}
            <span className="text-[10px] text-[#718290] font-normal">
              ({sourceType})
            </span>
          </div>

          {(provenance.normalized_value !== undefined || provenance.raw_value !== undefined) && (
            <div className="text-[11px] font-mono text-[#1a446c]">
              Extracted: <strong>{String(provenance.normalized_value ?? provenance.raw_value)}</strong>
              {provenance.unit ? ` ${provenance.unit}` : ""}
            </div>
          )}
        </div>

        {onInspect && (
          <button
            type="button"
            onClick={() => onInspect(provenance)}
            className="shrink-0 p-1 text-[#5a6e80] hover:text-[#163a5f] hover:bg-[#eaf0f6] rounded transition-colors focus-ring"
            title="Inspect document provenance and metadata"
            aria-label={`Inspect evidence from ${docName}`}
          >
            <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
          </button>
        )}
      </div>

      {provenance.quote && (
        <blockquote className="mt-2 pl-2.5 border-l-2 border-[#163a5f]/40 font-serif text-[11px] text-[#3a4c5c] italic leading-relaxed">
          &ldquo;{provenance.quote}&rdquo;
        </blockquote>
      )}
    </div>
  );
}
