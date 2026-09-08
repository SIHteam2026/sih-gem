"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowUpRight,
  Clock3,
  RefreshCw,
  CheckCircle2,
  Loader2,
  XCircle,
  Trash2,
  FolderGit2,
  ShieldCheck,
  FileText,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { fetchProcurements, clearProcurementLogs } from "@/services/api";

interface ProcurementRecord {
  id: string;
  external_reference?: string;
  title?: string;
  organization?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
  tender_count?: number;
  bidder_count?: number;
  document_count?: number;
}

export default function HistoryPage() {
  const [procurements, setProcurements] = useState<ProcurementRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchProcurements(10, 0);
      const items: ProcurementRecord[] = Array.isArray(data)
        ? data
        : Array.isArray(data?.items)
        ? data.items
        : Array.isArray(data?.procurements)
        ? data.procurements
        : [];

      // Sort descending by created_at and retain at most 7 (2 active + max 5 logs)
      const sorted = [...items]
        .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
        .slice(0, 7);

      setProcurements(sorted);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Review history could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleClearLogs = async () => {
    setClearing(true);
    setError(null);
    try {
      await clearProcurementLogs(2);
      // Immediately retain only the latest 2 active procurements in local state
      setProcurements((prev) => prev.slice(0, 2));
      setSuccessMessage("All historical logs cleared successfully from the application. The 2 latest active procurements have been retained for the officer.");
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to clear logs.");
    } finally {
      setClearing(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  // Derive latest 2 active procurements for the officer and max 5 historical logs
  const activeProcurements = procurements.slice(0, 2);
  const logProcurements = procurements.slice(2, 7);

  return (
    <div className="min-h-screen bg-[#f7f6f2]">
      <Navbar />
      <main className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-14">
        {/* Page Header */}
        <div className="flex flex-col justify-between gap-5 border-b border-slate-200 pb-8 sm:flex-row sm:items-end">
          <div>
            <p className="font-mono uppercase text-xs font-semibold tracking-wider text-slate-500">
              Statutory Record of Activity
            </p>
            <h1 className="mt-1.5 text-3xl sm:text-4xl font-bold tracking-tight text-[#111827]">
              Audit Trail & Activity Log
            </h1>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-500">
              A chronological ledger of completed statutory document verifications, evidence checks, and procurement workspaces.
            </p>
          </div>

          <div className="flex items-center gap-3 self-start sm:self-auto">
            {/* Clear Log Button */}
            <button
              type="button"
              onClick={handleClearLogs}
              disabled={clearing || loading || logProcurements.length === 0}
              className="focus-ring inline-flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50/70 px-4 py-2.5 text-xs font-bold text-rose-700 shadow-2xs transition-all hover:bg-rose-100/80 hover:shadow-xs disabled:opacity-40 disabled:pointer-events-none cursor-pointer"
              title="Clears all historical logs while keeping the 2 active procurements for the officer"
            >
              {clearing ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-rose-600" />
              ) : (
                <Trash2 className="h-3.5 w-3.5 text-rose-600" />
              )}
              <span>Clear Logs</span>
            </button>

            {/* Refresh Button */}
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="focus-ring inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-700 shadow-2xs transition-all hover:bg-slate-50 hover:shadow-xs disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Success Alert */}
        {successMessage && (
          <div className="mt-6 flex items-center gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-xs font-medium text-emerald-900 shadow-2xs">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="mt-6 flex gap-3 rounded-lg border border-[#e3c8b9] bg-[#fff8f4] p-4 text-sm text-[#7b3d20]">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Section 1: Active Officer Procurements (Latest 2) */}
        <div className="mt-8">
          <div className="flex items-center justify-between mb-3 px-1">
            <div className="flex items-center gap-2">
              <FolderGit2 className="h-4 w-4 text-[#163a5f]" />
              <h2 className="text-sm font-bold text-[#111827] uppercase tracking-wider">
                Active Officer Cases (Latest 2)
              </h2>
            </div>
            <span className="inline-flex items-center rounded-full bg-blue-50 border border-blue-200 px-2.5 py-0.5 text-[11px] font-semibold text-blue-800">
              {activeProcurements.length} Active Displayed
            </span>
          </div>

          <div className="rounded-xl border border-[#d9ddd9] bg-white overflow-hidden shadow-2xs">
            {loading ? (
              <div className="flex min-h-32 items-center justify-center gap-3 text-sm text-[#6e7980]">
                <RefreshCw className="h-5 w-5 animate-spin text-[#163a5f]" />
                Loading active procurements…
              </div>
            ) : activeProcurements.length > 0 ? (
              <div className="divide-y divide-[#edf2f7]">
                {activeProcurements.map((proc, index) => (
                  <ProcurementHistoryRow key={proc.id || `active-${index}`} procurement={proc} isLog={false} />
                ))}
              </div>
            ) : (
              <div className="py-12 text-center text-slate-500">
                <Clock3 className="mx-auto h-7 w-7 text-slate-400" />
                <p className="mt-2 text-sm font-medium text-slate-700">No active procurements in workspace</p>
                <p className="text-xs text-slate-500 mt-1">Ingest a tender package in Mock-GeM to start.</p>
              </div>
            )}
          </div>
        </div>

        {/* Section 2: Historical Logs (Max 5 Allowed) */}
        <div className="mt-10">
          <div className="flex items-center justify-between mb-3 px-1">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-slate-600" />
              <h2 className="text-sm font-bold text-[#111827] uppercase tracking-wider">
                Logs Section (Max 5 Allowed)
              </h2>
            </div>
            <span className="inline-flex items-center rounded-full bg-slate-100 border border-slate-200 px-2.5 py-0.5 text-[11px] font-semibold text-slate-700">
              {logProcurements.length} / 5 Logs
            </span>
          </div>

          <div className="rounded-xl border border-[#d9ddd9] bg-white overflow-hidden shadow-2xs">
            {loading ? (
              <div className="flex min-h-32 items-center justify-center gap-3 text-sm text-[#6e7980]">
                <RefreshCw className="h-5 w-5 animate-spin text-[#163a5f]" />
                Loading logs…
              </div>
            ) : logProcurements.length > 0 ? (
              <div className="divide-y divide-[#edf2f7]">
                {logProcurements.map((proc, index) => (
                  <ProcurementHistoryRow key={proc.id || `log-${index}`} procurement={proc} isLog={true} />
                ))}
              </div>
            ) : (
              <div className="py-12 text-center text-slate-500">
                <ShieldCheck className="mx-auto h-7 w-7 text-slate-400" />
                <p className="mt-2 text-sm font-medium text-slate-700">No records in logs section</p>
                <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                  Prior procurements beyond the latest 2 active cases will appear here (max 5 allowed). Older records are automatically cleared.
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

function ProcurementHistoryRow({
  procurement,
  isLog = false,
}: {
  procurement: ProcurementRecord;
  isLog?: boolean;
}) {
  const status = (procurement.status || "READY").toUpperCase();
  const date = procurement.created_at || procurement.updated_at;
  const organization = procurement.organization || "Public Sector Procurement";
  const title = procurement.title || "Procurement Package Verification";
  const reference = procurement.external_reference || procurement.id;

  const getStatusBadge = () => {
    switch (status) {
      case "PROCESSING":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 border border-blue-200 px-3 py-1 text-xs font-semibold text-blue-800">
            <Loader2 className="h-3 w-3 animate-spin text-blue-600" />
            PROCESSING
          </span>
        );
      case "READY":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1 text-xs font-semibold text-emerald-800">
            <CheckCircle2 className="h-3 w-3 text-emerald-600" />
            READY
          </span>
        );
      case "FAILED":
      case "ERROR":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 border border-rose-200 px-3 py-1 text-xs font-semibold text-rose-800">
            <XCircle className="h-3 w-3 text-rose-600" />
            FAILED
          </span>
        );
      case "CONFIRMED":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-300 px-3 py-1 text-xs font-semibold text-emerald-900">
            <CheckCircle2 className="h-3 w-3 text-emerald-700" />
            CONFIRMED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center rounded-full bg-slate-100 border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700">
            {status.replace(/_/g, " ")}
          </span>
        );
    }
  };

  return (
    <Link
      href={`/procurements/${procurement.id}`}
      className="group block p-5 sm:p-6 transition-colors hover:bg-[#fbfcfb]"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {/* Left info */}
        <div className="space-y-1 min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold text-[#163a5f] bg-[#eef4f8] px-2 py-0.5 rounded">
              {reference}
            </span>
            {isLog ? (
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
                Log
              </span>
            ) : (
              <span className="text-[10px] font-bold uppercase tracking-wider text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                Active
              </span>
            )}
            <span className="text-xs text-[#64748b] truncate">{organization}</span>
          </div>
          <h2 className="text-base font-semibold text-[#111827] group-hover:text-[#163a5f] transition-colors truncate">
            {title}
          </h2>
        </div>

        {/* Right metadata and status */}
        <div className="flex items-center justify-between sm:justify-end gap-5 shrink-0">
          <div className="text-left sm:text-right">
            <p className="text-xs text-[#64748b]">
              {date
                ? new Date(date).toLocaleString("en-IN", {
                    dateStyle: "medium",
                    timeStyle: "short",
                  })
                : "Recent"}
            </p>
          </div>
          <div>{getStatusBadge()}</div>
          <ArrowUpRight className="h-5 w-5 text-[#94a3b8] transition-transform group-hover:text-[#163a5f] group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
        </div>
      </div>
    </Link>
  );
}
