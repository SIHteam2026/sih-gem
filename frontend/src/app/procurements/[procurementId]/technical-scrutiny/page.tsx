"use client";

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { fetchTechnicalReview } from '@/services/api/technical-review';
import { fetchProcurementDetail } from '@/services/api';
import { TechnicalScrutinyView } from '@/components/procurement/TechnicalScrutiny/TechnicalScrutinyView';
import type { TechnicalReviewResponse } from '@/types/technical-review';
import { AlertTriangle, RefreshCw } from 'lucide-react';

/**
 * Technical Scrutiny page.
 *
 * Loads the canonical technical review from the backend and renders the
 * full officer-facing scrutiny experience. State is driven entirely by
 * backend data — no frontend-only compliance state is created here.
 */
export default function TechnicalScrutinyPage() {
  const params = useParams();
  const id = params.procurementId as string;

  const [data, setData] = useState<TechnicalReviewResponse | null>(null);
  const [organization, setOrganization] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!id) return;

    async function loadData() {
      setIsLoading(true);
      setError(null);

      try {
        // Primary: load the canonical technical review
        const reviewData = await fetchTechnicalReview(id);
        setData(reviewData);

        // Supplementary: load procurement detail for organization context
        try {
          const pData = await fetchProcurementDetail(id);
          if (pData?.organization) {
            setOrganization(pData.organization);
          }
        } catch {
          // Non-fatal — organization will be omitted from header
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error
            ? err.message
            : 'Failed to load technical scrutiny data.';
        setError(message);
      } finally {
        setIsLoading(false);
      }
    }

    loadData();
  }, [id]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-slate-200 border-t-slate-600 rounded-full animate-spin mx-auto" />
          <p className="text-sm text-slate-500">Loading technical review…</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center px-8">
        <div className="max-w-md text-center space-y-4">
          <div className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center mx-auto">
            <AlertTriangle className="w-5 h-5 text-red-500" />
          </div>
          <h2 className="text-lg font-bold text-slate-800">Technical Review Unavailable</h2>
          <p className="text-sm text-slate-500 leading-relaxed">
            {error ||
              'The technical review could not be loaded. The procurement may not have completed scrutiny yet.'}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-full transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
          <p className="text-xs text-slate-400">
            Procurement ID: <code className="font-mono">{id}</code>
          </p>
        </div>
      </div>
    );
  }

  return (
    <TechnicalScrutinyView
      data={data}
      procurementOrganization={organization}
    />
  );
}
