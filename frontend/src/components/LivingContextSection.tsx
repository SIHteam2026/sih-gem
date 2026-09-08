"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { List } from "lucide-react";
import { fetchProcurements } from "@/services/api";
import { ProcurementSummaryItem, ProcurementListResponse } from "@/types/procurement";

// Dynamic insights logic based on Supabase procurements
function getDynamicInsights(procurements: ProcurementSummaryItem[]): string {
  if (!procurements || procurements.length === 0) return "No active projects at the moment.";
  
  const newCount = procurements.filter(p => {
    const s = (p.status || "").toUpperCase();
    return s === "NEW" || s === "IMPORTED" || s === "PROCESSING";
  }).length;
  
  if (newCount > 0) {
    return "Most of the projects are under your evaluation. Though, we've a new high-stake project here.";
  }
  return "All projects are actively processing or ready for review.";
}

export default function LivingContextSection({
  className = "",
}: {
  className?: string;
}) {
  const [procurements, setProcurements] = useState<ProcurementSummaryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const response = (await fetchProcurements(10, 0)) as ProcurementListResponse;
      setProcurements(response?.procurements || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const dynamicInsight = getDynamicInsights(procurements);

  // Time based greeting
  const hour = new Date().getHours();
  let greeting = "Welcome again Sir!";
  if (hour < 12) greeting = "Good morning Sir!";
  else if (hour >= 17 && hour < 21) greeting = "Good evening Sir!";
  else if (hour >= 21) greeting = "Good night Sir!";

  return (
    <div className={`w-full max-w-[1000px] flex flex-col font-['Stack_Sans_Text',_sans-serif] tracking-tight ${className}`}>
      {/* 2. Header & Structural Breakdown */}
      <h1 className="text-[40px] font-medium text-[#111827] leading-tight ml-[24px] mb-[24px]">
        Opal Workspace
      </h1>

      <div className="ml-[24px] flex flex-col gap-1">
        <p className="text-[20px] text-[#111827] font-normal">{greeting}</p>
        <p className="text-[15px] text-[#6b7280]">{dynamicInsight}</p>
      </div>

      <div className="mt-[64px] ml-[24px] flex items-center gap-[12px] mb-[32px]">
        <List className="w-[24px] h-[24px] text-[#10b981]" />
        <h2 className="text-[22px] text-[#10b981] font-normal">Your Projects</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-[24px] ml-[24px]">
        {loading ? (
          <div className="text-sm text-gray-500">Loading projects...</div>
        ) : (
          procurements.map((project) => {
            const statusStr = (project.status || "New").toUpperCase();
            const badgeText = statusStr === "READY" ? "Technical Bid Complete" : statusStr;
            
            return (
              <Link
                key={project.id}
                href={`/workspace/${project.id}`}
                className="group block bg-white p-[24px] rounded-3xl shadow-[-12px_-12px_24px_-4px_rgba(0,0,0,0.04)] flex flex-col justify-between min-h-[200px] hover:shadow-[-12px_-12px_32px_-2px_rgba(0,0,0,0.07)] transition-shadow"
              >
                <div>
                  <h3 className="font-manrope text-[#111827] font-bold text-[19px] tracking-tight leading-[1.3] line-clamp-3 pb-2 group-hover:text-[#163a5f] transition-colors">
                    {project.title}
                  </h3>
                  <div className="flex items-center -mt-1">
                    <span className="font-sans px-2 py-0.5 text-[11px] font-medium rounded-full bg-lime-50/50 border border-lime-200/60 text-lime-700">
                      {badgeText}
                    </span>
                  </div>
                </div>
                <div className="mt-auto pt-[16px] space-y-1.5">
                  <p className="font-serif italic text-slate-400 text-[13.5px] truncate">
                    {project.organization || "Ministry of Health and Family Welfare"}
                  </p>
                  <p className="font-manrope text-slate-400 text-[13px]">
                    Tender date: {new Date(project.created_at || Date.now()).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' }).replace(/\//g, '.')}
                  </p>
                </div>
              </Link>
            );
          })
        )}
      </div>
    </div>
  );
}
