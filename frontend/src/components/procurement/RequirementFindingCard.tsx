import React, { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  FileText,
  ShieldAlert,
  HelpCircle,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Scale,
  Sparkles,
  Info,
} from "lucide-react";
import {
  RequirementEvaluationResult,
  EvaluationMethod,
  RiskLevel,
  ProvenanceRecord,
} from "@/types/procurement";
import ComplianceStateBadge from "./ComplianceStateBadge";
import EvidenceReference from "./EvidenceReference";
import EvidenceComparison from "./EvidenceComparison";
import AmbiguityNotice from "./AmbiguityNotice";

interface RequirementFindingCardProps {
  result: RequirementEvaluationResult;
  onInspectEvidence?: (record: ProvenanceRecord) => void;
  defaultExpanded?: boolean;
}

/**
 * Maps backend EvaluationMethod enum to readable human label
 */
function getEvaluationMethodLabel(method: EvaluationMethod | string): string {
  const norm = String(method || "").toUpperCase();
  switch (norm) {
    case "DETERMINISTIC":
      return "Deterministic Rule";
    case "CONTRADICTION_RECONCILIATION":
      return "Cross-Document Reconciliation";
    case "DOCUMENT_PRESENCE":
      return "Document Presence";
    case "EXTERNAL_VERIFICATION":
      return "External Registry Verification";
    case "SEMANTIC_LLM":
      return "Semantic Evaluation";
    case "HUMAN_REVIEW":
      return "Human Review";
    case "APPLICABILITY_EXEMPTION":
      return "Applicability Exemption";
    default:
      return norm.replaceAll("_", " ") || "Rule Engine";
  }
}

/**
 * Returns subtle badge style for risk levels
 */
function getRiskBadge(risk: RiskLevel | string) {
  const norm = String(risk || "NONE").toUpperCase();
  switch (norm) {
    case "CRITICAL":
      return { label: "Risk: Critical", style: "bg-red-100 text-red-900 border-red-300 font-bold" };
    case "HIGH":
      return { label: "Risk: High", style: "bg-rose-50 text-rose-800 border-rose-200 font-medium" };
    case "MEDIUM":
      return { label: "Risk: Medium", style: "bg-amber-50 text-amber-800 border-amber-200 font-medium" };
    case "LOW":
      return { label: "Risk: Low", style: "bg-stone-100 text-stone-700 border-stone-200" };
    default:
      return null;
  }
}

/**
 * RequirementFindingCard
 * 
 * Progressive disclosure card for displaying machine evaluation findings per tender requirement.
 * Shows requirement ID, title, compliance state, reason, method, risk, and expandable evidence.
 */
