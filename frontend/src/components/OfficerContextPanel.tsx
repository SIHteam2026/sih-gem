"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { FileText } from "lucide-react";
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
 * Implements the right-side human context and edge-emerging surface
 * matching the OPAL reference design.
 * 
 * Hierarchy:
 * 1. Freestanding Greeting & Name (Good Morning, / Mr. Srivastav)
 * 2. Edge-Emerging Context Surface:
 *    - Pending Approvals banner with Review action
 *    - Fiscal Allocation progress indicator
 *    - Compliance Recertification alert
 *    - Executive Audit Log stream
 */
export default function OfficerContextPanel({
  officerName = "Mr. Srivastav",
  roleTitle = "Procurement Review Officer",
  className = "",
}: OfficerContextPanelProps) {
  const [greeting, setGreeting] = useState("Good Morning,");
  const [, setRecentCases] = useState<ProcurementSummaryItem[]>([]);

  useEffect(() => {
    // Dynamic time-of-day greeting matching reference capitalization
    const hour = new Date().getHours();
    if (hour < 12) {
      setGreeting("Good Morning,");
    } else if (hour < 17) {
      setGreeting("Good Afternoon,");
    } else {
      setGreeting("Good Evening,");
    }

    let isMounted = true;
    async function loadRecent() {
      try {
        const res = (await fetchProcurements(3, 0)) as ProcurementListResponse;
        if (isMounted && res?.procurements) {
          setRecentCases(res.procurements);
        }
      } catch {
        if (isMounted) setRecentCases([]);
      }
    }
    loadRecent();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <aside
      className={`flex flex-col items-end w-full max-w-[440px] select-none ${className}`}
      aria-label="Officer Workspace Context"
    >
      {/* 1. Freestanding Greeting & Officer Identity */}
      <div className="w-full text-right mb-6 pr-2">
        <p className="text-xs font-medium text-[#6b7280]">
          {greeting}
        </p>
        <h2 className="text-3xl font-bold tracking-tight text-[#111827]">
          {officerName}
        </h2>
      </div>

      {/* 2. Edge-Emerging Context Surface Card */}
      <div
        className="w-full rounded-2xl sm:rounded-3xl border border-[#e5e7eb] bg-white p-5 sm:p-6 shadow-[0_4px_24px_rgba(0,0,0,0.02)] space-y-5"
      >
        {/* Pending Approvals Action Banner */}
        <div className="rounded-xl bg-[#f9fafb] border border-[#f3f4f6] p-3.5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-lg bg-white border border-[#e5e7eb] text-[#111827]">
              <FileText className="h-4 w-4" />
            </div>
            <div>
              <p className="text-xs font-bold text-[#111827]">
                3 Pending Approvals
              </p>
              <p className="text-[11px] text-[#6b7280]">
                Awaiting executive signature
              </p>
            </div>
          </div>
          <Link
            href="/procurements"
            className="focus-ring shrink-0 bg-[#111827] hover:bg-[#1f2937] text-white text-xs font-medium px-3.5 py-1.5 rounded-full transition-colors"
          >
            Review
          </Link>
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
