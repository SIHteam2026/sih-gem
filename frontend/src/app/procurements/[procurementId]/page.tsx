"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  FileText,
  Building,
  CheckCircle,
  Clock,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  Play
} from "lucide-react";
import Navbar from "@/components/Navbar";
import {
  fetchProcurementDetail,
} from "@/services/api";
import { runTechnicalScrutiny } from "@/services/api/technical-review";
import {
  ProcurementDetail,
  TenderSummary,
  SubmissionSummary,
} from "@/types/procurement";
import StatusBadge from "@/components/procurement/StatusBadge";
import { LoadingState, ErrorState } from "@/components/procurement/States";

export default function ProcurementWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const procurementId = typeof params?.procurementId === "string" ? params.procurementId : "";

  const [procurement, setProcurement] = useState<ProcurementDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState<boolean>(false);

  const [isProcessingAction, setIsProcessingAction] = useState<boolean>(false);
  const [processingError, setProcessingError] = useState<string | null>(null);

  const loadProcurement = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchProcurementDetail(procurementId);
      if (!data) {
        setNotFound(true);
      } else {
        setProcurement(data);
      }
    } catch (err: any) {
      if (err.message?.includes("404") || err.message?.includes("not found")) {
        setNotFound(true);
      } else {
        setError(err.message || "Failed to load procurement details");
      }
    } finally {
      setLoading(false);
    }
  }, [procurementId]);

  useEffect(() => {
    if (procurementId) {
      loadProcurement();
    }
  }, [loadProcurement, procurementId]);

  const handleRunTechnicalScrutiny = async () => {
    if (!procurement) return;
    setIsProcessingAction(true);
    setProcessingError(null);
    try {
      await runTechnicalScrutiny(procurement.id);
      router.push(`/procurements/${procurement.id}/technical-scrutiny`);
    } catch (err: any) {
      setProcessingError(err.message || "Failed to initiate technical scrutiny");
      setIsProcessingAction(false);
    }
  };

  if (loading) return <LoadingState message="Loading procurement workspace..." />;
  if (notFound) return <ErrorState message="Procurement not found." actionText="Return to Workspace" onAction={() => window.location.href = "/procurements"} />;
  if (error) return <ErrorState message={error} actionText="Retry" onAction={loadProcurement} />;
  if (!procurement) return <ErrorState message="Unknown error occurred." />;

  // Extract totals from tenders
  const totalTenders = procurement.tenders?.length || 0;
  const totalBidders = procurement.tenders?.reduce((acc, t) => acc + (t.bidder_count || 0), 0) || 0;
  const allSubmissions = procurement.tenders?.flatMap(t => t.submissions || []) || [];
  const totalRequirements = procurement.tenders?.reduce((acc, t) => acc + (t.requirement_count || 0), 0) || 0;
  
  // Use the actual deadline from the first tender if available.
  const tenderDateStr = procurement.created_at || new Date().toISOString();
  const submissionDeadlineStr = procurement.tenders?.[0]?.submission_deadline;
  
  const now = new Date();
  
  let isDeadlinePassed = false;
  let hasDeadline = false;
  let deadlineDate = null;
  
  if (submissionDeadlineStr) {
    hasDeadline = true;
    deadlineDate = new Date(submissionDeadlineStr);
    isDeadlinePassed = now >= deadlineDate;
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      <Navbar />
      
      <main className="flex-1 w-full max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* LEFT: Procurement Identity / Summary */}
        <div className="lg:col-span-2 space-y-8">
          <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm">
            <div className="flex justify-between items-start mb-6">
              <div>
                <p className="text-sm font-semibold text-slate-500 uppercase tracking-widest">{procurement.external_reference}</p>
                <h1 className="text-3xl font-bold text-slate-900 mt-2 leading-tight">
                  {procurement.title}
                </h1>
              </div>
              <StatusBadge status={procurement.status} />
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-3 gap-6 pt-6 border-t border-slate-100">
              <div>
                <p className="text-sm text-slate-500">Organization</p>
                <div className="flex items-center gap-2 mt-1 font-medium">
                  <Building className="w-4 h-4 text-slate-400" />
                  {procurement.organization}
                </div>
              </div>
              <div>
                <p className="text-sm text-slate-500">Tender Date</p>
                <div className="flex items-center gap-2 mt-1 font-medium">
                  <Clock className="w-4 h-4 text-slate-400" />
                  {new Date(tenderDateStr).toLocaleDateString()}
                </div>
              </div>
            </div>
            
            <div className="mt-8 p-4 bg-slate-50 rounded-lg border border-slate-100">
              <p className="text-slate-700 font-medium">
                {totalBidders} bidder submissions received and {totalRequirements} technical requirements identified.
              </p>
            </div>
          </div>
          
          {/* LOWER / CENTER: Submission Readiness */}
          <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm">
            <h2 className="text-xl font-bold text-slate-900 mb-4">Submission Readiness</h2>
            
            <div className="flex items-center gap-6 mb-6">
              <div className="flex items-center gap-2 text-slate-700">
                <CheckCircle className="w-5 h-5 text-emerald-500" />
                <span className="font-medium">{totalBidders} bidders received</span>
              </div>
              <div className="flex items-center gap-2 text-slate-700">
                <CheckCircle className="w-5 h-5 text-emerald-500" />
                <span className="font-medium">{allSubmissions.length} submission packages ingested</span>
              </div>
            </div>
            
            {/* DEADLINE GATE */}
            <div className="border-t border-slate-100 pt-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-sm font-medium text-slate-500 uppercase tracking-widest">Submission Deadline</p>
                  <p className="text-lg font-bold text-slate-900">
                    {hasDeadline && deadlineDate
                      ? deadlineDate.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" })
                      : "Not established"}
                  </p>
                </div>
                {!hasDeadline ? (
                  <span className="px-3 py-1 bg-amber-50 text-amber-800 border border-amber-200 rounded text-sm font-medium">
                    Deadline unavailable. Scrutiny locked.
                  </span>
                ) : isDeadlinePassed ? (
                  <span className="px-3 py-1 bg-slate-100 text-slate-700 rounded text-sm font-medium">
                    Deadline has passed. Technical scrutiny is available.
                  </span>
                ) : (
                  <span className="px-3 py-1 bg-amber-50 text-amber-800 border border-amber-200 rounded text-sm font-medium">
                    Deadline has not passed. Scrutiny locked.
                  </span>
                )}
              </div>
              
              {processingError && (
                <div className="mb-4 p-3 bg-red-50 text-red-700 border border-red-200 rounded-md flex items-center gap-2 text-sm">
                  <AlertTriangle className="w-4 h-4" />
                  {processingError}
                </div>
              )}
              
              <button
                onClick={handleRunTechnicalScrutiny}
                disabled={!isDeadlinePassed || isProcessingAction}
                className="w-full flex items-center justify-center gap-2 bg-[#163a5f] hover:bg-[#1c4b7a] disabled:bg-slate-300 disabled:cursor-not-allowed text-white px-6 py-4 rounded-lg font-bold text-lg transition-colors"
              >
                {isProcessingAction ? (
                  <>
                    <ShieldCheck className="w-5 h-5 animate-pulse" />
                    Executing Canonical Technical Scrutiny...
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    RUN TECHNICAL SCRUTINY
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
        
        {/* RIGHT: Document Repository */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900 mb-4">Tender Documents</h2>
            {procurement.documents && procurement.documents.length > 0 ? (
              <div className="space-y-3">
                {procurement.documents.map((doc, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 rounded bg-slate-50 border border-slate-100 hover:border-slate-300 transition-colors">
                    <div className="flex items-center gap-3 overflow-hidden">
                      <FileText className="w-4 h-4 text-slate-400 shrink-0" />
                      <span className="text-sm text-slate-700 truncate">{doc.filename}</span>
                    </div>
                    {doc.storage_path && (
                      <a href={`/api/documents?path=${encodeURIComponent(doc.storage_path)}`} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 text-xs font-medium ml-2 shrink-0">
                        View
                      </a>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No tender documents available.</p>
            )}
          </div>
          
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900 mb-4">Bidder Submissions</h2>
            {procurement.tenders && procurement.tenders.length > 0 ? (
              <div className="space-y-6">
                {procurement.tenders.map((tender, tIdx) => (
                  <div key={tIdx}>
                    <p className="text-xs font-semibold text-slate-500 uppercase mb-3 border-b border-slate-100 pb-2">{tender.tender_reference}</p>
                    {tender.submissions && tender.submissions.length > 0 ? (
                      <div className="space-y-3">
                        {tender.submissions.map((sub, sIdx) => (
                          <div key={sIdx} className="p-3 rounded bg-slate-50 border border-slate-100 hover:border-slate-300 transition-colors flex flex-col gap-2">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <Building className="w-4 h-4 text-slate-400" />
                                <span className="text-sm font-medium text-slate-700">{sub.bidder?.legal_name || `Bidder ${sIdx + 1}`}</span>
                              </div>
                              <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px] font-bold uppercase">{sub.status || 'SUBMITTED'}</span>
                            </div>
                            <div className="pl-6 text-xs text-slate-500">
                              {sub.document_count || sub.documents?.length || 0} documents submitted
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-slate-500">No submissions received yet.</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No bidder data available.</p>
            )}
          </div>
        </div>
        
      </main>
    </div>
  );
}
