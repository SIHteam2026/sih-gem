"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Building2,
  FileCheck,
  FileText,
  ArrowLeft,
  Mail,
  CreditCard,
  Hash,
  ShieldCheck,
  Sparkles,
  RefreshCw,
  Search,
  Filter,
  ListChecks,
  AlertCircle,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import {
  fetchSubmissionDetail,
  evaluateSubmission,
  fetchTenderRequirements,
} from "@/services/api";
import {
  SubmissionSummary,
  SubmissionEvaluationResult,
  RequirementEvaluationResult,
  ProvenanceRecord,
  TenderRequirement,
} from "@/types/procurement";
import WorkspaceHeader from "@/components/procurement/WorkspaceHeader";
import StatusBadge from "@/components/procurement/StatusBadge";
import DocumentTable from "@/components/procurement/DocumentTable";
import EvaluationSummary from "@/components/procurement/EvaluationSummary";
import ReviewRequiredBanner from "@/components/procurement/ReviewRequiredBanner";
import RequirementFindingCard from "@/components/procurement/RequirementFindingCard";
import DocumentDrawer from "@/components/procurement/DocumentDrawer";
import { LoadingState, ErrorState, EmptyState } from "@/components/procurement/States";

export default function SubmissionWorkspacePage() {
  const params = useParams();
  const submissionId = typeof params?.submissionId === "string" ? params.submissionId : "";

  const [submission, setSubmission] = useState<SubmissionSummary | null>(null);
  const [evaluation, setEvaluation] = useState<SubmissionEvaluationResult | null>(null);
  const [tenderReqs, setTenderReqs] = useState<TenderRequirement[]>([]);

  const [loading, setLoading] = useState<boolean>(true);
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState<boolean>(false);

  // Filter and Search states
  const [filterState, setFilterState] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Provenance drawer inspection
  const [inspectedProvenance, setInspectedProvenance] = useState<ProvenanceRecord | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);

  const handleInspectProvenance = useCallback((record: ProvenanceRecord) => {
    setInspectedProvenance(record);
    setIsDrawerOpen(true);
  }, []);

  const handleCloseDrawer = useCallback(() => {
    setIsDrawerOpen(false);
    setInspectedProvenance(null);
  }, []);

  // 1. Fetch submission data & tender requirements
  const loadSubmission = useCallback(async () => {
    if (!submissionId) return;
    setLoading(true);
    setError(null);
    setNotFound(false);

    try {
      const data = (await fetchSubmissionDetail(submissionId)) as SubmissionSummary;
      if (!data || !data.id) {
        setNotFound(true);
        return;
      }
      setSubmission(data);

      // Load tender requirements to enrich findings with title and metadata
      if (data.tender_id) {
        try {
          const reqs = (await fetchTenderRequirements(data.tender_id)) as TenderRequirement[];
          if (Array.isArray(reqs)) {
            setTenderReqs(reqs);
          }
        } catch {
          // Tender requirements enrichment is non-blocking
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load submission details.";
      if (msg.includes("404") || msg.toLowerCase().includes("not found")) {
        setNotFound(true);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [submissionId]);

  useEffect(() => {
    loadSubmission();
  }, [loadSubmission]);

  // 2. Explicit Officer Evaluation Trigger
  const runEvaluation = useCallback(async () => {
    if (!submissionId || !submission) return;
    setEvaluating(true);
    setEvalError(null);

    try {
      const bidderName = submission.bidder?.legal_name || "Bidder Entity";
      const evalResult = (await evaluateSubmission(
        submissionId,
        submission.tender_id,
        bidderName
      )) as SubmissionEvaluationResult;

      if (evalResult && evalResult.requirement_results) {
        setEvaluation(evalResult);
      } else {
        setEvalError("Evaluation completed but no requirement findings were returned.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to execute compliance evaluation.";
      setEvalError(msg);
    } finally {
      setEvaluating(false);
    }
  }, [submissionId, submission]);

  // Automatically trigger compliance evaluation once submission data is loaded
  useEffect(() => {
    if (submission && !evaluation && !evaluating && !evalError) {
      runEvaluation();
    }
  }, [submission, evaluation, evaluating, evalError, runEvaluation]);

  // Merge requirement metadata (title, category, description, is_ambiguous) into findings
  const enrichedResults = useMemo<RequirementEvaluationResult[]>(() => {
    if (!evaluation || !Array.isArray(evaluation.requirement_results)) {
      return [];
    }

    const reqMap = new Map<string, TenderRequirement>();
    tenderReqs.forEach((r) => {
      if (r.requirement_id) {
        reqMap.set(r.requirement_id.toUpperCase().trim(), r);
      }
    });

    return evaluation.requirement_results.map((res) => {
      const matchedReq = reqMap.get(res.requirement_id.toUpperCase().trim());
      return {
        ...res,
        title: matchedReq?.title || res.title || matchedReq?.category || res.requirement_id,
        category: matchedReq?.category || res.category || "GENERAL_CRITERIA",
        mandatory: matchedReq?.mandatory ?? res.mandatory ?? true,
        description: matchedReq?.description || res.description,
        is_ambiguous: matchedReq?.is_ambiguous ?? res.is_ambiguous ?? false,
        ambiguity_reason: matchedReq?.ambiguity_reason ?? res.ambiguity_reason,
      };
    });
  }, [evaluation, tenderReqs]);

  // Filtered & Searched findings
  const filteredResults = useMemo(() => {
    return enrichedResults.filter((res) => {
      // 1. State filter
      if (filterState) {
        const normState = String(res.state || "").toUpperCase();
        let targetState = filterState.toUpperCase();
        if (targetState === "PASS") {
          if (normState !== "PASS" && normState !== "VERIFIED" && normState !== "COMPLIANT") {
            return false;
          }
        } else if (targetState === "FAIL") {
          if (normState !== "FAIL" && normState !== "NON_COMPLIANT" && normState !== "REJECTED") {
            return false;
          }
        } else if (targetState === "REVIEW") {
          if (normState !== "REVIEW" && normState !== "REVIEW_REQUIRED" && !res.review_required) {
            return false;
          }
        } else if (targetState === "UNVERIFIED") {
          if (normState !== "UNVERIFIED") {
            return false;
          }
        } else if (targetState === "NOT_APPLICABLE") {
          if (normState !== "NOT_APPLICABLE") {
            return false;
          }
        }
      }

      // 2. Search query filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesId = (res.requirement_id || "").toLowerCase().includes(q);
        const matchesTitle = (res.title || "").toLowerCase().includes(q);
        const matchesReason = (res.reason || "").toLowerCase().includes(q);
        const matchesDesc = (res.description || "").toLowerCase().includes(q);
        if (!matchesId && !matchesTitle && !matchesReason && !matchesDesc) {
          return false;
        }
      }

      return true;
    });
  }, [enrichedResults, filterState, searchQuery]);

  return (
    <div className="min-h-screen bg-[#f7f6f2] text-[#162333] flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-6xl w-full mx-auto px-5 py-10 sm:px-8 sm:py-14">
        {loading ? (
          <LoadingState message="Loading bidder submission workspace…" />
        ) : notFound ? (
          <EmptyState
            title="Bid Submission Not Found"
            description={`No bid submission could be located matching identifier "${submissionId}".`}
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
            title="Unable to load submission"
            message={error}
            onRetry={loadSubmission}
            backHref="/procurements"
            backLabel="Return to procurements"
          />
        ) : submission ? (
          <div className="space-y-8">
            {/* 1. Header & Breadcrumbs */}
            <WorkspaceHeader
              breadcrumbs={[
                { label: "Procurements", href: "/procurements" },
                {
                  label: "Tender Workspace",
                  href: `/tenders/${submission.tender_id}`,
                },
                {
                  label:
                    submission.bidder?.legal_name ||
                    submission.external_submission_reference ||
                    "Submission",
                  active: true,
                },
              ]}
              eyebrow="Bidder Review & Compliance Workspace"
              title={submission.bidder?.legal_name || "Bid Submission Review"}
              reference={submission.external_submission_reference || submission.id}
              organization={submission.bidder?.gstin ? `GSTIN: ${submission.bidder.gstin}` : undefined}
              status={submission.status}
              updatedAt={submission.updated_at || submission.created_at}
            />

            {/* 2. Registered Bidder Profile Card */}
            <section aria-labelledby="bidder-identity-heading" className="space-y-4">
              <div className="flex items-center justify-between border-b border-[#d9ddd9] pb-3">
                <div className="flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-[#163a5f]" aria-hidden="true" />
                  <h2 id="bidder-identity-heading" className="text-sm font-semibold text-[#162333]">
                    Registered Bidder Identity & Profile
                  </h2>
                </div>
                <StatusBadge status={submission.status} size="sm" />
              </div>

              <div className="p-6 rounded border border-[#d9ddd9] bg-[#fffefa] space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-[#162333]">
                      {submission.bidder?.legal_name || "Corporate Entity"}
                    </h3>
                    <p className="font-mono text-xs text-[#6e7e8b] mt-0.5">
                      Bidder ID: {submission.bidder?.id || submission.bidder_id}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-[#edf0ee] text-xs">
                  <div>
                    <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                      Goods & Services Tax (GSTIN)
                    </span>
                    <span className="font-mono font-medium text-[#162333] flex items-center gap-1.5 mt-0.5">
                      <Hash className="w-3.5 h-3.5 text-[#8898a6]" aria-hidden="true" />
                      {submission.bidder?.gstin || "Not provided"}
                    </span>
                  </div>

                  <div>
                    <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                      Permanent Account Number (PAN)
                    </span>
                    <span className="font-mono font-medium text-[#162333] flex items-center gap-1.5 mt-0.5">
                      <CreditCard className="w-3.5 h-3.5 text-[#8898a6]" aria-hidden="true" />
                      {submission.bidder?.pan || "Not provided"}
                    </span>
                  </div>

                  <div>
                    <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                      Primary Contact Email
                    </span>
                    <span className="font-medium text-[#162333] flex items-center gap-1.5 mt-0.5 truncate">
                      <Mail className="w-3.5 h-3.5 text-[#8898a6]" aria-hidden="true" />
                      {submission.bidder?.email || "Not recorded"}
                    </span>
                  </div>
                </div>
              </div>
            </section>

            {/* 3. Evaluation Section: Trigger / Progress / Summary */}
            <section aria-labelledby="evaluation-section-heading" className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#d9ddd9] pb-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-[#163a5f]" aria-hidden="true" />
                  <h2 id="evaluation-section-heading" className="text-sm font-semibold text-[#162333]">
                    Requirement Compliance & Evidence Evaluation
                  </h2>
                </div>

                {/* Explicit Officer Action Trigger */}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={runEvaluation}
                    disabled={evaluating}
                    className={`focus-ring inline-flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold rounded transition-colors ${
                      evaluating
                        ? "bg-[#d8e0e8] text-[#556b80] cursor-not-allowed"
                        : "bg-[#163a5f] hover:bg-[#224d78] text-white shadow-xs"
                    }`}
                    aria-label={evaluation ? "Re-run compliance evaluation" : "Run compliance analysis"}
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${evaluating ? "animate-spin" : ""}`} aria-hidden="true" />
                    <span>
                      {evaluating
                        ? "Evaluating Requirements…"
                        : evaluation
                        ? "Re-Run Analysis"
                        : "Run Compliance Analysis"}
                    </span>
                  </button>
                </div>
              </div>

              {/* Evaluating In-Progress Banner */}
              {evaluating && (
                <div className="p-6 rounded border border-[#ccdbe6] bg-[#f4f8fb] text-xs text-[#1e3b56] text-center space-y-3">
                  <div className="inline-flex items-center justify-center p-3 bg-[#e4eff7] rounded-full text-[#163a5f]">
                    <RefreshCw className="w-5 h-5 animate-spin" aria-hidden="true" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-sm text-[#163a5f]">
                      Executing Canonical Compliance Evaluation
                    </h3>
                    <p className="text-[#4e6880] mt-1 max-w-md mx-auto leading-relaxed">
                      Extracting bidder claims, verifying evidence observations, and reconciling cross-document contradictions against tender requirements…
                    </p>
                  </div>
                </div>
              )}

              {/* Evaluation Error Banner */}
              {evalError && !evaluating && (
                <div className="p-4 rounded border border-rose-300 bg-[#fffbfc] text-xs text-rose-900 space-y-2">
                  <div className="flex items-center gap-2 font-semibold">
                    <AlertCircle className="w-4 h-4 text-rose-700" aria-hidden="true" />
                    <span>Evaluation Engine Error</span>
                  </div>
                  <p className="text-rose-800">{evalError}</p>
                  <button
                    type="button"
                    onClick={runEvaluation}
                    className="mt-1 text-xs font-semibold text-rose-900 underline hover:no-underline"
                  >
                    Retry Evaluation
                  </button>
                </div>
              )}

              {/* Un-evaluated Placeholder Prompt */}
              {!evaluation && !evaluating && !evalError && (
                <div className="p-8 rounded border border-dashed border-[#ccd2d1] bg-[#fffefa] text-center space-y-3">
                  <div className="inline-flex items-center justify-center p-3 bg-[#f0f4f7] rounded-full text-[#163a5f]">
                    <Sparkles className="w-5 h-5 text-[#163a5f]" aria-hidden="true" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-[#162333]">
                      Evaluation Ready to Execute
                    </h3>
                    <p className="text-xs text-[#637380] max-w-md mx-auto mt-1 leading-relaxed">
                      All bidder proof documents have been registered. Click &ldquo;Run Compliance Analysis&rdquo; to execute deterministic rule checks, claim extraction, and cross-document reconciliation.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={runEvaluation}
                    className="focus-ring inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-[#163a5f] hover:bg-[#224d78] rounded transition-colors shadow-xs"
                  >
                    <ShieldCheck className="w-3.5 h-3.5" aria-hidden="true" />
                    <span>Run Compliance Analysis</span>
                  </button>
                </div>
              )}

              {/* Evaluated Results View */}
              {evaluation && !evaluating && (
                <div className="space-y-6">
                  {/* Human-in-the-Loop Review Banner */}
                  <ReviewRequiredBanner
                    reviewRequired={evaluation.review_required}
                    reviewCount={evaluation.review_required_count || 0}
                    totalEvaluated={enrichedResults.length}
                    contradictionCount={evaluation.unresolved_contradiction_count || 0}
                    unverifiedCount={evaluation.unverified_count || 0}
                  />

                  {/* Summary Metric Breakdown */}
                  <EvaluationSummary
                    totalRequirements={enrichedResults.length}
                    stateCounts={evaluation.machine_review_summary || {}}
                    reviewRequired={evaluation.review_required}
                    reviewRequiredCount={evaluation.review_required_count || 0}
                    unresolvedContradictions={evaluation.unresolved_contradiction_count || 0}
                    unverifiedCount={evaluation.unverified_count || 0}
                    selectedFilter={filterState}
                    onFilterSelect={(state) => setFilterState(state)}
                  />

                  {/* Filter & Search Toolbar */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
                    <div className="flex items-center gap-2">
                      <ListChecks className="w-4 h-4 text-[#163a5f]" aria-hidden="true" />
                      <h3 className="text-sm font-semibold text-[#162333]">
                        Evaluated Requirements ({filteredResults.length} of {enrichedResults.length})
                      </h3>
                      {filterState && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#e6edf2] text-[#1c3c5c]">
                          Filtered: {filterState}
                        </span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      {/* Search input */}
                      <div className="relative">
                        <Search className="w-3.5 h-3.5 text-[#7f8f9e] absolute left-2.5 top-1/2 -translate-y-1/2" aria-hidden="true" />
                        <input
                          type="text"
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          placeholder="Search criteria or ID…"
                          className="pl-8 pr-3 py-1.5 text-xs bg-[#fffefa] border border-[#cbd2d1] rounded focus-ring placeholder:text-[#8898a6] text-[#162333] w-48 sm:w-56"
                          aria-label="Search evaluated requirements"
                        />
                      </div>

                      {/* Clear Filters Button */}
                      {(filterState || searchQuery) && (
                        <button
                          type="button"
                          onClick={() => {
                            setFilterState(null);
                            setSearchQuery("");
                          }}
                          className="px-2.5 py-1.5 text-xs font-semibold text-[#5a6a78] hover:text-[#162333] hover:bg-[#edf0ed] rounded transition-colors"
                        >
                          Clear Filters
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Requirement Finding Cards List */}
                  {filteredResults.length === 0 ? (
                    <div className="p-8 text-center border border-dashed border-[#cbd2d1] rounded bg-[#fffefa] text-xs text-[#6b7985]">
                      No evaluated requirements match the active filter or search query.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 gap-4">
                      {filteredResults.map((result, idx) => (
                        <RequirementFindingCard
                          key={result.requirement_id || `res-${idx}`}
                          result={result}
                          onInspectEvidence={handleInspectProvenance}
                          defaultExpanded={result.review_required}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </section>

            {/* 4. Submitted Proof Documents Inventory */}
            <section aria-labelledby="documents-heading" className="space-y-4 pt-4 border-t border-[#d9ddd9]">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-[#163a5f]" aria-hidden="true" />
                  <h2 id="documents-heading" className="text-sm font-semibold text-[#162333]">
                    Submitted Proof Documents Inventory
                  </h2>
                </div>
                <span className="text-xs text-[#71808b] font-mono">
                  {submission.documents?.length || 0} document(s) registered
                </span>
              </div>

              <DocumentTable
                documents={submission.documents || []}
                emptyMessage="No evidence documents attached to this bidder submission."
              />
            </section>

            {/* 5. Statutory Decision Support Boundary Note */}
            <section aria-label="Statutory Authority Note" className="pt-2">
              <div className="p-4 rounded border border-[#ccdbe4] bg-[#f4f7f9] text-[11px] text-[#334b60] leading-relaxed">
                <strong>Procurement Decision Boundary:</strong> Under Indian Public Procurement guidelines (GFR 2017 & GeM GTC), OPAL functions strictly as an AI-powered verification and decision-support instrument. Formal qualification, shortfall notice issuance, and final award determinations remain the sole legal authority of the designated Procurement Officer.
              </div>
            </section>
          </div>
        ) : null}
      </main>

      {/* Provenance Detail Drawer Modal */}
      <DocumentDrawer
        isOpen={isDrawerOpen}
        onClose={handleCloseDrawer}
        record={inspectedProvenance}
      />
    </div>
  );
}
