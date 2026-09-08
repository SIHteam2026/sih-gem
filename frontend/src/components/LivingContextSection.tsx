"use client";

import React, { useEffect, useState, useCallback } from "react";
import { List } from lucide-react;
import { fetchProcurements } from @/services/api;
import { ProcurementSummaryItem, ProcurementListResponse } from "@/types/procurement";

// Dynamic insights logic based on Supabase procurements
function getDynamicInsights(procurements: ProcurementSummaryItem[]): string {
  if (!procurements || procurements.length === 0) return No active projects at the moment.;
  
  const newCount = procurements.filter(p => {
    const s = (p.status || ").toUpperCase();
 return s === NEW || s === IMPORTED || s === PROCESSING;
 }).length;
 
 if (newCount > 0) {
 return Most of the projects are under your evaluation. Though, we've a new high-stake project here.;
 }
 return All projects are actively processing or ready for review.;
}

export default function LivingContextSection({
 className = ",
}: {
  className?: string;
}) {
  const [procurements, setProcurements] = useState<ProcurementSummaryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const response = (await fetchProcurements(10, 0)) as ProcurementListResponse;
      setProcurements(response?.procurements || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const dynamicInsight = getDynamicInsights(procurements);

  // Time based greeting
  const hour = new Date().getHours();
  let greeting = Welcome again Sir!;
  if (hour < 12) greeting = Good morning Sir!;
  else if (hour >= 17 && hour < 21) greeting = Good evening Sir!;
  else if (hour >= 21) greeting = Good night Sir!;

  return (
    <div className={w-full max-w-[1000px] flex flex-col font-['Stack_Sans_Text',_sans-serif] tracking-tight }>
      {/* 2. Header & Structural Breakdown */}
      <h1 className=text-[40px] font-medium text-[#111827] leading-tight ml-[24px] mb-[24px]>
        Opal Workspace
      </h1>

      <div className=ml-[24px] flex flex-col gap-1>
        <p className=text-[20px] text-[#111827] font-normal>{greeting}</p>
        <p className=text-[15px] text-[#6b7280]>{dynamicInsight}</p>
      </div>

      <div className=mt-[64px] ml-[24px] flex items-center gap-[12px] mb-[32px]>
        <List className=w-[24px] h-[24px] text-[#10b981] />
        <h2 className=text-[22px] text-[#10b981] font-normal>Your Projects</h2>
      </div>

      <div className=grid grid-cols-1 md:grid-cols-2 gap-[24px] ml-[24px]>
        {loading ? (
          <div className=text-sm text-gray-500>Loading projects...</div>
        ) : (
          procurements.map((project) => {
            const statusStr = (project.status || New).toUpperCase();
            const badgeText = statusStr === READY ? Technical Bid Complete : statusStr;
            const badgeColor = statusStr === READY ? text-[#84cc16] border-[#84cc16]/40 bg-[#84cc16]/5 : text-[#84cc16] border-[#84cc16]/40 bg-white;
            
            return (
              <div 
                key={project.id} 
                className=bg-white/70 backdrop-blur-md border border-white/20 p-[24px] rounded-3xl shadow-[0_4px_24px_rgba(0,0,0,0.02)] flex flex-col justify-between min-h-[200px]
              >
                <div>
                  <h3 className=text-[20px] font-normal text-[#111827] mb-[16px] leading-snug line-clamp-3>{project.title}</h3>
                  <div className=flex items-center mb-[16px]>
                    <span className={px-[10px] py-[2px] border text-[11px] rounded-full font-medium }>
                      {badgeText}
                    </span>
                  </div>
                </div>
                <div className=mt-auto pt-[16px]>
                  <p className=text-[13px] text-[#9ca3af] font-medium truncate>{project.organization || Ministry of Health and Family Welfare}</p>
                  <p className=text-[12px] text-[#9ca3af] mt-[4px]>Tender date: {new Date(project.created_at || Date.now()).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' }).replace(/\//g, '.')}</p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
