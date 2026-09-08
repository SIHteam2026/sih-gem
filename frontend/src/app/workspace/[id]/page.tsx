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

  // Deadline from first tender created_at as proxy
  const firstTender = procurement?.tenders?.[0];
  const deadlineDate = firstTender?.created_at ? new Date(firstTender.created_at) : null;
  const isDeadlinePast = deadlineDate ? deadlineDate < new Date() : false;
  const formattedDeadline = deadlineDate
    ? deadlineDate.toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : null;

  const description =
    firstTender?.description ||
    "This procurement workspace contains bid compliance verification records from GeM. Evidence is extracted, requirements are matched, and findings are prepared for officer review.";

  const tenderDateStr = procurement
    ? new Date(procurement.created_at || Date.now())
        .toLocaleDateString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric" })
        .replace(/\//g, ".")
    : "";

  return (
    <div className="min-h-screen bg-white font-['Stack_Sans_Text',_sans-serif]">
      <Navbar />

      <main className="w-full max-w-[1000px] mx-auto pt-10 pb-16">

        {/* Back link — same left margin as dashboard title */}
        <div className="ml-[24px] mb-8">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-[13px] text-[#9ca3af] hover:text-[#6b7280] transition-colors tracking-tight"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Workspace
          </Link>
        </div>

        {loading && (
          <p className="ml-[24px] text-[14px] text-[#9ca3af]">Loading project workspace…</p>
        )}
        {error && (
          <p className="ml-[24px] text-[14px] text-red-500">{error}</p>
        )}

        {!loading && !error && procurement && (
          <>
            {/* ── PROJECT TITLE ── same size/weight/margin as "Opal Workspace" */}
            <h1 className="text-[40px] font-medium text-[#111827] leading-tight ml-[24px] mb-[20px] tracking-tight max-w-[680px]">
              {procurement.title}
            </h1>

            {/* ── AI SUMMARY DESCRIPTION ── lighter color, same left margin */}
            <p className="ml-[24px] text-[15px] text-[#9ca3af] leading-relaxed max-w-[620px] mb-[20px]">
              {description}
            </p>

            {/* ── METADATA + TENDER PILL ROW ── */}
            {/* Ministry + Tender date left-aligned; Tender pill far right */}
            <div className="ml-[24px] flex items-end justify-between pr-0 mb-0">
              {/* Left: ministry + tender date */}
              <div className="flex flex-col gap-[3px]">
                <p className="text-[14px] text-[#6b7280] font-normal">
                  {procurement.organization}
                </p>
                <p className="text-[13px] text-[#9ca3af]">
                  Tender date: {tenderDateStr}
                </p>
              </div>

              {/* Right: Tender pill — vertically centered with the two metadata lines */}
              <div className="flex items-center gap-1.5 bg-yellow-100 border border-yellow-200 text-yellow-800 text-[13px] font-medium px-3 py-1 rounded-full shrink-0">
                <FileText className="w-3.5 h-3.5 text-yellow-600" />
                Tender
              </div>
            </div>

            {/* ── HORIZONTAL DIVIDER ── */}
            <hr className="border-[#f1f5f9] mt-5 mb-8 ml-[24px]" />

            {/* ── LOWER TWO-COLUMN SECTION ── */}
            <div className="ml-[24px] flex flex-col md:flex-row gap-10 items-start">

              {/* LEFT PANEL — Deadline + Officer action */}
              <div className="flex flex-col gap-5 min-w-[220px]">

                {/* Deadline string */}
                {formattedDeadline ? (
                  <div>
                    <p className="text-[14px] text-[#374151]">
                      Bidder Submission deadline was
                    </p>
                    <p
                      className={`font-semibold text-[16px] mt-0.5 ${
                        isDeadlinePast ? "text-red-600" : "text-[#374151]"
                      }`}
                    >
                      {formattedDeadline}
                    </p>
                  </div>
                ) : (
                  <p className="text-[14px] text-[#9ca3af]">No deadline recorded.</p>
                )}

                {/* Situational message */}
                <p className="text-[13.5px] text-[#374151] leading-snug max-w-[220px]">
                  {isDeadlinePast
                    ? "Sir, you are clear for the Technical Scrutiny of all the submitted bidders!"
                    : "Sir, the submission deadline has not yet passed. Technical scrutiny is not yet available."}
                </p>

                {/* Technical Scrutiny button — green if deadline past, gray if not */}
                {isDeadlinePast ? (
                  <Link
                    href={`/procurements/${procurement.id}`}
                    className="inline-flex items-center justify-center font-semibold text-[12px] tracking-wide uppercase text-white px-4 py-2 rounded-md transition-colors"
                    style={{ backgroundColor: "#61BF03" }}
                  >
                    Technical Scrutiny
                  </Link>
                ) : (
                  <span
                    aria-disabled="true"
                    title="Deadline has not passed yet"
                    className="inline-flex items-center justify-center font-semibold text-[12px] tracking-wide uppercase text-white px-4 py-2 rounded-md cursor-not-allowed select-none"
                    style={{ backgroundColor: "#d1d5db" }}
                  >
                    Technical Scrutiny
                  </span>
                )}
              </div>

              {/* RIGHT PANEL — Bidder Submissions */}
              <div className="flex-1 bg-yellow-50/60 rounded-xl p-6">
                <h2 className="font-semibold text-[#111827] text-[15px] mb-4">
                  Bidder Submissions
                </h2>

                {allSubmissions.length === 0 ? (
                  <p className="text-[13px] text-[#9ca3af]">
                    No bidder submissions registered yet.
                  </p>
                ) : (
                  <ul className="divide-y divide-yellow-100">
                    {allSubmissions.map((sub) => (
                      <li
                        key={sub.id}
                        className="flex items-center justify-between py-3"
                      >
                        <span className="text-[14px] text-[#111827]">
                          {sub.bidder?.legal_name || "Unknown Bidder"}
                        </span>
                        <Link
                          href={`/submissions/${sub.id}`}
                          className="shrink-0 ml-4 text-orange-400 hover:text-orange-500 transition-colors"
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
          </>
        )}
      </main>
    </div>
  );
}
