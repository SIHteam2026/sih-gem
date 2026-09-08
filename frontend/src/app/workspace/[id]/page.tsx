"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { FileText, ArrowLeft } from "lucide-react";
import Navbar from "@/components/Navbar";
import { fetchProcurementDetail } from "@/services/api";
import { ProcurementDetail, SubmissionSummary } from "@/types/procurement";

/**
 * WorkspaceDetailPage
 *
 * Premium high-fidelity project detail view matching the Opal reference design.
 * Reads procurement ID from URL, loads data via existing fetchProcurementDetail API,
 * renders deadline logic, bidder submissions list, and action panel.
 *
 * No backend or schema changes — pure presentation layer.
 */
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

  // Derive all bidder submissions from nested tenders
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

  // Derive deadline from tender created_at — use first tender if available
  const firstTender = procurement?.tenders?.[0];
  const deadlineDate = firstTender?.created_at
    ? new Date(firstTender.created_at)
    : null;
  const isDeadlinePast = deadlineDate ? deadlineDate < new Date() : false;
  const formattedDeadline = deadlineDate
    ? deadlineDate.toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : null;

  // Description from first tender if available
  const description =
    firstTender?.description ||
    "This procurement workspace contains bid compliance verification records from GeM. Evidence is extracted, requirements are matched, and findings are prepared for officer review.";

  return (
    <div className="min-h-screen bg-white font-sans">
      <Navbar />

      <main className="max-w-[1000px] mx-auto px-6 pt-10 pb-16">

        {/* Back link */}
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-600 mb-8 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Workspace
        </Link>

        {loading && (
          <div className="text-sm text-slate-400 py-12 text-center">
            Loading project workspace…
          </div>
        )}

        {error && (
          <div className="text-sm text-red-500 py-12 text-center">{error}</div>
        )}

        {!loading && !error && procurement && (
          <>
            {/* ── TOP SECTION ─────────────────────────────────────────────── */}
            <div className="flex items-start justify-between gap-4 mb-1">
              {/* Title */}
              <h1 className="font-manrope font-bold text-[#111827] text-[28px] leading-tight tracking-tight max-w-[600px]">
                {procurement.title}
              </h1>

              {/* Tender pill tag */}
              <div className="shrink-0 flex items-center gap-1.5 bg-yellow-100 border border-yellow-200 text-yellow-800 font-sans text-[13px] font-medium px-3 py-1 rounded-full mt-1">
                <FileText className="w-3.5 h-3.5 text-yellow-600" />
                Tender
              </div>
            </div>

            {/* Description paragraph */}
            <p className="font-sans text-[14px] text-[#4b5563] leading-relaxed mt-4 max-w-[620px]">
              {description}
            </p>

            {/* Metadata line */}
            <div className="mt-5 font-serif text-slate-400 text-[13.5px] space-y-[3px]">
              <p className="italic">{procurement.organization}</p>
              <p>
                Tender date:{" "}
                {new Date(procurement.created_at || Date.now()).toLocaleDateString("en-GB", {
                  day: "2-digit",
                  month: "2-digit",
                  year: "numeric",
                }).replace(/\//g, ".")}
              </p>
            </div>

            {/* Divider */}
            <hr className="border-[#f1f5f9] mt-7 mb-8" />

            {/* ── LOWER TWO-COLUMN SECTION ─────────────────────────────────── */}
            <div className="flex flex-col md:flex-row gap-10 items-start">

              {/* LEFT PANEL — Deadline + Officer action */}
              <div className="flex flex-col gap-5 min-w-[220px]">

                {/* Deadline indicator */}
                {formattedDeadline ? (
                  <div>
                    <p className="font-manrope text-[14px] text-[#374151]">
                      Bidder Submission deadline was
                    </p>
                    <p
                      className={`font-manrope font-bold text-[16px] mt-0.5 ${
                        isDeadlinePast ? "text-red-600" : "text-[#16a34a]"
                      }`}
                    >
                      {formattedDeadline}
                    </p>
                  </div>
                ) : (
                  <p className="font-manrope text-[14px] text-slate-400">
                    No deadline recorded.
                  </p>
                )}

                {/* Situational greeting box */}
                <div>
                  <p className="font-sans text-[13.5px] text-[#374151] leading-snug mb-4">
                    Sir, you are clear for the Technical Scrutiny of all the submitted bidders!
                  </p>
                  <Link
                    href={`/procurements/${procurement.id}`}
                    className="inline-flex items-center gap-2 bg-[#4ade80] hover:bg-[#22c55e] text-white font-manrope font-bold text-[12px] tracking-wide uppercase px-4 py-2 rounded-md transition-colors"
                  >
                    Technical Scrutiny
                  </Link>
                </div>
              </div>

              {/* RIGHT PANEL — Bidder Submissions container */}
              <div className="flex-1 bg-yellow-50/60 rounded-xl p-6">
                <h2 className="font-manrope font-semibold text-[#111827] text-[15px] mb-4">
                  Bidder Submissions
                </h2>

                {allSubmissions.length === 0 ? (
                  <p className="font-sans text-[13px] text-slate-400">
                    No bidder submissions registered yet.
                  </p>
                ) : (
                  <ul className="divide-y divide-yellow-100">
                    {allSubmissions.map((sub) => (
                      <li
                        key={sub.id}
                        className="flex items-center justify-between py-3"
                      >
                        <span className="font-manrope text-[14px] text-[#111827]">
                          {sub.bidder?.legal_name || "Unknown Bidder"}
                        </span>
                        <Link
                          href={`/submissions/${sub.id}`}
                          className="shrink-0 ml-4 text-orange-400 hover:text-orange-600 transition-colors"
                          aria-label={`Open submission file for ${sub.bidder?.legal_name || sub.id}`}
                        >
                          <FileText className="w-5 h-5" />
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
