"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  FileSpreadsheet,
  Users,
  ArrowRight,
  FileText,
  Building,
  CheckCircle2,
  Calendar,
  Layers,
  ArrowLeft,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { fetchProcurementDetail } from "@/services/api";
import { ProcurementDetail, TenderSummary, SubmissionSummary } from "@/types/procurement";
import WorkspaceHeader from "@/components/procurement/WorkspaceHeader";
import StatusBadge from "@/components/procurement/StatusBadge";
import DocumentTable from "@/components/procurement/DocumentTable";
import { LoadingState, ErrorState, EmptyState } from "@/components/procurement/States";

export default function ProcurementWorkspacePage() {
  const params = useParams();
  const procurementId = typeof params?.procurementId === "string" ? params.procurementId : "";

  const [procurement, setProcurement] = useState<ProcurementDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState<boolean>(false);

  const loadProcurement = useCallback(async () => {
    if (!procurementId) return;
    setLoading(true);
    setError(null);
    setNotFound(false);

    try {
      const data = (await fetchProcurementDetail(procurementId)) as ProcurementDetail;
      if (!data || !data.id) {
        setNotFound(true);
      } else {
        setProcurement(data);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load procurement workspace.";
      if (msg.includes("404") || msg.toLowerCase().includes("not found")) {
        setNotFound(true);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [procurementId]);

  useEffect(() => {
    loadProcurement();
  }, [loadProcurement]);

  return (
    <div className="min-h-screen bg-[#f7f6f2] text-[#162333] flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-6xl w-full mx-auto px-5 py-10 sm:px-8 sm:py-14">
        {loading ? (
          <LoadingState message="Opening procurement workspace…" />
        ) : notFound ? (
          <EmptyState
            title="Procurement Workspace Not Found"
            description={`No procurement workspace exists matching identifier "${procurementId}". It may have been removed or never ingested.`}
            action={
              <Link
                href="/procurements"
                className="focus-ring inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-[#163a5f] hover:bg-[#214c77] rounded transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Return to Procurements
              </Link>
            }
          />
        ) : error ? (
          <ErrorState
            title="Error opening procurement workspace"
            message={error}
            onRetry={loadProcurement}
            backHref="/procurements"
            backLabel="Return to procurements"
          />
        ) : procurement ? (
          <div className="space-y-10">
            {/* Case Workspace Header */}
            <WorkspaceHeader
              breadcrumbs={[
                { label: "Procurements", href: "/procurements" },
                { label: procurement.external_reference || procurement.title, active: true },
              ]}
              eyebrow="Procurement Case"
              title={procurement.title}
              reference={procurement.external_reference}
              organization={procurement.organization}
              sourceSystem={procurement.source_system}
              status={procurement.status}
              updatedAt={procurement.updated_at || procurement.created_at}
            />

            {/* Visual Hierarchy: Procurement -> Tenders */}
            <section aria-labelledby="tenders-heading" className="space-y-4">
              <div className="flex items-center justify-between border-b border-[#d9ddd9] pb-3">
                <div className="flex items-center gap-2">
                  <FileSpreadsheet className="w-4 h-4 text-[#163a5f]" aria-hidden="true" />
                  <h2 id="tenders-heading" className="text-base font-semibold text-[#162333]">
                    Associated Tenders
                  </h2>
                </div>
                <span className="text-xs text-[#6e7d89]">
                  {procurement.tenders?.length || 0} tender notice(s)
                </span>
              </div>

              {!procurement.tenders || procurement.tenders.length === 0 ? (
                <div className="p-6 text-center border border-dashed border-[#cbd2d1] rounded bg-[#fffefa] text-xs text-[#6b7985]">
                  No tender notices are currently attached to this procurement workspace.
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4">
                  {procurement.tenders.map((tender: TenderSummary) => (
                    <div
                      key={tender.id}
                      className="p-6 rounded border border-[#d9ddd9] bg-[#fffefa] hover:border-[#b4c4cf] transition-all space-y-4"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#ecefe9] pb-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-[#edf2f5] text-[#1c3850] border border-[#cbd9e2]">
                              {tender.tender_reference}
                            </span>
                            {tender.category && (
                              <span className="text-xs text-[#526372] font-medium">
                                Category: {tender.category}
                              </span>
                            )}
                          </div>
                          <h3 className="mt-2 text-base font-semibold text-[#162333]">
                            {tender.title}
                          </h3>
                        </div>

                        <StatusBadge status={tender.status} size="sm" />
                      </div>

                      {tender.description && (
                        <p className="text-xs leading-relaxed text-[#566572] line-clamp-2">
                          {tender.description}
                        </p>
                      )}

                      <div className="flex flex-wrap items-center justify-between gap-4 pt-2 text-xs">
                        <div className="flex flex-wrap items-center gap-5 text-[#526372]">
                          {tender.estimated_value !== undefined && tender.estimated_value !== null && (
                            <div>
                              <span className="text-[#81909c] block text-[10px] uppercase font-semibold">Estimated Value</span>
                              <span className="font-semibold text-[#162333]">
                                ₹{tender.estimated_value.toLocaleString("en-IN")}
                              </span>
                            </div>
                          )}

                          <div>
                            <span className="text-[#81909c] block text-[10px] uppercase font-semibold">Requirements</span>
                            <span className="font-semibold text-[#162333] font-mono">
                              {tender.requirement_count ?? 0} criteria
                            </span>
                          </div>

                          <div>
                            <span className="text-[#81909c] block text-[10px] uppercase font-semibold">Bidders</span>
                            <span className="font-semibold text-[#162333] font-mono">
                              {tender.bidder_count ?? 0} participating
                            </span>
                          </div>

                          <div>
                            <span className="text-[#81909c] block text-[10px] uppercase font-semibold">Documents</span>
                            <span className="font-semibold text-[#162333] font-mono">
                              {tender.document_count ?? 0} specifications
                            </span>
                          </div>
                        </div>

                        <Link
                          href={`/tenders/${tender.id}`}
                          className="focus-ring inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-[#163a5f] hover:bg-[#204c78] rounded transition-colors"
                        >
                          Open Tender Workspace <ArrowRight className="w-3.5 h-3.5" />
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Participating Bidders & Submissions Overview */}
            <section aria-labelledby="bidders-heading" className="space-y-4">
              <div className="flex items-center justify-between border-b border-[#d9ddd9] pb-3">
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-[#163a5f]" aria-hidden="true" />
                  <h2 id="bidders-heading" className="text-base font-semibold text-[#162333]">
                    Participating Bidders & Submissions
                  </h2>
                </div>
              </div>

              {/* Extract all submissions from tenders */}
              {(() => {
                const allSubmissions: Array<{ submission: SubmissionSummary; tenderRef: string }> = [];
                procurement.tenders?.forEach((t) => {
                  t.submissions?.forEach((s) => {
                    allSubmissions.push({ submission: s, tenderRef: t.tender_reference });
                  });
                });

                if (allSubmissions.length === 0) {
                  return (
                    <div className="p-6 text-center border border-dashed border-[#cbd2d1] rounded bg-[#fffefa] text-xs text-[#6b7985]">
                      No bidder submissions have been filed or registered under this procurement yet.
                    </div>
                  );
                }

                return (
                  <div className="overflow-x-auto border border-[#d9ddd9] rounded bg-[#fffefa]">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="border-b border-[#d9ddd9] bg-[#f5f6f4] text-[#4f5e6a] font-semibold">
                          <th scope="col" className="py-3 px-4">Bidder Legal Name</th>
                          <th scope="col" className="py-3 px-4">Submission Reference</th>
                          <th scope="col" className="py-3 px-4">Tender Reference</th>
                          <th scope="col" className="py-3 px-4 text-center">Status</th>
                          <th scope="col" className="py-3 px-4 text-center">Documents</th>
                          <th scope="col" className="py-3 px-4 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#e4e7e4]">
                        {allSubmissions.map(({ submission, tenderRef }) => {
                          const bidder = submission.bidder;
                          return (
                            <tr key={submission.id} className="hover:bg-[#f8faf8] transition-colors">
                              <td className="py-3.5 px-4 font-semibold text-[#162333]">
                                <div>{bidder?.legal_name || "Unregistered Bidder"}</div>
                                {bidder?.gstin && (
                                  <div className="font-mono text-[10px] text-[#6d7d8a] font-normal">
                                    GSTIN: {bidder.gstin}
                                  </div>
                                )}
                              </td>
                              <td className="py-3.5 px-4 font-mono text-[#445564]">
                                {submission.external_submission_reference || submission.id}
                              </td>
                              <td className="py-3.5 px-4 font-mono text-[#5b6a77]">
                                {tenderRef}
                              </td>
                              <td className="py-3.5 px-4 text-center">
                                <StatusBadge status={submission.status} size="sm" />
                              </td>
                              <td className="py-3.5 px-4 text-center font-mono text-[#384a5b]">
                                {submission.document_count ?? submission.documents?.length ?? 0}
                              </td>
                              <td className="py-3.5 px-4 text-right">
                                <Link
                                  href={`/submissions/${submission.id}`}
                                  className="focus-ring inline-flex items-center gap-1 font-medium text-[#163a5f] hover:underline underline-offset-2"
                                >
                                  Inspect Submission <ArrowRight className="w-3.5 h-3.5" />
                                </Link>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                );
              })()}
            </section>

            {/* Top-Level Procurement Documents */}
            <section aria-labelledby="documents-heading" className="space-y-4">
              <div className="flex items-center justify-between border-b border-[#d9ddd9] pb-3">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-[#163a5f]" aria-hidden="true" />
                  <h2 id="documents-heading" className="text-base font-semibold text-[#162333]">
                    Procurement Ingestion Documents
                  </h2>
                </div>
                <span className="text-xs text-[#6e7d89]">
                  {procurement.documents?.length || 0} document(s)
                </span>
              </div>

              <DocumentTable
                documents={procurement.documents || []}
                emptyMessage="No top-level procurement notice documents registered."
              />
            </section>
          </div>
        ) : null}
      </main>
    </div>
  );
}
