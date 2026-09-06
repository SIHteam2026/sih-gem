"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { fetchProcurements } from "@/services/api";
import { ProcurementSummaryItem, ProcurementListResponse } from "@/types/procurement";
import ProcurementCarousel from "./ProcurementCarousel";
import { LoadingState, ErrorState } from "./States";

interface RecentProcurementsSectionProps {
  className?: string;
}

export default function RecentProcurementsSection({ className = "" }: RecentProcurementsSectionProps) {
  const [procurements, setProcurements] = useState<ProcurementSummaryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = (await fetchProcurements(10, 0)) as ProcurementListResponse;
      setProcurements(response?.procurements || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load recent procurements.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return (
    <section className={`mt-16 sm:mt-24 border-t border-[#d9ddd9] pt-12 ${className}`}>
      {/* Section Header with Opal Workspace Action */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
        <div>
          <p className="eyebrow">Active Cases</p>
          <h2 className="mt-1 text-2xl sm:text-3xl font-medium tracking-tight text-[#162333]">
            Your Recent Procurements
          </h2>
        </div>

        {/* Opal Workspace Action (Single canonical CTA link adjacent to recent procurements) */}
        <div>
          <Link
            href="/procurements"
            className="focus-ring inline-flex items-center gap-2 px-4 py-2.5 text-xs font-semibold rounded bg-[#163a5f] text-white hover:bg-[#204b76] transition-colors"
          >
            <span>Opal Workspace</span>
            <ArrowUpRight className="w-3.5 h-3.5" aria-hidden="true" />
          </Link>
        </div>
      </div>

      {/* Main Content Area */}
      {error ? (
        <ErrorState
          title="Could not load recent procurements"
          message={error}
          onRetry={loadData}
          className="my-4"
        />
      ) : loading ? (
        <LoadingState message="Loading recent procurement cases…" className="my-4 min-h-[300px]" />
      ) : (
        <ProcurementCarousel procurements={procurements} workspaceHref="/procurements" />
      )}
    </section>
  );
}
