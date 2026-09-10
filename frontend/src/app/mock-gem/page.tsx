"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import {
  UploadCloud,
  FileText,
  FolderArchive,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Loader2,
  Plus,
  Trash2,
  Clock,
  ExternalLink,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { ingestMockGeMFiles } from "@/services/api";

interface BidderRow {
  id: string;
  name: string;
  file: File | null;
}

export default function MockGeMIntakePage() {
  const [tenderFile, setTenderFile] = useState<File | null>(null);
  const [bidders, setBidders] = useState<BidderRow[]>([
    { id: "bidder-1", name: "", file: null },
  ]);

  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);

  const tenderInputRef = useRef<HTMLInputElement>(null);

  // Handle Tender PDF selection
  const handleTenderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Invalid tender file. Tender specification document must be a .pdf file.");
      return;
    }
    setTenderFile(file);
  };

  // Bidder row management
  const handleAddBidder = () => {
    const newId = `bidder-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`;
    setBidders((prev) => [...prev, { id: newId, name: "", file: null }]);
  };

  const handleRemoveBidder = (id: string) => {
    setBidders((prev) => {
      const filtered = prev.filter((b) => b.id !== id);
      return filtered.length > 0
        ? filtered
        : [{ id: `bidder-${Date.now()}`, name: "", file: null }];
    });
  };

  const handleBidderNameChange = (id: string, name: string) => {
    setBidders((prev) =>
      prev.map((b) => (b.id === id ? { ...b, name } : b))
    );
  };

  const handleBidderFileChange = (id: string, file: File | null) => {
    setError(null);
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".zip")) {
      setError(`File "${file.name}" is not a .zip archive. Bidder packages must be .zip files.`);
      return;
    }

    setBidders((prev) =>
      prev.map((b) => {
        if (b.id !== id) return b;
        let derivedName = b.name;
        if (!derivedName.trim()) {
          const rawName = file.name
            .replace(/\.zip$/i, "")
            .replace(/^(bidder|submission|package)[-_]/i, "")
            .replace(/[-_]/g, " ")
            .trim();
          derivedName = rawName ? `${rawName} Pvt Ltd` : "";
        }
        return { ...b, file, name: derivedName };
      })
    );
  };

  // Submit Ingestion
  const handleSubmit = async () => {
    setError(null);
    setResult(null);

    if (!tenderFile) {
      setError("Please upload a Tender Specification PDF document.");
      return;
    }

    const validBidders = bidders.filter((b) => b.file !== null);
    if (validBidders.length === 0) {
      setError("Please upload at least one Bidder Submission ZIP package.");
      return;
    }

    setLoading(true);
    try {
      const bidderFiles = validBidders.map((b) => b.file as File);
      const bidderNames = validBidders.map(
        (b, i) => b.name.trim() || `Bidder ${i + 1} Pvt Ltd`
      );

      const res = await ingestMockGeMFiles(tenderFile, bidderFiles, {
        bidder_names: bidderNames,
      });
      setResult(res);
    } catch (err: any) {
      setError(err?.message || "Failed to ingest procurement package.");
    } finally {
      setLoading(false);
    }
  };

  const handleResetForm = () => {
    setTenderFile(null);
    setBidders([{ id: `bidder-${Date.now()}`, name: "", file: null }]);
    setError(null);
    setResult(null);
    if (tenderInputRef.current) {
      tenderInputRef.current.value = "";
    }
  };

  // Derived deadline representation from ingestion result hierarchy
  const firstTender = result?.hierarchy?.tenders?.[0];
  const submissionDeadlineRaw = firstTender?.submission_deadline;
  const deadlineDate = submissionDeadlineRaw ? new Date(submissionDeadlineRaw) : null;
  const isDeadlinePast = deadlineDate ? deadlineDate < new Date() : false;

  return (
    <div className="min-h-screen bg-[#f7f6f2] text-[#162333] flex flex-col font-sans selection:bg-[#d8e6ee]">
      <Navbar />

      <main className="flex-1 max-w-4xl w-full mx-auto py-10 px-5 sm:px-8 space-y-8">
        {/* Page Header */}
        <div className="border-b border-slate-200 pb-6 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <p className="font-mono uppercase text-xs font-semibold tracking-wider text-slate-500">
              Mock-GeM Ingestion Gateway
            </p>
            <h1 className="mt-1 text-3xl sm:text-4xl font-bold tracking-tight text-[#111827]">
              Procurement Intake Portal
            </h1>
            <p className="mt-1.5 text-sm text-[#64748b] max-w-2xl">
              Upload official tender specification PDF and bidder submission ZIP packages. Metadata and deadlines are derived directly from documents.
            </p>
          </div>

          <Link
            href="/procurements"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-slate-200 text-xs font-semibold text-slate-700 hover:text-[#111827] hover:border-slate-300 shadow-2xs transition-all shrink-0 cursor-pointer"
          >
            <span>View Workspace Shelf</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {/* Primary Ingestion Form */}
        <div className="p-6 sm:p-8 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-8">
          {/* Section 1: Tender Specification Document */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-[#163a5f] text-white text-xs font-bold flex items-center justify-center">
                  1
                </span>
                <h3 className="text-base font-bold text-[#111827]">
                  Tender Specification Document (PDF)
                </h3>
              </div>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-semibold">
                Mandatory
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Upload the official Notice Inviting Tender (NIT) or RFP document in PDF format. Requirements and submission deadline are extracted directly from the document.
            </p>

            {tenderFile ? (
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-lg bg-rose-50 border border-rose-200 flex items-center justify-center shrink-0">
                    <FileText className="w-5 h-5 text-rose-600" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-slate-900 truncate">
                      {tenderFile.name}
                    </p>
                    <p className="text-[11px] text-slate-400 font-mono">
                      {(tenderFile.size / 1024).toFixed(1)} KB • PDF Document
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setTenderFile(null);
                    if (tenderInputRef.current) tenderInputRef.current.value = "";
                  }}
                  className="text-xs text-rose-600 hover:text-rose-800 font-semibold px-2 py-1 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                >
                  Remove
                </button>
              </div>
            ) : (
              <div
                onClick={() => tenderInputRef.current?.click()}
                className="border-2 border-dashed border-slate-300 hover:border-[#163a5f] hover:bg-slate-50/70 transition-all rounded-xl p-6 text-center cursor-pointer space-y-2"
              >
                <UploadCloud className="w-8 h-8 text-slate-400 mx-auto" />
                <p className="text-xs font-semibold text-slate-700">
                  Click to choose Tender Specification PDF
                </p>
                <p className="text-[11px] text-slate-400">Accepts .pdf (NIT, RFP, Tender Notice)</p>
                <input
                  ref={tenderInputRef}
                  type="file"
                  accept=".pdf,application/pdf"
                  onChange={handleTenderChange}
                  className="hidden"
                />
              </div>
            )}
          </div>

          {/* Section 2: Bidder Submissions */}
          <div className="space-y-4 pt-6 border-t border-slate-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-[#163a5f] text-white text-xs font-bold flex items-center justify-center">
                  2
                </span>
                <h3 className="text-base font-bold text-[#111827]">
                  Bidder Submissions (.ZIP)
                </h3>
              </div>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-bold">
                Multi-Bidder
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Provide the bidder name and upload the corresponding submission package (.zip) for each participating vendor.
            </p>

            {/* Bidder Rows */}
            <div className="space-y-3">
              {bidders.map((bidder, index) => (
                <div
                  key={bidder.id}
                  className="p-4 rounded-xl bg-slate-50/80 border border-slate-200 flex flex-col sm:flex-row items-stretch sm:items-center gap-3"
                >
                  <span className="w-6 h-6 rounded-full bg-slate-200 text-slate-700 text-xs font-bold flex items-center justify-center shrink-0 self-start sm:self-center">
                    {index + 1}
                  </span>

                  {/* Bidder Legal Name Input */}
                  <div className="flex-1">
                    <input
                      type="text"
                      placeholder={`Bidder ${index + 1} Legal Name (e.g. HydroTech Solutions Pvt Ltd)`}
                      value={bidder.name}
                      onChange={(e) => handleBidderNameChange(bidder.id, e.target.value)}
                      className="w-full text-xs p-2.5 rounded-lg border border-slate-200 focus:outline-none focus:border-[#163a5f] bg-white font-medium placeholder:text-slate-400"
                    />
                  </div>

                  {/* Bidder ZIP File Attachment */}
                  <div className="sm:w-64 shrink-0">
                    {bidder.file ? (
                      <div className="flex items-center justify-between gap-2 p-2 rounded-lg bg-white border border-slate-200">
                        <div className="flex items-center gap-2 min-w-0">
                          <FolderArchive className="w-4 h-4 text-[#163a5f] shrink-0" />
                          <span className="text-xs font-mono text-slate-700 truncate">
                            {bidder.file.name}
                          </span>
                        </div>
                        <label className="text-[11px] text-blue-600 hover:text-blue-800 font-semibold cursor-pointer shrink-0">
                          Change
                          <input
                            type="file"
                            accept=".zip,application/zip"
                            onChange={(e) =>
                              handleBidderFileChange(bidder.id, e.target.files?.[0] || null)
                            }
                            className="hidden"
                          />
                        </label>
                      </div>
                    ) : (
                      <label className="flex items-center justify-center gap-2 p-2.5 rounded-lg bg-white hover:bg-slate-100 border border-dashed border-slate-300 hover:border-[#163a5f] text-xs font-semibold text-slate-600 cursor-pointer transition-colors">
                        <FolderArchive className="w-4 h-4 text-slate-400" />
                        <span>Upload Bidder ZIP</span>
                        <input
                          type="file"
                          accept=".zip,application/zip"
                          onChange={(e) =>
                            handleBidderFileChange(bidder.id, e.target.files?.[0] || null)
                          }
                          className="hidden"
                        />
                      </label>
                    )}
                  </div>

                  {/* Remove Button */}
                  <button
                    type="button"
                    onClick={() => handleRemoveBidder(bidder.id)}
                    className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer self-end sm:self-center shrink-0"
                    title="Remove bidder"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>

            {/* Add Bidder Row Button */}
            <button
              type="button"
              onClick={handleAddBidder}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold text-[#163a5f] hover:bg-blue-50/70 border border-slate-200 transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Another Bidder</span>
            </button>
          </div>

          {/* Action Row */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-between gap-4">
            <button
              type="button"
              onClick={handleResetForm}
              className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
            >
              Clear Form
            </button>

            <button
              type="button"
              onClick={handleSubmit}
              disabled={loading}
              className="flex-1 sm:flex-initial flex items-center justify-center gap-2 py-3 px-8 rounded-xl text-xs font-bold text-white bg-[#163a5f] hover:bg-[#102b48] active:bg-[#0c2035] shadow-2xs transition-all disabled:opacity-50 cursor-pointer"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Ingesting Procurement Package…</span>
                </>
              ) : (
                <>
                  <UploadCloud className="w-4 h-4" />
                  <span>Ingest Procurement</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-3 shadow-2xs">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
            <div>
              <strong className="font-bold">Ingestion Error:</strong> {error}
            </div>
          </div>
        )}

        {/* Ingestion Result Card */}
        {result && (
          <div className="p-6 sm:p-8 rounded-2xl bg-white border border-emerald-300 shadow-sm space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-2">
              <div className="flex items-center gap-2.5">
                <CheckCircle2 className="w-6 h-6 text-emerald-600" />
                <div>
                  <h3 className="font-bold text-[#111827] text-base">
                    Procurement Ingested & Persisted
                  </h3>
                  <p className="text-xs text-slate-500">
                    Case is now registered in the Opal Workspace.
                  </p>
                </div>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider self-start sm:self-auto ${
                  result.was_created
                    ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                    : "bg-blue-50 text-blue-800 border border-blue-200"
                }`}
              >
                {result.was_created ? "✨ Newly Created Case" : "🔄 Updated Match"}
              </span>
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center text-xs">
              <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Source Gateway</span>
                <span className="font-mono font-bold text-[#163a5f] text-sm mt-0.5 block">
                  {result.source_system}
                </span>
              </div>

              <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Bidders Registered</span>
                <span className="font-bold text-[#111827] text-sm mt-0.5 block">
                  {result.bidder_count}
                </span>
              </div>

              <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Submissions Ingested</span>
                <span className="font-bold text-[#111827] text-sm mt-0.5 block">
                  {result.submission_count}
                </span>
              </div>

              <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Documents Classified</span>
                <span className="font-bold text-emerald-700 text-sm mt-0.5 block">
                  {result.document_count}
                </span>
              </div>
            </div>

            {/* Details & Submission Deadline Status */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2 font-mono text-xs text-slate-700">
              <p>
                <span className="text-slate-400">External Ref:</span> {result.external_reference}
              </p>
              <p>
                <span className="text-slate-400">Procurement UUID:</span> {result.procurement_id}
              </p>

              {/* Deadline Status Display */}
              <div className="pt-2 border-t border-slate-200/60 flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-400" />
                {deadlineDate ? (
                  <span>
                    <span className="text-slate-500 font-sans">Document Submission Deadline:</span>{" "}
                    <strong className="text-slate-900 font-sans">
                      {deadlineDate.toLocaleDateString("en-GB", {
                        day: "numeric",
                        month: "long",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </strong>{" "}
                    {isDeadlinePast ? (
                      <span className="text-emerald-700 font-sans font-semibold">
                        (Deadline passed — Scrutiny unlocked)
                      </span>
                    ) : (
                      <span className="text-amber-700 font-sans font-semibold">
                        (Deadline active — Scrutiny locked until passed)
                      </span>
                    )}
                  </span>
                ) : (
                  <span className="text-amber-800 font-sans font-semibold">
                    Submission Deadline: Unavailable in document. Scrutiny locked.
                  </span>
                )}
              </div>
            </div>

            {/* Navigation Actions */}
            <div className="pt-2 flex flex-col sm:flex-row gap-3">
              <Link
                href={`/procurements/${result.procurement_id}`}
                className="flex-1 flex items-center justify-center gap-2 py-3 px-5 rounded-xl text-xs font-bold text-white bg-[#163a5f] hover:bg-[#102b48] shadow-2xs transition-all cursor-pointer"
              >
                <span>Open Command Page & Technical Scrutiny</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                href="/procurements"
                className="flex-1 flex items-center justify-center gap-2 py-3 px-5 rounded-xl text-xs font-bold text-slate-700 hover:text-[#111827] bg-slate-100 hover:bg-slate-200 border border-slate-200 transition-all cursor-pointer"
              >
                <span>View in Workspace Shelf</span>
                <ExternalLink className="w-4 h-4" />
              </Link>
              <button
                type="button"
                onClick={handleResetForm}
                className="px-4 py-3 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer"
              >
                Ingest Another Tender
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
