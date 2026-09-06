"use client";

import React from "react";

interface LivingVisualProps {
  className?: string;
}

/**
 * LivingVisual Component
 *
 * A quiet, architectural central composition object for OPAL Home.
 *
 * Visual Concept:
 * Conceptual movement from document to verified fact to final review:
 *   [ DOC ]
 *      ↓
 *   [ FACT ]
 *      ↓
 *  [ REVIEW ]
 *
 * Design Invariants:
 * - Thin, architectural hairline track with sparse drafting datum marks.
 * - Restrained editorial annotations (DOC, FACT, REVIEW) in tiny muted monospace.
 * - Slow, deliberate 11-second cycle: emergence at DOC → travel → pause at FACT → settle at REVIEW → quiet stillness.
 * - Zero gradients, zero neon, zero glow, zero pulse auras, zero generic AI effects.
 * - Full prefers-reduced-motion support rendering a calm, elegant, complete static composition.
 * - Responsive: maintains narrow vertical spine on desktop, scales gracefully on compact screens.
 */
export default function LivingVisual({ className = "" }: LivingVisualProps) {
  return (
    <div
      className={`relative flex flex-col items-center justify-between py-6 select-none ${className}`}
      style={{ minHeight: "360px", width: "54px" }}
      role="img"
      aria-label="Visual composition showing conceptual movement from document to verified fact to final review"
    >
      {/* Central Architectural Hairline Axis */}
      <div
        className="absolute inset-y-6 w-px bg-[#d5ded8] pointer-events-none"
        aria-hidden="true"
      />

      {/* Sparse Blueprint / Elevation Datum Ticks Along the Track */}
      <div
        className="absolute top-[23%] left-1/2 -translate-x-1/2 w-2 h-px bg-[#b8c4bc] pointer-events-none"
        aria-hidden="true"
      />
      <div
        className="absolute top-[37%] left-1/2 -translate-x-1/2 w-1.5 h-px bg-[#cfd7cf] pointer-events-none"
        aria-hidden="true"
      />
      <div
        className="absolute top-[63%] left-1/2 -translate-x-1/2 w-1.5 h-px bg-[#cfd7cf] pointer-events-none"
        aria-hidden="true"
      />
      <div
        className="absolute top-[77%] left-1/2 -translate-x-1/2 w-2 h-px bg-[#b8c4bc] pointer-events-none"
        aria-hidden="true"
      />

      {/* Station 1: Document Origin (Upper Section) */}
      <div className="relative z-10 flex flex-col items-center">
        <div
          className="grid h-7 w-7 place-items-center rounded-[2px] border border-[#cfd7cf] bg-[#fffefa] text-[#163a5f]"
          title="Document"
        >
          <svg
            width="12"
            height="14"
            viewBox="0 0 12 14"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.1"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-[#163a5f]/85"
            shapeRendering="geometricPrecision"
            aria-hidden="true"
          >
            {/* Minimal architectural document symbol */}
            <path d="M1.5 1h6l3 3v9H1.5V1z" />
            <path d="M7.5 1v3h3" />
            <line x1="3.5" y1="6.5" x2="7.5" y2="6.5" strokeWidth="0.9" />
            <line x1="3.5" y1="9" x2="6.5" y2="9" strokeWidth="0.9" />
          </svg>
        </div>
        <span className="mt-1.5 text-[8px] font-mono tracking-[0.22em] text-[#84929e] uppercase select-none">
          DOC
        </span>
      </div>

      {/* Station 2: Fact & Evidence Waypoint (Middle Section) */}
      <div className="relative z-10 flex flex-col items-center">
        <div
          className="grid h-7 w-7 place-items-center rounded-[2px] border border-[#cfd7cf] bg-[#fffefa] text-[#2c5378]"
          title="Fact"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.1"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-[#2c5378]/85"
            shapeRendering="geometricPrecision"
            aria-hidden="true"
          >
            {/* Precision architectural datum crosshair */}
            <line x1="1.5" y1="7" x2="4.5" y2="7" strokeWidth="1" />
            <line x1="9.5" y1="7" x2="12.5" y2="7" strokeWidth="1" />
            <line x1="7" y1="1.5" x2="7" y2="4.5" strokeWidth="1" />
            <line x1="7" y1="9.5" x2="7" y2="12.5" strokeWidth="1" />
            <circle cx="7" cy="7" r="1.5" fill="currentColor" stroke="none" />
          </svg>
        </div>
        <span className="mt-1.5 text-[8px] font-mono tracking-[0.22em] text-[#84929e] uppercase select-none">
          FACT
        </span>
      </div>

      {/* Station 3: Human Review / Resolved State (Lower Section) */}
      <div className="relative z-10 flex flex-col items-center">
        <div
          className="grid h-7 w-7 place-items-center rounded-[2px] border border-[#b8c6bd] bg-[#f2f7f4] text-[#1c4b37]"
          title="Review"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-[#1c4b37]"
            shapeRendering="geometricPrecision"
            aria-hidden="true"
          >
            {/* Restrained editorial sign-off seal */}
            <circle cx="7" cy="7" r="4.75" strokeWidth="0.9" />
            <polyline points="4.75 7 6.25 8.5 9.25 5.5" strokeWidth="1.2" />
          </svg>
        </div>
        <span className="mt-1.5 text-[8px] font-mono tracking-[0.22em] text-[#4a725b] uppercase font-medium select-none">
          REVIEW
        </span>
      </div>

      {/* Traveling Architectural Mark (No glow, no blur, intentional slow sequence) */}
      <div
        className="opal-traveler-mark absolute left-1/2 -translate-x-1/2 z-20 pointer-events-none"
        aria-hidden="true"
      >
        <div className="h-2 w-2 rounded-[1px] border border-[#163a5f] bg-[#163a5f]" />
      </div>

      {/* Embedded Restrained CSS Animation Styles */}
      <style jsx>{`
        @keyframes verticalStreamCycle {
          /* Phase 1: Silent emergence at DOC origin */
          0% {
            top: 36px;
            opacity: 0;
            transform: translate(-50%, -2px);
          }
          6% {
            top: 38px;
            opacity: 1;
            transform: translate(-50%, 0);
          }
          12% {
            top: 38px;
            opacity: 1;
            transform: translate(-50%, 0);
          }

          /* Phase 2: Steady travel toward middle FACT waypoint */
          36% {
            top: calc(50% - 4px);
            opacity: 1;
            transform: translate(-50%, 0);
          }

          /* Phase 3: Deliberate quiet pause at FACT marker */
          52% {
            top: calc(50% - 4px);
            opacity: 1;
            transform: translate(-50%, 0);
          }

          /* Phase 4: Settle toward lower REVIEW destination */
          76% {
            top: calc(100% - 46px);
            opacity: 1;
            transform: translate(-50%, 0);
          }
          84% {
            top: calc(100% - 46px);
            opacity: 1;
            transform: translate(-50%, 0);
          }

          /* Phase 5: Fade absorption into REVIEW station */
          89% {
            top: calc(100% - 45px);
            opacity: 0;
            transform: translate(-50%, 1px);
          }

          /* Phase 6: Long quiet interval / resting pause */
          100% {
            top: calc(100% - 45px);
            opacity: 0;
            transform: translate(-50%, 1px);
          }
        }

        .opal-traveler-mark {
          animation: verticalStreamCycle 11s cubic-bezier(0.4, 0, 0.2, 1) infinite;
        }

        /* Calm, static resting state for users with reduced motion preferences */
        @media (prefers-reduced-motion: reduce) {
          .opal-traveler-mark {
            animation: none !important;
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
}
