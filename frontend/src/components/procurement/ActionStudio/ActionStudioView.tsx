import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import type {
  ActionDocumentStatus,
  ActionDocumentType,
  ActionStudioAuditEvent,
  ActionStudioDocument,
  ActionStudioDocumentSummary,
  ActionStudioDocumentVersion,
  ActionStudioReadinessResponse,
} from '@/types/action-studio';
import {
  approveActionStudioDraft,
  checkActionStudioReadiness,
  createActionStudioDraft,
  getActionStudioContext,
  getActionStudioDraftDetail,
  listActionStudioAuditEvents,
  listActionStudioDrafts,
  listActionStudioVersions,
  regenerateActionStudioDraft,
  updateActionStudioDraft,
} from '@/services/api/action-studio';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock,
  Edit3,
  FileCheck,
  FileText,
  History,
  Info,
  Lock,
  RefreshCw,
  Send,
  Shield,
  ShieldCheck,
  UserCheck,
  Zap,
} from 'lucide-react';

interface ActionStudioViewProps {
  procurementId: string;
  procurementTitle?: string;
  procurementOrganization?: string;
}

const ACTION_TYPE_META: Record<
  ActionDocumentType,
  { label: string; description: string; badgeColor: string }
> = {
  EVALUATION_COMMITTEE_REPORT: {
    label: 'Evaluation Committee Report',
    description: 'Comprehensive technical and commercial evaluation report for committee sign-off.',
    badgeColor: 'bg-purple-50 text-purple-700 border-purple-200',
  },
  LETTER_OF_AWARD: {
    label: 'Letter of Award (LoA)',
    description: 'Official award notice to the lowest evaluated responsive bidder (L1).',
    badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  },
  REJECTION_LETTER: {
    label: 'Rejection Letter',
    description: 'Formal non-compliance notice citing specific technical/financial exclusion grounds.',
    badgeColor: 'bg-red-50 text-red-700 border-red-200',
  },
  REGRET_LETTER: {
    label: 'Regret Letter',
    description: 'Notice to unsuccessful bidders preserving internal reasoning confidentiality.',
    badgeColor: 'bg-amber-50 text-amber-700 border-amber-200',
  },
  NOTE_FOR_FILE: {
    label: 'Note for File',
    description: 'Governed internal record documenting procurement evaluation context and reasoning.',
    badgeColor: 'bg-blue-50 text-blue-700 border-blue-200',
  },
};

const STATUS_BADGE_STYLE: Record<ActionDocumentStatus, string> = {
  DRAFT: 'bg-slate-100 text-slate-700 border-slate-300',
  EDITED: 'bg-blue-50 text-blue-700 border-blue-200',
  READY_FOR_APPROVAL: 'bg-amber-50 text-amber-800 border-amber-200',
  APPROVED: 'bg-emerald-100 text-emerald-800 border-emerald-300 font-bold',
};