export default function RequirementFindingCard({
  result,
  onInspectEvidence,
  defaultExpanded = false,
}: RequirementFindingCardProps) {
  const [expanded, setExpanded] = useState<boolean>(defaultExpanded || result.review_required);

  const reqId = result.requirement_id || "REQ-000";
  const title = result.title || result.category || "Tender Requirement";
  const isMandatory = result.mandatory ?? true;
  const methodLabel = getEvaluationMethodLabel(result.evaluation_method);
  const riskInfo = getRiskBadge(result.risk_level);
  const isUnverified = String(result.state).toUpperCase() === "UNVERIFIED";
  const isReview = String(result.state).toUpperCase() === "REVIEW" || result.review_required;

  const contradictions = result.contradiction_findings || [];
  const provenanceList = result.provenance || [];
  const supportingList = result.supporting_evidence || [];
  const conflictingList = result.conflicting_evidence || [];

  return (
    <article
      className={`rounded border transition-all ${
        isReview
          ? "border-amber-300 bg-[#fffdfa] shadow-xs"
          : isUnverified
          ? "border-stone-300 bg-[#fafafa]"
          : "border-[#d8ded8] bg-[#fffefa]"
      }`}
      aria-labelledby={`heading-${reqId}`}
    >
      {/* Collapsed / Summary Header (Always Visible) */}
      <div className="p-4 sm:p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-bold text-[#163a5f] bg-[#eef3f7] px-2 py-0.5 rounded border border-[#ccdbe6]">
              {reqId}
            </span>
            <h3 id={`heading-${reqId}`} className="text-sm font-semibold text-[#162333]">
              {title}
            </h3>
            <span
              className={`text-[10px] font-mono px-1.5 py-0.2 rounded font-medium ${
                isMandatory
                  ? "bg-slate-100 text-slate-800 border border-slate-200"
                  : "bg-stone-100 text-stone-600"
              }`}
            >
              {isMandatory ? "Mandatory" : "Optional"}
            </span>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <ComplianceStateBadge state={result.state} size="sm" />
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              aria-expanded={expanded}
              aria-controls={`details-${reqId}`}
              className="focus-ring p-1.5 text-[#627382] hover:text-[#162333] hover:bg-[#edf0ed] rounded transition-colors"
              aria-label={`${expanded ? "Collapse" : "Expand"} requirement ${reqId}`}
            >
              {expanded ? (
                <ChevronUp className="w-4 h-4" aria-hidden="true" />
              ) : (
                <ChevronDown className="w-4 h-4" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>

        {/* Concise One-Line Reason */}
        <div className="mt-2.5 text-xs text-[#283848] leading-relaxed">
          <p className="font-medium">{result.reason}</p>
        </div>

        {/* Secondary Metadata Tags */}
        <div className="mt-3 pt-2.5 border-t border-[#edf0ee] flex flex-wrap items-center justify-between gap-2 text-[11px] text-[#607180]">
          <div className="flex flex-wrap items-center gap-2.5 font-mono">
            <span>
              Method: <strong>{methodLabel}</strong>
            </span>
            {riskInfo && (
              <>
                <span>•</span>
                <span className={`px-1.5 py-0.2 rounded border text-[10px] ${riskInfo.style}`}>
                  {riskInfo.label}
                </span>
              </>
            )}
            {result.confidence !== undefined && result.confidence !== null && (
              <>
                <span>•</span>
                <span>Confidence: {Math.round(result.confidence * 100)}%</span>
              </>
            )}
          </div>

          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="text-[11px] font-semibold text-[#163a5f] hover:underline flex items-center gap-1 focus-ring"
          >
            <span>{expanded ? "Hide Audit Evidence" : "View Audit Evidence & Provenance"}</span>
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        </div>
      </div>

      {/* Expanded Progressive Disclosure Section */}
      {expanded && (
        <div
          id={`details-${reqId}`}
          className="p-5 border-t border-[#e2e7e2] bg-[#f8faf8]/60 space-y-4 text-xs"
        >
          {/* Requirement Description & Expected Condition */}
          {(result.description || result.expected_condition) && (
            <div className="p-3.5 rounded border border-[#d8ded8] bg-[#fffefa] space-y-2">
              <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                Tender Requirement Specification & Expected Condition
              </span>
              {result.description && (
                <p className="text-[#334656] leading-relaxed">{result.description}</p>
              )}
              {result.expected_condition && (
                <div className="pt-2 border-t border-[#edf0ee] font-mono text-[11px] text-[#163a5f] bg-[#f5f8fa] p-2 rounded">
                  <code>{JSON.stringify(result.expected_condition, null, 2)}</code>
                </div>
              )}
            </div>
          )}

          {/* Ambiguity Callout if present */}
          {(result.is_ambiguous || result.ambiguity_reason) && (
            <AmbiguityNotice
              reason={result.ambiguity_reason}
              ambiguityType="UNRESOLVED_SELLER_CRITERIA"
            />
          )}

          {/* Missing Evidence Callout for UNVERIFIED */}
          {isUnverified && (
            <div className="p-3.5 rounded border border-stone-300 border-dashed bg-[#f7f6f5] text-stone-800 space-y-1">
              <div className="flex items-center gap-1.5 font-semibold text-stone-900">
                <HelpCircle className="w-4 h-4 text-stone-700" aria-hidden="true" />
                <span>Mandatory Evidence Not Submitted</span>
              </div>
              <p className="text-stone-700 text-[11px] leading-relaxed">
                The required proof document or statutory certificate for this criterion was not detected in the bidder submission package. The requirement is marked <strong>UNVERIFIED</strong> pending submission of clarification evidence.
              </p>
            </div>
          )}

          {/* Contradiction Findings (Side-by-Side Comparison) */}
          {contradictions.length > 0 && (
            <div className="space-y-3">
              <span className="text-[10px] uppercase font-bold text-amber-900 tracking-wider block">
                Cross-Document Contradiction Analysis ({contradictions.length})
              </span>
              {contradictions.map((ct, idx) => (
                <EvidenceComparison
                  key={ct.finding_id || `ct-${idx}`}
                  comparison={ct.side_by_side}
                  explanation={ct.explanation}
                  relationship={ct.relationship_status}
                  onInspect={onInspectEvidence}
                />
              ))}
            </div>
          )}

          {/* Supporting & Conflicting Evidence Records */}
          {provenanceList.length > 0 && (
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                  Cited Evidence Provenance ({provenanceList.length})
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {provenanceList.map((prov, pIdx) => (
                  <EvidenceReference
                    key={prov.document_id || prov.evidence_id || prov.claim_id || `prov-${pIdx}`}
                    provenance={prov}
                    onInspect={onInspectEvidence}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Observed Values / Parameter Summaries */}
          {result.observed_values && result.observed_values.length > 0 && (
            <div className="p-3 rounded border border-[#d8ded8] bg-[#fffefa] text-[11px] space-y-1">
              <span className="text-[10px] uppercase font-semibold text-[#7f8e9a] block">
                Observed Values Extracted
              </span>
              <div className="font-mono text-[#1a446c]">
                {result.observed_values.map((v, vIdx) => (
                  <div key={vIdx}>• {typeof v === "object" ? JSON.stringify(v) : String(v)}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </article>
  );
}
