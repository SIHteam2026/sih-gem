"use client";

import React from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { ProcurementSummaryItem } from "@/types/procurement";

export type ProjectCardStateTag = "NEW" | "DRAFT";

export interface ProjectCardProps {
  /** Project name or procurement title */
  title?: string;
  /** Department or procuring organization */
  department?: string;
  /** Formatted load date, e.g. "Loaded 6 Sep 2026" */
  loadedDate?: string;
  /** Dynamic working-state tag: "NEW" | "DRAFT" */
  state?: ProjectCardStateTag;
  /** Action triggered when the card is clicked/opened */
  onOpen?: () => void;
  /** Optional procurement reference identifier */
  reference?: string;
  /** Optional unique identifier */
  id?: string;
  /** Optional canonical procurement item */
  procurement?: ProcurementSummaryItem;
  /** Dynamic state tag alias */
  stateTag?: ProjectCardStateTag;
  /** Optional custom href */
  href?: string;
  /** Optional custom class name */
  className?: string;
}

/**
 * Helper to format date into human-readable text (e.g., "Loaded 14 Oct 2026").
 */
function formatLoadedDate(dateString?: string): string {
  if (!dateString) return "Loaded recently";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return "Loaded recently";
    const formatted = d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
    return `Loaded ${formatted}`;
  } catch {
    return "Loaded recently";
  }
}

/**
 * ProjectCard Component for Opal Workspace
 * 
 * Digital Case File Representation:
 * - Medium-sized, calm, premium card surface with comfortable internal padding.
 * - Clear 4-element typography hierarchy:
 *   1. PROJECT NAME: Dominant, largest text (2-line maximum with graceful wrap)
 *   2. DEPARTMENT / ORGANIZATION: Secondary, smaller text directly below
 *   3. LOADED DATE: Tertiary, small, quiet metadata at the bottom
 *   4. DYNAMIC STATE TAG: Exactly NEW or DRAFT (subtle, non-red/green semantics)
 * 
 * Invariants:
 * - Interactive, keyboard-accessible card with visible focus-ring.
 * - Zero KPI widgets, zero charts, zero progress bars, zero noise.
 * - Minimal hover and focus state transitions.
 */
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
  // Resolve title
  const resolvedTitle = title || procurement?.title || procurement?.external_reference || "Procurement Project";

  // Resolve department / organization
  const resolvedDepartment =
    department || procurement?.organization || procurement?.source_system || "Department of Procurement";

  // Resolve loaded date
  const resolvedLoadedDate =
    loadedDate || formatLoadedDate(procurement?.created_at || procurement?.updated_at);

  // Resolve state tag
  const resolvedState: ProjectCardStateTag =
    state ||
    stateTag ||
    (() => {
      const status = (procurement?.status || "").toUpperCase();
      if (status === "READY" || status === "PROCESSING" || status === "COMPLETED") {
        return "DRAFT";
      }
      return "NEW";
    })();

  const isNew = resolvedState === "NEW";
  const resolvedId = id || procurement?.id || procurement?.procurement_id || "";
  const targetHref = href || (resolvedId ? `/procurements/${encodeURIComponent(resolvedId)}` : undefined);

  const handleClick = () => {
    if (onOpen) {
      onOpen();
    }
  };

  const cardContent = (
    <>
      {/* Top Section: Project Name & Department Subtitle */}
      <div className="space-y-2">
        {/* 1. PROJECT NAME - Dominant Headline */}
        <h2 className="text-base sm:text-lg font-semibold tracking-tight text-[#111827] group-hover:text-[#163a5f] transition-colors line-clamp-2">
          {resolvedTitle}
        </h2>

        {/* 2. DEPARTMENT / ORGANIZATION - Secondary Subtitle directly below */}
        <p className="text-xs sm:text-sm font-normal text-[#64748b] line-clamp-1">
          {resolvedDepartment}
        </p>

        {reference && (
          <p className="font-mono text-[11px] text-[#94a3b8] truncate">
            {reference}
          </p>
        )}
      </div>

      {/* Bottom Section: Loaded Date & Dynamic State Tag */}
      <div className="mt-8 flex items-center justify-between gap-3 pt-4 border-t border-[#f1f5f9]">
        {/* 3. LOADED DATE - Small, Quiet Metadata */}
        <span className="text-xs font-normal text-[#64748b]">
          {resolvedLoadedDate}
        </span>

        {/* 4. DYNAMIC STATE TAG - Exactly NEW or DRAFT */}
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider ${
              isNew
                ? "border border-[#d1d5db] bg-[#f9fafb] text-[#374151]"
                : "border border-[#fed7aa] bg-[#fff7ed] text-[#c2410c]"
            }`}
            aria-label={`Status: ${resolvedState}`}
          >
            {resolvedState}
          </span>

          <span className="hidden sm:inline-flex items-center gap-1 text-xs font-medium text-[#111827] group-hover:text-[#163a5f] transition-colors">
            <ArrowUpRight className="h-3.5 w-3.5 text-[#94a3b8] group-hover:text-[#163a5f] group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
          </span>
        </div>
      </div>
    </>
  );

  if (targetHref && !onOpen) {
    return (
      <Link
        href={targetHref}
        aria-label={`Open project case file: ${resolvedTitle}`}
        className={`focus-ring group relative flex flex-col justify-between rounded-xl sm:rounded-2xl border border-[#e5e7eb] bg-white p-6 sm:p-7 shadow-[0_2px_12px_rgba(0,0,0,0.02)] transition-all duration-200 hover:border-[#cbd5e1] hover:shadow-[0_4px_20px_rgba(0,0,0,0.05)] cursor-pointer text-left select-none ${className}`}
      >
        {cardContent}
      </Link>
    );
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleClick();
        }
      }}
      className={`focus-ring group relative flex flex-col justify-between rounded-xl sm:rounded-2xl border border-[#e5e7eb] bg-white p-6 sm:p-7 shadow-[0_2px_12px_rgba(0,0,0,0.02)] transition-all duration-200 hover:border-[#cbd5e1] hover:shadow-[0_4px_20px_rgba(0,0,0,0.05)] cursor-pointer text-left select-none ${className}`}
      aria-label={`Open project case file: ${resolvedTitle}`}
    >
      {cardContent}
    </div>
  );
}
