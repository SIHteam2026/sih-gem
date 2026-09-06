"use client";

import React from "react";

interface LivingVisualProps {
  className?: string;
}

/**
 * LivingVisual Component
 *
 * A quiet, static architectural central composition object matching the OPAL reference.
 *
 * Visual Language:
 * - Narrow vertical spine creating intentional negative space and composition breathing room.
 * - Geometric markers connected by a thin hairline structural line.
 * - Exact static presentation with zero animation, glow, or unnecessary effects.
 */
export default function LivingVisual({ className = "" }: LivingVisualProps) {
  return (
    <div
      className={`relative flex flex-col items-center justify-between py-12 select-none h-[420px] w-12 ${className}`}
      role="img"
      aria-label="Structural composition element representing document evidence review flow"
    >
      {/* Central Thin Structural Hairline Axis */}
      <div
        className="absolute inset-y-12 w-px bg-[#e5e7eb] pointer-events-none"
        aria-hidden="true"
      />

      {/* Top Station: Small Geometric Document Mark */}
      <div className="relative z-10 flex flex-col items-center">
        <div
          className="h-2.5 w-2.5 rounded-[2px] border border-[#9ca3af] bg-white"
          title="Document marker"
        />
        <span className="sr-only">Document stage</span>
      </div>

      {/* Middle Station: Small Precision Circular Evidence Node */}
      <div className="relative z-10 flex flex-col items-center">
        <div className="relative flex items-center justify-center">
          <div className="h-1.5 w-1.5 rounded-full bg-[#111827]" />
          <div
            className="absolute -inset-1 rounded-full border border-[#d1d5db]"
            aria-hidden="true"
          />
        </div>
        <span className="sr-only">Evidence stage</span>
      </div>

      {/* Lower Station: Small Geometric Review Anchor */}
      <div className="relative z-10 flex flex-col items-center">
        <div
          className="h-2.5 w-2.5 rotate-45 border border-[#9ca3af] bg-white"
          title="Review anchor"
        />
        <span className="sr-only">Review stage</span>
      </div>
    </div>
  );
}
