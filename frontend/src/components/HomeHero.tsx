"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

interface HomeHeroProps {
  className?: string;
  showQuietAction?: boolean;
}

/**
 * HomeHero Component
 * 
 * Clean, left-anchored editorial hero composition for the OPAL Home workspace.
 * 
 * Design Principles:
 * - Strong left-edge anchor with deliberate negative space to the right.
 * - Restrained, human-authored editorial typography on paper background.
 * - Removed heavy multi-button landing-page chrome in favor of a quiet directional action.
 * - Natural visual alignment with the active procurement workspace below.
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

      {/* Quiet Directional Workspace Action */}
      {showQuietAction && (
        <div className="mt-7 pt-1">
          <Link
            href="/procurements"
            className="focus-ring group inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#163a5f] transition-colors hover:text-[#235384]"
          >
            <span>Open Procurement Workspace</span>
            <ArrowRight className="h-3.5 w-3.5 text-[#163a5f] transition-transform group-hover:translate-x-1" />
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
