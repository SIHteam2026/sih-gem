"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { fetchProcurements } from "@/services/api";
import { ProcurementSummaryItem, ProcurementListResponse } from "@/types/procurement";
import { computeReviewStats, subscribeToReviewDecisions } from "@/services/reviewDecisions";

interface OfficerContextPanelProps {
  officerName?: string;
  roleTitle?: string;
  className?: string;
}

/**
 * Resolves the time-based greeting for the officer based on local browser time.
 * 
 * Time intervals:
 * - 05:00 – 11:59: Good Morning
 * - 12:00 – 16:59: Good Afternoon
 * - 17:00 – 20:59: Good Evening
 * - 21:00 – 04:59: Good Night (handles midnight and late night)
 */
export function getTimeBasedGreeting(date: Date = new Date()): string {
  const hour = date.getHours();
  if (hour >= 5 && hour < 12) {
    return "Good Morning";
  } else if (hour >= 12 && hour < 17) {
    return "Good Afternoon";
  } else if (hour >= 17 && hour < 21) {
    return "Good Evening";
  } else {
    return "Good Night";
  }
}

/**
 * Resolves a contextual formal greeting from real application state.
 * Returns null if the default time-of-day greeting should be retained.
 * 
 * Work-Aware Precedence:
 * 1. "Review in progress": Any procurement actively processing ('PROCESSING' or 'IN_PROGRESS')
 * 2. "Review complete": A procurement recently completed review (within the last 15 minutes)
 * 3. "Your reviews are ready": Multiple/recent reviews ready for officer sign-off (within 2 hours)
 * 
 * Invariant: Unresolved review findings or older cases in the database default to the time greeting.
 */
export function getContextualGreeting(
  procurements: ProcurementSummaryItem[],
  now: Date = new Date()
): string | null {
  if (!procurements || procurements.length === 0) {
    return null;
  }

  // 1. Actively processing procurement takes precedence
  const hasActiveProcessing = procurements.some((p) => {
    const s = (p.status || "").toUpperCase();
    return s === "PROCESSING" || s === "IN_PROGRESS" || s === "ANALYZING";
  });
  if (hasActiveProcessing) {
    return "Review in progress";
  }

  // 2. Review completed within the last 15 minutes
  const fifteenMinutesMs = 15 * 60 * 1000;
  const justCompleted = procurements.find((p) => {
    const s = (p.status || "").toUpperCase();
    if (s !== "READY" && s !== "COMPLETED") return false;
    const ts = p.updated_at || p.created_at;
    if (!ts) return false;
    const itemTime = new Date(ts).getTime();
    return !isNaN(itemTime) && now.getTime() - itemTime >= 0 && now.getTime() - itemTime < fifteenMinutesMs;
  });
  if (justCompleted) {
    return "Review complete";
  }

  // 3. Reviews recently ready (within the last 2 hours)
  const twoHoursMs = 2 * 60 * 60 * 1000;
  const recentlyReady = procurements.find((p) => {
    const s = (p.status || "").toUpperCase();
    if (s !== "READY") return false;
    const ts = p.updated_at || p.created_at;
    if (!ts) return false;
    const itemTime = new Date(ts).getTime();
    return !isNaN(itemTime) && now.getTime() - itemTime >= 0 && now.getTime() - itemTime < twoHoursMs;
  });
  if (recentlyReady) {
    return "Your reviews are ready";
  }

  // 4. Default: Return null to keep time-of-day greeting primary for general cases
  return null;
}

/**
 * OfficerContextPanel Component
 * 
 * Implements the right-side human context and edge-emerging surface
 * matching the OPAL reference design.
 * 
 * Hierarchy:
 * 1. Freestanding Dynamic Greeting & Name (Good Morning / Mr. Srivastav)
 * 2. Edge-Emerging Context Surface:
 *    - Dynamic Procurement Verification Status breakdown (Pending, Further Analysis, Confirmed)
 *    - Fiscal Allocation progress indicator
 *    - Compliance Recertification alert
 *    - Executive Audit Log stream
 */
