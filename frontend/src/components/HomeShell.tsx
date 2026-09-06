"use client";

import React from "react";
import Navbar from "@/components/Navbar";

export interface HomeShellProps {
  /** Custom header (defaults to reference Navbar) */
  header?: React.ReactNode;
  /** Dominant left column: Headline statement, description, recent procurements cluster */
  heroSlot?: React.ReactNode;
  /** Narrow center column: Vertical static living visual */
  livingVisualSlot?: React.ReactNode;
  /** Right column: Greeting and edge-emerging context surface */
  contextSlot?: React.ReactNode;
  /** Optional lower slot */
  recentProcurementSlot?: React.ReactNode;
  /** Supplementary children elements if needed */
  children?: React.ReactNode;
  /** Optional custom className for outer wrapper */
  className?: string;
}

/**
 * HomeShell Component
 * 
 * Rebuilds the unified OPAL Home editorial canvas matching the reference composition:
 * - Pure white canvas background without heavy borders or shadows.
 * - Asymmetric layout: Left hero narrative & cases, Center quiet vertical axis, Right greeting & emerging panel.
 * - One coherent single-viewport opening composition on standard desktop screens.
 */
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
    <div className={`min-h-screen bg-white text-[#111827] flex flex-col selection:bg-[#d8e6ee] ${className}`}>
      {/* Top Navigation */}
      {header}

      {/* Main Workspace Canvas */}
      <main
        id="main-content"
        className="mx-auto w-full max-w-[1360px] flex-1 px-6 sm:px-10 lg:px-12 pt-6 sm:pt-8 lg:pt-10 pb-12"
      >
        {/* Upper Composition: Hero + Living Visual + Officer Context Panel */}
        <section
          aria-label="Overview and Orientation"
          className="grid grid-cols-1 gap-10 lg:grid-cols-12 lg:gap-6 xl:gap-10 lg:items-start"
        >
          {/* Dominant Left Column (6-7 columns on desktop) */}
          <div className="lg:col-span-7 xl:col-span-7 flex flex-col justify-start">
            {heroSlot}
          </div>

          {/* Narrow Center Column: Vertical Architectural Spine */}
          {livingVisualSlot && (
            <div
              className="hidden lg:flex lg:col-span-1 justify-center items-center self-stretch pt-6"
              aria-hidden="true"
            >
              {livingVisualSlot}
            </div>
          )}

          {/* Right Column: Greeting & Emerging Surface (4-5 columns on desktop) */}
          {contextSlot && (
            <div
              className={`w-full ${
                livingVisualSlot
                  ? "lg:col-span-4 xl:col-span-4"
                  : "lg:col-span-5 xl:col-span-5"
              } flex flex-col justify-start items-end`}
            >
              {contextSlot}
            </div>
          )}
        </section>

        {/* Optional Lower Content */}
        {recentProcurementSlot && (
          <section aria-label="Additional Cases" className="mt-8">
            {recentProcurementSlot}
          </section>
        )}

        {children}
      </main>
    </div>
  );
}
