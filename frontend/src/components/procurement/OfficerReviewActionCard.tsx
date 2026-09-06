"use client";

import React, { useState, useEffect } from "react";
import { CheckCircle2, AlertCircle, Clock, ShieldCheck, RotateCcw } from "lucide-react";
import {
  getOfficerDecisionFor,
  saveOfficerDecision,
  clearOfficerDecision,
  subscribeToReviewDecisions,
  OfficerDecision,
  OfficerDecisionType,
} from "@/services/reviewDecisions";

interface OfficerReviewActionCardProps {
  targetId: string;
  targetTitle?: string;
  targetReference?: string;
  officerName?: string;
  className?: string;
  onDecisionChange?: (decision: OfficerDecisionType | null) => void;
}

export default function OfficerReviewActionCard({
  targetId,
  targetTitle,
  targetReference,
  officerName = "Mr. Srivastav",
  className = "",
  onDecisionChange,
}: OfficerReviewActionCardProps) {
  const [currentDecision, setCurrentDecision] = useState<OfficerDecision | null>(() =>
    targetId ? getOfficerDecisionFor(targetId) : null
  );
  const [notes, setNotes] = useState<string>(
    () => (targetId ? getOfficerDecisionFor(targetId)?.notes || "" : "")
  );
  const [showNotesInput, setShowNotesInput] = useState<boolean>(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  useEffect(() => {
    return subscribeToReviewDecisions(() => {
      if (targetId) {
        const dec = getOfficerDecisionFor(targetId);
        setCurrentDecision(dec);
        if (dec?.notes) setNotes(dec.notes);
      }
    });
  }, [targetId]);

  const handleDecision = (type: OfficerDecisionType) => {
    const dec = saveOfficerDecision(targetId, type, {
      title: targetTitle,
      reference: targetReference,
      officerName,
      notes: notes.trim() || undefined,
    });
    setCurrentDecision(dec);
    if (onDecisionChange) onDecisionChange(type);

    const msg =
      type === "CONFIRMED"
        ? "Compliance verification confirmed. Decision recorded in officer audit trail."
        : "Procurement flagged for further review & analysis. Case queued for follow-up.";
    setFeedbackMessage(msg);
    setTimeout(() => setFeedbackMessage(null), 4500);
  };

  const handleReset = () => {
    clearOfficerDecision(targetId);
    setCurrentDecision(null);
    setNotes("");
    if (onDecisionChange) onDecisionChange(null);
    setFeedbackMessage("Review status reset to pending.");
    setTimeout(() => setFeedbackMessage(null), 3000);
  };

  return (
    <div
      className={`rounded-xl border border-[#cbd9e2] bg-[#fcfdfe] p-5 sm:p-6 shadow-xs space-y-4 ${className}`}
      aria-label="Officer Verification and Review Actions"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#e1ebf0] pb-3.5">
        <div className="flex items-center gap-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-md bg-[#163a5f] text-white">
            <ShieldCheck className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[#162333]">
              Officer Verification & Compliance Determination
            </h3>
            <p className="text-[11px] text-[#5b6e7f]">
              Human-in-the-loop decision layer under statutory procurement rules.
            </p>
          </div>
        </div>

        {/* Current Determination Badge */}
        <div>
          {currentDecision?.decision === "CONFIRMED" ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-full">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              Verifications Confirmed
            </span>
          ) : currentDecision?.decision === "NEEDS_FURTHER_REVIEW" ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-amber-800 bg-amber-50 border border-amber-200 rounded-full">
              <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
              Marked: Needs Further Review
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-xs font-medium text-[#64748b] bg-[#f1f5f9] border border-[#e2e8f0] rounded-full">
              <Clock className="w-3 h-3 text-[#94a3b8]" />
              Pending Officer Determination
            </span>
          )}
        </div>
      </div>

      {/* Rationale & Action Controls */}
      <div className="space-y-3 pt-1">
        <p className="text-xs leading-relaxed text-[#4b5b6a]">
          After reviewing the compliance report, evidence observations, and statutory verifications above, record your procurement review determination:
        </p>

        {/* Primary Action Buttons */}
        <div className="flex flex-wrap items-center gap-3 pt-1">
          {/* 1. Confirm Verifications Button */}
          <button
            type="button"
            onClick={() => handleDecision("CONFIRMED")}
            className={`focus-ring inline-flex items-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-lg transition-all shadow-xs cursor-pointer ${
              currentDecision?.decision === "CONFIRMED"
                ? "bg-emerald-700 text-white ring-2 ring-emerald-600/30"
                : "bg-emerald-600 hover:bg-emerald-700 text-white"
            }`}
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Confirm Verifications</span>
          </button>

          {/* 2. Need Further Review Button */}
          <button
            type="button"
            onClick={() => handleDecision("NEEDS_FURTHER_REVIEW")}
            className={`focus-ring inline-flex items-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-lg transition-all shadow-xs cursor-pointer ${
              currentDecision?.decision === "NEEDS_FURTHER_REVIEW"
                ? "bg-amber-700 text-white ring-2 ring-amber-600/30"
                : "bg-amber-600 hover:bg-amber-700 text-white"
            }`}
          >
            <AlertCircle className="w-4 h-4" />
            <span>Need Further Review</span>
          </button>

          {/* Optional Notes Toggle & Reset */}
          <button
            type="button"
            onClick={() => setShowNotesInput(!showNotesInput)}
            className="text-xs font-medium text-[#163a5f] hover:underline px-2 py-1"
          >
            {showNotesInput ? "Hide officer notes" : "Add officer note…"}
          </button>

          {currentDecision && (
            <button
              type="button"
              onClick={handleReset}
              className="inline-flex items-center gap-1 text-[11px] text-[#64748b] hover:text-[#0f172a] ml-auto"
              title="Reset determination"
            >
              <RotateCcw className="w-3 h-3" /> Reset
            </button>
          )}
        </div>

        {/* Optional Notes Input */}
        {showNotesInput && (
          <div className="pt-2">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add review notes, clarification queries, or executive remarks for the audit trail…"
              rows={2}
              className="w-full text-xs p-2.5 rounded border border-[#cbd5e1] bg-white focus:outline-none focus:ring-1 focus:ring-[#163a5f]"
            />
          </div>
        )}

        {/* Feedback / Toast Notice */}
        {feedbackMessage && (
          <div className="p-2.5 rounded bg-[#f0fdf4] border border-[#bbf7d0] text-emerald-800 text-xs flex items-center gap-2 animate-in fade-in duration-200">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{feedbackMessage}</span>
          </div>
        )}

        {/* Recorded Timestamp Metadata */}
        {currentDecision && currentDecision.timestamp && (
          <div className="text-[10px] text-[#64748b] pt-1">
            Recorded by <strong>{currentDecision.officerName}</strong> on{" "}
            {(() => {
              try {
                const d = new Date(currentDecision.timestamp);
                return isNaN(d.getTime())
                  ? currentDecision.timestamp
                  : d.toLocaleString("en-IN", {
                      dateStyle: "medium",
                      timeStyle: "short",
                    });
              } catch {
                return currentDecision.timestamp;
              }
            })()}
          </div>
        )}
      </div>
    </div>
  );
}
