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
  Play,
  RefreshCw,
  Clock,
  AlertTriangle,
  Cpu,
  CheckCircle,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import {
  fetchProcurementDetail,
  startProcurementProcessing,
  getProcurementProcessingStatus,
} from "@/services/api";
import {
  ProcurementDetail,
  TenderSummary,
  SubmissionSummary,
  ProcurementProcessingStatusResponse,
  ProcessingStage,
} from "@/types/procurement";
import WorkspaceHeader from "@/components/procurement/WorkspaceHeader";
import StatusBadge from "@/components/procurement/StatusBadge";
import DocumentTable from "@/components/procurement/DocumentTable";
import { LoadingState, ErrorState, EmptyState } from "@/components/procurement/States";

const PIPELINE_STAGES: Array<{ id: ProcessingStage; label: string; description: string }> = [
  {
    id: "TENDER_INTELLIGENCE",
    label: "Tender Intelligence",
    description: "Tender clause decomposition, category extraction & canonical requirement mapping",
  },
  {
    id: "DOCUMENT_INTELLIGENCE",
    label: "Document Intelligence",
    description: "Multi-modal OCR, layout parsing, classification & entity resolution",
  },
  {
    id: "EVIDENCE_EXTRACTION",
    label: "Evidence Extraction",
    description: "Claim extraction, verbatim provenance grounding & observation reconciliation",
  },
  {
    id: "COMPLIANCE_EVALUATION",
    label: "Compliance Evaluation",
    description: "Deterministic criteria verification, contradiction detection & ambiguity scoring",
  },
];

