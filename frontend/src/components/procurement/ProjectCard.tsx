"use client";

import React from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { ProcurementSummaryItem } from "@/types/procurement";

export type ProjectCardStateTag = "NEW" | "UNDER PROCESS" | "ALMOST COMPLETED";

export interface ProjectCardProps {
  title?: string;
  department?: string;
  loadedDate?: string;
  state?: ProjectCardStateTag;
  onOpen?: () => void;
  reference?: string;
  id?: string;
  procurement?: ProcurementSummaryItem;
  stateTag?: ProjectCardStateTag;
  href?: string;
  className?: string;
}

function formatLoadedDate(dateString?: string): string {
  if (!dateString) return "Loaded recently";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return "Loaded recently";
    return `Loaded ${d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    })}`;
  } catch (e) {
    return "Loaded recently";
  }
}

export default function ProjectCard({
  title,
  department,
  loadedDate,
  state,
  onOpen,
  reference,
  id,
  procurement,
  stateTag,
  href,
  className = "",
}: ProjectCardProps) {
  const resolvedTitle = title || procurement?.title || procurement?.external_reference || "Procurement Project";
  const resolvedDepartment = department || procurement?.organization || procurement?.source_system || "Department of Procurement";
  const resolvedLoadedDate = loadedDate || formatLoadedDate(procurement?.created_at || procurement?.updated_at);
  const resolvedState: ProjectCardStateTag = state || stateTag || "NEW";

  const isNew = resolvedState === "NEW";
  const tagClasses = isNew
    ? "bg-[#edf2f5] text-[#1c3850] border-[#cbd9e2]"
    : resolvedState === "UNDER PROCESS" 
    ? "bg-amber-50 text-amber-800 border-amber-200"
    : "bg-[#e8f1ec] text-[#2c5f43] border-[#a0c5b0]";

  const content = (
    <div className="flex flex-col h-full justify-between p-6">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div className="space-y-1 w-full max-w-xl">
          <h2 className="text-xl font-bold tracking-tight text-slate-900 group-hover:text-blue-700 transition-colors leading-snug break-words">
            {resolvedTitle}
          </h2>
          <p className="text-sm font-medium text-slate-500 line-clamp-1">{resolvedDepartment}</p>
          {reference && (
            <p className="text-xs font-mono text-slate-400 mt-1">Ref: {reference}</p>
          )}
        </div>
        
        <div className="shrink-0 flex items-center gap-3">
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded text-[11px] font-bold uppercase tracking-widest border ${tagClasses}`}>
            {resolvedState}
          </span>
          <div className="flex items-center justify-center w-8 h-8 rounded-full border border-slate-200 bg-white text-slate-400 group-hover:border-blue-300 group-hover:bg-blue-50 group-hover:text-blue-600 transition-all shadow-sm">
            <ArrowUpRight className="w-4 h-4" />
          </div>
        </div>
      </div>
      
      <div className="mt-8 border-t border-slate-100 pt-4 flex items-center justify-between">
        <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">{resolvedLoadedDate}</p>
      </div>
    </div>
  );

  const cardClasses = `group block w-full bg-white border border-slate-200/90 rounded-xl shadow-sm hover:shadow-md hover:border-slate-300 transition-all focus-ring focus-within-ring cursor-pointer text-left min-h-[160px] ${className}`;

  if (href) {
    return (
      <Link href={href} className={cardClasses}>
        {content}
      </Link>
    );
  }

  if (onOpen) {
    return (
      <button type="button" onClick={onOpen} className={cardClasses}>
        {content}
      </button>
    );
  }

  return <div className={cardClasses}>{content}</div>;
}
