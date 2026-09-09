"use client";

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { fetchProcurementDetail } from '@/services/api';
import { ActionStudioView } from '@/components/procurement/ActionStudio/ActionStudioView';

export default function ActionStudioPage() {
  const params = useParams();
  const id = params.procurementId as string;

  const [procurementTitle, setProcurementTitle] = useState<string>('');
  const [organization, setOrganization] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (id) {
      fetchProcurementDetail(id)
        .then((pData) => {
          if (pData?.title) setProcurementTitle(pData.title);
          if (pData?.organization) setOrganization(pData.organization);
        })
        .catch(() => {
          // Non-fatal, ActionStudioView has internal context fallbacks
        });
    }
  }, [id]);

  return (
    <ActionStudioView
      procurementId={id}
      procurementTitle={procurementTitle}
      procurementOrganization={organization}
    />
  );
}
