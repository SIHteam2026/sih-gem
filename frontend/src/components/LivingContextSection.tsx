"use client";

import React from "react";
import LivingVisual from "./LivingVisual";
import OfficerContextPanel from "./OfficerContextPanel";

interface LivingContextSectionProps {
  officerName?: string;
  roleTitle?: string;
  className?: string;
}

/**
 * LivingContextSection Component
 * 
 * Unites the narrow vertical LivingVisual stream and the OfficerContextPanel
 * into a harmonious, balanced right-side living orientation layout.
 */
export default function LivingContextSection({
  officerName = "Mr. Srivastav",
  roleTitle = "Procurement Review Officer",
  className = "",
}: LivingContextSectionProps) {
  return (
    <div className={`flex items-stretch gap-4 sm:gap-6 ${className}`}>
      {/* Narrow Center Vertical Visual */}
      <div className="hidden md:flex shrink-0 items-center justify-center">
        <LivingVisual />
      </div>

      {/* Right Officer Context Panel */}
      <div className="w-full flex-1">
        <OfficerContextPanel officerName={officerName} roleTitle={roleTitle} />
      </div>
    </div>
  );
}

export { LivingVisual, OfficerContextPanel };
