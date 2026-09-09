"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { ArrowRight, AlertCircle } from "lucide-react";
import { fetchProcurements } from "@/services/api";
import { ProcurementSummaryItem, ProcurementListResponse } from "@/types/procurement";

function getDynamicInsights(procurements: ProcurementSummaryItem[]): { message: string, activity: string[] } {
  if (!procurements || procurements.length === 0) return { message: "No active projects at the moment.", activity: [] };
  
  const readyCount = procurements.filter(p => p.status?.toUpperCase() === "READY").length;
  const importedCount = procurements.filter(p => p.status?.toUpperCase() === "IMPORTED").length;
  const processingCount = procurements.filter(p => p.status?.toUpperCase() === "PROCESSING").length;
  
  const activity = [];
  if (readyCount > 0) activity.push(`${readyCount} procurement(s) awaiting technical scrutiny`);
  if (importedCount > 0) activity.push(`${importedCount} new procurement(s) received`);
  if (processingCount > 0) activity.push(`${processingCount} procurement(s) actively processing`);

  return {
    message: `You have ${procurements.length} active procurements requiring attention.`,
    activity
  };
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

  const insights = getDynamicInsights(procurements);
  const topProcurements = procurements.slice(0, 2);

  return (
    <div className={`w-full max-w-5xl mx-auto flex flex-col font-sans text-left mt-8 ${className}`}>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Officer Dashboard</h1>
        <p className="text-slate-600 mt-2">{insights.message}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* ACTIVITY / ATTENTION AREA */}
        <div className="lg:col-span-1 space-y-4">
          <h2 className="text-lg font-semibold text-slate-800">Attention Required</h2>
          <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-4 space-y-3">
            {insights.activity.length === 0 ? (
              <p className="text-sm text-slate-500">No immediate actions pending.</p>
            ) : (
              insights.activity.map((act, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="mt-0.5 text-amber-600">
                    <AlertCircle className="w-4 h-4" />
                  </div>
                  <p className="text-sm text-slate-700">{act}</p>
                </div>
              ))
            )}
          </div>
          
          <Link href="/procurements" className="inline-flex items-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-800 mt-4">
            View All Projects in Workspace <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        {/* QUICK ACCESS */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-lg font-semibold text-slate-800">Quick Access</h2>
          {loading ? (
            <div className="py-10 text-center text-sm text-slate-400 border border-slate-200 rounded-lg">Loading...</div>
          ) : topProcurements.length === 0 ? (
            <div className="p-8 rounded-lg border border-slate-200 bg-slate-50 text-center text-sm text-slate-500">
              No active procurements available.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {topProcurements.map((project) => (
                <Link
                  key={project.id}
                  href={`/procurements/${project.id}`}
                  className="block bg-white p-5 rounded-lg border border-slate-200 shadow-sm hover:border-slate-300 hover:shadow transition-all"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="font-semibold text-slate-900 text-lg leading-snug hover:text-blue-700">
                        {project.title}
                      </h3>
                      <p className="text-slate-500 text-sm mt-1">{project.organization || "Public Procurement"}</p>
                    </div>
                    <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-slate-100 text-slate-700 whitespace-nowrap ml-4">
                      {project.status || 'NEW'}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
