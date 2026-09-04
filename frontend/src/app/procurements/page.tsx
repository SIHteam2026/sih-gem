"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  FolderKanban,
  FileSpreadsheet,
  Users,
  FileText,
  ArrowUpRight,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { fetchProcurements } from "@/services/api";
import { ProcurementSummaryItem, ProcurementListResponse } from "@/types/procurement";
import StatusBadge from "@/components/procurement/StatusBadge";
import SourceBadge from "@/components/procurement/SourceBadge";
import { LoadingState, EmptyState, ErrorState } from "@/components/procurement/States";

export default function ProcurementsPage() {
  const [procurements, setProcurements] = useState<ProcurementSummaryItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadProcurements = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = (await fetchProcurements(50, 0)) as ProcurementListResponse;
      setProcurements(data?.procurements || []);
      setTotal(data?.total || 0);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load procurement list from server.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProcurements();
  }, [loadProcurements]);

  return (
    <div className="min-h-screen bg-[#f7f6f2] text-[#162333] flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-6xl w-full mx-auto px-5 py-10 sm:px-8 sm:py-14">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-5 border-b border-[#d9ddd9] pb-8">
          <div>
            <p className="eyebrow">Officer Workspace</p>
            <h1 className="mt-2 text-3xl sm:text-4xl font-medium tracking-tight text-[#162333]">
              Procurements
            </h1>
            <p className="mt-2.5 max-w-xl text-sm leading-relaxed text-[#616e7a]">
              Active procurement workspaces ingested from authorized sources. Select a procurement to inspect its tenders, requirements, and bidder evidence.
            </p>
          </div>

          <div className="flex items-center gap-3 self-start sm:self-auto">
            <button
              type="button"
              onClick={loadProcurements}
              disabled={loading}
              className="focus-ring inline-flex items-center gap-2 px-3.5 py-2 text-xs font-medium border border-[#cfd5d5] bg-[#fffefa] hover:bg-white text-[#2c3f4e] rounded transition-colors disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
              Refresh
            </button>

            <Link
              href="/mock-gem"
              className="focus-ring inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-[#4a5b69] border border-dashed border-[#ccd3d7] bg-[#fbfbf9] hover:bg-white rounded transition-colors"
              title="Open the development simulator to ingest sample procurement packages"
            >
              <ExternalLink className="w-3.5 h-3.5 text-[#73828f]" aria-hidden="true" />
              Mock-GeM (Dev)
            </Link>
          </div>
        </div>

        {/* Status / Content Section */}
        <div className="mt-8">
          {error && (
            <ErrorState
              title="Procurement service unavailable"
              message={error}
              onRetry={loadProcurements}
              className="mb-6"
            />
          )}

          {loading ? (
            <LoadingState message="Fetching active procurement workspaces…" />
          ) : procurements.length === 0 ? (
            <EmptyState
              title="No procurements available"
              description="No active procurement cases are currently registered. Procurements arrive automatically when ingested from external sources. You can use the Mock-GeM simulator during development to ingest a sample procurement."
              action={
                <Link
                  href="/mock-gem"
                  className="focus-ring inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-[#163a5f] hover:bg-[#214c77] rounded transition-colors"
                >
                  Open Mock-GeM Simulator <ArrowUpRight className="w-3.5 h-3.5" />
                </Link>
              }
            />
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs text-[#6e7d89] px-1">
                <span>
                  Showing <strong>{procurements.length}</strong> of <strong>{total}</strong> procurements
                </span>
                <span className="hidden sm:inline">Click any case to open workspace</span>
              </div>

              {/* Restrained Enterprise Procurement Table */}
              <div className="overflow-x-auto border border-[#d9ddd9] rounded bg-[#fffefa]">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-[#d9ddd9] bg-[#f5f6f4] text-[#4f5e6a] font-semibold">
                      <th scope="col" className="py-3.5 px-4">Procurement & Reference</th>
                      <th scope="col" className="py-3.5 px-4">Organization</th>
                      <th scope="col" className="py-3.5 px-4">Source</th>
                      <th scope="col" className="py-3.5 px-4 text-center">Tenders</th>
                      <th scope="col" className="py-3.5 px-4 text-center">Bidders</th>
                      <th scope="col" className="py-3.5 px-4 text-center">Status</th>
                      <th scope="col" className="py-3.5 px-4 text-right">Last Updated</th>
                      <th scope="col" className="py-3.5 px-2 text-center sr-only">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#e4e7e4]">
                    {procurements.map((item) => {
                      const procurementId = item.id || item.procurement_id;
                      return (
                        <tr
                          key={procurementId}
                          className="group hover:bg-[#f8faf8] transition-colors"
                        >
                          <td className="py-4 px-4">
                            <Link
                              href={`/procurements/${procurementId}`}
                              className="focus-ring block"
                            >
                              <p className="font-semibold text-sm text-[#162333] group-hover:text-[#163a5f] transition-colors">
                                {item.title}
                              </p>
                              <p className="font-mono text-[11px] text-[#6d7c88] mt-0.5">
                                {item.external_reference}
                              </p>
                            </Link>
                          </td>
                          <td className="py-4 px-4 text-[#334657]">
                            {item.organization}
                          </td>
                          <td className="py-4 px-4">
                            <SourceBadge source={item.source_system} />
                          </td>
                          <td className="py-4 px-4 text-center font-medium text-[#2d3e4e]">
                            <span className="inline-flex items-center gap-1 font-mono">
                              <FileSpreadsheet className="w-3.5 h-3.5 text-[#5e7080]" aria-hidden="true" />
                              {item.tender_count ?? 0}
                            </span>
                          </td>
                          <td className="py-4 px-4 text-center font-medium text-[#2d3e4e]">
                            <span className="inline-flex items-center gap-1 font-mono">
                              <Users className="w-3.5 h-3.5 text-[#5e7080]" aria-hidden="true" />
                              {item.bidder_count ?? 0}
                            </span>
                          </td>
                          <td className="py-4 px-4 text-center">
                            <StatusBadge status={item.status} size="sm" />
                          </td>
                          <td className="py-4 px-4 text-right text-[#707f8c] whitespace-nowrap">
                            {item.updated_at || item.created_at
                              ? new Date(item.updated_at || item.created_at!).toLocaleDateString(
                                  "en-IN",
                                  {
                                    day: "2-digit",
                                    month: "short",
                                    year: "numeric",
                                  }
                                )
                              : "—"}
                          </td>
                          <td className="py-4 px-2 text-center">
                            <Link
                              href={`/procurements/${procurementId}`}
                              aria-label={`Open workspace for ${item.title}`}
                              className="focus-ring inline-flex p-1 rounded text-[#93a1ab] group-hover:text-[#163a5f] group-hover:translate-x-0.5 transition-all"
                            >
                              <ArrowUpRight className="w-4 h-4" />
                            </Link>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
