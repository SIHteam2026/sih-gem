"use client";

import React from "react";
import RecentProcurementsSection from "@/components/procurement/RecentProcurementsSection";

interface HomeHeroProps {
  className?: string;
  showQuietAction?: boolean;
}

/**
 * HomeHero Component
 * 
 * Implements the left-anchored editorial hero composition matching the OPAL reference:
 * - Headline: "See What the\nEvidence Says"
 * - Supporting description: Explains reconciliation of requirements against evidence.
 * - Embedded Recent Procurements card cluster and Opal Workspace button.
 * - Pure static presentation with zero continuous animation or clutter.
 */
export default function HomeHero({
  className = "",
}: HomeHeroProps) {
  return (
    <section
      aria-label="Procurement Review Overview"
      className={`flex flex-col items-start text-left max-w-[560px] select-none ${className}`}
    >
      {/* Large Primary Statement Headline matching Reference */}
      <h1 className="text-4xl sm:text-5xl lg:text-[3.75rem] font-bold tracking-tight text-[#111827] leading-[1.08] text-balance">
        See What the
        <br />
        Evidence Says
      </h1>

      {/* Concise Human Supporting Paragraph */}
      <p className="mt-6 max-w-[460px] text-sm sm:text-base leading-relaxed text-[#4b5563] text-pretty">
        Opal reconciles tender requirements against bidder evidence—surfacing contradictions, gaps, and ambiguities so officers focus on critical judgment.
      </p>

      {/* Integrated Recent Procurements Section & Opal Workspace Action */}
      <div className="mt-10 sm:mt-12 w-full">
        <RecentProcurementsSection />
      </div>
    </section>
  );
}
