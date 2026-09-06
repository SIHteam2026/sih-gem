"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight, Server, Clock, User, ArrowRight } from "lucide-react";
import { ProcurementSummaryItem } from "@/types/procurement";

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

  // Fallback demo items if backend has no records yet
  const defaultItems = [
    {
      id: "PROC-GEM-001",
      title: "Cloud Infrastructure",
      subtitle: "Tier-1 Cluster",
      organization: "Amazon Web Services • PO-89241",
      amount: "$420,000",
      commitment: "Q3 Annual Commitment",
      statusText: "Approved",
      dispatched: "Dispatched 2h ago",
      requester: "Req: DevOps Lead",
    },
    {
      id: "PROC-GEM-002",
      title: "Enterprise Storage Suite",
      subtitle: "High-Density SAN",
      organization: "Dell Technologies • PO-89218",
      amount: "$280,000",
      commitment: "Q3 Project Allocation",
      statusText: "Under Review",
      dispatched: "Dispatched 5h ago",
      requester: "Req: Infrastructure Lead",
    },
  ];

  const displayList =
    procurements && procurements.length > 0
      ? procurements.map((p, i) => ({
          id: p.id || p.procurement_id || `PROC-${i}`,
          title: p.title || "Procurement Case",
          subtitle: p.category || (p.tender_count ? `${p.tender_count} Tender Requirements` : "Standard Procurement"),
          organization: p.organization ? `${p.organization} • ${p.external_reference || `PO-${1000 + i}`}` : p.external_reference || "Government Authority",
          amount: p.estimated_value ? `₹${p.estimated_value}` : "$420,000",
          commitment: "Annual Contract",
          statusText: p.status === "ACTIVE" || p.status === "READY" ? "Approved" : "Under Review",
          dispatched: "Updated recently",
          requester: `Bidders: ${p.bidder_count ?? 1}`,
        }))
      : defaultItems;

  const currentItem = displayList[selectedIndex] || displayList[0];

  const handlePrev = () => {
    setSelectedIndex((prev) => (prev > 0 ? prev - 1 : displayList.length - 1));
  };

  const handleNext = () => {
    setSelectedIndex((prev) => (prev < displayList.length - 1 ? prev + 1 : 0));
  };

  return (
    <div className={`w-full space-y-3.5 select-none ${className}`}>
      {/* Header with Title and Nav Controls */}
      <div className="flex items-center justify-between max-w-[460px]">
        <h3 className="text-sm font-bold tracking-tight text-[#111827]">
          Your Recent Procurements
        </h3>

        {/* Carousel Prev/Next Buttons */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handlePrev}
            className="focus-ring h-6 w-6 rounded-full bg-[#f3f4f6] hover:bg-[#e5e7eb] flex items-center justify-center text-[#4b5563] transition-colors"
            aria-label="Previous case"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={handleNext}
            className="focus-ring h-6 w-6 rounded-full bg-[#f3f4f6] hover:bg-[#e5e7eb] flex items-center justify-center text-[#4b5563] transition-colors"
            aria-label="Next case"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Cards Area + Opal Workspace Button Side-by-Side Layout */}
      <div className="flex flex-wrap lg:flex-nowrap items-center gap-4 sm:gap-6">
        {/* Stacked Procurement Cards Container */}
        <div className="relative w-full max-w-[380px] h-[160px]">
          {/* Background Layer Card (Partial Stacked Effect) */}
          <div
            className="absolute inset-0 translate-x-3 translate-y-2 rounded-2xl border border-[#e5e7eb] bg-[#f9fafb] opacity-80 pointer-events-none"
            aria-hidden="true"
          />

          {/* Foreground Primary Active Card */}
          <div
            onClick={() => router.push(`/procurements/${currentItem.id}`)}
            className="absolute inset-0 rounded-2xl border border-[#e5e7eb] bg-white p-4 sm:p-4.5 shadow-[0_2px_12px_rgba(0,0,0,0.03)] cursor-pointer hover:border-[#cbd5e1] transition-all flex flex-col justify-between"
          >
            {/* Top Row: Icon + Title/Status + Amount */}
            <div className="flex items-start justify-between gap-2.5">
              <div className="flex items-start gap-2.5 min-w-0">
                <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[#f3f4f6] text-[#111827]">
                  <Server className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-xs sm:text-sm font-bold text-[#111827]">
                      {currentItem.title}
                    </p>
                    <span className="shrink-0 rounded-md bg-[#ecfdf5] px-1.5 py-0.5 text-[10px] font-semibold text-[#059669]">
                      {currentItem.statusText}
                    </span>
                  </div>
                  <p className="text-xs font-semibold text-[#111827]">
                    {currentItem.subtitle}
                  </p>
                  <p className="truncate text-[11px] text-[#6b7280]">
                    {currentItem.organization}
                  </p>
                </div>
              </div>

              {/* Amount on Right */}
              <div className="text-right shrink-0">
                <p className="text-xs sm:text-sm font-bold text-[#111827]">
                  {currentItem.amount}
                </p>
                <p className="text-[10px] text-[#6b7280]">
                  {currentItem.commitment}
                </p>
              </div>
            </div>

            {/* Bottom Row: Metadata & Details Link */}
            <div className="flex items-center justify-between border-t border-[#f3f4f6] pt-2.5 text-[11px] text-[#9ca3af]">
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  <span>{currentItem.dispatched}</span>
                </span>
                <span className="flex items-center gap-1">
                  <User className="h-3 w-3" />
                  <span>{currentItem.requester}</span>
                </span>
              </div>

              <span className="text-xs font-semibold text-[#2563eb] hover:underline flex items-center gap-0.5">
                Details →
              </span>
            </div>
          </div>
        </div>

        {/* Quiet Opal Workspace Invitation Button */}
        <div className="shrink-0 pl-1">
          <Link
            href="/procurements"
            className="focus-ring group inline-flex items-center gap-2 rounded-full border border-[#e5e7eb] bg-white px-5 py-2.5 text-xs font-semibold text-[#111827] shadow-xs transition-all hover:bg-[#f9fafb] hover:border-[#d1d5db]"
          >
            <span>Opal Workspace</span>
            <ArrowRight className="h-3.5 w-3.5 text-[#111827] transition-transform group-hover:translate-x-1" />
          </Link>
        </div>
      </div>
    </div>
  );
}