export default function ProcurementWorkspacePage() {
  const params = useParams();
  const procurementId = typeof params?.procurementId === "string" ? params.procurementId : "";

  const [procurement, setProcurement] = useState<ProcurementDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState<boolean>(false);

  // Processing Lifecycle State
  const [processingStatus, setProcessingStatus] = useState<ProcurementProcessingStatusResponse | null>(null);
  const [isProcessingAction, setIsProcessingAction] = useState<boolean>(false);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [pollCount, setPollCount] = useState<number>(0);

  const loadProcurement = useCallback(async (silent = false) => {
    if (!procurementId) return;
    if (!silent) setLoading(true);
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
      if (!silent) setLoading(false);
    }
  }, [procurementId]);

  const loadProcessingStatus = useCallback(async () => {
    if (!procurementId) return;
    try {
      const status = (await getProcurementProcessingStatus(procurementId)) as ProcurementProcessingStatusResponse;
      if (status) {
        setProcessingStatus(status);
        return status;
      }
    } catch {
      // Non-blocking if status endpoint is not yet populated
    }
    return null;
  }, [procurementId]);

  useEffect(() => {
    loadProcurement();
    loadProcessingStatus();
  }, [loadProcurement, loadProcessingStatus]);

  // Bounded Polling while PROCESSING
  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;
    const isCurrentlyProcessing =
      procurement?.status === "PROCESSING" ||
      processingStatus?.status === "PROCESSING" ||
      isProcessingAction;

    if (isCurrentlyProcessing && pollCount < 20) {
      timer = setTimeout(async () => {
        const latestStatus = await loadProcessingStatus();
        if (latestStatus?.status === "READY" || latestStatus?.status === "FAILED") {
          setIsProcessingAction(false);
          await loadProcurement(true);
        }
        setPollCount((prev) => prev + 1);
      }, 2500);
    } else if (pollCount >= 20) {
      setIsProcessingAction(false);
    }

    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [procurement?.status, processingStatus?.status, isProcessingAction, pollCount, loadProcessingStatus, loadProcurement]);

  const handleStartProcessing = async (force = false) => {
    if (!procurementId) return;
    setIsProcessingAction(true);
    setProcessingError(null);
    setPollCount(0);

    try {
      await startProcurementProcessing(procurementId, force);
      // Immediately refresh status
      await loadProcessingStatus();
      await loadProcurement(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to start processing pipeline.";
      setProcessingError(msg);
      setIsProcessingAction(false);
    }
  };

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

            {/* Processing Lifecycle Pipeline Card */}
            <section aria-labelledby="processing-pipeline-heading" className="p-6 rounded-lg border border-[#cbd9e2] bg-[#fbfdfd] space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#e1ebf0] pb-4">
                <div className="flex items-center gap-2.5">
                  <Cpu className="w-5 h-5 text-[#163a5f]" aria-hidden="true" />
                  <div>
                    <h2 id="processing-pipeline-heading" className="text-sm font-semibold text-[#162333]">
                      Evidence Ingestion & Compliance Processing Lifecycle
                    </h2>
                    <p className="text-[11px] text-[#5a6e80]">
                      Automated multi-stage evidence extraction, deterministic verification, and contradiction detection.
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <StatusBadge status={procurement.status} size="md" />

                  {procurement.status !== "PROCESSING" && !isProcessingAction && (
                    <button
                      type="button"
                      onClick={() => handleStartProcessing(procurement.status === "READY" || procurement.status === "FAILED")}
                      className="focus-ring inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-[#163a5f] hover:bg-[#204c78] rounded transition-colors"
                    >
                      {procurement.status === "READY" ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" /> Re-run Processing
                        </>
                      ) : procurement.status === "FAILED" ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" /> Retry Processing
                        </>
                      ) : (
                        <>
                          <Play className="w-3.5 h-3.5" aria-hidden="true" /> Process Procurement
                        </>
                      )}
                    </button>
                  )}

                  {(procurement.status === "PROCESSING" || isProcessingAction) && (
                    <div className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-[#163a5f] bg-[#e6eff5] border border-[#cbdce7] rounded">
                      <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#163a5f]" aria-hidden="true" />
                      <span>Pipeline Running…</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Processing Error Banner */}
              {(processingError || (procurement.status === "FAILED" && (processingStatus?.last_error_message || processingStatus?.last_error_code))) && (
                <div className="p-3.5 rounded border border-rose-200 bg-rose-50 text-rose-800 text-xs flex items-start gap-2.5">
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" aria-hidden="true" />
                  <div>
                    <span className="font-semibold block">Processing Error</span>
                    <span>{processingError || processingStatus?.last_error_message || `Pipeline failed at stage: ${processingStatus?.failed_stage || "Unknown"}`}</span>
                  </div>
                </div>
              )}

              {/* Pipeline Stages Progression */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 pt-1">
                {PIPELINE_STAGES.map((stage, idx) => {
                  const isCompleted =
                    processingStatus?.completed_stages?.includes(stage.id) ||
                    procurement.status === "READY";
                  const isCurrent =
                    (procurement.status === "PROCESSING" || isProcessingAction) &&
                    (processingStatus?.current_stage === stage.id || (!processingStatus?.current_stage && idx === 0));
                  const stageResult = processingStatus?.stage_results?.find((r) => r.stage === stage.id);

                  return (
                    <div
                      key={stage.id}
                      className={`p-3.5 rounded border transition-colors ${
                        isCompleted
                          ? "border-[#c4dccb] bg-[#f5fbf7]"
                          : isCurrent
                          ? "border-[#b8d4e8] bg-[#f0f7fc] ring-1 ring-[#163a5f]/20"
                          : "border-[#dce2e6] bg-[#fafbfc] opacity-75"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-1.5 mb-1.5">
                        <span className="text-[10px] font-mono uppercase font-bold text-[#637584]">
                          Stage 0{idx + 1}
                        </span>
                        {isCompleted ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700">
                            <CheckCircle className="w-3.5 h-3.5" aria-hidden="true" /> Done
                          </span>
                        ) : isCurrent ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#163a5f]">
                            <RefreshCw className="w-3 h-3 animate-spin" aria-hidden="true" /> Active
                          </span>
                        ) : (
                          <span className="text-[10px] font-medium text-[#8898a6]">Pending</span>
                        )}
                      </div>

                      <div className="text-xs font-semibold text-[#162333]">{stage.label}</div>
                      <div className="text-[11px] text-[#556777] mt-1 leading-snug">
                        {stage.description}
                      </div>

                      {(stageResult?.execution_time_ms !== undefined || stageResult?.metadata?.summary) && (
                        <div className="mt-2 pt-2 border-t border-[#d8e3dc] text-[10px] text-[#2c6341] font-mono">
                          {stageResult.metadata?.summary || `Executed in ${stageResult.execution_time_ms}ms`}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="text-[11px] text-[#6b7d8c] bg-[#edf3f7] p-2.5 rounded border border-[#d6e3ec] leading-relaxed">
                <strong>Decision Support Architecture:</strong> Pipeline execution extracts requirements and evidence to power deterministic compliance verification. The system never autonomously awards or disqualifies bidders; all conclusions remain recommendations for human officer review.
              </div>
            </section>

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
