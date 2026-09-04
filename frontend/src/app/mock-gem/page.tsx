"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Building2,
  Database,
  UploadCloud,
  Play,
  CheckCircle2,
  AlertCircle,
  FolderArchive,
  ArrowRight,
  Code2,
  Info,
  Sparkles,
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
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-blue-600 selection:text-white">
      <Navbar />

      <main className="flex-1 max-w-5xl w-full mx-auto py-10 px-4 sm:px-6 lg:px-8 space-y-8">
        {/* Banner Notice */}
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 flex items-start gap-3 text-xs leading-relaxed">
          <Info className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <strong className="font-bold text-amber-200">Development Simulator Disclaimer:</strong>{" "}
            This interface simulates the future authorized GeM data exchange. It is not a live GeM connection. All data ingested here is fed into the canonical OPAL database model via the standard ingestion boundary.
          </div>
        </div>

        {/* Page Header */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30 text-xs font-semibold uppercase tracking-wider">
            <Building2 className="w-3.5 h-3.5 text-blue-400" />
            Mock GeM Development Simulator
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            External Procurement Source Simulator
          </h1>
          <p className="text-sm sm:text-base text-slate-400 max-w-2xl mx-auto">
            Simulate incoming procurement packages from an external source (GeM) into OPAL canonical entities without officer-facing file uploads.
          </p>
        </div>

        {/* Ingestion Actions Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Card 1: Fast Demo Package Ingestion */}
          <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-5 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono px-2.5 py-1 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 font-bold">
                  Preset Synthetic Package
                </span>
                <Sparkles className="w-4 h-4 text-yellow-400" />
              </div>
              <h3 className="text-lg font-bold text-white">Import Demo Procurement</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Ingest synthetic procurement <strong>DEMO/CPCL/WQM/2026/017</strong> (Chennai Petroleum Corp Ltd) containing 1 tender, 2 bidders, and 4 evidence documents.
              </p>
            </div>

            <button
              type="button"
              onClick={handleIngestDemo}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 active:bg-blue-700 shadow-md transition-all disabled:opacity-50 cursor-pointer"
            >
              <Play className="w-4 h-4 fill-current" />
              Ingest Synthetic Demo Package
            </button>
          </div>

          {/* Card 2: ZIP Package Ingestion */}
          <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-5 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono px-2.5 py-1 rounded bg-violet-500/20 text-violet-300 border border-violet-500/30 font-bold">
                  Archive (.zip) Payload
                </span>
                <FolderArchive className="w-4 h-4 text-violet-400" />
              </div>
              <h3 className="text-lg font-bold text-white">Upload Simulated GeM ZIP</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Upload a ZIP archive containing <code>metadata.json</code> and associated document files for automated ingestion.
              </p>
            </div>

            <div className="space-y-3">
              <input
                type="file"
                accept=".zip"
                onChange={(e) => setZipFile(e.target.files?.[0] || null)}
                className="block w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-slate-200 hover:file:bg-slate-700 cursor-pointer"
              />
              <button
                type="button"
                onClick={handleIngestZip}
                disabled={loading || !zipFile}
                className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs font-bold text-white bg-violet-600 hover:bg-violet-500 active:bg-violet-700 shadow-md transition-all disabled:opacity-50 cursor-pointer"
              >
                <UploadCloud className="w-4 h-4" />
                Ingest ZIP Package
              </button>
            </div>
          </div>
        </div>

        {/* Custom JSON Payload Input */}
        <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-300 flex items-center gap-2">
              <Code2 className="w-4 h-4 text-blue-400" />
              Custom JSON Procurement Package
            </span>
            <button
              type="button"
              onClick={handleIngestJson}
              disabled={loading}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg transition-colors cursor-pointer"
            >
              Submit Custom Package JSON
            </button>
          </div>

          <textarea
            value={customJson}
            onChange={(e) => setCustomJson(e.target.value)}
            rows={12}
            className="w-full font-mono text-xs p-4 rounded-xl bg-slate-950 border border-slate-800 text-green-400 focus:outline-none focus:border-blue-500 leading-relaxed"
          />
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0" />
            <div>
              <strong className="font-bold">Ingestion Error:</strong> {error}
            </div>
          </div>
        )}

        {/* Ingestion Outcome Result Card */}
        {result && (
          <div className="p-6 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-blue-950 border border-blue-500/40 shadow-xl space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <span className="font-extrabold text-white text-base">
                  Canonical Ingestion Outcome
                </span>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                  result.was_created
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                }`}
              >
                {result.was_created ? "✨ NEWLY CREATED" : "🔄 IDEMPOTENT MATCH (ALREADY PERSISTED)"}
              </span>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed font-mono bg-slate-950/60 p-3 rounded-lg border border-slate-800">
              {result.message}
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center text-xs">
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-slate-400 block text-[11px]">Source System</span>
                <span className="font-mono font-bold text-blue-400 text-sm">{result.source_system}</span>
              </div>

              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-slate-400 block text-[11px]">Bidders Ingested</span>
                <span className="font-bold text-white text-sm">{result.bidder_count}</span>
              </div>

              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-slate-400 block text-[11px]">Submissions</span>
                <span className="font-bold text-white text-sm">{result.submission_count}</span>
              </div>

              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-slate-400 block text-[11px]">Documents Registered</span>
                <span className="font-bold text-emerald-400 text-sm">{result.document_count}</span>
              </div>
            </div>

            <div className="space-y-1.5 font-mono text-xs text-slate-300 pt-2 border-t border-slate-800">
              <p><span className="text-slate-500">Procurement UUID:</span> {result.procurement_id}</p>
              <p><span className="text-slate-500">External Ref:</span> {result.external_reference}</p>
              <p><span className="text-slate-500">Tender UUID:</span> {result.tender_id}</p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
