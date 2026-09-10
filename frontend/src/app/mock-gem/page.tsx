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
  Sparkles,
  Download,
  Loader2,
  Plus,
  Trash2,
  Building2,
  FileCheck,
  RefreshCw,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import {
  ingestMockGeMFiles,
  ingestMockGeMZip,
  ingestMockGeMDemo,
} from "@/services/api";

interface BidderItem {
  id: string;
  file: File;
  name: string;
}

export default function MockGeMIntakePage() {
  const [activeTab, setActiveTab] = useState<"files" | "archive" | "demo">("files");

  // Multi-File Intake State
  const [tenderFile, setTenderFile] = useState<File | null>(null);
  const [bidderList, setBidderList] = useState<BidderItem[]>([]);
  const [customTitle, setCustomTitle] = useState<string>("");
  const [customOrg, setCustomOrg] = useState<string>("");

  // Single Archive State
  const [singleZipFile, setSingleZipFile] = useState<File | null>(null);

  // Common UI State
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);

  const tenderInputRef = useRef<HTMLInputElement>(null);
  const bidderInputRef = useRef<HTMLInputElement>(null);

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

  // Handle Bidder ZIP selection (supports multiple files)
  const handleBiddersChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const newItems: BidderItem[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (!file.name.toLowerCase().endsWith(".zip")) {
        setError(`File "${file.name}" is not a .zip archive. All bidder packages must be .zip files.`);
        return;
      }
      const rawName = file.name
        .replace(/\.zip$/i, "")
        .replace(/^(bidder|submission|package)[-_]/i, "")
        .replace(/[-_]/g, " ")
        .trim();
      const derivedName = rawName ? `${rawName} Pvt Ltd` : `Bidder ${bidderList.length + newItems.length + 1} Pvt Ltd`;

      newItems.push({
        id: `${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
        file,
        name: derivedName,
      });
    }

    setBidderList((prev) => [...prev, ...newItems]);
    if (bidderInputRef.current) {
      bidderInputRef.current.value = "";
    }
  };

  const handleRemoveBidder = (id: string) => {
    setBidderList((prev) => prev.filter((b) => b.id !== id));
  };

  // Submit Live Multi-File Intake
  const handleSubmitFiles = async () => {
    setError(null);
    setResult(null);

    if (!tenderFile) {
      setError("Please upload a Tender Specification PDF document.");
      return;
    }

    if (bidderList.length === 0) {
      setError("Please upload at least one Bidder Submission ZIP package.");
      return;
    }

    setLoading(true);
    try {
      const bidderFiles = bidderList.map((b) => b.file);
      const res = await ingestMockGeMFiles(tenderFile, bidderFiles, {
        title: customTitle.trim() || undefined,
        organization: customOrg.trim() || undefined,
      });
      setResult(res);
    } catch (err: any) {
      setError(err?.message || "Failed to ingest procurement package.");
    } finally {
      setLoading(false);
    }
  };

  // Submit Single Archive ZIP
  const handleSubmitArchive = async () => {
    setError(null);
    setResult(null);

    if (!singleZipFile) {
      setError("Please select a ZIP package file containing procurement documents.");
      return;
    }

    setLoading(true);
    try {
      const res = await ingestMockGeMZip(singleZipFile);
      setResult(res);
    } catch (err: any) {
      setError(err?.message || "ZIP package ingestion failed.");
    } finally {
      setLoading(false);
    }
  };

  // Submit Preset Demo Package
  const handleIngestDemo = async () => {
    setError(null);
    setResult(null);
    setLoading(true);

    try {
      const res = await ingestMockGeMDemo();
      setResult(res);
    } catch (err: any) {
      setError(err?.message || "Failed to ingest synthetic demo package.");
    } finally {
      setLoading(false);
    }
  };

  const handleResetForm = () => {
    setTenderFile(null);
    setBidderList([]);
    setSingleZipFile(null);
    setCustomTitle("");
    setCustomOrg("");
    setError(null);
    setResult(null);
  };

  return (
    <div className="min-h-screen bg-[#f7f6f2] text-[#162333] flex flex-col font-sans selection:bg-[#d8e6ee]">
      <Navbar />

      <main className="flex-1 max-w-5xl w-full mx-auto py-10 px-5 sm:px-8 space-y-8">
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
              Procurements appear in Opal only when ingested through Mock-GeM. Upload official tender specifications and bidder submission packages to register live cases for compliance review.
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

        {/* Sample Bundle Download Card */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-2xs flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center shrink-0">
              <FolderArchive className="w-5 h-5 text-[#163a5f]" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-[#111827]">Sample Tender & Bidders Test Packages</h4>
              <p className="text-xs text-slate-500 mt-0.5">
                Download the official sample documents bundle containing CPCL tender RFP and bidder submission documents.
              </p>
            </div>
          </div>
          <a
            href="/sample_documents/Mock_GeM_CPCL_Tender_and_Bidders_Package.zip"
            download="Mock_GeM_CPCL_Tender_and_Bidders_Package.zip"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#163a5f] hover:bg-[#102b48] active:bg-[#0c2035] text-white font-bold text-xs shadow-2xs transition-all shrink-0 cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download Sample ZIP Bundle</span>
          </a>
        </div>

        {/* Ingestion Mode Tabs */}
        <div className="flex border-b border-slate-200 gap-2 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setActiveTab("files")}
            className={`pb-3 px-3 transition-colors cursor-pointer border-b-2 ${
              activeTab === "files"
                ? "border-[#163a5f] text-[#163a5f] font-bold"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Tender PDF + Bidder ZIPs (Recommended)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("archive")}
            className={`pb-3 px-3 transition-colors cursor-pointer border-b-2 ${
              activeTab === "archive"
                ? "border-[#163a5f] text-[#163a5f] font-bold"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Combined Package Archive (.ZIP)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("demo")}
            className={`pb-3 px-3 transition-colors cursor-pointer border-b-2 ${
              activeTab === "demo"
                ? "border-[#163a5f] text-[#163a5f] font-bold"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Synthetic Preset (Quick Import)
          </button>
        </div>

        {/* TAB 1: Live Tender PDF + Multi-Bidder ZIP Uploads */}
        {activeTab === "files" && (
          <div className="space-y-6">
            <div className="p-6 sm:p-8 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-8">
              {/* Step 1: Tender Specification Document */}
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
                  Upload the official Notice Inviting Tender (NIT) or RFP document in PDF format. Requirements and eligibility criteria will be extracted dynamically.
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
                      onClick={() => setTenderFile(null)}
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

              {/* Step 2: Bidder Submissions (Multiple Bidders) */}
              <div className="space-y-3 pt-6 border-t border-slate-100">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-[#163a5f] text-white text-xs font-bold flex items-center justify-center">
                      2
                    </span>
                    <h3 className="text-base font-bold text-[#111827]">
                      Bidder Submission Packages (.ZIP)
                    </h3>
                  </div>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-bold">
                    Multi-Bidder Supported
                  </span>
                </div>
                <p className="text-xs text-slate-500">
                  Upload one or more bidder packages (each packaged as a .zip containing bidder evidence like GST, MII, Turnover, MAF, and Commercial BOQ).
                </p>

                {/* Selected Bidder Packages List */}
                {bidderList.length > 0 && (
                  <div className="space-y-2">
                    {bidderList.map((b, idx) => (
                      <div
                        key={b.id}
                        className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between gap-4"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="w-6 h-6 rounded-full bg-slate-200 text-slate-700 text-[11px] font-bold flex items-center justify-center shrink-0">
                            {idx + 1}
                          </span>
                          <FolderArchive className="w-5 h-5 text-[#163a5f] shrink-0" />
                          <div className="min-w-0">
                            <p className="text-xs font-bold text-slate-900 truncate">
                              {b.name}
                            </p>
                            <p className="text-[11px] text-slate-400 font-mono">
                              {b.file.name} ({(b.file.size / 1024).toFixed(1)} KB)
                            </p>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleRemoveBidder(b.id)}
                          className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                          title="Remove bidder package"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Add Bidder Button Dropzone */}
                <div
                  onClick={() => bidderInputRef.current?.click()}
                  className="border-2 border-dashed border-slate-300 hover:border-[#163a5f] hover:bg-slate-50/70 transition-all rounded-xl p-5 text-center cursor-pointer flex items-center justify-center gap-2"
                >
                  <Plus className="w-4 h-4 text-slate-500" />
                  <span className="text-xs font-semibold text-slate-700">
                    {bidderList.length > 0 ? "Add Another Bidder ZIP Package" : "Click to select Bidder ZIP Package(s)"}
                  </span>
                  <input
                    ref={bidderInputRef}
                    type="file"
                    multiple
                    accept=".zip,application/zip"
                    onChange={handleBiddersChange}
                    className="hidden"
                  />
                </div>
              </div>

              {/* Step 3: Optional Metadata Override */}
              <div className="space-y-3 pt-6 border-t border-slate-100">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-slate-200 text-slate-700 text-xs font-bold flex items-center justify-center">
                    3
                  </span>
                  <h3 className="text-sm font-bold text-[#111827]">
                    Optional Metadata Override
                  </h3>
                  <span className="text-[10px] text-slate-400">(Auto-extracted from PDF if blank)</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">
                      Procurement Project Title
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Supply of Industrial Sensors"
                      value={customTitle}
                      onChange={(e) => setCustomTitle(e.target.value)}
                      className="w-full text-xs p-2.5 rounded-xl border border-slate-200 focus:outline-none focus:border-[#163a5f] bg-[#fafaf8]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">
                      Procuring Entity / Ministry
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Chennai Petroleum Corporation Limited"
                      value={customOrg}
                      onChange={(e) => setCustomOrg(e.target.value)}
                      className="w-full text-xs p-2.5 rounded-xl border border-slate-200 focus:outline-none focus:border-[#163a5f] bg-[#fafaf8]"
                    />
                  </div>
                </div>
              </div>

              {/* Submit Button */}
              <div className="pt-4 flex items-center justify-between gap-4">
                <button
                  type="button"
                  onClick={handleResetForm}
                  className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  Clear All
                </button>

                <button
                  type="button"
                  onClick={handleSubmitFiles}
                  disabled={loading}
                  className="flex-1 sm:flex-initial flex items-center justify-center gap-2 py-3 px-8 rounded-xl text-xs font-bold text-white bg-[#163a5f] hover:bg-[#102b48] active:bg-[#0c2035] shadow-2xs transition-all disabled:opacity-50 cursor-pointer"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Ingesting & Parsing Package into Opal…</span>
                    </>
                  ) : (
                    <>
                      <UploadCloud className="w-4 h-4" />
                      <span>Ingest Procurement Case ({bidderList.length} Bidders)</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: Combined Package Archive */}
        {activeTab === "archive" && (
          <div className="p-6 sm:p-8 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-6">
            <div>
              <h3 className="text-base font-bold text-[#111827]">
                Upload Combined GeM Archive (.ZIP)
              </h3>
              <p className="text-xs text-slate-500 mt-1">
                Upload a complete ZIP package containing the tender specification PDF and bidder PDF folders (or a metadata.json manifest).
              </p>
            </div>

            <div className="space-y-4">
              <input
                type="file"
                accept=".zip,application/zip"
                onChange={(e) => setSingleZipFile(e.target.files?.[0] || null)}
                className="block w-full text-xs text-slate-600 file:mr-3 file:py-2.5 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-slate-100 file:text-slate-800 hover:file:bg-slate-200 cursor-pointer border border-slate-200 rounded-xl p-2 bg-[#fafaf8]"
              />

              <button
                type="button"
                onClick={handleSubmitArchive}
                disabled={loading || !singleZipFile}
                className="w-full flex items-center justify-center gap-2 py-3 px-6 rounded-xl text-xs font-bold text-white bg-[#163a5f] hover:bg-[#102b48] active:bg-[#0c2035] shadow-2xs transition-all disabled:opacity-50 cursor-pointer"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
                <span>Ingest Archive Package into Opal</span>
              </button>
            </div>
          </div>
        )}

        {/* TAB 3: Synthetic Preset Demo */}
        {activeTab === "demo" && (
          <div className="p-6 sm:p-8 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-6">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-bold">
                  Preset Synthetic Package
                </span>
                <Sparkles className="w-4 h-4 text-amber-500" />
              </div>
              <h3 className="text-lg font-bold text-[#111827]">Import Canonical CPCL Package</h3>
              <p className="text-xs text-slate-500 leading-relaxed max-w-xl">
                Ingest synthetic procurement <strong>DEMO/CPCL/WQM/2026/017</strong> (Chennai Petroleum Corp Ltd) containing 1 tender, 3 bidders (HydroTech, AquaPure, CleanFlow), and evidence documents.
              </p>
            </div>

            <button
              type="button"
              onClick={handleIngestDemo}
              disabled={loading}
              className="flex items-center justify-center gap-2 py-3 px-6 rounded-xl text-xs font-bold text-white bg-[#163a5f] hover:bg-[#102b48] active:bg-[#0c2035] shadow-2xs transition-all disabled:opacity-50 cursor-pointer"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              <span>Ingest Canonical CPCL Demo Package</span>
            </button>
          </div>
        )}

        {/* Honest Error Banner */}
        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-3 shadow-2xs">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
            <div>
              <strong className="font-bold">Ingestion Rejection:</strong> {error}
            </div>
          </div>
        )}

        {/* Ingestion Outcome Result Card */}
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
                    Case is now active in the Opal Workspace and ready for technical scrutiny.
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
                {result.was_created ? "✨ Newly Created Case" : "🔄 Updated / Idempotent Match"}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center text-xs">
              <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Source Gateway</span>
                <span className="font-mono font-bold text-[#163a5f] text-sm mt-0.5 block">{result.source_system}</span>
              </div>

              <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Bidders Registered</span>
                <span className="font-bold text-[#111827] text-sm mt-0.5 block">{result.bidder_count}</span>
              </div>

              <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Submissions Ingested</span>
                <span className="font-bold text-[#111827] text-sm mt-0.5 block">{result.submission_count}</span>
              </div>

              <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Documents Classified</span>
                <span className="font-bold text-emerald-700 text-sm mt-0.5 block">{result.document_count}</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5 font-mono text-xs text-slate-700">
              <p><span className="text-slate-400">External Ref:</span> {result.external_reference}</p>
              <p><span className="text-slate-400">Procurement UUID:</span> {result.procurement_id}</p>
              {result.tender_id && (
                <p><span className="text-slate-400">Tender UUID:</span> {result.tender_id}</p>
              )}
              <p className="text-emerald-700 font-semibold pt-1">
                ✓ Submission deadline gate verified: Deadline passed, scrutiny unlocked.
              </p>
            </div>

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
                <ArrowRight className="w-4 h-4" />
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