export default function OfficerContextPanel({
  officerName = "Mr. Srivastav",
  className = "",
}: OfficerContextPanelProps) {
  const [greeting, setGreeting] = useState<string>("Good Evening");
  const [stats, setStats] = useState({
    totalProcessed: 0,
    pendingCount: 0,
    furtherReviewCount: 0,
    confirmedCount: 0,
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const updateStats = useCallback((cases: ProcurementSummaryItem[]) => {
    const computed = computeReviewStats(cases);
    setStats(computed);
  }, []);

  useEffect(() => {
    let isMounted = true;
    let latestCases: ProcurementSummaryItem[] = [];

    // Helper to evaluate and apply the current active greeting (strictly time-based)
    function applyCurrentGreeting() {
      if (!isMounted) return;
      const now = new Date();
      setGreeting(getTimeBasedGreeting(now));
    }

    // Initialize client-side time-based greeting asynchronously
    const mountTimer = setTimeout(() => {
      applyCurrentGreeting();
    }, 0);

    // Minute-level timer for natural boundary updates across midnight / hour boundaries
    const intervalId = setInterval(() => {
      applyCurrentGreeting();
    }, 60000);

    async function loadData() {
      setIsLoading(true);
      try {
        const res = (await fetchProcurements(50, 0)) as ProcurementListResponse;
        if (isMounted && res?.procurements) {
          latestCases = res.procurements;
          updateStats(res.procurements);
        } else if (isMounted) {
          latestCases = [];
          updateStats([]);
        }
      } catch {
        if (isMounted) {
          latestCases = [];
          updateStats([]);
          applyCurrentGreeting([]);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }
    loadData();

    // Subscribe to live review decision updates across tabs/components
    const unsubscribe = subscribeToReviewDecisions(() => {
      if (isMounted) {
        updateStats(latestCases);
      }
    });

    return () => {
      isMounted = false;
      clearTimeout(mountTimer);
      clearInterval(intervalId);
      unsubscribe();
    };
  }, [updateStats]);

  return (
    <aside
      className={`flex flex-col items-end w-full max-w-[440px] lg:max-w-none select-none ${className}`}
      aria-label="Officer Workspace Context"
    >
      {/* 1. Freestanding Dynamic Greeting & Officer Identity */}
      <div className="w-full text-right mb-6 pr-2 lg:pr-4">
        <p className="text-sm sm:text-base font-medium text-[#6b7280]">
          {greeting}
        </p>
        <h2 className="text-3xl font-bold tracking-tight text-[#111827]">
          {officerName}
        </h2>
      </div>

      {/* 2. Edge-Emerging Context Surface Card (Half-emerging from right margin) */}
      <div
        className="w-full lg:w-[calc(100%+3.5rem)] xl:w-[calc(100%+5rem)] lg:-mr-10 xl:-mr-14 rounded-2xl sm:rounded-3xl lg:rounded-r-none border border-[#e5e7eb] lg:border-r-0 bg-white p-5 sm:p-6 shadow-[0_4px_24px_rgba(0,0,0,0.03)] space-y-5 transition-transform"
      >
        {/* Officer Review & Verification Status Panel */}
        <div className="rounded-2xl bg-[#f8fafc] border border-[#e2e8f0] p-4 space-y-3.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-[#163a5f]" />
              <span className="text-xs font-bold text-[#0f172a]">
                Procurement Verification Status
              </span>
            </div>
            <Link
              href="/procurements"
              className="focus-ring shrink-0 bg-[#163a5f] hover:bg-[#204b76] text-white text-[11px] font-semibold px-3 py-1 rounded-full transition-colors inline-flex items-center gap-1"
            >
              Review Queue
            </Link>
          </div>

          {/* 3 Metric Counts Breakdown */}
          <div className="grid grid-cols-3 gap-2">
            {/* 1. Pending Reviews */}
            <div className="rounded-xl bg-white border border-[#e2e8f0] p-2.5 text-center">
              <div className="text-lg font-bold font-mono text-[#0f172a]">
                {isLoading ? "…" : stats.pendingCount}
              </div>
              <div className="text-[10px] font-medium text-[#64748b] mt-0.5">
                Pending Reviews
              </div>
            </div>

            {/* 2. Need Further Review */}
            <div className="rounded-xl bg-amber-50/80 border border-amber-200/90 p-2.5 text-center">
              <div className="text-lg font-bold font-mono text-amber-900">
                {isLoading ? "…" : stats.furtherReviewCount}
              </div>
              <div className="text-[10px] font-semibold text-amber-800 mt-0.5">
                Further Analysis
              </div>
            </div>

            {/* 3. Confirmed Verifications */}
            <div className="rounded-xl bg-emerald-50/80 border border-emerald-200/90 p-2.5 text-center">
              <div className="text-lg font-bold font-mono text-emerald-900">
                {isLoading ? "…" : stats.confirmedCount}
              </div>
              <div className="text-[10px] font-semibold text-emerald-800 mt-0.5">
                Confirmed
              </div>
            </div>
          </div>

          <div className="text-[11px] text-[#64748b] flex items-center justify-between border-t border-[#edf2f7] pt-2">
            <span>
              {isLoading
                ? "Checking processed procurement cases…"
                : `${stats.totalProcessed} completely processed case${stats.totalProcessed === 1 ? "" : "s"}`}
            </span>
            <span className="font-mono text-[10px] font-semibold text-[#163a5f]">
              {stats.pendingCount > 0 ? "Action Required" : "Up to Date"}
            </span>
          </div>
        </div>

        {/* Fiscal Allocation Progress Bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-[#111827]">Fiscal Q3 Allocation</span>
            <span className="font-mono font-bold text-[#111827]">$4.12M / $5.50M</span>
          </div>
          <div className="w-full h-2 rounded-full bg-[#f3f4f6] overflow-hidden">
            <div className="h-full bg-[#111827] rounded-full" style={{ width: "74%" }} />
          </div>
          <div className="flex items-center justify-between text-[10px] text-[#6b7280]">
            <span>74% committed</span>
            <span>18 days remaining</span>
          </div>
        </div>

        {/* Compliance Recertification Notice */}
        <div className="border-t border-[#f3f4f6] pt-4 space-y-1">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[#f59e0b] shrink-0" aria-hidden="true" />
            <p className="text-xs font-semibold text-[#111827]">
              Compliance Recertification
            </p>
          </div>
          <p className="text-[11px] text-[#6b7280] leading-relaxed pl-4">
            HexaCorp ISO 27001 audit statement is due in 4 business days.
          </p>
        </div>

        {/* Executive Audit Log */}
        <div className="border-t border-[#f3f4f6] pt-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold tracking-wider uppercase text-[#6b7280]">
              Executive Audit Log
            </span>
            <Link
              href="/history"
              className="text-[11px] font-medium text-[#2563eb] hover:underline"
            >
              Full Log
            </Link>
          </div>

          <div className="space-y-2.5">
            {/* Log Item 1 */}
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-[#10b981] shrink-0" aria-hidden="true" />
                <p className="text-xs font-medium text-[#111827]">
                  Contract #89241 executed with AWS
                </p>
              </div>
              <p className="text-[10px] text-[#6b7280] pl-3.5">
                09:42 AM • Automated by Opal Engine
              </p>
            </div>

            {/* Log Item 2 */}
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-[#3b82f6] shrink-0" aria-hidden="true" />
                <p className="text-xs font-medium text-[#111827]">
                  RFP generated: High-density storage upgrade
                </p>
              </div>
              <p className="text-[10px] text-[#6b7280] pl-3.5">
                08:15 AM • Hardware Committee
              </p>
            </div>

            {/* Log Item 3 */}
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-[#9ca3af] shrink-0" aria-hidden="true" />
                <p className="text-xs font-medium text-[#111827]">
                  Vendor benchmark scorecards updated
                </p>
              </div>
              <p className="text-[10px] text-[#6b7280] pl-3.5">
                Yesterday • Analytics Group
              </p>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
