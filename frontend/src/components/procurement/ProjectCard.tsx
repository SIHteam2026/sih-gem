"use client";

import React from "react";
import { ArrowUpRight } from "lucide-react";

export interface ProjectCardProps {
  /** Project name or procurement title */
  title: string;
  /** Department or procuring organization */
  department: string;
  /** Formatted load date, e.g. "Loaded 6 Sep 2026" */
  loadedDate: string;
  /** Dynamic working-state tag: "NEW" | "DRAFT" */
  state: "NEW" | "DRAFT";
  /** Action triggered when the card is clicked/opened */
  onOpen: () => void;
  /** Optional procurement reference identifier */
  reference?: string;
  /** Optional unique identifier */
  id?: string;
  /** Optional custom class name */
  className?: string;
}

/**
 * ProjectCard Component
 * 
 * Reusable project shelf card adhering to OPAL's calm, utilitarian design language:
 * - Clean white card with subtle 1px border and quiet hover elevation
 * - Displays department/organization, dynamic working-state tag (NEW / DRAFT),
 *   project title, formatted canonical load date, and open affordance.
 * - Card internals designed as an isolated interface for teammate extension.
 */
export default function ProjectCard({
  title,
  department,
  loadedDate,
  state,
  onOpen,
  reference,
  className = "",
}: ProjectCardProps) {
  const isNew = state === "NEW";

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen();
        }
      }}
      className={`group flex flex-col justify-between rounded-xl sm:rounded-2xl border border-[#e5e7eb] bg-white p-6 sm:p-7 shadow-[0_2px_12px_rgba(0,0,0,0.02)] transition-all duration-200 hover:border-[#cbd5e1] hover:shadow-[0_4px_20px_rgba(0,0,0,0.05)] cursor-pointer text-left focus-ring select-none ${className}`}
      aria-label={`Open project ${title}`}
    >
      {/* Top Meta Row: Department & Dynamic State Tag */}
      <div>
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-medium uppercase tracking-wider text-[#64748b] truncate">
            {department || "Government Organization"}
          </p>

          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider ${
              isNew
                ? "border border-[#d1d5db] bg-[#f9fafb] text-[#374151]"
                : "border border-[#fed7aa] bg-[#fff7ed] text-[#c2410c]"
            }`}
          >
            {state}
          </span>
        </div>

        {/* Project / Procurement Title */}
        <h2 className="mt-3 text-lg sm:text-xl font-semibold text-[#111827] leading-snug tracking-tight group-hover:text-[#163a5f] transition-colors line-clamp-2">
          {title}
        </h2>

        {reference && (
          <p className="mt-1 font-mono text-[11px] text-[#94a3b8] truncate">
            {reference}
          </p>
        )}
      </div>

      {/* Bottom Row: Human-Readable Load Date & Navigation Action */}
      <div className="mt-6 pt-4 border-t border-[#f1f5f9] flex items-center justify-between text-xs text-[#64748b]">
        <span className="font-normal text-[#64748b]">
          {loadedDate}
        </span>

        <span className="inline-flex items-center gap-1 font-medium text-[#111827] group-hover:text-[#163a5f] transition-colors">
          <span>Open</span>
          <ArrowUpRight className="h-3.5 w-3.5 text-[#94a3b8] group-hover:text-[#163a5f] group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
        </span>
      </div>
    </div>
  );
}
