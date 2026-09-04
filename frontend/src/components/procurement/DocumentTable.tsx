import React from "react";
import { FileText, CheckCircle2, Clock, AlertTriangle, FileCode } from "lucide-react";
import { DocumentMetadata } from "@/types/procurement";

interface DocumentTableProps {
  documents: DocumentMetadata[];
  emptyMessage?: string;
  className?: string;
}

function formatFileSize(bytes?: number | null): string {
  if (!bytes || bytes <= 0) return "Unknown size";
  const units = ["B", "KB", "MB", "GB"];
  let val = bytes;
  let unitIndex = 0;
  while (val >= 1024 && unitIndex < units.length - 1) {
    val /= 1024;
    unitIndex++;
  }
  return `${val.toFixed(val >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

function formatDocumentType(docType?: string | null): string {
  if (!docType) return "Document";
  return docType
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function DocumentTable({
  documents,
  emptyMessage = "No documents registered in this section.",
  className = "",
}: DocumentTableProps) {
  if (!documents || documents.length === 0) {
    return (
      <div className={`p-8 text-center border border-dashed border-[#d2d6d4] rounded bg-[#fffefa] text-xs text-[#6e7b85] ${className}`}>
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className={`overflow-x-auto border border-[#d9ddd9] rounded bg-[#fffefa] ${className}`}>
      <table className="w-full text-left border-collapse text-xs">
        <thead>
          <tr className="border-b border-[#d9ddd9] bg-[#f5f6f4] text-[#4f5e6a] font-semibold">
            <th scope="col" className="py-3 px-4">Document ID & Name</th>
            <th scope="col" className="py-3 px-4">Document Type</th>
            <th scope="col" className="py-3 px-4">Size</th>
            <th scope="col" className="py-3 px-4">Status</th>
            <th scope="col" className="py-3 px-4 text-right">Registered</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#e4e7e4]">
          {documents.map((doc) => {
            // Strictly key on canonical document UUID to prevent collisions between identical filenames
            const canonicalId = doc.id;
            const status = String(doc.processing_status || "PENDING").toUpperCase();

            let statusIcon = <Clock className="w-3.5 h-3.5 text-sky-600" aria-hidden="true" />;
            let statusColor = "text-sky-800 bg-sky-50 border-sky-200";

            if (status === "COMPLETED" || status === "PROCESSED" || status === "READY") {
              statusIcon = <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" aria-hidden="true" />;
              statusColor = "text-emerald-800 bg-emerald-50 border-emerald-200";
            } else if (status === "FAILED" || status === "ERROR") {
              statusIcon = <AlertTriangle className="w-3.5 h-3.5 text-rose-600" aria-hidden="true" />;
              statusColor = "text-rose-800 bg-rose-50 border-rose-200";
            }

            return (
              <tr key={canonicalId} className="hover:bg-[#f9faf8] transition-colors">
                <td className="py-3.5 px-4">
                  <div className="flex items-start gap-2.5">
                    <FileText className="w-4 h-4 text-[#204970] shrink-0 mt-0.5" aria-hidden="true" />
                    <div className="min-w-0">
                      <p className="font-medium text-[#162333] truncate max-w-xs sm:max-w-md" title={doc.filename}>
                        {doc.filename}
                      </p>
                      <div className="flex items-center gap-1.5 mt-0.5 font-mono text-[10px] text-[#71808b]">
                        <FileCode className="w-3 h-3" aria-hidden="true" />
                        <span title={`Canonical Document UUID: ${canonicalId}`}>ID: {canonicalId}</span>
                      </div>
                    </div>
                  </div>
                </td>
                <td className="py-3.5 px-4 text-[#2c3d4d]">
                  <span className="inline-block px-2 py-0.5 rounded bg-[#edf1f2] border border-[#d2dbdf] text-[11px] font-medium">
                    {formatDocumentType(doc.document_type)}
                  </span>
                </td>
                <td className="py-3.5 px-4 text-[#5e6d7a] font-mono">
                  {formatFileSize(doc.file_size)}
                </td>
                <td className="py-3.5 px-4">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-semibold tracking-wider ${statusColor}`}>
                    {statusIcon}
                    <span>{status}</span>
                  </span>
                </td>
                <td className="py-3.5 px-4 text-right text-[#71808b] whitespace-nowrap">
                  {doc.created_at
                    ? new Date(doc.created_at).toLocaleDateString("en-IN", {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                      })
                    : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