export function ActionStudioView({
  procurementId,
  procurementTitle,
  procurementOrganization,
}: ActionStudioViewProps) {
  const router = useRouter();

  // State
  const [readiness, setReadiness] = useState<ActionStudioReadinessResponse | null>(null);
  const [contextData, setContextData] = useState<Record<string, any> | null>(null);
  const [draftsList, setDraftsList] = useState<ActionStudioDocumentSummary[]>([]);
  const [auditEvents, setAuditEvents] = useState<ActionStudioAuditEvent[]>([]);
  
  const [selectedType, setSelectedType] = useState<ActionDocumentType>('NOTE_FOR_FILE');
  const [selectedTargetBidder, setSelectedTargetBidder] = useState<string>('');
  const [currentDraft, setCurrentDraft] = useState<ActionStudioDocument | null>(null);
  const [versions, setVersions] = useState<ActionStudioDocumentVersion[]>([]);
  
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Editor State
  const [editContent, setEditContent] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [changeSummary, setChangeSummary] = useState('');
  const [officerActor, setOfficerActor] = useState('HUMAN_PROCUREMENT_OFFICER');
  const [approvalNotes, setApprovalNotes] = useState('');
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [showEvidenceTraceability, setShowEvidenceTraceability] = useState(false);

  // Load initial readiness and context
  const loadWorkspaceData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const readyRes = await checkActionStudioReadiness(procurementId);
      setReadiness(readyRes);

      if (!readyRes.is_unlocked) {
        setIsLoading(false);
        return;
      }

      const [ctx, drafts, audits] = await Promise.all([
        getActionStudioContext(procurementId),
        listActionStudioDrafts(procurementId),
        listActionStudioAuditEvents(procurementId),
      ]);

      setContextData(ctx);
      setDraftsList(drafts.documents || []);
      setAuditEvents(audits || []);

      // If drafts exist, select the latest one
      if (drafts.documents && drafts.documents.length > 0) {
        const latest = drafts.documents[0];
        setSelectedType(latest.document_type);
        loadDraftDetail(latest.id);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load Action Studio workspace.');
    } finally {
      setIsLoading(false);
    }
  };

  const loadDraftDetail = async (draftId: string) => {
    try {
      setActionError(null);
      const detail = await getActionStudioDraftDetail(draftId);
      setCurrentDraft(detail);
      setEditContent(detail.content);
      setIsEditing(false);
      setSelectedType(detail.document_type);

      const vers = await listActionStudioVersions(draftId);
      setVersions(vers || []);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Failed to load draft detail.');
    }
  };

  useEffect(() => {
    if (procurementId) loadWorkspaceData();
  }, [procurementId]);

  // Excluded bidders list for target selection
  const excludedBidders = contextData?.technical?.excluded_bidders || [];
  const eligibleBidders = contextData?.technical?.technically_eligible_bidders || [];
  const l1Bidder = contextData?.financial?.l1_bidder;

  // Handle draft creation
  const handleCreateDraft = async () => {
    setIsGenerating(true);
    setActionError(null);
    try {
      const newDraft = await createActionStudioDraft(procurementId, {
        document_type: selectedType,
        target_bidder_id: selectedTargetBidder || undefined,
        created_by: officerActor,
      });

      setCurrentDraft(newDraft);
      setEditContent(newDraft.content);
      setIsEditing(false);

      // Refresh list and audit events
      const [drafts, audits] = await Promise.all([
        listActionStudioDrafts(procurementId),
        listActionStudioAuditEvents(procurementId),
      ]);
      setDraftsList(drafts.documents || []);
      setAuditEvents(audits || []);
      
      const vers = await listActionStudioVersions(newDraft.id);
      setVersions(vers || []);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Failed to generate document draft.');
    } finally {
      setIsGenerating(false);
    }
  };

  // Handle saving edits
  const handleSaveEdits = async (markReady: boolean = false) => {
    if (!currentDraft) return;
    setIsSaving(true);
    setActionError(null);
    try {
      const updated = await updateActionStudioDraft(currentDraft.id, {
        content: editContent,
        updated_by: officerActor,
        change_summary: changeSummary || (markReady ? 'Marked ready for approval.' : 'Officer text edit.'),
        mark_ready_for_approval: markReady,
      });

      setCurrentDraft(updated);
      setEditContent(updated.content);
      setIsEditing(false);
      setChangeSummary('');

      const [drafts, audits, vers] = await Promise.all([
        listActionStudioDrafts(procurementId),
        listActionStudioAuditEvents(procurementId),
        listActionStudioVersions(currentDraft.id),
      ]);
      setDraftsList(drafts.documents || []);
      setAuditEvents(audits || []);
      setVersions(vers || []);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Failed to save document edits.');
    } finally {
      setIsSaving(false);
    }
  };

  // Handle regeneration
  const handleRegenerate = async () => {
    if (!currentDraft) return;
    setIsGenerating(true);
    setActionError(null);
    try {
      const regenerated = await regenerateActionStudioDraft(currentDraft.id);
      setCurrentDraft(regenerated);
      setEditContent(regenerated.content);
      setIsEditing(false);

      const [audits, vers] = await Promise.all([
        listActionStudioAuditEvents(procurementId),
        listActionStudioVersions(currentDraft.id),
      ]);
      setAuditEvents(audits || []);
      setVersions(vers || []);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Failed to regenerate draft.');
    } finally {
      setIsGenerating(false);
    }
  };

  // Handle formal approval
  const handleApprove = async () => {
    if (!currentDraft) return;
    if (!officerActor.trim()) {
      setActionError('Valid officer identity is required for approval.');
      return;
    }

    setIsApproving(true);
    setActionError(null);
    try {
      const approved = await approveActionStudioDraft(currentDraft.id, {
        officer_actor: officerActor,
        notes: approvalNotes || 'Approved by authorized procurement officer.',
      });

      setCurrentDraft(approved);
      setIsEditing(false);

      const [drafts, audits, vers] = await Promise.all([
        listActionStudioDrafts(procurementId),
        listActionStudioAuditEvents(procurementId),
        listActionStudioVersions(currentDraft.id),
      ]);
      setDraftsList(drafts.documents || []);
      setAuditEvents(audits || []);
      setVersions(vers || []);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Failed to approve draft.');
    } finally {
      setIsApproving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-slate-300 border-t-slate-800 rounded-full animate-spin mx-auto" />
          <p className="text-sm font-medium text-slate-500">Loading Action Studio Workspace…</p>
        </div>
      </div>
    );
  }

  // Blocker Gate State
  if (readiness && !readiness.is_unlocked) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center px-6 py-12">
        <div className="max-w-lg bg-white border border-slate-200 rounded-2xl p-8 shadow-sm text-center space-y-5">
          <div className="w-12 h-12 rounded-full bg-amber-50 border border-amber-200 flex items-center justify-center mx-auto text-amber-600">
            <Lock className="w-6 h-6" />
          </div>
          <div>
            <span className="px-2.5 py-1 bg-amber-50 text-amber-800 text-[10px] font-bold uppercase tracking-wider rounded border border-amber-200">
              Entry Gate Blocked
            </span>
            <h2 className="text-xl font-bold text-slate-900 mt-2">Action Studio Unavailable</h2>
            <p className="text-sm text-slate-600 mt-2 leading-relaxed">
              Action Studio is reachable only after the financial/commercial workflow reaches its appropriate officer-confirmation readiness state.
            </p>
          </div>

          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-left text-xs space-y-2">
            <p className="font-bold text-slate-700 uppercase tracking-wider text-[10px]">Actual Backend Blocker:</p>
            <p className="text-slate-800 font-medium">{readiness.blocker_reason || 'Prerequisite evaluation steps incomplete.'}</p>
            <div className="pt-2 border-t border-slate-200 grid grid-cols-2 gap-2 text-[11px] text-slate-500">
              <div>Technical Freeze: <span className={readiness.technical_freeze_completed ? 'text-emerald-600 font-bold' : 'text-amber-600 font-bold'}>{readiness.technical_freeze_completed ? 'COMPLETE' : 'PENDING'}</span></div>
              <div>Cover 2 Financial Eval: <span className={readiness.financial_evaluation_completed ? 'text-emerald-600 font-bold' : 'text-amber-600 font-bold'}>{readiness.financial_evaluation_completed ? 'COMPLETE' : 'PENDING'}</span></div>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            <button
              onClick={() => router.push(`/procurements/${procurementId}/financial-evaluation`)}
              className="w-full inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-[#0f172a] hover:bg-[#1e293b] text-white text-xs font-medium rounded-full transition-colors"
            >
              Return to Financial Scrutiny <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center px-6">
        <div className="max-w-md bg-white p-8 rounded-xl border border-slate-200 text-center space-y-4">
          <AlertTriangle className="w-8 h-8 text-red-500 mx-auto" />
          <h3 className="font-bold text-slate-800 text-base">Error Loading Action Studio</h3>
          <p className="text-xs text-slate-500">{error}</p>
          <button onClick={loadWorkspaceData} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium rounded-full">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-[#0f172a] font-sans flex flex-col">
      {/* Header (Phase 2) */}
      <header className="sticky top-0 z-20 bg-white/95 backdrop-blur-md border-b border-slate-200 py-4 px-6 sm:px-8">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest bg-slate-100 text-slate-600 uppercase">
                {procurementId.slice(0, 10)}
              </span>
              <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">
                Action Studio · Governed Workspace
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-50 text-emerald-700 border border-emerald-200">
                Commercial Review Complete
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#0f172a] truncate">
              {procurementTitle || contextData?.title || `Procurement ${procurementId.slice(0, 8)}`}
            </h1>
            <div className="flex flex-wrap items-center gap-4 mt-1 text-xs text-slate-500">
              <span>{procurementOrganization || contextData?.organization || 'Central Agency'}</span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Technical Freeze Verified
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Financial Cover 2 Evaluated
              </span>
              {l1Bidder && (
                <>
                  <span>•</span>
                  <span className="font-medium text-slate-700">L1: {l1Bidder.bidder_name}</span>
                </>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <div className="px-3 py-1.5 bg-slate-100 border border-slate-200 rounded-full flex items-center gap-2 text-xs">
              <UserCheck className="w-3.5 h-3.5 text-slate-600" />
              <span className="font-medium text-slate-700">{officerActor}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-6 sm:px-8 py-8 flex-1 w-full grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Column: Action Type Selector & Drafts Navigation (Phase 3 & Phase 19) */}
        <div className="lg:col-span-4 space-y-6">
          
          {/* Action Type Selection */}
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Select Official Action</h2>
              <p className="text-xs text-slate-500 mt-0.5">Prepare governed procurement document</p>
            </div>

            <div className="space-y-2">
              {(Object.keys(ACTION_TYPE_META) as ActionDocumentType[]).map((typeKey) => {
                const meta = ACTION_TYPE_META[typeKey];
                const existingDrafts = draftsList.filter((d) => d.document_type === typeKey);
                const isSelected = selectedType === typeKey;

                return (
                  <div
                    key={typeKey}
                    onClick={() => {
                      setSelectedType(typeKey);
                      if (existingDrafts.length > 0) {
                        loadDraftDetail(existingDrafts[0].id);
                      }
                    }}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'border-slate-800 bg-slate-900/5 shadow-sm'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase border ${meta.badgeColor}`}>
                          {meta.label}
                        </span>
                        <p className="text-xs font-semibold text-slate-800 mt-1.5">{meta.label}</p>
                        <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">{meta.description}</p>
                      </div>
                      {existingDrafts.length > 0 && (
                        <span className="px-2 py-0.5 bg-slate-200 text-slate-700 text-[10px] font-bold rounded-full shrink-0">
                          {existingDrafts.length} draft{existingDrafts.length > 1 ? 's' : ''}
                        </span>
                      )}
                    </div>

                    {/* Show existing draft status chips */}
                    {existingDrafts.length > 0 && (
                      <div className="mt-2.5 pt-2 border-t border-slate-100 flex flex-wrap gap-1.5">
                        {existingDrafts.map((d) => (
                          <button
                            key={d.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              loadDraftDetail(d.id);
                            }}
                            className={`px-2 py-0.5 text-[10px] font-medium rounded border ${STATUS_BADGE_STYLE[d.status]} ${
                              currentDraft?.id === d.id ? 'ring-1 ring-slate-800 font-bold' : ''
                            }`}
                          >
                            v{d.version} · {d.status}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Target Bidder Selector for Rejection/Regret */}
            {(selectedType === 'REJECTION_LETTER' || selectedType === 'REGRET_LETTER') && (
              <div className="pt-2 border-t border-slate-100 space-y-2">
                <label className="text-xs font-bold text-slate-700 block">Target Excluded Bidder:</label>
                <select
                  value={selectedTargetBidder}
                  onChange={(e) => setSelectedTargetBidder(e.target.value)}
                  className="w-full text-xs p-2.5 bg-slate-50 border border-slate-300 rounded-lg text-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-800"
                >
                  <option value="">-- Select Target Bidder --</option>
                  {excludedBidders.map((b: any) => (
                    <option key={b.bidder_id} value={b.bidder_id}>
                      {b.legal_name} (Excluded)
                    </option>
                  ))}
                  {eligibleBidders.map((b: any) => (
                    <option key={b.bidder_id} value={b.bidder_id}>
                      {b.legal_name} (Eligible)
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Create / Prepare Draft Button */}
            <button
              disabled={isGenerating}
              onClick={handleCreateDraft}
              className="w-full inline-flex items-center justify-center gap-2 py-3 bg-[#0f172a] hover:bg-[#1e293b] text-white text-xs font-medium rounded-xl transition-colors shadow-sm disabled:opacity-50"
            >
              {isGenerating ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Generating Draft…
                </>
              ) : (
                <>
                  <Zap className="w-3.5 h-3.5" />
                  Prepare Draft Document
                </>
              )}
            </button>
          </div>

          {/* Source Context Summary Card (Phase 4 & Phase 12) */}
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">Canonical Source Context</h3>
              <button
                onClick={() => setShowEvidenceTraceability(!showEvidenceTraceability)}
                className="text-[11px] text-blue-600 hover:text-blue-800 font-medium"
              >
                {showEvidenceTraceability ? 'Hide Evidence' : 'Show Evidence'}
              </button>
            </div>

            <div className="text-xs space-y-2 text-slate-600 leading-relaxed">
              <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                <span className="font-semibold text-slate-800">Procurement Ref:</span> {contextData?.external_reference || procurementId}
              </div>
              <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                <span className="font-semibold text-slate-800">Technical Qualification:</span> {eligibleBidders.length} Qualified, {excludedBidders.length} Excluded
              </div>
              {l1Bidder && (
                <div className="p-2.5 bg-emerald-50 rounded-lg border border-emerald-100 text-emerald-900">
                  <span className="font-bold">L1 Position:</span> {l1Bidder.bidder_name} (INR {l1Bidder.evaluated_amount?.toLocaleString('en-IN')})
                </div>
              )}
            </div>

            {/* Traceability List */}
            {showEvidenceTraceability && currentDraft?.evidence_references && (
              <div className="mt-3 pt-3 border-t border-slate-100 space-y-2 max-h-48 overflow-y-auto">
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Traceable Findings:</p>
                {currentDraft.evidence_references.map((ref, idx) => (
                  <div key={idx} className="p-2 bg-slate-50 rounded border border-slate-100 text-[11px] space-y-0.5">
                    <span className="font-mono text-slate-500 font-bold">{ref.requirement_id || 'REVISION'}</span>
                    <p className="text-slate-700">{ref.quote || ref.provenance_summary}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Audit History Panel (Phase 17 & Phase 18) */}
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-3">
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
              <History className="w-3.5 h-3.5 text-slate-500" /> Action Audit Trail
            </h3>
            {auditEvents.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No audit events recorded yet.</p>
            ) : (
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {auditEvents.map((evt) => (
                  <div key={evt.id} className="p-2.5 bg-slate-50 rounded-lg border border-slate-100 text-[11px]">
                    <div className="flex items-center justify-between font-bold text-slate-800">
                      <span>{evt.event_type}</span>
                      <span className="text-[10px] font-normal text-slate-400">
                        {new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <p className="text-slate-500 text-[10px] mt-0.5">Actor: {evt.actor} · v{evt.version}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Dominant Object — THE ACTION DOCUMENT WORKSPACE */}
        <div className="lg:col-span-8 space-y-6">
          
          {actionError && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-500 shrink-0" />
              <span>{actionError}</span>
            </div>
          )}

          {!currentDraft ? (
            <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center space-y-4">
              <FileText className="w-10 h-10 text-slate-300 mx-auto" />
              <h3 className="text-base font-bold text-slate-800">No Action Document Selected</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
                Select an official document type from the left panel and click &ldquo;Prepare Draft Document&rdquo; to generate an evidence-grounded action draft for officer review.
              </p>
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden flex flex-col">
              
              {/* Document Workspace Header (Phase 2 & Phase 10) */}
              <div className="p-6 border-b border-slate-200 bg-slate-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${ACTION_TYPE_META[currentDraft.document_type].badgeColor}`}>
                      {ACTION_TYPE_META[currentDraft.document_type].label}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${STATUS_BADGE_STYLE[currentDraft.status]}`}>
                      Status: {currentDraft.status.replace(/_/g, ' ')}
                    </span>
                    <span className="text-xs font-mono text-slate-400">
                      Version {currentDraft.version}
                    </span>
                  </div>
                  <h2 className="text-lg font-bold text-slate-900">{currentDraft.title}</h2>
                </div>

                {/* Top Document Actions */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowVersionHistory(!showVersionHistory)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-medium rounded-full"
                  >
                    <History className="w-3.5 h-3.5" /> History ({versions.length})
                  </button>

                  {currentDraft.status !== 'APPROVED' && (
                    <button
                      disabled={isGenerating}
                      onClick={handleRegenerate}
                      className="inline-flex items-center gap-1 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-medium rounded-full disabled:opacity-50"
                    >
                      <RefreshCw className="w-3.5 h-3.5" /> Regenerate
                    </button>
                  )}
                </div>
              </div>

              {/* Version History Drawer */}
              {showVersionHistory && (
                <div className="p-4 bg-slate-100 border-b border-slate-200 space-y-2">
                  <p className="text-xs font-bold text-slate-700 uppercase tracking-wider">Version History Snapshots:</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {versions.map((v) => (
                      <div key={v.id} className="p-3 bg-white border border-slate-200 rounded-lg text-xs space-y-1">
                        <div className="flex justify-between font-bold text-slate-800">
                          <span>Version {v.version} ({v.status})</span>
                          <span className="text-[10px] text-slate-400">{new Date(v.updated_at).toLocaleDateString()}</span>
                        </div>
                        <p className="text-slate-600 text-[11px]">{v.change_summary || 'No summary provided.'}</p>
                        <p className="text-[10px] text-slate-400">By: {v.updated_by}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Governance & AI Attribution Label (Phase 13 & Phase 20) */}
              <div className="px-6 py-2.5 bg-amber-50/70 border-b border-amber-200/60 flex items-center justify-between text-xs text-amber-900">
                <div className="flex items-center gap-2">
                  <Info className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>
                    {currentDraft.is_ai_generated
                      ? 'Draft prepared from canonical context with Opal assistance. Review before approval.'
                      : 'Draft prepared from canonical evidence context (Deterministic Fallback). Review before approval.'}
                  </span>
                </div>
                <span className="font-bold text-[10px] uppercase tracking-wider text-amber-800 shrink-0">
                  Decision Authority: {currentDraft.decision_authority}
                </span>
              </div>

              {/* Document Editor & View Area (Phase 11) */}
              <div className="p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Document Body Content</span>
                  
                  {currentDraft.status !== 'APPROVED' && (
                    <button
                      onClick={() => setIsEditing(!isEditing)}
                      className="inline-flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 font-semibold"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                      {isEditing ? 'Cancel Edit Mode' : 'Edit Document Text'}
                    </button>
                  )}
                </div>

                {isEditing ? (
                  <div className="space-y-3">
                    <textarea
                      rows={18}
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      className="w-full font-mono text-xs p-4 bg-slate-900 text-slate-100 rounded-xl border border-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 leading-relaxed"
                    />
                    <div className="flex items-center gap-3">
                      <input
                        type="text"
                        placeholder="Optional change summary (e.g. Refined legal clause wording)"
                        value={changeSummary}
                        onChange={(e) => setChangeSummary(e.target.value)}
                        className="flex-1 text-xs p-2.5 bg-slate-50 border border-slate-300 rounded-lg text-slate-800 focus:outline-none"
                      />
                      <button
                        disabled={isSaving}
                        onClick={() => handleSaveEdits(false)}
                        className="px-4 py-2.5 bg-slate-800 hover:bg-slate-900 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                      >
                        {isSaving ? 'Saving…' : 'Save Draft Edits'}
                      </button>
                      <button
                        disabled={isSaving}
                        onClick={() => handleSaveEdits(true)}
                        className="px-4 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                      >
                        Mark Ready for Approval
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="p-6 bg-slate-50 border border-slate-200 rounded-xl max-h-[500px] overflow-y-auto font-mono text-xs text-slate-800 leading-relaxed whitespace-pre-wrap">
                    {currentDraft.content}
                  </div>
                )}
              </div>

              {/* Approval & Dispatch Governance Boundary Section (Phase 15 & Phase 16) */}
              <div className="p-6 bg-slate-100 border-t border-slate-200 space-y-6">
                
                {/* Approval Control Box */}
                {currentDraft.status !== 'APPROVED' ? (
                  <div className="p-5 bg-white border border-slate-300 rounded-xl space-y-4 shadow-sm">
                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-600" /> Human Officer Action Approval
                    </h3>
                    <p className="text-xs text-slate-600 leading-relaxed">
                      Approval is an explicit governance action. Approving converts this draft into an official action record and locks it from further content edits.
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] font-bold text-slate-700 block mb-1">Approving Officer Identity:</label>
                        <input
                          type="text"
                          value={officerActor}
                          onChange={(e) => setOfficerActor(e.target.value)}
                          className="w-full text-xs p-2.5 bg-slate-50 border border-slate-300 rounded-lg font-medium text-slate-800"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] font-bold text-slate-700 block mb-1">Approval Notes / Remarks:</label>
                        <input
                          type="text"
                          placeholder="Committee approval reference / officer remarks"
                          value={approvalNotes}
                          onChange={(e) => setApprovalNotes(e.target.value)}
                          className="w-full text-xs p-2.5 bg-slate-50 border border-slate-300 rounded-lg text-slate-800"
                        />
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-2">
                      <span className="text-[11px] text-slate-500 font-medium">
                        Current Status: <strong className="text-slate-800">{currentDraft.status}</strong>
                      </span>
                      <button
                        disabled={isApproving}
                        onClick={handleApprove}
                        className="inline-flex items-center gap-2 px-6 py-2.5 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold rounded-full transition-colors shadow-sm disabled:opacity-50"
                      >
                        {isApproving ? (
                          <>
                            <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            Approving…
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="w-4 h-4" />
                            APPROVE ACTION DOCUMENT
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="p-5 bg-emerald-50 border border-emerald-200 rounded-xl space-y-2">
                    <div className="flex items-center gap-2 text-emerald-900 font-bold text-sm">
                      <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                      OFFICIALLY APPROVED DOCUMENT
                    </div>
                    <p className="text-xs text-emerald-800">
                      Approved by <strong>{currentDraft.approved_by}</strong> on{' '}
                      {currentDraft.approved_at
                        ? new Date(currentDraft.approved_at).toLocaleString()
                        : 'Record Saved'}
                    </p>
                  </div>
                )}

                {/* Dispatch Boundary Card (Phase 16) */}
                <div className="p-4 bg-slate-200/70 border border-slate-300 rounded-xl text-xs space-y-1.5">
                  <div className="flex items-center gap-2 font-bold text-slate-800">
                    <Send className="w-4 h-4 text-slate-600" />
                    <span>Dispatch Boundary Notice</span>
                  </div>
                  <p className="text-slate-600 leading-relaxed">
                    {currentDraft.status === 'APPROVED'
                      ? 'Approved — External dispatch to GeM or official channels is not connected in this prototype. The document is stored in audit history.'
                      : 'Approval is NOT external dispatch. Once approved, the document reaches the external dispatch boundary.'}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
