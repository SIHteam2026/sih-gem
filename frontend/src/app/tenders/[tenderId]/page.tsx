"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  FileSpreadsheet,
  ListChecks,
  Users,
  FileText,
  ArrowRight,
  ArrowLeft,
  Info,
  ShieldCheck,
  Building,
  CheckCircle2,
  Clock,
  Sparkles,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import {
  fetchTenderDetail,
  fetchTenderRequirements,
  fetchTenderEvaluationContract,
} from "@/services/api";
import {
  TenderWorkspaceDetail,
  TenderRequirement,
  TenderEvaluationContract,
  SubmissionSummary,
} from "@/types/procurement";
import WorkspaceHeader from "@/components/procurement/WorkspaceHeader";
import StatusBadge from "@/components/procurement/StatusBadge";
import DocumentTable from "@/components/procurement/DocumentTable";
import RequirementCard from "@/components/procurement/RequirementCard";
import { LoadingState, ErrorState, EmptyState } from "@/components/procurement/States";

type ActiveTab = "requirements" | "submissions" | "overview";

export default function TenderWorkspacePage() {
  const params = useParams();
  const tenderId = typeof params?.tenderId === "string" ? params.tenderId : "";

  const [tender, setTender] = useState<TenderWorkspaceDetail | null>(null);
  const [requirements, setRequirements] = useState<TenderRequirement[]>([]);
  const [contract, setContract] = useState<TenderEvaluationContract | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>("requirements");

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState<boolean>(false);

  const loadTenderData = useCallback(async () => {
    if (!tenderId) return;
    setLoading(true);
    setError(null);
    setNotFound(false);

    try {
      // 1. Fetch canonical tender workspace detail
      const tenderData = (await fetchTenderDetail(tenderId)) as TenderWorkspaceDetail;
      if (!tenderData || !tenderData.id) {
        setNotFound(true);
        return;
      }
      setTender(tenderData);

      // 2. Fetch canonical extracted requirements from GET /api/tenders/{id}/requirements
      try {
        const reqs = (await fetchTenderRequirements(tenderId)) as TenderRequirement[];
        if (Array.isArray(reqs) && reqs.length > 0) {
          setRequirements(reqs);
        } else if (tenderData.requirements && tenderData.requirements.length > 0) {
          setRequirements(tenderData.requirements as TenderRequirement[]);
        }
      } catch (reqErr) {
        console.warn("Could not fetch separate requirements endpoint, falling back to embedded:", reqErr);
        if (tenderData.requirements) {
          setRequirements(tenderData.requirements as TenderRequirement[]);
        }
      }

      // 3. Optional supporting metadata from evaluation-contract
      try {
        const contractData = (await fetchTenderEvaluationContract(tenderId)) as TenderEvaluationContract;
        if (contractData && contractData.tender_id) {
          setContract(contractData);
        }
      } catch {
        // Optional supporting metadata - ignore if not yet generated
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load tender workspace.";
      if (msg.includes("404") || msg.toLowerCase().includes("not found")) {
        setNotFound(true);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [tenderId]);

  useEffect(() => {
    loadTenderData();
  }, [loadTenderData]);

  return (
    <div className="min-h-screen bg-[#f7f6f2] text-[#162333] flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-6xl w-full mx-auto px-5 py-10 sm:px-8 sm:py-14">
        {loading ? (
          <LoadingState message="Loading tender workspace and canonical requirements…" />
        ) : notFound ? (
          <EmptyState
            title="Tender Not Found"
            description={`No tender workspace could be located matching identifier "${tenderId}".`}
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
            title="Unable to load tender workspace"
            message={error}
            onRetry={loadTenderData}
            backHref="/procurements"
            backLabel="Return to procurements"
          />
        ) : tender ? (
          <div className="space-y-8">
            {/* Header & Breadcrumbs */}
            <WorkspaceHeader
              breadcrumbs={[
                { label: "Procurements", href: "/procurements" },
                {
                  label: tender.procurement_external_reference || "Procurement Workspace",
                  href: `/procurements/${tender.procurement_id}`,
                },
                { label: tender.tender_reference || tender.title, active: true },
              ]}
              eyebrow="Tender Workspace"
              title={tender.title}
              reference={tender.tender_reference}
              organization={tender.category ? `Category: ${tender.category}` : undefined}
              sourceSystem={tender.source_system || undefined}
              status={tender.status}
              updatedAt={tender.updated_at || tender.created_at}
            />

            {/* Supporting Evaluation Contract Summary Banner (if available) */}
            {contract && (
              <div className="p-4 rounded border border-[#ccdbe4] bg-[#f1f6fa] text-xs text-[#294a69] flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-2 font-medium">
                  <Sparkles className="w-4 h-4 text-[#1a4b75]" aria-hidden="true" />
                  <span>
                    Canonical Evaluation Contract Generated:{" "}
                    <strong>{contract.requirements_count}</strong> rules registered
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-[11px] text-[#4d6985] font-mono">
                  <span>Deterministic: {contract.deterministic_count}</span>
                  <span>•</span>
                  <span>External Verify: {contract.external_verification_count}</span>
                  <span>•</span>
                  <span>Doc Presence: {contract.document_presence_count}</span>
                  <span>•</span>
                  <span>Ambiguities: {contract.ambiguous_count}</span>
                </div>
              </div>
            )}

            {/* Navigation Tabs */}
            <div className="border-b border-[#d9ddd9]">
              <nav aria-label="Tender workspace tabs" className="flex gap-6 -mb-px">
                <button
                  type="button"
                  onClick={() => setActiveTab("requirements")}
                  className={`focus-ring flex items-center gap-2 pb-3.5 text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
                    activeTab === "requirements"
                      ? "border-[#163a5f] text-[#163a5f]"
                      : "border-transparent text-[#62707d] hover:text-[#162333] hover:border-[#cbd0cd]"
                  }`}
                >
                  <ListChecks className="w-4 h-4" aria-hidden="true" />
                  <span>Requirements Criteria</span>
                  <span className="ml-1 px-2 py-0.5 rounded-full text-[10px] font-mono bg-[#e9edf0] text-[#334b5c]">
                    {requirements.length}
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab("submissions")}
                  className={`focus-ring flex items-center gap-2 pb-3.5 text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
                    activeTab === "submissions"
                      ? "border-[#163a5f] text-[#163a5f]"
                      : "border-transparent text-[#62707d] hover:text-[#162333] hover:border-[#cbd0cd]"
                  }`}
                >
                  <Users className="w-4 h-4" aria-hidden="true" />
                  <span>Bidders & Submissions</span>
                  <span className="ml-1 px-2 py-0.5 rounded-full text-[10px] font-mono bg-[#e9edf0] text-[#334b5c]">
                    {tender.submissions?.length || 0}
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab("overview")}
                  className={`focus-ring flex items-center gap-2 pb-3.5 text-xs font-semibold border-b-2 transition-colors cursor-pointer ${
                    activeTab === "overview"
                      ? "border-[#163a5f] text-[#163a5f]"
                      : "border-transparent text-[#62707d] hover:text-[#162333] hover:border-[#cbd0cd]"
                  }`}
                >
                  <Info className="w-4 h-4" aria-hidden="true" />
                  <span>Overview & Specs</span>
                </button>
              </nav>
            </div>

            {/* TAB 1: REQUIREMENTS */}
            {activeTab === "requirements" && (
              <section aria-labelledby="requirements-tab-heading" className="space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h2 id="requirements-tab-heading" className="text-sm font-semibold text-[#162333]">
                      Extracted Tender Requirements & Conditions
                    </h2>
                    <p className="text-xs text-[#63727f] mt-0.5">
                      Structured criteria parsed from the tender notice. Each requirement details its statutory category, conditions, and exact clause provenance.
                    </p>
                  </div>
                  <span className="text-xs text-[#71808b] font-mono">
                    {requirements.length} Total Requirement(s)
                  </span>
                </div>

                {requirements.length === 0 ? (
                  <div className="p-8 text-center border border-dashed border-[#cbd2d1] rounded bg-[#fffefa] text-xs text-[#6b7985]">
                    No structured requirements have been extracted for this tender yet.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-4">
                    {requirements.map((req, idx) => (
                      <RequirementCard
                        key={req.requirement_id || req.id || `req-${idx}`}
                        requirement={req}
                        index={idx}
                      />
                    ))}
                  </div>
                )}
              </section>
            )}

            {/* TAB 2: BIDDERS & SUBMISSIONS */}
            {activeTab === "submissions" && (
              <section aria-labelledby="submissions-tab-heading" className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 id="submissions-tab-heading" className="text-sm font-semibold text-[#162333]">
                      Participating Bidders & Evidence Packages
                    </h2>
                    <p className="text-xs text-[#63727f] mt-0.5">
                      Review submitted bidder evidence documents against extracted requirements.
                    </p>
                  </div>
                </div>

                {!tender.submissions || tender.submissions.length === 0 ? (
                  <div className="p-8 text-center border border-dashed border-[#cbd2d1] rounded bg-[#fffefa] text-xs text-[#6b7985]">
                    No bidder submissions are registered for this tender.
                  </div>
                ) : (
                  <div className="overflow-x-auto border border-[#d9ddd9] rounded bg-[#fffefa]">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="border-b border-[#d9ddd9] bg-[#f5f6f4] text-[#4f5e6a] font-semibold">
                          <th scope="col" className="py-3 px-4">Bidder Legal Name</th>
                          <th scope="col" className="py-3 px-4">Identifiers</th>
                          <th scope="col" className="py-3 px-4">Submission Ref</th>
                          <th scope="col" className="py-3 px-4 text-center">Status</th>
                          <th scope="col" className="py-3 px-4 text-center">Evidence Docs</th>
                          <th scope="col" className="py-3 px-4 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#e4e7e4]">
                        {tender.submissions.map((sub: SubmissionSummary) => (
                          <tr key={sub.id} className="hover:bg-[#f8faf8] transition-colors">
                            <td className="py-4 px-4 font-semibold text-[#162333]">
                              {sub.bidder?.legal_name || "Unregistered Bidder"}
                              {sub.bidder?.email && (
                                <p className="text-[11px] text-[#6e7d89] font-normal">
                                  {sub.bidder.email}
                                </p>
                              )}
                            </td>
                            <td className="py-4 px-4 font-mono text-[11px] text-[#556472]">
                              {sub.bidder?.gstin && <div>GSTIN: {sub.bidder.gstin}</div>}
                              {sub.bidder?.pan && <div>PAN: {sub.bidder.pan}</div>}
                            </td>
                            <td className="py-4 px-4 font-mono text-[#3e5060]">
                              {sub.external_submission_reference || sub.id}
                            </td>
                            <td className="py-4 px-4 text-center">
                              <StatusBadge status={sub.status} size="sm" />
                            </td>
                            <td className="py-4 px-4 text-center font-mono text-[#25394d]">
                              {sub.document_count ?? sub.documents?.length ?? 0}
                            </td>
                            <td className="py-4 px-4 text-right">
                              <Link
                                href={`/submissions/${sub.id}`}
                                className="focus-ring inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-[#163a5f] hover:bg-[#224c77] rounded transition-colors"
                              >
                                Review Bidder <ArrowRight className="w-3.5 h-3.5" />
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            )}

            {/* TAB 3: OVERVIEW & SPECS */}
            {activeTab === "overview" && (
              <section aria-labelledby="overview-tab-heading" className="space-y-6">
                <div className="p-6 rounded border border-[#d9ddd9] bg-[#fffefa] space-y-4">
                  <h2 id="overview-tab-heading" className="text-sm font-semibold text-[#162333]">
                    Tender Scope of Work & Specification Details
                  </h2>
                  <p className="text-xs leading-relaxed text-[#51616e]">
                    {tender.description || "No narrative description provided in tender notice."}
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-[#edf0ee] text-xs">
                    <div>
                      <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                        Estimated Budget
                      </span>
                      <span className="font-semibold text-sm text-[#162333]">
                        {tender.estimated_value !== undefined && tender.estimated_value !== null
                          ? `₹${tender.estimated_value.toLocaleString("en-IN")}`
                          : "Not disclosed"}
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                        Procurement Category
                      </span>
                      <span className="font-semibold text-sm text-[#162333]">
                        {tender.category || "General Procurement"}
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                        Parent Procurement Reference
                      </span>
                      <span className="font-mono text-sm text-[#162333]">
                        {tender.procurement_external_reference || tender.procurement_id}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-[#526372]">
                    Tender Specification Documents
                  </h3>
                  <DocumentTable
                    documents={tender.documents || []}
                    emptyMessage="No specification documents attached to this tender notice."
                  />
                </div>
              </section>
            )}
          </div>
        ) : null}
      </main>
    </div>
  );
}
