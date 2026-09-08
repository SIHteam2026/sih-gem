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
    <div className={`w-full max-w-5xl mx-auto flex flex-col font-sans tracking-tight ${className}`}>
      {/* Header & Structural Breakdown */}
      <div className="mb-6">
        <h1 className="text-3xl sm:text-4xl font-bold text-[#111827] leading-tight mb-2">
          Opal Workspace
        </h1>
        <p className="text-lg text-[#111827] font-medium">{greeting}</p>
        <p className="text-sm text-[#6b7280] mt-0.5">{dynamicInsight}</p>
      </div>

      <div className="mt-8 flex items-center gap-2.5 mb-6">
        <List className="w-5 h-5 text-emerald-600" />
        <h2 className="text-xl font-semibold text-emerald-700">Your Projects</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {loading ? (
          <div className="col-span-full py-12 text-center text-sm text-gray-500">
            Loading projects...
          </div>
        ) : procurements.length === 0 ? (
          <div className="col-span-full p-8 rounded-2xl border border-dashed border-gray-200 text-center text-sm text-gray-500">
            No projects registered yet. You can ingest sample tenders via the GeM Gateway.
          </div>
        ) : (
          procurements.map((project) => {
            const statusStr = (project.status || "New").toUpperCase();
            const badgeText = statusStr === "READY" ? "Technical Bid Complete" : statusStr;
            
            return (
              <Link
                key={project.id}
                href={`/workspace/${project.id}`}
                className="group block bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs hover:border-slate-300 hover:shadow-md transition-all flex flex-col justify-between min-h-[200px]"
              >
                <div>
                  <h3 className="font-bold text-[#111827] text-lg tracking-tight leading-snug line-clamp-2 pb-2 group-hover:text-[#163a5f] transition-colors">
                    {project.title}
                  </h3>
                  <div className="flex items-center">
                    <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 border border-emerald-200/70 text-emerald-700">
                      {badgeText}
                    </span>
                  </div>
                </div>
                <div className="mt-6 pt-4 border-t border-slate-100 space-y-1">
                  <p className="text-slate-500 text-xs font-medium truncate">
                    {project.organization || "Ministry of Petroleum and Natural Gas"}
                  </p>
                  <p className="text-slate-400 text-xs font-mono">
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
