"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Clock, FolderGit2, ShieldCheck, Activity } from "lucide-react";
import { fetchProcurements } from "@/services/api";
import { ProcurementSummaryItem, ProcurementListResponse } from "@/types/procurement";

interface OfficerContextPanelProps {
  officerName?: string;
  roleTitle?: string;
  className?: string;
}

/**
 * OfficerContextPanel Component
 * 
 * Implements the OPAL Right Context & Edge Panel:
 * 1. Freestanding Greeting & Identity: Unconstrained by card borders, positioned toward the right edge with generous breathing room.
 * 2. Half-Emerging Edge Surface: Contextual activity panel anchored to the right edge appearing as if sliding halfway into the workspace.
 * 3. Real Procurement Activity: Consumes fetchProcurements(3, 0) with graceful loading and calm empty fallback.
 * 4. Human-First Language: Strictly zero machine learning/pipeline jargon.
 * 5. Motion & Accessibility: Restrained entrance motion from the right with full prefers-reduced-motion support.
 */
export default function OfficerContextPanel({
  officerName = "Mr. Srivastav",
  roleTitle = "Procurement Review Officer",
  className = "",
}: OfficerContextPanelProps) {
  const [greeting, setGreeting] = useState("Good day");
  const [formattedDate, setFormattedDate] = useState("");
  const [recentCases, setRecentCases] = useState<ProcurementSummaryItem[]>([]);
  const [loadingCases, setLoadingCases] = useState<boolean>(true);

  useEffect(() => {
    // Dynamic local time-of-day greeting
    const hour = new Date().getHours();
    if (hour < 12) {
      setGreeting("Good morning");
    } else if (hour < 17) {
      setGreeting("Good afternoon");
    } else {
      setGreeting("Good evening");
    }

    // Locale-aware date string
    try {
      const dateStr = new Intl.DateTimeFormat("en-IN", {
        weekday: "long",
        day: "numeric",
        month: "short",
        year: "numeric",
      }).format(new Date());
      setFormattedDate(dateStr);
    } catch {
      setFormattedDate("Today's Session");
    }

    // Load recent procurement cases for contextual activity
    let isMounted = true;
    async function loadRecent() {
      try {
        const res = (await fetchProcurements(3, 0)) as ProcurementListResponse;
        if (isMounted && res?.procurements) {
          setRecentCases(res.procurements.slice(0, 3));
        }
      } catch {
        // Calm fallback if backend is unreachable
        if (isMounted) setRecentCases([]);
      } finally {
        if (isMounted) setLoadingCases(false);
      }
    }
    loadRecent();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <aside
      className={`flex flex-col items-end w-full ${className}`}
      aria-label="Officer Workspace Context"
    >
      {/* 1. Unconstrained Greeting & Officer Identity (Freestanding with generous breathing room) */}
      <div className="w-full text-right mb-6 pr-1 sm:pr-2">
        <p className="text-xs font-semibold uppercase tracking-widest text-[#66717d]">
          {greeting}
        </p>
        <h2 className="mt-1 text-2xl sm:text-3xl font-semibold tracking-tight text-[#162333]">
          {officerName}
        </h2>
        <div className="mt-2 flex items-center justify-end gap-2 text-xs text-[#586570]">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#163a5f]" aria-hidden="true" />
          <span className="font-medium text-[#163a5f]">{roleTitle}</span>
        </div>
      </div>

      {/* Hairline subtle stem connecting greeting to the edge panel */}
      <div className="w-full flex justify-end pr-6 mb-2" aria-hidden="true">
        <div className="h-4 w-px bg-[#d9ddd9]" />
      </div>

      {/* 2. Half-Emerging Edge Panel Surface */}
      <div
        className="opal-edge-surface w-full rounded-lg lg:rounded-r-none lg:rounded-l-xl border border-[#d9ddd9] lg:border-r-0 bg-[#fffefa] p-5 sm:p-6 shadow-xs lg:-mr-5 xl:-mr-8 transition-all"
      >
        {/* Header with quiet shield indicator */}
        <div className="flex items-center justify-between gap-3 border-b border-[#edf0ed] pb-3.5">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-[#163a5f]" aria-hidden="true" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[#162333]">
              Contextual Activity
            </h3>
          </div>
          <div
            className="grid h-7 w-7 place-items-center rounded-full border border-[#d9ddd9] bg-[#f7f6f2] text-[#163a5f]"
            title="Procurement Officer Anchor"
            aria-hidden="true"
          >
            <ShieldCheck className="h-3.5 w-3.5 stroke-[2]" />
          </div>
        </div>

        {/* Human Context Description */}
        <div className="mt-3.5">
          <p className="text-xs sm:text-sm leading-relaxed text-[#586570]">
            Your procurement reviews and recent activity. Cases and submitted bidder records are organized for your decision.
          </p>
        </div>

        {/* Real Activity Stream / Cases List */}
        <div className="mt-4 pt-3 border-t border-[#edf0ed]">
          <div className="flex items-center justify-between mb-2.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#7a8894]">
              Recent Reviews
            </span>
            {recentCases.length > 0 && (
              <span className="text-[10px] font-mono text-[#8a97a2]">
                {recentCases.length} active
              </span>
            )}
          </div>

          {loadingCases ? (
            <div className="space-y-2 py-1" aria-label="Loading recent activity">
              <div className="h-9 rounded bg-[#f2f4f2] animate-pulse" />
              <div className="h-9 rounded bg-[#f2f4f2] animate-pulse" />
            </div>
          ) : recentCases.length > 0 ? (
            <ul className="space-y-2" aria-label="Recent procurement items">
              {recentCases.map((item) => (
                <li key={item.id}>
                  <Link
                    href={`/procurements/${encodeURIComponent(item.id)}`}
                    className="focus-ring group flex items-center justify-between rounded-md border border-[#e5e9e6] bg-[#fbfbfa] p-2.5 text-xs transition-colors hover:border-[#b8c6bd] hover:bg-white"
                  >
                    <div className="min-w-0 flex-1 pr-2">
                      <p className="truncate font-medium text-[#162333] group-hover:text-[#163a5f]">
                        {item.title || item.external_reference || "Procurement Case"}
                      </p>
                      <p className="truncate text-[11px] text-[#7a8894]">
                        {item.organization || item.external_reference || "Government Authority"}
                      </p>
                    </div>
                    <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-[#8a97a2] group-hover:text-[#163a5f]" />
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <div className="rounded-md border border-dashed border-[#d9ddd9] bg-[#f9f9f7] p-3 text-center">
              <p className="text-xs text-[#7a8894]">
                No pending procurement alerts. Review queue is clear.
              </p>
            </div>
          )}
        </div>

        {/* Quick Action Navigation */}
        <div className="mt-5 space-y-2 border-t border-[#edf0ed] pt-4">
          <Link
            href="/procurements"
            className="focus-ring flex items-center justify-between rounded-md border border-[#d9ddd9] bg-[#f7f6f2] px-3.5 py-2.5 text-xs font-medium text-[#162333] transition-colors hover:border-[#b8c6bd] hover:bg-white"
          >
            <span className="flex items-center gap-2">
              <FolderGit2 className="h-3.5 w-3.5 text-[#163a5f]" />
              <span>Open review queue</span>
            </span>
            <ArrowUpRight className="h-3.5 w-3.5 text-[#66717d]" />
          </Link>

          <Link
            href="/history"
            className="focus-ring flex items-center justify-between rounded-md border border-transparent bg-transparent px-3.5 py-2 text-xs font-medium text-[#586570] transition-colors hover:bg-[#f7f6f2] hover:text-[#162333]"
          >
            <span className="flex items-center gap-2">
              <Clock className="h-3.5 w-3.5 text-[#7a8894]" />
              <span>View past decisions</span>
            </span>
            <ArrowUpRight className="h-3.5 w-3.5 text-[#7a8894]" />
          </Link>
        </div>

        {/* Formatted Date Footer */}
        {formattedDate && (
          <div className="mt-4 border-t border-[#edf0ed] pt-2.5 text-right">
            <span className="text-[10px] font-mono text-[#8a97a2]">
              {formattedDate}
            </span>
          </div>
        )}
      </div>

      {/* Scoped CSS for restrained entrance animation & reduced motion */}
      <style jsx>{`
        .opal-edge-surface {
          animation: edgeSlideIn 0.65s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        @keyframes edgeSlideIn {
          from {
            transform: translateX(1.25rem);
            opacity: 0.85;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .opal-edge-surface {
            animation: none !important;
            transform: none !important;
            opacity: 1 !important;
          }
        }
      `}</style>
    </aside>
  );
}
