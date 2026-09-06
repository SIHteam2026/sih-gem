"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight, Users, FileText, ArrowUpRight } from "lucide-react";
import { ProcurementSummaryItem } from "@/types/procurement";
import StatusBadge from "./StatusBadge";
import SourceBadge from "./SourceBadge";

interface ProcurementCarouselProps {
  procurements: ProcurementSummaryItem[];
  className?: string;
}

export default function ProcurementCarousel({
  procurements = [],
  className = "",
}: ProcurementCarouselProps) {
  const router = useRouter();
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
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      const item = procurements[selectedIndex];
      if (item) {
        const id = item.id || item.procurement_id;
        router.push(`/procurements/${id}`);
      }
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
      <div className={`rounded border border-dashed border-[#cbd2d1] bg-[#fffefa]/90 p-6 text-center ${className}`}>
        <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-[#f0f3f1] text-[#556977]">
          <FileText className="h-4 w-4" aria-hidden="true" />
        </div>
        <h4 className="text-sm font-semibold text-[#162333]">No procurements yet</h4>
        <p className="mx-auto mt-1 max-w-xs text-[11px] leading-relaxed text-[#65717b]">
          Cases appear here automatically upon ingestion.
        </p>
        <div className="mt-3">
          <Link
            href="/procurements"
            className="focus-ring inline-flex items-center gap-1.5 rounded bg-[#163a5f] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[#204b76]"
          >
            Open Workspace <ArrowUpRight className="h-3 w-3" />
          </Link>
        </div>
      </div>
    );
  }

  const selectedItem = procurements[selectedIndex] || procurements[0];
  const selectedProcurementId = selectedItem.id || selectedItem.procurement_id;
  const isSingleItem = procurements.length === 1;

  const handleCardClick = (idx: number, procurementId: string) => {
    if (idx === selectedIndex) {
      router.push(`/procurements/${procurementId}`);
    } else {
      setSelectedIndex(idx);
    }
  };

  return (
    <div
      ref={containerRef}
      className={`space-y-4 outline-none ${className}`}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
      aria-label="Recent procurements hero composition. Use left and right arrow keys to navigate, press Enter to open case."
    >
      {/* Subordinate Section Label */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-mono font-medium tracking-wider uppercase text-[#6e7d89]">
          Your Recent Procurements
        </h3>
        {!isSingleItem && (
          <span className="text-[11px] font-mono text-[#7b8994]">
            {selectedIndex + 1} / {procurements.length}
          </span>
        )}
      </div>

      {/* Hero Stacked Card Desk Composition Container */}
      <div className="relative min-h-[240px] sm:min-h-[250px]">
        {/* Desktop & Tablet Physical Document Stacked Desk Composition */}
        <div className="hidden sm:block relative w-full h-[240px]">
          {procurements.map((item, idx) => {
            const itemId = item.id || item.procurement_id;
            const isSelected = idx === selectedIndex;
            const offset = idx - selectedIndex;

            // Show adjacent items for realistic physical document layout
            if (Math.abs(offset) > 2) return null;

            let style: React.CSSProperties = {};
            let layerClasses = "";

            if (isSelected) {
              style = {
                zIndex: 30,
                transform: "translate3d(0, 0, 0) scale(1)",
                opacity: 1,
              };
              layerClasses =
                "border-[#b4c0be] shadow-[0_6px_20px_rgba(22,35,51,0.06)] bg-[#fffefa] cursor-pointer hover:border-[#163a5f]";
            } else if (offset > 0) {
              // Right receding physical documents
              const shiftX = Math.min(offset * 22 + 18, 65);
              const scale = 1 - offset * 0.04;
              const opacity = 1 - offset * 0.3;
              style = {
                zIndex: 30 - offset,
                transform: `translate3d(${shiftX}px, ${offset * 5}px, 0) scale(${scale})`,
                opacity: Math.max(opacity, 0.45),
              };
              layerClasses =
                "border-[#d7deda] bg-[#fbfbf9] cursor-pointer hover:border-[#9cb0ae]";
            } else {
              // Left receding physical documents
              const shiftX = Math.max(offset * 22 - 18, -65);
              const scale = 1 - Math.abs(offset) * 0.04;
              const opacity = 1 - Math.abs(offset) * 0.3;
              style = {
                zIndex: 30 - Math.abs(offset),
                transform: `translate3d(${shiftX}px, ${Math.abs(offset) * 5}px, 0) scale(${scale})`,
                opacity: Math.max(opacity, 0.45),
              };
              layerClasses =
                "border-[#d7deda] bg-[#fbfbf9] cursor-pointer hover:border-[#9cb0ae]";
            }

            return (
              <div
                key={itemId || idx}
                onClick={() => handleCardClick(idx, itemId)}
                style={style}
                className={`absolute top-0 left-0 right-0 p-5 rounded border transition-all duration-250 ease-out select-none ${layerClasses}`}
              >
                {/* Physical Document Header */}
                <div className="flex items-center justify-between border-b border-[#e8ece8] pb-2.5 mb-3">
                  <div className="flex items-center gap-2">
                    {item.external_reference && (
                      <span className="font-mono text-[11px] text-[#4a5a67] font-semibold">
                        {item.external_reference}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <SourceBadge source={item.source_system} />
                    <StatusBadge status={item.status} size="sm" />
                  </div>
                </div>

                {/* Information Hierarchy */}
                {/* 1. TITLE First */}
                <h4 className="text-base sm:text-lg font-medium tracking-tight text-[#162333] leading-snug line-clamp-2">
                  {item.title}
                </h4>

                {/* 2. CONTEXT Second */}
                <p className="mt-1.5 text-xs text-[#526270] font-medium line-clamp-1">
                  {item.organization}
                </p>

                {/* Document / Bidder Count Context Footer */}
                <div className="mt-4 pt-3 border-t border-[#edf0ee] flex items-center justify-between">
                  <div className="flex items-center gap-4 text-[11px] text-[#61717e]">
                    <div className="flex items-center gap-1.5" title="Bidder submissions count">
                      <Users className="w-3.5 h-3.5 text-[#798895]" aria-hidden="true" />
                      <span>
                        <strong className="font-mono font-semibold text-[#162333]">
                          {item.bidder_count ?? 0}
                        </strong>{" "}
                        {item.bidder_count === 1 ? "Bidder" : "Bidders"}
                      </span>
                    </div>
                    {item.tender_count !== undefined && item.tender_count > 0 && (
                      <div className="flex items-center gap-1.5" title="Tender count">
                        <FileText className="w-3.5 h-3.5 text-[#798895]" aria-hidden="true" />
                        <span>
                          <strong className="font-mono font-semibold text-[#162333]">
                            {item.tender_count}
                          </strong>{" "}
                          Tender
                        </span>
                      </div>
                    )}
                  </div>

                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#163a5f] group-hover:underline">
                    {isSelected ? "Open Case →" : "Inspect"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Mobile Horizontal Touch Card Sequence */}
        <div className="sm:hidden w-full">
          <div
            onClick={() => router.push(`/procurements/${selectedProcurementId}`)}
            className="p-4 rounded border border-[#b4c0be] bg-[#fffefa] shadow-sm cursor-pointer active:bg-[#f4f7f6]"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-[#e6eae6] pb-2 mb-2">
              <span className="font-mono text-[11px] text-[#4c5b67] font-semibold">
                {selectedItem.external_reference || `Case #${selectedIndex + 1}`}
              </span>
              <StatusBadge status={selectedItem.status} size="sm" />
            </div>

            {/* TITLE First */}
            <h4 className="text-base font-medium text-[#162333] leading-snug">
              {selectedItem.title}
            </h4>

            {/* CONTEXT Second */}
            <p className="mt-1 text-xs text-[#526270] font-medium">
              {selectedItem.organization}
            </p>

            {/* Footer */}
            <div className="mt-4 pt-2.5 border-t border-[#edf0ee] flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs text-[#5f6e7a]">
                <Users className="w-3.5 h-3.5 text-[#798895]" aria-hidden="true" />
                <span>
                  <strong className="font-mono text-[#162333]">
                    {selectedItem.bidder_count ?? 0}
                  </strong>{" "}
                  Bidders
                </span>
              </div>

              <span className="text-xs font-semibold text-[#163a5f]">Open Case →</span>
            </div>
          </div>
        </div>
      </div>

      {/* Carousel Controls (only shown when multiple items exist) */}
      {!isSingleItem && (
        <div className="flex items-center justify-between pt-1">
          {/* Indicator Dots */}
          <div className="flex items-center gap-1.5">
            {procurements.map((_, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setSelectedIndex(idx)}
                className={`h-1.5 rounded-full transition-all duration-200 cursor-pointer ${
                  idx === selectedIndex ? "w-5 bg-[#163a5f]" : "w-1.5 bg-[#d1d7d6] hover:bg-[#9cb0ae]"
                }`}
                aria-label={`Go to procurement ${idx + 1}`}
              />
            ))}
          </div>

          {/* Nav Buttons */}
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handlePrev}
              disabled={selectedIndex === 0}
              className="focus-ring p-1.5 rounded border border-[#d2d8d7] bg-[#fffefa] text-[#2c3f4e] hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
              aria-label="Previous procurement"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={handleNext}
              disabled={selectedIndex === procurements.length - 1}
              className="focus-ring p-1.5 rounded border border-[#d2d8d7] bg-[#fffefa] text-[#2c3f4e] hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
              aria-label="Next procurement"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
