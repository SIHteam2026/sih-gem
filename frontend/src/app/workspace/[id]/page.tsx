"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { FileText, ArrowLeft } from "lucide-react";
import Navbar from "@/components/Navbar";
import { fetchProcurementDetail } from "@/services/api";
import { ProcurementDetail, SubmissionSummary } from "@/types/procurement";

export default function WorkspaceDetailPage() {
  const params = useParams();
  const id = typeof params?.id === "string" ? params.id : "";

  const [procurement, setProcurement] = useState<ProcurementDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = (await fetchProcurementDetail(id)) as ProcurementDetail;
      if (!data?.id) {
        setError("Project not found.");
      } else {
        setProcurement(data);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load project workspace.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Collect all bidder submissions from nested tenders
  const allSubmissions: SubmissionSummary[] = [];
  if (procurement?.tenders) {
    for (const tender of procurement.tenders) {
      if (tender.submissions) {
        for (const sub of tender.submissions) {
          allSubmissions.push(sub);
        }
      }
    }
  }

  // Deadline from first tender
  const firstTender = procurement?.tenders?.[0];
  const submissionDeadline = firstTender?.submission_deadline ? new Date(firstTender.submission_deadline) : null;
  const demoDeadline = firstTender?.demo_effective_deadline ? new Date(firstTender.demo_effective_deadline) : null;
  
  // Use demo deadline if available for the lock condition, otherwise use real submission deadline
  const gateDeadline = demoDeadline || submissionDeadline;
  const isDeadlinePast = gateDeadline ? gateDeadline < new Date() : false;
  
  // Always display the true document deadline
  const formattedDeadline = submissionDeadline
    ? submissionDeadline.toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }) + " IST"
    : null;

  // Dynamic description summarizing requirements if available
  const requirementsList = firstTender?.requirements;
  let dynamicReqSummary = "";
  if (requirementsList && Array.isArray(requirementsList) && requirementsList.length > 0) {
    const summaryParts = requirementsList
      .map((r: any) => r.title || r.category)
      .filter(Boolean)
      .slice(0, 5);
    if (summaryParts.length > 0) {
      dynamicReqSummary = `Mandatory criteria: ${summaryParts.join(", ")}.`;
    }
  }

  const description =
    firstTender?.description ||
    (dynamicReqSummary
      ? `Turnkey procurement for ${firstTender?.title || procurement?.title || "this tender"}. ${dynamicReqSummary}`
      : "This procurement workspace contains bid compliance verification records from GeM. Evidence is extracted, requirements are matched, and findings are prepared for officer review.");

  const tenderDateStr = procurement
    ? new Date(procurement.created_at || Date.now())
        .toLocaleDateString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric" })
        .replace(/\//g, ".")
    : "";

  return (
    <div className="min-h-screen bg-white font-sans text-[#111827]">
      <Navbar />

      <main className="w-full max-w-[1100px] mx-auto pt-10 pb-16 px-6 md:px-12">
        {loading && (
          <div className="py-20 text-center text-sm text-slate-400">Loading project workspace…</div>
        )}
        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm">{error}</div>
        )}

        {!loading && !error && procurement && (
          <>
            {/* ── PROJECT TITLE ── */}
            <h1 className="text-3xl sm:text-4xl font-bold text-[#111827] leading-tight mb-4 tracking-tight max-w-3xl">
              {procurement.title}
            </h1>

            {/* ── AI SUMMARY DESCRIPTION ── */}
            <p className="text-sm sm:text-[15px] text-slate-500 leading-relaxed max-w-2xl mb-6">
              {description}
            </p>

            {/* ── METADATA + TENDER PILL ROW ── */}
            <div className="flex items-end justify-between pr-0 mb-0">
              {/* Left: ministry + tender date */}
              <div className="flex flex-col gap-0.5">
                <p className="text-sm text-[#374151] font-medium">
                  {procurement.organization}
                </p>
                <p className="text-xs text-slate-400 font-mono">
                  Tender date: {tenderDateStr}
                </p>
              </div>

              {/* Right: Tender pill */}
              <div className="flex items-center gap-1.5 bg-amber-50 border border-amber-200 text-amber-800 text-xs font-semibold px-3 py-1 rounded-full shrink-0 shadow-2xs">
                <FileText className="w-3.5 h-3.5 text-amber-600" />
                Tender
              </div>
            </div>

            {/* ── HORIZONTAL DIVIDER ── */}
            <hr className="border-slate-100 mt-6 mb-8" />

            {/* ── LOWER TWO-COLUMN SECTION ── */}
            <div className="flex flex-col md:flex-row gap-10 items-start justify-between">

              {/* LEFT PANEL — Deadline + Officer action */}
              <div className="flex flex-col gap-4 min-w-[240px]">

                {/* Deadline string */}
                {formattedDeadline ? (
                  <div>
                    <p className="text-sm text-slate-600">
                      Bidder Submission deadline was
                    </p>
                    <p
                      className={`font-bold text-base mt-0.5 ${
                        isDeadlinePast ? "text-rose-600" : "text-slate-800"
                      }`}
                    >
                      {formattedDeadline}
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="text-sm text-slate-600">Submission deadline</p>
                    <p className="font-semibold text-sm text-amber-700 mt-0.5">
                      Deadline unavailable. Scrutiny locked.
                    </p>
                  </div>
                )}

                {/* Situational message */}
                <p className="text-xs sm:text-sm text-slate-700 leading-snug max-w-[260px]">
                  {!formattedDeadline
                    ? "Sir, no valid submission deadline was found in the tender specification document. Technical scrutiny is locked."
                    : isDeadlinePast
                    ? "Sir, you are clear for the Technical Scrutiny of all the submitted bidders!"
                    : "Sir, the submission deadline has not yet passed. Technical scrutiny is not yet available."}
                </p>

                {/* Technical Scrutiny button */}
                {formattedDeadline && isDeadlinePast ? (
                  <Link
                    href={`/procurements/${procurement.id}`}
                    className="inline-flex items-center justify-center font-bold text-xs tracking-wider uppercase text-white px-5 py-2.5 rounded-xl transition-all shadow-xs hover:shadow-md hover:brightness-105 active:scale-[0.98] w-fit"
                    style={{ backgroundColor: "#16a34a" }}
                  >
                    Technical Scrutiny
                  </Link>
                ) : (
                  <span
                    aria-disabled="true"
                    title={!formattedDeadline ? "Deadline unavailable" : "Deadline has not passed yet"}
                    className="inline-flex items-center justify-center font-bold text-xs tracking-wider uppercase text-white px-5 py-2.5 rounded-xl cursor-not-allowed select-none w-fit bg-slate-300"
                  >
                    Technical Scrutiny
                  </span>
                )}
              </div>

              {/* RIGHT PANEL — Bidder Submissions */}
              <div className="w-full max-w-sm flex flex-col">
                <h2 className="font-bold text-slate-900 text-sm mb-3 md:text-right">
                  Bidder Submissions
                </h2>
                
                <div className="bg-amber-50/70 border border-amber-100/90 rounded-2xl p-5 w-full shadow-xs">
                  {allSubmissions.length === 0 ? (
                    <p className="text-xs text-slate-400">
                      No bidder submissions registered yet.
                    </p>
                  ) : (
                    <ul className="divide-y divide-amber-100/80">
                      {allSubmissions.map((sub) => (
                        <li
                          key={sub.id}
                          className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
                        >
                          <span className="text-sm font-medium text-slate-900">
                            {sub.bidder?.legal_name || "Unknown Bidder"}
                          </span>
                          <Link
                            href={`/submissions/${sub.id}`}
                            className="shrink-0 ml-4 text-amber-500 hover:text-amber-600 transition-colors p-1"
                            aria-label={`Open submission for ${sub.bidder?.legal_name || sub.id}`}
                          >
                            <FileText className="w-5 h-5" />
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>

            </div>
          </>
        )}
      </main>
    </div>
  );
}
