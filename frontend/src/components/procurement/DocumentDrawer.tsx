import React from "react";
import { X, FileText, ExternalLink, Hash, CheckCircle, Percent, Bookmark } from "lucide-react";
import { ProvenanceRecord } from "@/types/procurement";

interface DocumentDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  record: ProvenanceRecord | null;
}

/**
 * DocumentDrawer
 * 
 * Reusable modal/drawer for inspecting evidence provenance and document metadata.
 * Displays canonical document UUID, page number, verbatim excerpt, and normalized value
 * without needing a complex PDF renderer.
 */
export default function DocumentDrawer({ isOpen, onClose, record }: DocumentDrawerProps) {
  if (!isOpen || !record) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-labelledby="evidence-drawer-title"
    >
      <div className="bg-[#fffefa] border border-[#cbd2d1] rounded-lg shadow-xl max-w-lg w-full overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#e4e8e4] bg-[#f8faf8]">
          <div className="flex items-center gap-2.5">
            <FileText className="w-4 h-4 text-[#163a5f]" aria-hidden="true" />
            <div>
              <h3 id="evidence-drawer-title" className="text-sm font-semibold text-[#162333]">
                Evidence Provenance Details
              </h3>
              <p className="text-[11px] text-[#6b7b8a] font-mono mt-0.5">
                {record.source_type || "Supporting Document Proof"}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded text-[#6b7b8a] hover:text-[#162333] hover:bg-[#eaeaea] transition-colors focus-ring"
            aria-label="Close evidence details"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 overflow-y-auto space-y-4 text-xs">
          {/* Document Reference Info */}
          <div className="p-3.5 rounded border border-[#d9ddd9] bg-[#fafbfa] space-y-2">
            <div>
              <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                Document Name / Title
              </span>
              <span className="font-semibold text-[#162333] text-xs break-all">
                {record.document_name || "Document"}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2 border-t border-[#edf0ee]">
              <div>
                <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                  Location Reference
                </span>
                <span className="font-mono font-medium text-[#162333]">
                  {record.page_number !== undefined && record.page_number !== null
                    ? `Page ${record.page_number}`
                    : record.sheet_name || record.cell_reference || record.row_number
                    ? [
                        record.sheet_name ? `Sheet: ${record.sheet_name}` : null,
                        record.cell_reference ? `Cell: ${record.cell_reference}` : record.row_number ? `Row: ${record.row_number}` : null,
                      ].filter(Boolean).join(", ")
                    : record.section_context
                    ? `Section: ${record.section_context}`
                    : "Full Document"}
                </span>
              </div>

              <div>
                <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                  Extraction Confidence
                </span>
                <span className="font-mono font-medium text-[#162333]">
                  {record.extraction_confidence !== undefined && record.extraction_confidence !== null
                    ? `${Math.round(record.extraction_confidence * 100)}%`
                    : "100% (Deterministic)"}
                </span>
              </div>
            </div>

            {record.document_id && (
              <div className="pt-2 border-t border-[#edf0ee]">
                <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                  Canonical Document UUID
                </span>
                <span className="font-mono text-[11px] text-[#4d5d6c] break-all select-all">
                  {record.document_id}
                </span>
              </div>
            )}
          </div>

          {/* Observed / Normalized Value */}
          {(record.normalized_value !== undefined || record.raw_value !== undefined) && (
            <div className="p-3.5 rounded border border-[#d9ddd9] bg-[#fafbfa] space-y-2">
              <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                Extracted & Normalized Value
              </span>
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-bold text-[#163a5f]">
                  {String(record.normalized_value ?? record.raw_value ?? "N/A")}
                  {record.unit ? ` ${record.unit}` : ""}
                </span>
              </div>
              {record.raw_value !== undefined && record.raw_value !== record.normalized_value && (
                <div className="text-[11px] text-[#6b7b8a]">
                  Raw statement: <span className="font-mono text-[#334b5c]">{String(record.raw_value)}</span>
                </div>
              )}
            </div>
          )}

          {/* Verbatim Quote Snippet */}
          {record.quote && (
            <div className="space-y-1.5">
              <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                Verbatim Quote Snippet
              </span>
              <blockquote className="p-3.5 rounded border-l-2 border-[#163a5f] bg-[#f4f7f9] text-[#223544] font-serif text-xs italic leading-relaxed">
                &ldquo;{record.quote}&rdquo;
              </blockquote>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-[#e4e8e4] bg-[#f8faf8] flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-semibold text-[#162333] bg-[#eef1ee] hover:bg-[#e2e6e2] rounded transition-colors focus-ring"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
