"use client";

import React, { useEffect, useState, useCallback } from "react";
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
      const response = (await fetchProcurements(5, 0)) as ProcurementListResponse;
      setProcurements((response?.procurements || []).slice(0, 2));
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

  if (error) {
    return (
      <ErrorState
        title="Could not load recent procurements"
        message={error}
        onRetry={loadData}
        className={`mt-6 ${className}`}
      />
    );
  }

  if (loading) {
    return <LoadingState message="Loading procurement cases…" className={`mt-6 min-h-[220px] ${className}`} />;
  }

  return (
    <div className={`mt-8 sm:mt-10 ${className}`}>
      <ProcurementCarousel procurements={procurements} />
    </div>
  );
}
