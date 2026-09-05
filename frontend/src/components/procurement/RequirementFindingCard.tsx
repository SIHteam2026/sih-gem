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
  const isFail = String(result.state).toUpperCase() === "FAIL";
  const isPass = String(result.state).toUpperCase() === "PASS";
  const isUnverified = String(result.state).toUpperCase() === "UNVERIFIED";
  const isReview = String(result.state).toUpperCase() === "REVIEW" || result.review_required;

  const contradictions = result.contradiction_findings || [];
  const provenanceList = result.provenance || [];
  const supportingList = result.supporting_evidence || [];
  const conflictingList = result.conflicting_evidence || [];
  const primaryDoc = provenanceList[0] || supportingList[0] || null;

  return (
    <article
      className={`rounded border transition-all ${
        isFail
          ? "border-red-300 bg-[#fffdfd] shadow-xs"
          : isReview
          ? "border-amber-300 bg-[#fffdfa] shadow-xs"
          : isUnverified
          ? "border-stone-300 bg-[#fafafa]"
          : "border-[#d8ded8] bg-[#fffefa]"
      }`}
      aria-labelledby={`heading-${reqId}`}
    >
      {/* Collapsed / Summary Header (Always Visible) */}
      <div className="p-4 sm:p-5 space-y-3">
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

        {/* Side-by-Side Required vs Uploaded Delta Comparison Box */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-3.5 rounded border border-[#e1e6e1] bg-[#ffffff]">
          {/* Left: Necessary Requirement (Tender Expectation) */}
          <div className="space-y-1.5 border-b md:border-b-0 md:border-r border-[#ecefec] pb-2.5 md:pb-0 md:pr-3">
            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-[#163a5f]">
              <Scale className="w-3.5 h-3.5 text-[#163a5f]" />
              <span>1. Tender Necessary Requirement</span>
            </div>
            <div className="text-xs font-semibold text-[#162333] line-clamp-2">
              {result.description || title}
            </div>
            <div className="flex flex-wrap gap-1.5 pt-1 text-[11px] font-mono text-[#334656]">
              {result.expected_condition?.value !== undefined && (
                <span className="bg-[#eef3f7] px-2 py-0.5 rounded border border-[#ccdbe6]">
                  Threshold: <strong>{String(result.expected_condition.operator || "≥")} {String(result.expected_condition.value)}{result.expected_condition.unit ? ` ${result.expected_condition.unit}` : ""}</strong>
                </span>
              )}
              {result.expected_condition?.evidence_required && (
                <span className="bg-[#f0f4f0] px-2 py-0.5 rounded border border-[#ccdcd0] text-[#1b432a]">
                  Doc: <strong>{result.expected_condition.evidence_required.join(", ")}</strong>
                </span>
              )}
            </div>
          </div>

          {/* Right: Uploaded Evidence (Observed Bidder Proof) */}
          <div className="space-y-1.5 md:pl-1">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-[#2d4a2d]">
                <FileText className="w-3.5 h-3.5 text-[#2d4a2d]" />
                <span>2. Uploaded Bidder Evidence</span>
              </div>
              {isUnverified && (
                <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-stone-200 text-stone-800">
                  Not Submitted
                </span>
              )}
            </div>

            {primaryDoc ? (
              <div className="space-y-1">
                <div className="text-xs font-medium text-[#162333] flex flex-wrap items-center gap-1">
                  <span className="font-semibold text-[#163a5f]">{primaryDoc.source_document || "Uploaded Document"}</span>
                  {primaryDoc.page_number && (
                    <span className="text-[11px] text-[#71808b]">(Page {primaryDoc.page_number})</span>
                  )}
                </div>
                <div className="font-mono text-xs font-bold bg-[#f8faf8] p-1.5 rounded border border-[#e2e7e2]">
                  Observed: <span className={isFail ? "text-red-700" : isPass ? "text-emerald-800" : "text-amber-800"}>{String(primaryDoc.raw_value || result.observed_values?.[0] || "Declared")}</span>
                </div>
              </div>
            ) : (
              <div className="text-xs text-[#8c6b6b] italic bg-[#faf6f6] p-2 rounded border border-[#eddcdc]">
                No supporting proof document or certificate detected in submission package.
              </div>
            )}
          </div>
        </div>

        {/* Evaluation Reason & Action Alert */}
        <div
          className={`p-3 rounded border text-xs leading-relaxed flex items-start gap-2 ${
            isFail
              ? "bg-red-50/80 border-red-200 text-red-900"
              : isReview
              ? "bg-amber-50/80 border-amber-200 text-amber-900"
              : isUnverified
              ? "bg-stone-100/90 border-stone-200 text-stone-800"
              : "bg-emerald-50/70 border-emerald-200 text-emerald-900"
          }`}
        >
          {isFail ? (
            <XCircle className="w-4 h-4 text-red-700 shrink-0 mt-0.5" />
          ) : isReview ? (
            <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
          ) : isUnverified ? (
            <HelpCircle className="w-4 h-4 text-stone-600 shrink-0 mt-0.5" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0 mt-0.5" />
          )}
          <div className="space-y-0.5">
            <span className="font-bold block">
              {isFail
                ? "Requirement Discrepancy / Deficit Detected"
                : isReview
                ? "Procurement Officer Review Required"
                : isUnverified
                ? "Mandatory Evidence Missing"
                : "Requirement Compliant"}
            </span>
            <p className="font-normal">{result.reason}</p>
          </div>
        </div>

        {/* Secondary Metadata Tags */}
        <div className="pt-2 border-t border-[#edf0ee] flex flex-wrap items-center justify-between gap-2 text-[11px] text-[#607180]">
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
