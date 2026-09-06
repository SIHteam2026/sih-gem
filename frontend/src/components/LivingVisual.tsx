"use client";

import React from "react";

interface LivingVisualProps {
  className?: string;
}

/**
 * LivingVisual Component
 * 
 * A quiet piece of OPAL product identity representing the transformation of
 * raw procurement documents into verified evidence and officer review readiness.
 * 
 * Design Principles:
 * - Thin geometry, hairline axis and restrained iconography.
 * - Slow 11-second cycle avoiding distracting rapid motion.
 * - Full support for prefers-reduced-motion with an elegant, balanced static state.
 * - Pure CSS animations with zero runtime dependencies or CPU overhead.
 */
export default function LivingVisual({ className = "" }: LivingVisualProps) {
  return (
    <div
      className={`relative flex flex-col items-center justify-between py-6 select-none ${className}`}
      style={{ minHeight: "360px", width: "56px" }}
      role="img"
      aria-label="Visual representation of document and evidence flow leading to review"
    >
      {/* Central Thin Vertical Axis Line */}
      <div
        className="absolute inset-y-8 w-px pointer-events-none"
        style={{
          background:
            "linear-gradient(180deg, rgba(217, 221, 217, 0) 0%, rgba(200, 208, 202, 0.8) 15%, rgba(180, 192, 185, 0.9) 50%, rgba(200, 208, 202, 0.8) 85%, rgba(217, 221, 217, 0) 100%)",
        }}
        aria-hidden="true"
      />

      {/* Station 1: Ingested Document (Top) */}
      <div className="relative z-10 flex flex-col items-center group">
        <div
          className="grid h-8 w-8 place-items-center rounded-sm border border-[#cfd7cf] bg-[#fffefa] text-[#163a5f] shadow-xs transition-colors"
          title="Tender & Submissions"
        >
          <svg
            width="14"
            height="16"
            viewBox="0 0 14 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-[#163a5f]/80"
            aria-hidden="true"
          >
            {/* Document silhouette with micro-folded corner */}
            <path d="M2 1h7l4 4v10H2V1z" />
            <path d="M9 1v4h4" />
            <line x1="4.5" y1="8" x2="9.5" y2="8" strokeWidth="1" />
            <line x1="4.5" y1="11" x2="8" y2="11" strokeWidth="1" />
          </svg>
        </div>
        <span className="mt-1 text-[9px] font-mono tracking-wider text-[#7a8894] uppercase opacity-70">
          Doc
        </span>
      </div>

      {/* Station 2: Reconciled Evidence (Middle Waypoint) */}
      <div className="relative z-10 flex flex-col items-center group">
        <div
          className="grid h-8 w-8 place-items-center rounded-sm border border-[#cfd7cf] bg-[#fffefa] text-[#2c5378] shadow-xs transition-colors"
          title="Reconciled Evidence"
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
            className="text-[#2c5378]/85"
            aria-hidden="true"
          >
            {/* Evidence datum alignment marks */}
            <line x1="2" y1="7" x2="5.5" y2="7" strokeWidth="1.2" />
            <line x1="8.5" y1="7" x2="12" y2="7" strokeWidth="1.2" />
            <circle cx="7" cy="7" r="1.75" fill="currentColor" stroke="none" />
            <path d="M7 2.5v2M7 9.5v2" strokeWidth="1" />
          </svg>
        </div>
        <span className="mt-1 text-[9px] font-mono tracking-wider text-[#7a8894] uppercase opacity-70">
          Fact
        </span>
      </div>

      {/* Station 3: Human Review Ready (Bottom Destination) */}
      <div className="relative z-10 flex flex-col items-center group">
        <div
          className="grid h-8 w-8 place-items-center rounded-sm border border-[#b8c6bd] bg-[#f2f7f4] text-[#1c4b37] shadow-xs transition-colors"
          title="Review Ready"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.3"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-[#1c4b37]"
            aria-hidden="true"
          >
            {/* Balanced review seal node */}
            <circle cx="7" cy="7" r="5" strokeDasharray="1.5 1.5" strokeWidth="1" />
            <polyline points="4.5 7 6.2 8.8 9.5 5.5" />
          </svg>
        </div>
        <span className="mt-1 text-[9px] font-mono tracking-wider text-[#527763] uppercase font-medium">
          Ready
        </span>
      </div>

      {/* Animated Traveling Evidence Marker */}
      <div
        className="opal-traveler-node absolute left-1/2 -translate-x-1/2 z-20 pointer-events-none"
        aria-hidden="true"
      >
        <div className="relative flex items-center justify-center">
          <div className="h-3.5 w-3.5 rounded-sm border border-[#163a5f]/40 bg-[#163a5f] shadow-sm flex items-center justify-center">
            <div className="h-1 w-1 rounded-full bg-white opacity-90" />
          </div>
          {/* Subtle quiet pulse aura around traveling marker */}
          <div className="opal-traveler-pulse absolute -inset-1 rounded-full bg-[#163a5f]/15" />
        </div>
      </div>

      {/* Embedded Restrained CSS Animation Styles */}
      <style jsx>{`
        @keyframes verticalStreamCycle {
          0% {
            top: 40px;
            opacity: 0;
            transform: translate(-50%, -4px) scale(0.9);
          }
          6% {
            top: 42px;
            opacity: 0.95;
            transform: translate(-50%, 0) scale(1);
          }
          32% {
            top: calc(50% - 7px);
            opacity: 0.95;
            transform: translate(-50%, 0) scale(1);
          }
          48% {
            top: calc(50% - 7px);
            opacity: 1;
            transform: translate(-50%, 0) scale(1.08);
          }
          74% {
            top: calc(100% - 50px);
            opacity: 0.95;
            transform: translate(-50%, 0) scale(1);
          }
          88% {
            top: calc(100% - 48px);
            opacity: 0.95;
            transform: translate(-50%, 0) scale(1.05);
          }
          96% {
            top: calc(100% - 46px);
            opacity: 0;
            transform: translate(-50%, 3px) scale(0.9);
          }
          100% {
            top: calc(100% - 46px);
            opacity: 0;
            transform: translate(-50%, 3px) scale(0.9);
          }
        }

        @keyframes subtleAuraPulse {
          0%, 100% {
            transform: scale(1);
            opacity: 0.2;
          }
          50% {
            transform: scale(1.4);
            opacity: 0.5;
          }
        }

        .opal-traveler-node {
          animation: verticalStreamCycle 11s cubic-bezier(0.42, 0, 0.58, 1) infinite;
        }

        .opal-traveler-pulse {
          animation: subtleAuraPulse 3s ease-in-out infinite;
        }

        /* Calm, static resting state when prefers-reduced-motion is active */
        @media (prefers-reduced-motion: reduce) {
          .opal-traveler-node {
            animation: none !important;
            display: none !important;
          }
          .opal-traveler-pulse {
            animation: none !important;
          }
        }
      `}</style>
    </div>
  );
}
