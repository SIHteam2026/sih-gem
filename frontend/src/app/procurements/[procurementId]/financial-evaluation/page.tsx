"use client";

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { fetchProcurementDetail } from '@/services/api';
import { getFinancialReview } from '@/services/api/financial';
import type { ProcurementFinancialEvaluationResponse } from '@/types/financial';
import { FinancialScrutinyView } from '@/components/procurement/FinancialScrutiny/FinancialScrutinyView';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default function FinancialEvaluationPage() {
  const params = useParams();
  const id = params.procurementId as string;
  const router = useRouter();

  const [data, setData] = useState<ProcurementFinancialEvaluationResponse | null>(null);
  const [procurementTitle, setProcurementTitle] = useState<string>('');
  const [organization, setOrganization] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const reviewData = await getFinancialReview(id);
      setData(reviewData);

      try {
        const pData = await fetchProcurementDetail(id);
        if (pData?.title) setProcurementTitle(pData.title);
        if (pData?.organization) setOrganization(pData.organization);
      } catch {
        // Non-fatal
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load financial scrutiny data.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (id) loadData();
  }, [id]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-slate-200 border-t-slate-600 rounded-full animate-spin mx-auto" />
          <p className="text-sm text-slate-500">Loading financial review…</p>
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
          <h2 className="text-lg font-bold text-slate-800">Financial Review Unavailable</h2>
          <p className="text-sm text-slate-500 leading-relaxed">
            {error || 'The financial review could not be loaded.'}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-full transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
          <div className="pt-4">
            <button
              onClick={() => router.push(`/procurements/${id}/technical-scrutiny`)}
              className="text-sm text-slate-500 hover:text-slate-800 underline"
            >
              Return to Technical Scrutiny
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <FinancialScrutinyView
      data={data}
      procurementTitle={procurementTitle || `Procurement ${id.slice(0, 8)}`}
      procurementOrganization={organization}
      onReloadRequested={loadData}
    />
  );
}
