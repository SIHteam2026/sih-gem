"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Building2,
  FileCheck,
  FileText,
  Clock,
  ArrowLeft,
  Mail,
  CreditCard,
  Hash,
  ShieldAlert,
  Info,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { fetchSubmissionDetail } from "@/services/api";
import { SubmissionSummary } from "@/types/procurement";
import WorkspaceHeader from "@/components/procurement/WorkspaceHeader";
import StatusBadge from "@/components/procurement/StatusBadge";
import DocumentTable from "@/components/procurement/DocumentTable";
import { LoadingState, ErrorState, EmptyState } from "@/components/procurement/States";

export default function SubmissionWorkspacePage() {
  const params = useParams();
  const submissionId = typeof params?.submissionId === "string" ? params.submissionId : "";

  const [submission, setSubmission] = useState<SubmissionSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState<boolean>(false);

  const loadSubmission = useCallback(async () => {
    if (!submissionId) return;
    setLoading(true);
    setError(null);
    setNotFound(false);

    try {
      const data = (await fetchSubmissionDetail(submissionId)) as SubmissionSummary;
      if (!data || !data.id) {
        setNotFound(true);
      } else {
        setSubmission(data);
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
            {/* Header & Breadcrumbs */}
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
              eyebrow="Bidder Submission Workspace"
              title={submission.bidder?.legal_name || "Bid Submission"}
              reference={submission.external_submission_reference || submission.id}
              organization={submission.bidder?.gstin ? `GSTIN: ${submission.bidder.gstin}` : undefined}
              status={submission.status}
              updatedAt={submission.updated_at || submission.created_at}
            />

            {/* Visual Hierarchy: Bidder Identity Card */}
            <section aria-labelledby="bidder-identity-heading" className="space-y-4">
              <div className="flex items-center gap-2 border-b border-[#d9ddd9] pb-3">
                <Building2 className="w-4 h-4 text-[#163a5f]" aria-hidden="true" />
                <h2 id="bidder-identity-heading" className="text-sm font-semibold text-[#162333]">
                  Registered Bidder Profile
                </h2>
              </div>

              <div className="p-6 rounded border border-[#d9ddd9] bg-[#fffefa] space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-[#162333]">
                      {submission.bidder?.legal_name || "Corporate Entity"}
                    </h3>
                    <p className="font-mono text-xs text-[#6e7e8b] mt-0.5">
                      Bidder UUID: {submission.bidder?.id || submission.bidder_id}
                    </p>
                  </div>

                  <StatusBadge status={submission.status} size="sm" />
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

            {/* Submission Metadata */}
            <section aria-labelledby="submission-meta-heading" className="space-y-4">
              <div className="flex items-center gap-2 border-b border-[#d9ddd9] pb-3">
                <FileCheck className="w-4 h-4 text-[#163a5f]" aria-hidden="true" />
                <h2 id="submission-meta-heading" className="text-sm font-semibold text-[#162333]">
                  Submission Specifications & Filing Record
                </h2>
              </div>

              <div className="p-5 rounded border border-[#d9ddd9] bg-[#fffefa] text-xs grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                    External Submission Reference
                  </span>
                  <span className="font-mono font-medium text-[#162333] mt-0.5 block">
                    {submission.external_submission_reference || "N/A"}
                  </span>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                    Submitted Timestamp
                  </span>
                  <span className="text-[#162333] mt-0.5 block">
                    {submission.submitted_at
                      ? new Date(submission.submitted_at).toLocaleString("en-IN", {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })
                      : "Timestamp unavailable"}
                  </span>
                </div>

                <div>
                  <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                    Canonical Submission UUID
                  </span>
                  <span className="font-mono text-[#162333] mt-0.5 block truncate" title={submission.id}>
                    {submission.id}
                  </span>
                </div>
              </div>
            </section>

            {/* Submitted Evidence Documents (Keyed by canonical document UUIDs) */}
            <section aria-labelledby="documents-heading" className="space-y-4">
              <div className="flex items-center justify-between border-b border-[#d9ddd9] pb-3">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-[#163a5f]" aria-hidden="true" />
                  <h2 id="documents-heading" className="text-sm font-semibold text-[#162333]">
                    Submitted Proof Documents & Evidence
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

            {/* Future Findings / Evidence Notice */}
            <section aria-labelledby="future-findings-heading">
              <div className="p-5 rounded border border-[#cfdbe5] bg-[#f5f8fa] text-xs text-[#2a465e] space-y-2">
                <div className="flex items-center gap-2 font-semibold text-[#163a5f]">
                  <Info className="w-4 h-4 text-[#163a5f]" aria-hidden="true" />
                  <h3 id="future-findings-heading">Automated Compliance Findings & Reconciliation Pipeline</h3>
                </div>
                <p className="leading-relaxed text-[#4b6377]">
                  Detailed requirement compliance findings, claim extraction, and cross-document contradiction checks are processed asynchronously by the OPAL evaluation pipeline. Verified findings and evidence citations will appear here for officer review and audit replay once evaluation is executed.
                </p>
              </div>
            </section>
          </div>
        ) : null}
      </main>
    </div>
  );
}
