"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import Navbar from "@/components/Navbar";
import { fetchProcurements } from "@/services/api";
import { ProcurementSummaryItem, ProcurementListResponse } from "@/types/procurement";
import { getOfficerDecisions, OfficerDecision } from "@/services/reviewDecisions";
import ProjectCard from "@/components/procurement/ProjectCard";

/**
 * Deterministic derivation of the working-state tag from real application signals:
 * 
 * Canonical Signals:
 * 1. `procurement.status`: ('IMPORTED', 'PROCESSING', 'READY', 'FAILED')
 * 2. `officerDecision`: Retrieved via `getOfficerDecisions()` ('CONFIRMED', 'NEEDS_FURTHER_REVIEW', notes)
 * 3. `procurement.updated_at` vs `procurement.created_at`: Progress updates indicating pipeline modifications
 * 
 * Rules:
 * - 'DRAFT': The project has review/progress activity (e.g. status is 'PROCESSING',
 *    or an officer review decision / notes are recorded, or post-ingestion progress activity exists),
 *    but final review is in draft / not complete.
 * - 'NEW': The project has been loaded/ingested into the workspace (e.g. status is 'IMPORTED',
 *    or newly ingested 'READY' case awaiting initial officer review activity).
 */
export function deriveProjectState(
  procurement: ProcurementSummaryItem,
  officerDecision?: OfficerDecision | null
): "NEW" | "DRAFT" {
  // If officer review activity is recorded (decision or notes present)
  if (officerDecision && (officerDecision.decision || officerDecision.notes)) {
    return "DRAFT";
  }

  const status = (procurement.status || "").toUpperCase();

  // Active pipeline processing represents in-flight review activity
  if (status === "PROCESSING" || status === "IN_PROGRESS" || status === "ANALYZING") {
    return "DRAFT";
  }

  // If status is IMPORTED, it has been loaded but not yet processed/reviewed
  if (status === "IMPORTED") {
    return "NEW";
  }

  // For READY status: if updated_at is distinctly after created_at (> 2 minutes),
  // indicating progress/evaluation processing activity occurred
  if (procurement.created_at && procurement.updated_at) {
    const created = new Date(procurement.created_at).getTime();
    const updated = new Date(procurement.updated_at).getTime();
    if (!isNaN(created) && !isNaN(updated) && updated - created > 120000) {
      return "DRAFT";
    }
  }

  // Default: newly loaded procurement awaiting initial review
  return "NEW";
}

/**
 * Format canonical ISO timestamp into clean human-readable date.
 * Example visual language: "Loaded 6 Sep 2026"
 */
export function formatLoadedDate(dateStr?: string | null): string {
  if (!dateStr) return "Loaded recently";
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return "Loaded recently";
    const formatted = new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(date);
    return `Loaded ${formatted}`;
  } catch {
    return "Loaded recently";
  }
}

export default function WorkspaceShelfPage() {
  const router = useRouter();
  const [procurements, setProcurements] = useState<ProcurementSummaryItem[]>([]);
  const [decisions, setDecisions] = useState<Record<string, OfficerDecision>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const handleRefresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = (await fetchProcurements(50, 0)) as ProcurementListResponse;
      setProcurements(data?.procurements || []);
      setDecisions(getOfficerDecisions());
    } catch {
      setError("Unable to load workspace projects at this time. Please check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    async function loadInitial() {
      try {
        const data = (await fetchProcurements(50, 0)) as ProcurementListResponse;
        if (isMounted) {
          setProcurements(data?.procurements || []);
          setDecisions(getOfficerDecisions());
          setLoading(false);
        }
      } catch {
        if (isMounted) {
          setError("Unable to load workspace projects at this time. Please check your connection and try again.");
          setLoading(false);
        }
      }
    }
    loadInitial();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="min-h-screen bg-[#f7f6f2] text-[#162333] flex flex-col font-sans selection:bg-[#d8e6ee]">
      <Navbar />

      <main id="main-content" className="flex-1 w-full max-w-5xl mx-auto px-6 sm:px-10 py-10 sm:py-14">
        {/* Large Clean Page Title */}
        <div className="mb-8 sm:mb-10 flex items-center justify-between">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#111827]">
            Opal Workspace
          </h1>

          <button
            type="button"
            onClick={handleRefresh}
            disabled={loading}
            className="focus-ring inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#64748b] hover:text-[#111827] rounded-md transition-colors disabled:opacity-50 cursor-pointer"
            aria-label="Refresh workspace"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>

        {/* Loading State: Simple, quiet placeholders without flashy skeleton animation */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 sm:gap-8" aria-busy="true">
            <div className="h-48 rounded-2xl border border-dashed border-[#e2e8f0] bg-white/50 p-6 flex flex-col justify-between">
              <div className="space-y-3">
                <div className="h-3 w-28 bg-[#e2e8f0] rounded" />
                <div className="h-5 w-3/4 bg-[#e2e8f0] rounded" />
              </div>
              <div className="h-3 w-32 bg-[#e2e8f0] rounded" />
            </div>
            <div className="h-48 rounded-2xl border border-dashed border-[#e2e8f0] bg-white/50 p-6 flex flex-col justify-between">
              <div className="space-y-3">
                <div className="h-3 w-28 bg-[#e2e8f0] rounded" />
                <div className="h-5 w-3/4 bg-[#e2e8f0] rounded" />
              </div>
              <div className="h-3 w-32 bg-[#e2e8f0] rounded" />
            </div>
          </div>
        )}

        {/* Error State: Human-readable error message with retry */}
        {!loading && error && (
          <div className="rounded-2xl border border-[#fee2e2] bg-[#fff5f5] p-8 text-center max-w-lg mx-auto">
            <p className="text-sm font-semibold text-[#991b1b]">
              Workspace unavailable
            </p>
            <p className="mt-1 text-xs text-[#7f1d1d] leading-relaxed">
              {error}
            </p>
            <button
              type="button"
              onClick={handleRefresh}
              className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-[#991b1b] hover:bg-[#7f1d1d] rounded-full transition-colors cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty State: Calm message and appropriate existing action */}
        {!loading && !error && procurements.length === 0 && (
          <div className="rounded-2xl border border-dashed border-[#d1d5db] bg-white/60 p-12 text-center max-w-md mx-auto">
            <p className="text-base font-semibold text-[#111827]">
              Your workspace is empty.
            </p>
            <p className="mt-1 text-xs text-[#64748b] leading-relaxed">
              No procurement projects are currently registered in your workspace shelf.
            </p>
            <div className="mt-6">
              <Link
                href="/mock-gem"
                className="focus-ring inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-[#111827] hover:bg-[#1f2937] rounded-full transition-colors"
              >
                <span>Load sample in Mock-GeM</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        )}

        {/* Desktop 2-Column Grid / Tablet & Mobile Responsive Cards */}
        {!loading && !error && procurements.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 sm:gap-8">
            {procurements.map((item) => {
              const id = item.id || item.procurement_id || item.external_reference;
              const decision = id ? decisions[id] : null;
              const cardState = deriveProjectState(item, decision);
              const loadedDate = formatLoadedDate(item.created_at || item.updated_at);
              const department = item.organization || item.source_system || "Government Organization";
              const title = item.title || item.external_reference || "Procurement Project";

              return (
                <ProjectCard
                  key={id}
                  id={id}
                  title={title}
                  department={department}
                  loadedDate={loadedDate}
                  state={cardState}
                  reference={item.external_reference}
                  onOpen={() => router.push(`/procurements/${encodeURIComponent(id)}`)}
                />
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
