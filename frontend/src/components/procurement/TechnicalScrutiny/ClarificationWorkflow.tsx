"use client";

import React, { useState, useCallback } from 'react';
import type { CheckResult } from '@/types/technical-review';
import type { ClarificationRecord } from '@/types/clarification';
import {
  createClarification,
  getDraftClarification,
  respondToClarification,
  reEvaluateClarification,
  resolveClarification,
} from '@/services/api/clarifications';
import {
  X,
  ArrowRight,
  Sparkles,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  Clock,
  FileText,
  ChevronDown,
  ChevronUp,
  Info,
} from 'lucide-react';

interface ClarificationWorkflowProps {
  check: CheckResult;
  bidderName: string;
  bidderSubmissionId: string;
  procurementId: string;
  /** Called when the workflow should be dismissed */
  onClose: () => void;
  /** Called when re-evaluation completes — parent should refresh canonical review */
  onReEvaluationComplete: () => void;
}

// ---------------------------------------------------------------------------
// Clarification status presentation
// ---------------------------------------------------------------------------
const STATUS_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  OPEN:                          { label: 'Open — Awaiting bidder response',        color: 'text-blue-700',   bg: 'bg-blue-50 border-blue-200' },
  RESPONDED:                     { label: 'Bidder responded',                        color: 'text-amber-700',  bg: 'bg-amber-50 border-amber-200' },
  UNDER_REVIEW:                  { label: 'Officer reviewing response',              color: 'text-amber-700',  bg: 'bg-amber-50 border-amber-200' },
  RESOLVED:                      { label: 'Resolved',                               color: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-200' },
  REQUIRES_FURTHER_CLARIFICATION:{ label: 'Further clarification requested',         color: 'text-amber-700',  bg: 'bg-amber-50 border-amber-200' },
  EXPIRED:                       { label: 'Response deadline expired',               color: 'text-red-700',    bg: 'bg-red-50 border-red-200' },
  CANCELLED:                     { label: 'Cancelled',                              color: 'text-slate-600',   bg: 'bg-slate-50 border-slate-200' },
  REJECTED:                      { label: 'Representation rejected — finding retained', color: 'text-red-700', bg: 'bg-red-50 border-red-200' },
};

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_LABELS[status] ?? { label: status, color: 'text-slate-600', bg: 'bg-slate-50 border-slate-200' };
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-[11px] font-bold tracking-wider border ${cfg.bg} ${cfg.color}`}>
      {cfg.label}
    </span>
  );
}

function SectionLabel({ label }: { label: string }) {
  return (
    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">{label}</p>
  );
}

type Step = 'CREATE' | 'OPEN' | 'RESPOND' | 'REVIEW' | 'REEVALUATE' | 'DONE';

/**
 * ClarificationWorkflow
 *
 * The full officer-facing Shortfall & Representation review surface.
 *
 * Lifecycle:
 * CREATE → OPEN → (bidder responds) → RESPOND → REVIEW → (officer action):
 *   - Accept & Re-evaluate → REEVALUATE → backend re-evaluation → DONE
 *   - Require Further → back to OPEN
 *   - Reject / Retain → DONE (finding unchanged)
 *
 * CRITICAL: No action in this component directly mutates PASS/FAIL/REVIEW/UNVERIFIED.
 * Re-evaluation goes through the canonical backend evaluator.
 * The parent component is responsible for refreshing canonical state after completion.
 */
export function ClarificationWorkflow({
  check,
  bidderName,
  bidderSubmissionId,
  procurementId,
  onClose,
  onReEvaluationComplete,
}: ClarificationWorkflowProps) {
  const [step, setStep] = useState<Step>('CREATE');
  const [clarification, setClarification] = useState<ClarificationRecord | null>(null);
  const [questionText, setQuestionText] = useState('');
  const [responseText, setResponseText] = useState('');
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [isDraftLoading, setIsDraftLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAuditHistory, setShowAuditHistory] = useState(false);
  const [reEvalResult, setReEvalResult] = useState<ClarificationRecord | null>(null);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleGetDraft = useCallback(async () => {
    setIsDraftLoading(true);
    setError(null);
    try {
      const draft = await getDraftClarification(procurementId, {
        procurementId,
        submissionId: bidderSubmissionId,
        requirementId: check.id,
        originatingFindingId: check.id,
      });
      // Pre-fill the question with the draft — officer must review and edit
      setQuestionText(draft.requestedClarification || draft.observedShortfall || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not generate draft wording.');
    } finally {
      setIsDraftLoading(false);
    }
  }, [procurementId, bidderSubmissionId, check.id]);

  const handleCreateClarification = useCallback(async () => {
    if (!questionText.trim()) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const record = await createClarification(procurementId, {
        submissionId: bidderSubmissionId,
        requirementId: check.id,
        originatingFindingId: check.id,
        question: questionText.trim(),
      });
      setClarification(record);
      setStep('OPEN');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create clarification.');
    } finally {
      setIsSubmitting(false);
    }
  }, [procurementId, bidderSubmissionId, check.id, questionText]);

  const handleSubmitResponse = useCallback(async () => {
    if (!clarification || !responseText.trim()) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const updated = await respondToClarification(procurementId, clarification.id, {
        responseText: responseText.trim(),
        respondedBy: 'BIDDER',
      });
      setClarification(updated);
      setStep('REVIEW');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit response.');
    } finally {
      setIsSubmitting(false);
    }
  }, [procurementId, clarification, responseText]);

  const handleReEvaluate = useCallback(async () => {
    if (!clarification) return;
    setIsSubmitting(true);
    setError(null);
    try {
      // The ONLY path that can change the underlying technical finding.
      // Backend runs the canonical verification engine.
      const result = await reEvaluateClarification(procurementId, clarification.id);
      setReEvalResult(result);
      setClarification(result);
      setStep('DONE');
      // Notify parent to refresh canonical technical review
      onReEvaluationComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Re-evaluation failed.');
    } finally {
      setIsSubmitting(false);
    }
  }, [procurementId, clarification, onReEvaluationComplete]);

  const handleRequireFurther = useCallback(async () => {
    if (!clarification) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const updated = await resolveClarification(procurementId, clarification.id, {
        resolutionStatus: 'REQUIRES_FURTHER_CLARIFICATION',
        resolutionNotes: resolutionNotes.trim() || undefined,
      });
      setClarification(updated);
      setStep('OPEN'); // Back to waiting for response
      setResponseText('');
      setResolutionNotes('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to request further clarification.');
    } finally {
      setIsSubmitting(false);
    }
  }, [procurementId, clarification, resolutionNotes]);

  const handleRejectRepresentation = useCallback(async () => {
    if (!clarification) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const updated = await resolveClarification(procurementId, clarification.id, {
        resolutionStatus: 'REJECTED',
        resolutionNotes: resolutionNotes.trim() || 'Representation rejected; original finding retained.',
      });
      setClarification(updated);
      setStep('DONE');
      // Note: finding is NOT changed. The canonical FAIL/REVIEW remains.
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to record rejection.');
    } finally {
      setIsSubmitting(false);
    }
  }, [procurementId, clarification, resolutionNotes]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="border border-slate-200 rounded-xl bg-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50">
        <div>
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
            Shortfall & Representation
          </p>
          <h3 className="text-sm font-bold text-slate-800 mt-0.5">{check.description}</h3>
          <p className="text-xs text-slate-500 mt-0.5">{bidderName}</p>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 text-slate-400 hover:text-slate-700 rounded-full hover:bg-slate-100 transition-colors"
          title="Close"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Original finding context — always visible */}
      <div className="px-5 py-4 border-b border-slate-100 grid grid-cols-1 sm:grid-cols-3 gap-4">
        {check.requirement && (
          <div>
            <SectionLabel label="Requirement" />
            <p className="text-xs text-slate-700 leading-relaxed">{check.requirement}</p>
          </div>
        )}
        {check.evidence && (
          <div>
            <SectionLabel label="Original Evidence" />
            <p className="text-xs text-slate-700 leading-relaxed">{check.evidence}</p>
          </div>
        )}
        <div>
          <SectionLabel label="Original Finding" />
          <p className="text-xs text-slate-700 leading-relaxed">
            {check.finding || check.synthesis || 'See status.'}
          </p>
          <span className={`mt-1.5 inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold tracking-wider
            ${check.status === 'FAIL' ? 'bg-red-50 text-red-700 border border-red-200'
            : check.status === 'REVIEW' ? 'bg-amber-50 text-amber-700 border border-amber-200'
            : 'bg-slate-50 text-slate-600 border border-slate-200'}`}
          >
            {check.status}
          </span>
        </div>
      </div>

      {/* Workflow body */}
      <div className="px-5 py-5 space-y-5">

        {/* Error display */}
        {error && (
          <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* ================================================================ */}
        {/* STEP: CREATE — Compose clarification request                      */}
        {/* ================================================================ */}
        {step === 'CREATE' && (
          <div className="space-y-4">
            <div>
              <SectionLabel label="Clarification Request" />
              <div className="flex items-start justify-between mb-2">
                <p className="text-xs text-slate-500 leading-relaxed max-w-lg">
                  Compose a formal clarification request to the bidder. You may request suggested
                  wording from Opal, which you must review and edit before sending.
                </p>
                <button
                  onClick={handleGetDraft}
                  disabled={isDraftLoading}
                  className="shrink-0 ml-4 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-full transition-colors disabled:opacity-50"
                >
                  {isDraftLoading ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5" />
                  )}
                  Suggest wording
                </button>
              </div>
              {isDraftLoading && (
                <p className="text-[11px] text-slate-400 italic mb-2">
                  Generating suggested wording — this is a draft you must review and edit before sending.
                </p>
              )}
              <textarea
                value={questionText}
                onChange={(e) => setQuestionText(e.target.value)}
                placeholder="Describe the shortfall and the specific evidence or documentation required from the bidder…"
                className="w-full text-sm p-3 border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-slate-300 min-h-[120px] resize-y placeholder:text-slate-300"
                disabled={isSubmitting}
              />
              {questionText && isDraftLoading === false && (
                <div className="flex items-center gap-1.5 mt-1.5">
                  <Info className="w-3 h-3 text-slate-400" />
                  <p className="text-[11px] text-slate-400">
                    Review and edit the text above before creating the clarification request.
                  </p>
                </div>
              )}
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleCreateClarification}
                disabled={!questionText.trim() || isSubmitting}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0f172a] hover:bg-[#1e293b] text-white text-sm font-medium rounded-full transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {isSubmitting ? 'Creating…' : 'Create Clarification Request'}
                {!isSubmitting && <ArrowRight className="w-4 h-4" />}
              </button>
              <button onClick={onClose} className="text-sm text-slate-400 hover:text-slate-600">
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* STEP: OPEN — Clarification created, awaiting bidder response      */}
        {/* ================================================================ */}
        {(step === 'OPEN' || step === 'RESPOND') && clarification && (
          <div className="space-y-5">
            {/* Clarification record */}
            <div className="p-4 bg-slate-50 border border-slate-100 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <SectionLabel label="Clarification Request" />
                  <p className="text-sm text-slate-700 leading-relaxed">{clarification.question}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 flex-wrap">
                <StatusBadge status={clarification.status} />
                <span className="text-xs text-slate-400 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  Created {new Date(clarification.createdAt).toLocaleString()}
                </span>
                {clarification.dueAt && (
                  <span className="text-xs text-amber-600 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    Due {new Date(clarification.dueAt).toLocaleString()}
                  </span>
                )}
              </div>
            </div>

            {/* Bidder response input (demo mode: officer submits on behalf for testing) */}
            {step === 'OPEN' && (
              <div>
                <SectionLabel label="Bidder Response" />
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg mb-3">
                  <p className="text-xs text-blue-700 leading-relaxed">
                    In production, bidders submit responses through the bidder portal.
                    During development, you may record a response here to advance the lifecycle.
                  </p>
                </div>
                <textarea
                  value={responseText}
                  onChange={(e) => setResponseText(e.target.value)}
                  placeholder="Bidder response text…"
                  className="w-full text-sm p-3 border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-slate-300 min-h-[90px] resize-y placeholder:text-slate-300"
                  disabled={isSubmitting}
                />
                <button
                  onClick={handleSubmitResponse}
                  disabled={!responseText.trim() || isSubmitting}
                  className="mt-3 inline-flex items-center gap-2 px-5 py-2.5 bg-[#0f172a] hover:bg-[#1e293b] text-white text-sm font-medium rounded-full transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? 'Submitting…' : 'Record Bidder Response'}
                  {!isSubmitting && <ArrowRight className="w-4 h-4" />}
                </button>
              </div>
            )}
          </div>
        )}

        {/* ================================================================ */}
        {/* STEP: REVIEW — Response received, officer adequacy review         */}
        {/* ================================================================ */}
        {step === 'REVIEW' && clarification && (
          <div className="space-y-5">
            {/* Status */}
            <StatusBadge status={clarification.status} />

            {/* Bidder response */}
            <div>
              <SectionLabel label="Bidder Response" />
              <div className="p-4 bg-slate-50 border border-slate-100 rounded-lg">
                <p className="text-sm text-slate-700 leading-relaxed">
                  {clarification.responseText || '(No text provided)'}
                </p>
                {clarification.respondedAt && (
                  <p className="text-xs text-slate-400 mt-2 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    Responded {new Date(clarification.respondedAt).toLocaleString()}
                  </p>
                )}
              </div>
            </div>

            {/* Response documents */}
            {clarification.responseDocuments.length > 0 ? (
              <div>
                <SectionLabel label="Response Evidence" />
                <div className="space-y-2">
                  {clarification.responseDocuments.map((doc, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-3 p-3 border border-slate-100 rounded-lg bg-white"
                    >
                      <FileText className="w-4 h-4 text-slate-400 shrink-0" />
                      <div>
                        <p className="text-sm text-slate-700 font-medium">{doc.filename}</p>
                        {doc.document_type && (
                          <p className="text-xs text-slate-400">{doc.document_type}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="p-3 bg-slate-50 border border-slate-100 rounded-lg">
                <p className="text-xs text-slate-400 italic">
                  No additional documents were attached with this response.
                </p>
              </div>
            )}

            {/* Opal assessment — if backend provides re_evaluation_status */}
            {clarification.reEvaluationStatus && (
              <div>
                <SectionLabel label="Opal Assessment" />
                <div className="p-3 bg-slate-50 border border-slate-100 rounded-lg">
                  <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wider mb-1">
                    Evidence Assessment — Analytical Aid Only
                  </p>
                  <p className="text-sm text-slate-700">{clarification.reEvaluationStatus}</p>
                  <p className="text-[10px] text-slate-400 italic mt-2">
                    This assessment does not alter the compliance finding. Only canonical re-evaluation
                    through the verification engine can change the underlying finding.
                  </p>
                </div>
              </div>
            )}

            {/* Officer resolution notes */}
            <div>
              <SectionLabel label="Officer Resolution Notes (optional)" />
              <textarea
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
                placeholder="Record rationale for the action taken…"
                className="w-full text-sm p-3 border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-slate-300 min-h-[80px] resize-y placeholder:text-slate-300"
                disabled={isSubmitting}
              />
            </div>

            {/* Officer action buttons */}
            <div className="space-y-3">
              <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Officer Action</p>
              <div className="flex flex-wrap gap-3">
                {/* Submit response and trigger canonical re-evaluation */}
                <button
                  onClick={handleReEvaluate}
                  disabled={isSubmitting}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0f172a] hover:bg-[#1e293b] text-white text-sm font-medium rounded-full transition-colors disabled:opacity-40"
                >
                  {isSubmitting ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                  Submit Response for Re-Evaluation
                </button>

                {/* Require further clarification */}
                <button
                  onClick={handleRequireFurther}
                  disabled={isSubmitting}
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-full transition-colors disabled:opacity-40"
                >
                  Require Further Clarification
                </button>

                {/* Reject representation — finding is NOT changed by this action */}
                <button
                  onClick={handleRejectRepresentation}
                  disabled={isSubmitting}
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-slate-200 hover:bg-red-50 hover:text-red-700 hover:border-red-200 text-slate-600 text-sm font-medium rounded-full border border-slate-200 transition-colors disabled:opacity-40"
                >
                  Reject Representation / Retain Finding
                </button>
              </div>
              <p className="text-[11px] text-slate-400 italic">
                "Submit Response for Re-Evaluation" invokes the canonical verification engine.
                "Reject Representation" retains the original finding unchanged.
                No action here directly changes PASS / FAIL / REVIEW / UNVERIFIED.
              </p>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* STEP: DONE — Outcome                                             */}
        {/* ================================================================ */}
        {step === 'DONE' && clarification && (
          <div className="space-y-5">
            <StatusBadge status={clarification.status} />

            {clarification.status === 'REJECTED' && (
              <div className="p-4 bg-slate-50 border border-slate-100 rounded-lg">
                <p className="text-sm text-slate-700 font-medium">Representation rejected.</p>
                <p className="text-sm text-slate-600 mt-1">
                  The original finding is retained. No compliance state was changed through this workflow.
                </p>
              </div>
            )}

            {reEvalResult && (
              <div className="space-y-3">
                <div>
                  <SectionLabel label="Re-Evaluation Result" />
                  <div className="p-4 bg-slate-50 border border-slate-100 rounded-lg">
                    {reEvalResult.resultingFinding ? (
                      <div>
                        <p className="text-[11px] text-slate-400 uppercase tracking-wider mb-2">
                          Updated Finding — from Canonical Re-Evaluation
                        </p>
                        <p className="text-sm font-bold text-slate-800">
                          Status:{' '}
                          {String((reEvalResult.resultingFinding as Record<string, unknown>).state ||
                            (reEvalResult.resultingFinding as Record<string, unknown>).status || 'See backend')}
                        </p>
                        {(reEvalResult.resultingFinding as Record<string, unknown>).reason && (
                          <p className="text-sm text-slate-600 mt-1">
                            {String((reEvalResult.resultingFinding as Record<string, unknown>).reason)}
                          </p>
                        )}
                        <div className="mt-3 flex items-center gap-1.5">
                          <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
                          <p className="text-[11px] text-emerald-700 font-medium">
                            Finding updated through canonical verification engine.
                            Technical review has been refreshed.
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div>
                        <p className="text-sm text-slate-600">
                          Re-evaluation completed. The technical review has been refreshed with the
                          latest canonical findings. Check the updated Technical Completion section.
                        </p>
                        <div className="mt-2 flex items-center gap-1.5">
                          <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
                          <p className="text-[11px] text-emerald-700 font-medium">
                            Canonical state refreshed.
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            <button
              onClick={onClose}
              className="inline-flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-full transition-colors"
            >
              Close
            </button>
          </div>
        )}

        {/* Audit history — collapsible, always available once clarification exists */}
        {clarification && clarification.auditHistory.length > 0 && (
          <div className="mt-4 border-t border-slate-100 pt-4">
            <button
              onClick={() => setShowAuditHistory((v) => !v)}
              className="flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-slate-700 transition-colors"
            >
              {showAuditHistory ? (
                <ChevronUp className="w-3.5 h-3.5" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5" />
              )}
              Audit History ({clarification.auditHistory.length} events)
            </button>

            {showAuditHistory && (
              <div className="mt-3 space-y-2">
                {clarification.auditHistory.map((entry, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 p-2.5 rounded-lg bg-slate-50 border border-slate-100 text-xs"
                  >
                    <div className="shrink-0 mt-0.5">
                      <div className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-bold text-slate-700">{entry.event}</p>
                      {entry.detail && (
                        <p className="text-slate-500 mt-0.5 leading-relaxed">{entry.detail}</p>
                      )}
                      <div className="flex items-center gap-3 mt-1 text-slate-400">
                        {entry.actor && <span>{entry.actor}</span>}
                        <span>{new Date(entry.timestamp).toLocaleString()}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
