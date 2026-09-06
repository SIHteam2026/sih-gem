"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Clock, FolderGit2, ShieldCheck } from "lucide-react";

interface OfficerContextPanelProps {
  officerName?: string;
  roleTitle?: string;
  className?: string;
}

/**
 * OfficerContextPanel Component
 * 
 * A calm personal workspace anchor providing human orientation for the
 * procurement review officer.
 * 
 * Design Principles:
 * - Human-first greeting and orientation, not analytics or metrics.
 * - Time-of-day awareness with SSR-safe mounting.
 * - Clean, lightweight surface treatment matching the OPAL paper aesthetic.
 * - Plain language strictly focused on the officer decisions.
 */
export default function OfficerContextPanel({
  officerName = "Mr. Srivastav",
  roleTitle = "Procurement Review Officer",
  className = "",
}: OfficerContextPanelProps) {
  const [greeting, setGreeting] = useState("Good day");
  const [formattedDate, setFormattedDate] = useState("");

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
  }, []);

  return (
    <aside
      className={`rounded-lg border border-[#d9ddd9] bg-[#fffefa] p-6 shadow-xs transition-all ${className}`}
      aria-label="Officer Workspace Context"
    >
      {/* Header & Orientation */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#66717d]">
            {greeting}
          </p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight text-[#162333]">
            {officerName}
          </h2>
          <div className="mt-1 flex items-center gap-2">
            <span className="inline-flex items-center rounded-full bg-[#edf2f5] px-2 py-0.5 text-[11px] font-medium text-[#163a5f]">
              {roleTitle}
            </span>
          </div>
        </div>

        {/* Quiet seal indicator */}
        <div
          className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-[#d9ddd9] bg-[#f7f6f2] text-[#163a5f]"
          aria-hidden="true"
        >
          <ShieldCheck className="h-5 w-5 stroke-[1.75]" />
        </div>
      </div>

      {/* Human Context Description */}
      <div className="mt-5 border-t border-[#edf0ed] pt-4">
        <p className="text-sm leading-relaxed text-[#586570]">
          Your procurement reviews and recent activity. Cases and submitted bidder records are organized for your decision.
        </p>
      </div>

      {/* Calm Status and Quick Paths */}
      <div className="mt-6 space-y-2.5">
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

      {/* Date Footer */}
      {formattedDate && (
        <div className="mt-5 border-t border-[#edf0ed] pt-3 text-right">
          <span className="text-[11px] font-mono text-[#8a97a2]">
            {formattedDate}
          </span>
        </div>
      )}
    </aside>
  );
}
