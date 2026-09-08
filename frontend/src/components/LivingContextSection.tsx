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
  const [typedGreeting, setTypedGreeting] = useState<string>("");
  const [isTypingComplete, setIsTypingComplete] = useState<boolean>(false);

  const fullGreeting = "Welcome to OPAL Workspace!";

  // Autocomplete typing animation
  useEffect(() => {
    let currentIdx = 0;
    setTypedGreeting("");
    setIsTypingComplete(false);

    const typingInterval = setInterval(() => {
      currentIdx++;
      setTypedGreeting(fullGreeting.slice(0, currentIdx));
      if (currentIdx >= fullGreeting.length) {
        setIsTypingComplete(true);
        clearInterval(typingInterval);
      }
    }, 45);

    return () => clearInterval(typingInterval);
  }, []);

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

  // Time based subtitle greeting
  const hour = new Date().getHours();
  let timeOfDay = "Welcome Sir!";
  if (hour < 12) timeOfDay = "Good morning Sir!";
  else if (hour >= 17 && hour < 21) timeOfDay = "Good evening Sir!";
  else if (hour >= 21) timeOfDay = "Good night Sir!";

  return (
    <div className={`w-full max-w-4xl mx-auto flex flex-col font-sans tracking-tight text-center ${className}`}>
      {/* ── CENTER ALIGNED HEADER & ANIMATED GREETING ── */}
      <div className="mb-10 text-center space-y-3 pt-2">
        <div className="inline-flex items-center justify-center gap-2 px-3.5 py-1 rounded-full bg-emerald-50 border border-emerald-200/80 text-emerald-800 text-xs font-semibold shadow-2xs">
          <span>{timeOfDay}</span>
        </div>

        {/* Animated Autocomplete Heading */}
        <h1 className="text-3xl sm:text-5xl font-bold text-[#111827] leading-tight tracking-tight min-h-[48px] sm:min-h-[60px] flex items-center justify-center">
          <span>{typedGreeting}</span>
          {!isTypingComplete && (
            <span className="inline-block w-1 h-8 sm:h-10 ml-1 bg-emerald-600 animate-pulse align-middle" />
          )}
        </h1>

        <p className="text-sm sm:text-base text-slate-500 max-w-xl mx-auto leading-relaxed">
          {dynamicInsight}
        </p>
      </div>

      {/* ── SECTION TITLE ── */}
      <div className="flex items-center justify-center gap-2.5 mb-8">
        <List className="w-5 h-5 text-emerald-600" />
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">Your Projects</h2>
      </div>

      {/* ── CENTERED PROJECTS GRID ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-left">
        {loading ? (
          <div className="col-span-full py-14 text-center text-sm text-slate-400">
            Loading procurement projects…
          </div>
        ) : procurements.length === 0 ? (
          <div className="col-span-full p-10 rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 text-center text-sm text-slate-500">
            No active projects registered. You can simulate and ingest sample tenders via the GeM Gateway.
          </div>
        ) : (
          procurements.map((project) => {
            const statusStr = (project.status || "New").toUpperCase();
            const badgeText = statusStr === "READY" ? "Technical Bid Complete" : statusStr;
            
            return (
              <Link
                key={project.id}
                href={`/workspace/${project.id}`}
                className="group block bg-white p-6 rounded-2xl border border-slate-200/90 shadow-xs hover:border-slate-300 hover:shadow-md transition-all flex flex-col justify-between min-h-[200px]"
              >
                <div>
                  <h3 className="font-bold text-[#111827] text-lg tracking-tight leading-snug line-clamp-2 pb-2 group-hover:text-[#163a5f] transition-colors">
                    {project.title}
                  </h3>
                  <div className="flex items-center mt-1">
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
