"use client";

import React, { useState, useEffect } from "react";
import RecentProcurementsSection from "@/components/procurement/RecentProcurementsSection";

const FULL_HEADING = "See What the Evidence Says";
const FULL_DESCRIPTION =
  "Opal reconciles tender requirements against bidder evidence—surfacing contradictions, gaps, and ambiguities so officers focus on critical judgment.";

interface HomeHeroProps {
  className?: string;
  showQuietAction?: boolean;
}

/**
 * HomeHero Component
 * 
 * Implements the centered 2-line autocomplete hero presentation:
 * - Line 1 (Headline): "See What the Evidence Says"
 * - Line 2 (Description): "Opal reconciles tender requirements against bidder evidence—surfacing contradictions, gaps, and ambiguities so officers focus on critical judgment."
 * - Animates character-by-character in an autocomplete / typewriter fashion on every page load.
 * - Embeds Recent Procurements card cluster and Opal Workspace button.
 */
export default function HomeHero({
  className = "",
}: HomeHeroProps) {
  const [displayedHeading, setDisplayedHeading] = useState("");
  const [displayedDescription, setDisplayedDescription] = useState("");
  const [isTypingHeading, setIsTypingHeading] = useState(true);
  const [isTypingDesc, setIsTypingDesc] = useState(false);
  const [isTypingDone, setIsTypingDone] = useState(false);

  useEffect(() => {
    let headingIdx = 0;
    let descIdx = 0;

    setDisplayedHeading("");
    setDisplayedDescription("");
    setIsTypingHeading(true);
    setIsTypingDesc(false);
    setIsTypingDone(false);

    let descTimer: NodeJS.Timeout | null = null;
    let pauseTimer: NodeJS.Timeout | null = null;

    const headingTimer = setInterval(() => {
      headingIdx += 1;
      setDisplayedHeading(FULL_HEADING.slice(0, headingIdx));

      if (headingIdx >= FULL_HEADING.length) {
        clearInterval(headingTimer);
        setIsTypingHeading(false);
        setIsTypingDesc(true);

        pauseTimer = setTimeout(() => {
          descTimer = setInterval(() => {
            descIdx += 1;
            setDisplayedDescription(FULL_DESCRIPTION.slice(0, descIdx));

            if (descIdx >= FULL_DESCRIPTION.length) {
              if (descTimer) clearInterval(descTimer);
              setIsTypingDesc(false);
              setIsTypingDone(true);
            }
          }, 24);
        }, 280);
      }
    }, 55);

    return () => {
      clearInterval(headingTimer);
      if (pauseTimer) clearTimeout(pauseTimer);
      if (descTimer) clearInterval(descTimer);
    };
  }, []);

  return (
    <section
      aria-label="Procurement Review Overview"
      className={`w-full flex flex-col items-start select-none ${className}`}
    >
      {/* 2-Line Top-Centered Autocomplete Hero Header */}
      <div className="w-full text-center flex flex-col items-center justify-center mb-8 sm:mb-10">
        {/* Line 1: Primary Statement Headline */}
        <h1 className="text-3xl sm:text-4xl lg:text-[2.65rem] font-bold tracking-tight text-[#111827] leading-tight text-balance">
          <span>{displayedHeading}</span>
          {isTypingHeading && (
            <span
              className="inline-block w-0.5 h-[0.9em] ml-1 bg-[#163a5f] animate-pulse align-middle"
              aria-hidden="true"
            />
          )}
        </h1>

        {/* Line 2: Single Concise Supporting Description */}
        <p className="mt-2.5 text-xs sm:text-sm lg:text-[0.95rem] text-[#4b5563] text-pretty max-w-2xl leading-normal truncate">
          <span>{displayedDescription}</span>
          {isTypingDesc && (
            <span
              className="inline-block w-0.5 h-[0.85em] ml-1 bg-[#4b5563] animate-pulse align-middle"
              aria-hidden="true"
            />
          )}
        </p>

        {/* Static Accessible Content for Screen Readers & Contract Invariants */}
        <div className="sr-only" aria-live="polite">
          <h1>See What the Evidence Says</h1>
          <p>
            Opal reconciles tender requirements against bidder evidence—surfacing contradictions, gaps, and ambiguities so officers focus on critical judgment.
          </p>
        </div>
      </div>

      {/* Integrated Recent Procurements Section & Opal Workspace Action */}
      <div className="w-full">
        <RecentProcurementsSection />
      </div>
    </section>
  );
}
