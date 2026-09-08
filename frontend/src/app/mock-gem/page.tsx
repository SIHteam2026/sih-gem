"use client";

import { useState } from "react";
import Link from "next/link";
import {
  UploadCloud,
  Play,
  CheckCircle2,
  AlertCircle,
  FolderArchive,
  ArrowRight,
  Code2,
  Sparkles,
  Download,
  Loader2,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import {
  ingestMockGeMDemo,
  ingestMockGeMPackage,
  ingestMockGeMZip,
} from "@/services/api";

export default function MockGeMSimulatorPage() {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);

  // Custom JSON Ingestion State
  const [customJson, setCustomJson] = useState<string>(`{
  "source_system": "MOCK_GEM",
  "external_reference": "DEMO/CPCL/WQM/2026/017",
  "procurement": {
    "title": "Supply and commissioning of industrial water quality monitoring units",
    "organization": "Chennai Petroleum Corporation Limited (CPCL)"
  },
  "tender": {
    "tender_reference": "CPCL/WQM/2026/RFP-017",
    "title": "RFP for Industrial Water Quality Monitoring Sensor Network",
    "description": "Turnkey procurement of online water quality sensors.",
    "estimated_value": 45000000.0,
    "category": "INDUSTRIAL_EQUIPMENT",
    "documents": [
      {
        "filename": "RFP_Specification_WQM_2026_017.pdf",
        "document_type": "TENDER_SPECIFICATION",
        "mime_type": "application/pdf",
        "file_size": 3240000,
        "content_text": "Notice Inviting Tender for CPCL Water Quality Sensors..."
      }
    ]
  },
  "bidders": [
    {
      "bidder": {
        "legal_name": "HydroTech Analytics India Pvt Ltd",
        "gstin": "33AAACH123411Z9",
        "pan": "AAACH12341",
        "email": "bids@hydrotech.co.in"
      },
      "submission": {
        "external_submission_reference": "GEM-SUB-HTA-2026-017",
        "status": "SUBMITTED"
      },
      "documents": [
        {
          "filename": "HydroTech_GST_Registration.pdf",
          "document_type": "GST_CERTIFICATE",
          "mime_type": "application/pdf",
          "file_size": 450000,
          "content_text": "GSTIN: 33AAACH123411Z9..."
        }
      ]
    }
  ]
}`);

  // Zip Upload State
  const [zipFile, setZipFile] = useState<File | null>(null);

  const handleIngestDemo = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await ingestMockGeMDemo();
      setResult(res);
    } catch (err: any) {
      setError(err?.message || "Failed to ingest demo procurement.");
    } finally {
      setLoading(false);
    }
  };

  const handleIngestJson = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const parsedPayload = JSON.parse(customJson);
      const res = await ingestMockGeMPackage(parsedPayload);
      setResult(res);
    } catch (err: any) {
      setError(err?.message || "Invalid JSON payload or ingestion error.");
    } finally {
      setLoading(false);
    }
  };

  const handleIngestZip = async () => {
    if (!zipFile) {
      setError("Please select a ZIP package file first.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await ingestMockGeMZip(zipFile);
      setResult(res);
    } catch (err: any) {
      setError(err?.message || "ZIP package ingestion failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f7f6f2] text-[#162333] flex flex-col font-sans selection:bg-[#d8e6ee]">
      <Navbar />

      <main className="flex-1 max-w-5xl w-full mx-auto py-10 px-5 sm:px-8 space-y-8">
        {/* Page Header */}
        <div className="border-b border-slate-200 pb-6">
          <p className="font-mono uppercase text-xs font-semibold tracking-wider text-slate-500">
            GeM Integration
          </p>
          <h1 className="mt-1 text-3xl sm:text-4xl font-bold tracking-tight text-[#111827]">
            GeM Integration Gateway
          </h1>
          <p className="mt-1.5 text-sm text-[#64748b] max-w-2xl">
            Simulate and ingest procurement packages from Government e-Marketplace (GeM) into OPAL canonical entities.
          </p>
        </div>

        {/* Sample Documents ZIP Download Banner */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-2xs flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center shrink-0">
              <FolderArchive className="w-5 h-5 text-[#163a5f]" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-[#111827]">Download Sample Bidder PDFs & Tender Archive (.ZIP)</h4>
              <p className="text-xs text-slate-500 mt-0.5">
                Contains all 8 official PDF documents (Tender RFP, HydroTech GST/MII/Turnover/MAF, AquaPure GST/MII/Turnover).
              </p>
            </div>
          </div>
          <a
            href="/sample_documents/Mock_GeM_CPCL_Tender_and_Bidders_Package.zip"
            download="Mock_GeM_CPCL_Tender_and_Bidders_Package.zip"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#163a5f] hover:bg-[#102b48] active:bg-[#0c2035] text-white font-bold text-xs shadow-2xs transition-all shrink-0 cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download ZIP Bundle</span>
          </a>
        </div>

        {/* Ingestion Actions Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 sm:gap-8">
          {/* Card 1: Fast Demo Package Ingestion */}
          <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-5 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-bold">
                  Preset Synthetic Package
                </span>
                <Sparkles className="w-4 h-4 text-amber-500" />
              </div>
              <h3 className="text-lg font-bold text-[#111827]">Import Demo Procurement</h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                Ingest synthetic procurement <strong>DEMO/CPCL/WQM/2026/017</strong> (Chennai Petroleum Corp Ltd) containing 1 tender, 2 bidders, and 4 evidence documents.
              </p>
            </div>

            <button
              type="button"
              onClick={handleIngestDemo}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs font-bold text-white bg-[#163a5f] hover:bg-[#102b48] active:bg-[#0c2035] shadow-2xs transition-all disabled:opacity-50 cursor-pointer"
            >
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
              <span>Ingest Synthetic Demo Package</span>
            </button>
          </div>

          {/* Card 2: ZIP Package Ingestion */}
          <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-5 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200 font-bold">
                  Archive (.zip) Payload
                </span>
                <FolderArchive className="w-4 h-4 text-purple-600" />
              </div>
              <h3 className="text-lg font-bold text-[#111827]">Upload Simulated GeM ZIP</h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                Upload a ZIP archive containing <code>metadata.json</code> and associated document files for automated ingestion.
              </p>
            </div>

            <div className="space-y-3">
              <input
                type="file"
                accept=".zip"
                onChange={(e) => setZipFile(e.target.files?.[0] || null)}
                className="block w-full text-xs text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-100 file:text-slate-800 hover:file:bg-slate-200 cursor-pointer border border-slate-200 rounded-xl p-1.5 bg-[#fafaf8]"
              />
              <button
                type="button"
                onClick={handleIngestZip}
                disabled={loading || !zipFile}
                className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs font-bold text-white bg-[#1e293b] hover:bg-[#0f172a] active:bg-black shadow-2xs transition-all disabled:opacity-50 cursor-pointer"
              >
                {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
                <span>Ingest ZIP Package</span>
              </button>
            </div>
          </div>
        </div>

        {/* Custom JSON Payload Input */}
        <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-700 flex items-center gap-2">
              <Code2 className="w-4 h-4 text-[#163a5f]" />
              Custom JSON Procurement Package
            </span>
            <button
              type="button"
              onClick={handleIngestJson}
              disabled={loading}
              className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold rounded-xl shadow-2xs transition-colors cursor-pointer"
            >
              {loading ? "Processing…" : "Submit Custom Package JSON"}
            </button>
          </div>

          <textarea
            value={customJson}
            onChange={(e) => setCustomJson(e.target.value)}
            rows={12}
            className="w-full font-mono text-xs p-4 rounded-xl bg-[#fafaf8] border border-slate-300 text-slate-800 focus:outline-none focus:border-[#163a5f] leading-relaxed shadow-inner"
          />
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-3 shadow-2xs">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <div>
              <strong className="font-bold">Ingestion Error:</strong> {error}
            </div>
          </div>
        )}

        {/* Ingestion Outcome Result Card */}
        {result && (
          <div className="p-6 rounded-2xl bg-white border border-emerald-300 shadow-sm space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                <span className="font-bold text-[#111827] text-base">
                  Canonical Ingestion Outcome
                </span>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                  result.was_created
                    ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                    : "bg-amber-50 text-amber-800 border border-amber-200"
                }`}
              >
                {result.was_created ? "✨ Newly Created" : "🔄 Idempotent Match (Already Persisted)"}
              </span>
            </div>

            <p className="text-xs text-slate-700 leading-relaxed font-mono bg-slate-50 p-3.5 rounded-xl border border-slate-200">
              {result.message}
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center text-xs">
              <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Source System</span>
                <span className="font-mono font-bold text-[#163a5f] text-sm mt-0.5 block">{result.source_system}</span>
              </div>

              <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Bidders Ingested</span>
                <span className="font-bold text-[#111827] text-sm mt-0.5 block">{result.bidder_count}</span>
              </div>

              <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Submissions</span>
                <span className="font-bold text-[#111827] text-sm mt-0.5 block">{result.submission_count}</span>
              </div>

              <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Documents Registered</span>
                <span className="font-bold text-emerald-700 text-sm mt-0.5 block">{result.document_count}</span>
              </div>
            </div>

            <div className="space-y-1.5 font-mono text-xs text-slate-600 pt-2 border-t border-slate-100">
              <p><span className="text-slate-400">Procurement UUID:</span> {result.procurement_id}</p>
              <p><span className="text-slate-400">External Ref:</span> {result.external_reference}</p>
              <p><span className="text-slate-400">Tender UUID:</span> {result.tender_id}</p>
            </div>

            <div className="pt-2 flex flex-col sm:flex-row gap-3">
              <Link
                href={`/procurements/${result.procurement_id}`}
                className="flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs font-bold text-white bg-[#163a5f] hover:bg-[#102b48] shadow-2xs transition-all cursor-pointer"
              >
                <span>Open Procurement Workspace</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
              {result.tender_id && (
                <Link
                  href={`/tenders/${result.tender_id}`}
                  className="flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs font-bold text-slate-700 hover:text-[#111827] bg-slate-100 hover:bg-slate-200 border border-slate-200 transition-all cursor-pointer"
                >
                  <span>Open Tender Workspace</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
