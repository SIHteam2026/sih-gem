"use client";

import React, { useEffect, useState } from 'react';
import { fetchTechnicalReview } from '@/services/api/technical-review';
import { TechnicalScrutinyView } from '@/components/procurement/TechnicalScrutiny/TechnicalScrutinyView';
import type { TechnicalReviewResponse } from '@/types/technical-review';
import { useParams } from 'next/navigation';
// Using standard fetch for procurement info
import { fetchProcurementDetail } from '@/services/api';

export default function TechnicalScrutinyPage() {
  const params = useParams();
  const id = params.procurementId as string;
  
  const [data, setData] = useState<TechnicalReviewResponse | null>(null);
  const [projectName, setProjectName] = useState('Loading...');
  const [projectRef, setProjectRef] = useState('...');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const reviewData = await fetchTechnicalReview(id);
        setData(reviewData);

        try {
          // fetchProcurementDetail from actual services/api
          const pData = await fetchProcurementDetail(id);
          if (pData) {
            setProjectName(pData.title || pData.external_reference || 'Procurement Project');
            setProjectRef(pData.external_reference || id);
          }
        } catch (e) {
          setProjectName('Procurement Project');
          setProjectRef(id);
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to load technical scrutiny.';
        setError(message);
      } finally {
        setIsLoading(false);
      }
    }
    
    if (id) {
      loadData();
    }
  }, [id]);

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500">Loading procurement record...</div>;
  }

  if (error || !data) {
    return <div className="p-8 text-center text-red-500">Error: {error}</div>;
  }

  return <TechnicalScrutinyView data={data} projectName={projectName} projectRef={projectRef} />;
}
