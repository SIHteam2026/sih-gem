"use client";

import React from "react";
import Navbar from "@/components/Navbar";

export interface HomeShellProps {
  /** Optional custom header (defaults to quiet institutional Navbar) */
  header?: React.ReactNode;
  /** Dominant left column: Large primary statement, hero carousel scene */
  heroSlot?: React.ReactNode;
  /** Narrow center column: Vertical living visual stream */
  livingVisualSlot?: React.ReactNode;
  /** Right column: Human greeting, time/session orientation */
  contextSlot?: React.ReactNode;
  /** Legacy lower slot retained for backwards compatibility if passed */
  recentProcurementSlot?: React.ReactNode;
  /** Supplementary children elements if needed */
  children?: React.ReactNode;
  /** Optional custom className for outer wrapper */
  className?: string;
}

export default function HomeShell({
  header = <Navbar />,
  heroSlot,
  livingVisualSlot,
  contextSlot,
  recentProcurementSlot,
  children,
  className = "",
}: HomeShellProps) {
  return (
    <div className={`min-h-screen bg-[#f7f6f2] text-[#162333] flex flex-col selection:bg-[#d8e6ee] ${className}`}>
      {/* Header Slot */}
      {header}

      {/* Main Workspace Landmark */}
      <main
        id="main-content"
        className="mx-auto w-full max-w-6xl flex-1 px-5 py-10 sm:px-8 sm:py-14 lg:py-16"
      >
        {/* Upper Composition: Unified Hero Scene + Living Visual + Officer Context Panel */}
        <section
          aria-label="Overview and Orientation"
          className="grid grid-cols-1 gap-10 lg:grid-cols-12 lg:gap-8 lg:items-start"
        >
          {/* Dominant Left Column: Primary Statement & Integrated Recent Procurements Hero Experience */}
          <div className="lg:col-span-7 xl:col-span-7 flex flex-col justify-start">
            {heroSlot}
          </div>

          {/* Narrow Center Column: Vertical Living Visual Axis */}
          {livingVisualSlot && (
            <div
              className="hidden lg:flex lg:col-span-1 justify-center items-center self-stretch pt-2"
              aria-hidden="true"
            >
              {livingVisualSlot}
            </div>
          )}

          {/* Right Column: Human Context & Orientation */}
          {contextSlot && (
            <div
              className={`w-full ${
                livingVisualSlot
                  ? "lg:col-span-4 xl:col-span-4"
                  : "lg:col-span-5 xl:col-span-5"
              } flex flex-col justify-start`}
            >
              {contextSlot}
            </div>
          )}
        </section>

        {/* Legacy lower slot (rendered only if passed explicitly outside hero) */}
        {recentProcurementSlot && (
          <section aria-label="Recent Procurements" className="mt-10 sm:mt-14">
            {recentProcurementSlot}
          </section>
        )}

        {/* Optional Supplementary Content */}
        {children}
      </main>
    </div>
  );
}
