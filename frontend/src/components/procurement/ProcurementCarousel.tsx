"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight, Users, FileText, ArrowRight, Sparkles } from "lucide-react";
import { ProcurementSummaryItem } from "@/types/procurement";
import StatusBadge from "./StatusBadge";
import SourceBadge from "./SourceBadge";

interface ProcurementCarouselProps {
  procurements: ProcurementSummaryItem[];
  workspaceHref?: string;
  className?: string;
}

export default function ProcurementCarousel({
  procurements = [],
  workspaceHref = "/procurements",
  className = "",
}: ProcurementCarouselProps) {
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const touchStartXRef = useRef<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Keep selected index valid when procurements change
  useEffect(() => {
    if (selectedIndex >= procurements.length && procurements.length > 0) {
      setSelectedIndex(0);
    }
  }, [procurements.length, selectedIndex]);

  const handlePrev = useCallback(() => {
    setSelectedIndex((prev) => (prev > 0 ? prev - 1 : prev));
  }, []);

  const handleNext = useCallback(() => {
    setSelectedIndex((prev) => (prev < procurements.length - 1 ? prev + 1 : prev));
  }, [procurements.length]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      handlePrev();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      handleNext();
    }
  };

  // Touch handlers for mobile swipe
  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartXRef.current = e.touches[0].clientX;
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartXRef.current === null) return;
    const diffX = touchStartXRef.current - e.changedTouches[0].clientX;
    if (diffX > 40) {
      handleNext();
    } else if (diffX < -40) {
      handlePrev();
    }
    touchStartXRef.current = null;
  };

  if (!procurements || procurements.length === 0) {
    return (
      <div className={`rounded border border-dashed border-[#cbd2d1] bg-[#fffefa] p-8 text-center sm:p-10 ${className}`}>
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[#f2f4f2] text-[#556977]">
          <FileText className="h-5 w-5" aria-hidden="true" />
        </div>
        <h3 className="text-base font-semibold text-[#162333]">No procurements yet</h3>
        <p className="mx-auto mt-2 max-w-sm text-xs leading-relaxed text-[#65717b]">
          Procurement cases appear here automatically once ingested into the system.
        </p>
        <div className="mt-5">
          <Link
            href={workspaceHref}
            className="focus-ring inline-flex items-center gap-2 rounded bg-[#163a5f] px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-[#214c77]"
          >
            Go to Workspace <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    );
  }

  const selectedItem = procurements[selectedIndex] || procurements[0];
  const selectedProcurementId = selectedItem.id || selectedItem.procurement_id;
  const isCanonicalDemo =
    selectedItem.title?.toLowerCase().includes("water quality monitoring") ||
    selectedItem.external_reference?.includes("CPCL/WQM/2026/RFP-017") ||
    selectedItem.external_reference?.includes("DEMO/CPCL/WQM/2026/017");

  return (
    <div
      ref={containerRef}
      className={`space-y-6 outline-none ${className}`}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
      aria-label="Recent procurements carousel. Use left and right arrow keys to navigate."
    >
      {/* Visual Composition Container */}
      <div className="relative min-h-[360px] sm:min-h-[380px]">
        {/* Desktop & Tablet Stacked Card Visual Composition */}
        <div className="hidden sm:block relative w-full h-[360px]">
          {procurements.map((item, idx) => {
            const itemId = item.id || item.procurement_id;
            const isSelected = idx === selectedIndex;
            const offset = idx - selectedIndex;
            
            // Only render items close to selection for clean physical document aesthetic
            if (Math.abs(offset) > 3) return null;

            // Compute depth layering style based on relative offset
            let style: React.CSSProperties = {};
            let layerClasses = "";

            if (isSelected) {
              style = {
                zIndex: 30,
                transform: "translate3d(0, 0, 0) scale(1)",
                opacity: 1,
              };
              layerClasses = "border-[#b8c4c2] shadow-[0_8px_30px_rgb(0,0,0,0.06)] bg-[#fffefa]";
            } else if (offset > 0) {
              // Right receding cards
              const shiftX = Math.min(offset * 28 + 24, 90);
              const scale = 1 - Math.min(offset * 0.04, 0.12);
              const opacity = 1 - offset * 0.22;
              style = {
                zIndex: 30 - offset,
                transform: `translate3d(${shiftX}px, ${offset * 6}px, 0) scale(${scale})`,
                opacity: Math.max(opacity, 0.4),
              };
              layerClasses = "border-[#d8deda] bg-[#fbfbf9] cursor-pointer hover:border-[#a0b0ae]";
            } else {
              // Left receding cards
              const shiftX = Math.max(offset * 28 - 24, -90);
              const scale = 1 - Math.min(Math.abs(offset) * 0.04, 0.12);
              const opacity = 1 - Math.abs(offset) * 0.22;
              style = {
                zIndex: 30 - Math.abs(offset),
                transform: `translate3d(${shiftX}px, ${Math.abs(offset) * 6}px, 0) scale(${scale})`,
                opacity: Math.max(opacity, 0.4),
              };
              layerClasses = "border-[#d8deda] bg-[#fbfbf9] cursor-pointer hover:border-[#a0b0ae]";
            }

            return (
              <div
                key={itemId || idx}
                onClick={() => !isSelected && setSelectedIndex(idx)}
                style={style}
                className={`absolute top-0 left-0 right-0 max-w-2xl mx-auto p-6 sm:p-7 rounded border transition-all duration-300 ease-out select-none ${layerClasses}`}
              >
                {/* Physical Document Header Accent */}
                <div className="flex items-center justify-between border-b border-[#e6eae6] pb-4 mb-4">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] font-medium tracking-wider text-[#73828e] uppercase">
                      Case #{idx + 1}
                    </span>
                    {item.external_reference && (
                      <>
                        <span className="text-[#c1c9c8]" aria-hidden="true">•</span>
                        <span className="font-mono text-xs text-[#4c5b67] font-semibold">
                          {item.external_reference}
                        </span>
                      </>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <SourceBadge source={item.source_system} />
                    <StatusBadge status={item.status} size="sm" />
                  </div>
                </div>

                {/* Primary Information Hierarchy */}
                {/* 1. TITLE First */}
                <h3 className="text-xl sm:text-2xl font-medium tracking-tight text-[#162333] leading-snug line-clamp-2">
                  {item.title}
                </h3>

                {/* 2. CONTEXT Second */}
                <div className="mt-3 flex items-center gap-2 text-xs sm:text-sm text-[#4e5d6a]">
                  <span className="font-medium text-[#263746]">{item.organization}</span>
                </div>

                {/* Canonical Demo Indicator */}
                {isCanonicalDemo && isSelected && (
                  <div className="mt-4 inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#f0f5fa] border border-[#cbdceb] text-xs text-[#1c4b75] font-medium">
                    <Sparkles className="w-3.5 h-3.5 text-[#2b6ba3]" aria-hidden="true" />
                    <span>Canonical Demo Case</span>
                  </div>
                )}

                {/* Metadata Details & Footer */}
                <div className="mt-6 pt-4 border-t border-[#edf0ee] flex items-center justify-between">
                  <div className="flex items-center gap-5 text-xs text-[#5f6e7a]">
                    <div className="flex items-center gap-1.5" title="Bidder submissions count">
                      <Users className="w-4 h-4 text-[#798895]" aria-hidden="true" />
                      <span>
                        <strong className="font-mono font-semibold text-[#162333]">{item.bidder_count ?? 0}</strong> {item.bidder_count === 1 ? "Bidder" : "Bidders"}
                      </span>
                    </div>
                    {item.tender_count !== undefined && item.tender_count > 0 && (
                      <div className="flex items-center gap-1.5" title="Tenders count">
                        <FileText className="w-4 h-4 text-[#798895]" aria-hidden="true" />
                        <span>
                          <strong className="font-mono font-semibold text-[#162333]">{item.tender_count}</strong> {item.tender_count === 1 ? "Tender" : "Tenders"}
                        </span>
                      </div>
                    )}
                  </div>

                  {isSelected ? (
                    <Link
                      href={`/procurements/${selectedProcurementId}`}
                      className="focus-ring inline-flex items-center gap-2 px-4 py-2 rounded text-xs font-medium bg-[#163a5f] hover:bg-[#204b76] text-white transition-colors"
                    >
                      Open Workspace <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  ) : (
                    <span className="text-xs font-medium text-[#657582] group-hover:text-[#163a5f]">
                      Click to inspect
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Mobile Horizontal Card Touch Sequence */}
        <div className="sm:hidden w-full">
          <div className="p-5 rounded border border-[#b8c4c2] bg-[#fffefa] shadow-sm">
            {/* Header Accent */}
            <div className="flex items-center justify-between border-b border-[#e6eae6] pb-3 mb-3">
              <span className="font-mono text-xs text-[#4c5b67] font-semibold">
                {selectedItem.external_reference || `Case #${selectedIndex + 1}`}
              </span>
              <StatusBadge status={selectedItem.status} size="sm" />
            </div>

            {/* TITLE First */}
            <h3 className="text-lg font-medium text-[#162333] leading-snug">
              {selectedItem.title}
            </h3>

            {/* CONTEXT Second */}
            <p className="mt-2 text-xs text-[#4e5d6a] font-medium">
              {selectedItem.organization}
            </p>

            {/* Footer & CTA */}
            <div className="mt-5 pt-3 border-t border-[#edf0ee] flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs text-[#5f6e7a]">
                <Users className="w-3.5 h-3.5 text-[#798895]" aria-hidden="true" />
                <span>
                  <strong className="font-mono text-[#162333]">{selectedItem.bidder_count ?? 0}</strong> Bidders
                </span>
              </div>

              <Link
                href={`/procurements/${selectedProcurementId}`}
                className="focus-ring inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-[#163a5f] text-white"
              >
                Open Workspace <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Control Toolbar: Navigation Controls & Indicator Dots */}
      <div className="flex items-center justify-between pt-2 px-1">
        {/* Step Indicator */}
        <div className="flex items-center gap-1.5">
          {procurements.map((_, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setSelectedIndex(idx)}
              className={`h-2 rounded-full transition-all duration-200 cursor-pointer ${
                idx === selectedIndex ? "w-6 bg-[#163a5f]" : "w-2 bg-[#d1d7d6] hover:bg-[#a3b1b0]"
              }`}
              aria-label={`Go to procurement item ${idx + 1}`}
            />
          ))}
          <span className="ml-2 text-xs font-mono text-[#6e7e8a]">
            {selectedIndex + 1} / {procurements.length}
          </span>
        </div>

        {/* Navigation Buttons */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handlePrev}
            disabled={selectedIndex === 0}
            className="focus-ring p-2 rounded border border-[#d2d8d7] bg-[#fffefa] text-[#2c3f4e] hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
            aria-label="Previous procurement"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={handleNext}
            disabled={selectedIndex === procurements.length - 1}
            className="focus-ring p-2 rounded border border-[#d2d8d7] bg-[#fffefa] text-[#2c3f4e] hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
            aria-label="Next procurement"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
