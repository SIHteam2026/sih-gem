"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */

import { useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  ChevronRight,
  FileSpreadsheet,
  FileText,
  FileCode,
  Files,
  LoaderCircle,
  Paperclip,
  Search,
  Trash2,
  X,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { analyzeTender, verifyBid } from "@/services/api";

type Requirement = {
  requirement_id?: string;
  id?: string;
  category?: string;
  description?: string;
  mandatory?: boolean;
  evidence_required?: string[] | string;
  is_ambiguous?: boolean;
  ambiguity_reason?: string;
};

export default function ReviewPage() {
  const [tender, setTender] = useState<File | null>(null);
  const [bidderFiles, setBidderFiles] = useState<File[]>([]);
  const [analysis, setAnalysis] = useState<{ tender_id?: string; requirements?: Requirement[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [checkingId, setCheckingId] = useState<string | null>(null);
  const [findings, setFindings] = useState<Record<string, any>>({});

  const requirements = useMemo(() => analysis?.requirements || [], [analysis]);

  const selectTenderFile = (file: File | undefined) => {
    if (!file) return;
    setTender(file);
    setAnalysis(null);
    setFindings({});
    setActiveId(null);
    setError(null);
  };

  const addBidderFiles = (files: FileList | File[] | null) => {
    if (!files) return;
    const newFiles = Array.from(files);
    setBidderFiles((prev) => {
      const existing = new Set(prev.map((f) => `${f.name}-${f.size}`));
      const toAdd = newFiles.filter((f) => !existing.has(`${f.name}-${f.size}`));
      return [...prev, ...toAdd];
    });
    setFindings({});
    setError(null);
  };

  const removeBidderFile = (index: number) => {
    setBidderFiles((prev) => prev.filter((_, i) => i !== index));
    setFindings({});
  };

  const clearBidderFiles = () => {
    setBidderFiles([]);
    setFindings({});
  };

  const beginReview = async () => {
    if (!tender) {
      setError("Add the tender document to begin a review.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setAnalysis(await analyzeTender(tender));
    } catch (err: any) {
      setError(err?.message || "The tender could not be reviewed.");
    } finally {
      setLoading(false);
    }
  };

  const inspect = async (requirement: Requirement, index: number) => {
    const id = requirement.requirement_id || requirement.id || `REQ-${index + 1}`;
    setActiveId(id);
    if (!tender || bidderFiles.length === 0 || findings[id]) return;
    setCheckingId(id);
    setError(null);
    try {
      const result = await verifyBid(tender, bidderFiles as any, id);
      setFindings((current) => ({ ...current, [id]: result }));
    } catch (err: any) {
      setError(err?.message || "The evidence could not be checked for this requirement.");
    } finally {
      setCheckingId(null);
    }
  };

  const activeRequirement = requirements.find(
    (r, index) => (r.requirement_id || r.id || `REQ-${index + 1}`) === activeId
  );
  const activeFinding = activeId ? findings[activeId] : null;

  return (
    <div className="min-h-screen bg-[#f7f6f2]">
      <Navbar />
      <main className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-14">
        <div className="flex flex-col justify-between gap-6 border-b border-[#d9ddd9] pb-8 sm:flex-row sm:items-end">
          <div>
            <p className="eyebrow">New review</p>
            <h1 className="mt-2 text-3xl font-medium tracking-[-.035em] text-[#162333] sm:text-4xl">
              Prepare a procurement review
            </h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-[#65717b]">
              Add the tender specification and multiple bidder evidence files (PDF, CSV, DOCX, XLSX, TXT).
              Requirements will be extracted and verified against all submitted documents.
            </p>
          </div>
          {analysis && (
            <p className="border-l border-[#b9c8d0] pl-4 text-sm leading-5 text-[#36566d]">
              <span className="block font-medium text-[#163a5f]">
                {requirements.length} requirements identified
              </span>
              Choose a requirement to inspect evidence across {bidderFiles.length} bidder document(s).
            </p>
          )}
        </div>

        {!analysis ? (
          <section className="mt-10 grid gap-6 lg:grid-cols-[1fr_1.3fr_.7fr]">
            {/* Tender Single Document Slot */}
            <TenderSlot
              title="Tender Specification"
              detail="The notice, RFP, or specification (PDF, DOCX, TXT)"
              file={tender}
              onFile={selectTenderFile}
              onRemove={() => setTender(null)}
            />

            {/* Multi-Format, Multi-Document Bidder Slot */}
            <MultiBidderSlot
              title="Bidder Evidence Documents"
              detail="Upload certificates, declarations, turnover CSVs, Word undertakings, and sheets"
              files={bidderFiles}
              onAddFiles={addBidderFiles}
              onRemoveFile={removeBidderFile}
              onClearAll={clearBidderFiles}
            />

            {/* Action Box */}
            <div className="flex min-h-64 flex-col justify-between border border-[#d4d9d8] bg-[#163a5f] p-6 text-white">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[.14em] text-[#bcd0dd]">
                  Step 1
                </p>
                <h2 className="mt-4 text-xl font-medium tracking-[-.02em]">
                  Multi-Document Evidence Evaluation
                </h2>
                <p className="mt-3 text-sm leading-6 text-[#d3dfe5]">
                  {bidderFiles.length > 0
                    ? `${bidderFiles.length} bidder file(s) attached across formats. Click below to parse requirements.`
                    : "Attach tender and one or more bidder files (PDF, CSV, DOCX, XLSX, TXT) to proceed."}
                </p>
              </div>
              <button
                onClick={beginReview}
                disabled={!tender || loading}
                className="focus-ring inline-flex w-full items-center justify-between bg-white px-4 py-3 text-sm font-medium text-[#163a5f] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Identifying requirements…" : "Identify requirements"}
                {loading ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowRight className="h-4 w-4" />
                )}
              </button>
            </div>
          </section>
        ) : (
          <section className="mt-10 grid gap-10 lg:grid-cols-[.95fr_1.35fr]">
            <aside className="lg:border-r lg:border-[#d9ddd9] lg:pr-8">
              <div className="flex items-center justify-between">
                <p className="eyebrow">Requirements</p>
                <span className="text-xs text-[#71808a]">
                  {requirements.length} total · {bidderFiles.length} bidder doc(s)
                </span>
              </div>
              <div className="mt-4 divide-y divide-[#dce0dd] border-y border-[#dce0dd]">
                {requirements.map((requirement, index) => {
                  const id = requirement.requirement_id || requirement.id || `REQ-${index + 1}`;
                  const finding = findings[id];
                  const state = String(finding?.compliance_finding?.state || "");
                  return (
                    <button
                      key={id}
                      onClick={() => inspect(requirement, index)}
                      className={`focus-ring group w-full px-1 py-5 text-left transition-colors ${
                        activeId === id ? "bg-[#eef3f4]" : "hover:bg-[#fbfbf8]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-xs font-medium tracking-[.08em] text-[#647784]">
                            {String(index + 1).padStart(2, "0")} · {requirement.category || "REQUIREMENT"}
                          </p>
                          <p className="mt-2 text-sm font-medium leading-6 text-[#1b2a35]">
                            {requirement.description || "Tender requirement"}
                          </p>
                        </div>
                        <StateMark state={state} />
                      </div>
                      {requirement.is_ambiguous && (
                        <p className="mt-2 text-xs leading-5 text-[#a85e31]">Needs interpretation</p>
                      )}
                    </button>
                  );
                })}
              </div>
              <button
                onClick={() => {
                  setAnalysis(null);
                  setActiveId(null);
                }}
                className="focus-ring mt-6 text-sm text-[#526977] hover:text-[#163a5f]"
              >
                ← Change documents ({bidderFiles.length} attached)
              </button>
            </aside>
            <div>
              {activeRequirement ? (
                <Finding
                  requirement={activeRequirement}
                  finding={activeFinding}
                  waiting={checkingId === activeId}
                  bidderCount={bidderFiles.length}
                />
              ) : (
                <div className="grid min-h-80 place-items-center border border-dashed border-[#cbd2d1] bg-[#fffefa] p-8 text-center">
                  <div>
                    <Search className="mx-auto h-5 w-5 text-[#668394]" />
                    <h2 className="mt-4 text-lg font-medium text-[#21323d]">Choose a requirement</h2>
                    <p className="mt-2 max-w-sm text-sm leading-6 text-[#69757e]">
                      Evidence extracted from your {bidderFiles.length} attached bidder document(s) will be
                      synthesized and compared against the tender clause.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {error && (
          <div className="mt-7 flex gap-3 border border-[#e3c8b9] bg-[#fff8f4] p-4 text-sm text-[#7b3d20]">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            {error}
            <button onClick={() => setError(null)} className="ml-auto">
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

function TenderSlot({
  title,
  detail,
  file,
  onFile,
  onRemove,
}: {
  title: string;
  detail: string;
  file: File | null;
  onFile: (file?: File) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex min-h-64 flex-col justify-between border border-[#d4d9d8] bg-[#fffefa] p-6">
      <div>
        <p className="eyebrow">{title}</p>
        <p className="mt-2 text-sm leading-6 text-[#67737d]">{detail}</p>
      </div>
      {file ? (
        <div className="mt-6 border-t border-[#e0e2de] pt-4">
          <div className="flex items-center gap-3">
            <FileText className="h-5 w-5 shrink-0 text-[#2e638d]" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-[#1d2f3d]">{file.name}</p>
              <p className="mt-0.5 text-xs text-[#71808a]">
                {(file.size / 1024).toFixed(1)} KB · Ready
              </p>
            </div>
          </div>
          <button
            onClick={onRemove}
            className="focus-ring mt-4 text-xs font-medium text-[#596d79] hover:text-[#a85e31]"
          >
            Remove tender
          </button>
        </div>
      ) : (
        <label
          htmlFor="tender-input"
          className="focus-ring mt-6 flex cursor-pointer items-center justify-center gap-2 border border-dashed border-[#c0cbd2] bg-[#fbfbf9] py-5 text-sm font-medium text-[#2e638d] hover:bg-white hover:text-[#163a5f]"
        >
          <Paperclip className="h-4 w-4" />
          Attach tender document
          <input
            id="tender-input"
            type="file"
            accept=".pdf,.docx,.doc,.txt"
            onChange={(e) => onFile(e.target.files?.[0])}
            className="sr-only"
          />
        </label>
      )}
    </div>
  );
}

function getFileFormatIcon(filename: string) {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  if (ext === "csv" || ext === "tsv" || ext === "xlsx" || ext === "xls") {
    return <FileSpreadsheet className="h-4 w-4 text-emerald-600 shrink-0" />;
  }
  if (ext === "docx" || ext === "doc") {
    return <FileCode className="h-4 w-4 text-indigo-600 shrink-0" />;
  }
  return <FileText className="h-4 w-4 text-[#2e638d] shrink-0" />;
}

function MultiBidderSlot({
  title,
  detail,
  files,
  onAddFiles,
  onRemoveFile,
  onClearAll,
}: {
  title: string;
  detail: string;
  files: File[];
  onAddFiles: (files: FileList | null) => void;
  onRemoveFile: (index: number) => void;
  onClearAll: () => void;
}) {
  return (
    <div className="flex min-h-64 flex-col justify-between border border-[#d4d9d8] bg-[#fffefa] p-6">
      <div>
        <div className="flex items-center justify-between">
          <p className="eyebrow">{title}</p>
          {files.length > 0 && (
            <span className="rounded bg-[#eaf1f5] px-2 py-0.5 text-xs font-semibold text-[#163a5f]">
              {files.length} attached
            </span>
          )}
        </div>
        <p className="mt-2 text-sm leading-6 text-[#67737d]">{detail}</p>
      </div>

      {files.length > 0 ? (
        <div className="mt-4 border-t border-[#e0e2de] pt-3">
          <div className="max-h-48 overflow-y-auto divide-y divide-[#edf1ed] pr-1">
            {files.map((f, idx) => (
              <div key={`${f.name}-${idx}`} className="flex items-center justify-between py-2 gap-2 text-left">
                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                  {getFileFormatIcon(f.name)}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-[#1d2f3d]">{f.name}</p>
                    <p className="text-[10px] text-[#78858e]">
                      {f.name.split(".").pop()?.toUpperCase()} · {(f.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => onRemoveFile(idx)}
                  className="p-1 text-[#8c9ba5] hover:text-[#b24a45] transition-colors"
                  title="Remove document"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-[#edf1ed] pt-2">
            <label
              htmlFor="bidder-more-input"
              className="cursor-pointer text-xs font-medium text-[#2e638d] hover:text-[#163a5f] inline-flex items-center gap-1"
            >
              <Paperclip className="h-3.5 w-3.5" />+ Add more files
              <input
                id="bidder-more-input"
                type="file"
                multiple
                accept=".pdf,.csv,.tsv,.docx,.doc,.xlsx,.xls,.txt"
                onChange={(e) => onAddFiles(e.target.files)}
                className="sr-only"
              />
            </label>
            <button
              onClick={onClearAll}
              className="text-xs text-[#8c9ba5] hover:text-[#b24a45] inline-flex items-center gap-1"
            >
              <Trash2 className="h-3 w-3" />Clear all
            </button>
          </div>
        </div>
      ) : (
        <label
          htmlFor="bidder-input"
          className="focus-ring mt-6 flex cursor-pointer flex-col items-center justify-center gap-1.5 border border-dashed border-[#c0cbd2] bg-[#fbfbf9] py-5 text-center text-sm font-medium text-[#2e638d] hover:bg-white hover:text-[#163a5f]"
        >
          <div className="flex items-center gap-1.5">
            <Files className="h-4 w-4 text-[#2e638d]" />
            <span>Select Multiple Bidder Documents</span>
          </div>
          <span className="text-[11px] font-normal text-[#788892]">
            Supports PDF, CSV, DOCX, XLSX, TXT
          </span>
          <input
            id="bidder-input"
            type="file"
            multiple
            accept=".pdf,.csv,.tsv,.docx,.doc,.xlsx,.xls,.txt"
            onChange={(e) => onAddFiles(e.target.files)}
            className="sr-only"
          />
        </label>
      )}
    </div>
  );
}

function StateMark({ state }: { state: string }) {
  if (!state) return <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-[#89949a]" />;
  const review = state.includes("REVIEW") || state.includes("UNVERIFIED");
  return (
    <span
      className={`mt-1 h-2.5 w-2.5 rounded-full ${
        review ? "bg-[#b66e3c]" : state.includes("NON") ? "bg-[#b24a45]" : "bg-[#4b806f]"
      }`}
    />
  );
}

function Finding({
  requirement,
  finding,
  waiting,
  bidderCount,
}: {
  requirement: Requirement;
  finding: any;
  waiting: boolean;
  bidderCount: number;
}) {
  const evidence = finding?.extracted_evidence;
  const compliance = finding?.compliance_finding;

  return (
    <article className="border border-[#d4d9d8] bg-[#fffefa]">
      <div className="border-b border-[#d9ddd9] px-6 py-5">
        <p className="eyebrow">Requirement record</p>
        <h2 className="mt-2 text-xl font-medium tracking-[-.025em] text-[#1b2a35]">
          {requirement.category || "Requirement"}
        </h2>
      </div>
      {waiting ? (
        <div className="flex min-h-64 items-center justify-center gap-3 text-sm text-[#5b6e79]">
          <LoaderCircle className="h-4 w-4 animate-spin" />
          Checking submitted evidence across {bidderCount} document(s)…
        </div>
      ) : finding ? (
        <div className="p-6">
          <Record label="Tender requirement" value={requirement.description || "Not available"} />
          <Record
            label="Evidence found"
            value={
              evidence?.source_quote ||
              (evidence?.is_present
                ? "Evidence was found in the submitted bidder documents."
                : "No supporting evidence was identified in any uploaded documents.")
            }
          />
          <Record
            label="Assessment"
            value={compliance?.reasoning_trace || "No assessment available."}
            last
          />
          <div className="mt-6 flex items-center justify-between border-t border-[#d9ddd9] pt-5">
            <span
              className={`text-xs font-semibold tracking-[.12em] ${
                String(compliance?.state).includes("NON")
                  ? "text-[#a64842]"
                  : String(compliance?.state).includes("REVIEW")
                  ? "text-[#9b5a2e]"
                  : "text-[#367363]"
              }`}
            >
              {String(compliance?.state || "REVIEW").replaceAll("_", " ")}
            </span>
            <span className="text-xs text-[#77838a]">
              Evaluated across {bidderCount} bidder document(s)
            </span>
          </div>
        </div>
      ) : (
        <div className="p-6">
          <p className="text-sm leading-6 text-[#63717a]">
            {bidderCount > 0
              ? `Open this requirement to verify the tender clause against all ${bidderCount} attached bidder documents.`
              : "Add bidder evidence documents to compare them against this tender requirement."}
          </p>
          {bidderCount === 0 && (
            <div className="mt-6 flex items-center gap-2 border-t border-[#d9ddd9] pt-5 text-xs text-[#77838a]">
              <FileText className="h-4 w-4" />
              No bidder evidence attached
            </div>
          )}
        </div>
      )}
    </article>
  );
}

function Record({ label, value, last = false }: { label: string; value: string; last?: boolean }) {
  return (
    <div className={`py-5 ${last ? "" : "border-b border-[#e1e4e0]"}`}>
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm leading-6 text-[#263641]">{value}</p>
    </div>
  );
}
