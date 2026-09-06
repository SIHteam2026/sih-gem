"use client";

import React from "react";
import Link from "next/link";
import { History, Terminal } from "lucide-react";
import RecentProcurementsSection from "@/components/procurement/RecentProcurementsSection";

interface HomeHeroProps {
  className?: string;
  showQuietAction?: boolean;
}

/**
 * HomeHero Component
 * 
 * Clean, left-anchored editorial hero composition for the OPAL Home workspace.
 * Houses the headline narrative, supporting explanation, and the embedded
 * Recent Procurements carousel desk composition.
 */
export default function HomeHero({
  className = "",
  showQuietAction = true,
}: HomeHeroProps) {
  return (
    <section
      aria-label="Procurement Review Overview"
      className={`flex flex-col items-start text-left max-w-xl select-none opal-hero-entrance ${className}`}
    >
      {/* Small Restrained Eyebrow */}
      <p className="eyebrow text-[#516574]">Procurement Review</p>

      {/* Large Primary Statement Headline */}
      <h1 className="mt-3.5 text-3xl font-medium tracking-[-0.035em] text-[#162333] sm:text-4xl lg:text-[3.25rem] lg:leading-[1.12] text-balance">
        Review the procurement.
        <br className="hidden sm:inline" />
        {" "}We’ll bring the evidence.
      </h1>

      {/* Concise Human Supporting Paragraph */}
      <p className="mt-5 max-w-lg text-base leading-relaxed text-[#586574] sm:text-[1.0625rem] text-pretty">
        Opal brings together tender requirements, bidder claims, supporting
        evidence, and verification findings, allowing officers to focus on what
        needs human judgment.
      </p>

      {/* Integrated Recent Procurements Hero Experience */}
      <RecentProcurementsSection />

      {/* Secondary Actions (History & Simulator) */}
      {showQuietAction && (
        <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-[#e2e7e4] pt-4 w-full">
          <Link
            href="/history"
            className="focus-ring inline-flex items-center gap-1.5 rounded border border-[#cfd5d5] bg-[#fffefa] px-3.5 py-2 text-xs font-medium text-[#263746] transition-colors hover:bg-white hover:border-[#b8c2c2]"
          >
            <History className="h-3.5 w-3.5 text-[#697987]" />
            Review history
          </Link>
          <Link
            href="/mock-gem"
            className="focus-ring inline-flex items-center gap-1.5 rounded border border-dashed border-[#cbd2d5] bg-[#fbfbf9] px-3.5 py-2 font-mono text-xs text-[#586774] transition-colors hover:bg-white hover:text-[#162333]"
          >
            <Terminal className="h-3.5 w-3.5 text-[#7e8e9c]" />
            Mock-GeM Simulator
          </Link>
        </div>
      )}

      {/* Micro-Interaction & Reduced Motion Styles */}
      <style jsx>{`
        @keyframes heroEntrance {
          from {
            opacity: 0;
            transform: translateY(4px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .opal-hero-entrance {
          animation: heroEntrance 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
        }

        @media (prefers-reduced-motion: reduce) {
          .opal-hero-entrance {
            animation: none !important;
            opacity: 1 !important;
            transform: none !important;
          }
        }
      `}</style>
    </section>
  );
}
