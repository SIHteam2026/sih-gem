"use client";

import { useState } from "react";
import {
  ShieldCheck,
  AlertTriangle,
  XCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Search,
  Filter,
  FileText,
  Clock,
  ArrowRight,
  ExternalLink,
  Layers,
  HelpCircle,
  Eye,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export interface EvidenceChainItem {
  criterion: string;
  evidence_found: string;
  source_doc?: string;
  status: "PASSED" | "FAILED" | "DISCREPANCY" | "NEEDS_REVIEW" | string;
  notes?: string;
}

export interface ComplianceItem {
  id: string | number;
  bidder_name: string;
  tender_ref?: string;
  status: "VERIFIED" | "NON_COMPLIANT" | "REVIEW_REQUIRED" | string;
  risk_level: "HIGH" | "MEDIUM" | "LOW" | string;
  match_score?: number;
  ai_explanation: string;
  flagged_anomalies?: string[];
  evidence_chain?: EvidenceChainItem[];
  submitted_at?: string;
}

const DEFAULT_SAMPLE_QUEUE: ComplianceItem[] = [
  {
    id: "BID-2026-081",
    bidder_name: "Apex Infra & Power Solutions Pvt Ltd",
    tender_ref: "GEM/2026/B/894120",
    status: "NON_COMPLIANT",
    risk_level: "HIGH",
    match_score: 42.0,
    ai_explanation:
      "Critical discrepancy detected: The GSTIN on the submitted GST Certificate (07BBBBB9999B1Z5) does not match the jurisdictional state code in the Bidder Registration data. Furthermore, the mandatory OEM Authorization letter is missing the requisite manufacturer digital seal.",
    flagged_anomalies: [
      "GSTIN State Code Mismatch (Submitted Delhi code 07 vs Registered Haryana code 06)",
      "Missing OEM Authorization Digital Verification Seal",
      "Audited Turnover shortfall: ₹4.2 Cr vs Required ₹10.0 Cr",
    ],
    evidence_chain: [
      {
        criterion: "Valid GST Registration (Form GST REG-06)",
        evidence_found: "GST Certificate extracted with GSTIN 07BBBBB9999B1Z5",
        source_doc: "mismatch_gst.pdf",
        status: "FAILED",
        notes: "Mismatched entity registration ID against master records",
      },
      {
        criterion: "Minimum 3 Years Operating Experience",
        evidence_found: "Registration date verified: 01/07/2017 (9+ years active)",
        source_doc: "mismatch_gst.pdf",
        status: "PASSED",
        notes: "Meets operational age criteria",
      },
      {
        criterion: "OEM Authorization Compliance",
        evidence_found: "Authorization letter dated 14/01/2026 without digital signature",
        source_doc: "oem_auth.pdf",
        status: "DISCREPANCY",
        notes: "Failed cryptographical signature check",
      },
    ],
    submitted_at: "2026-08-29T11:24:00Z",
  },
  {
    id: "BID-2026-082",
    bidder_name: "Global Trade & Logistics Corporation",
    tender_ref: "GEM/2026/B/894120",
    status: "REVIEW_REQUIRED",
    risk_level: "MEDIUM",
    match_score: 78.5,
    ai_explanation:
      "Partial name deviation identified between Legal Name on GST REG-06 ('Global Trade & Logistics Private Limited') and Vendor Portal registration ('Global Trade and Logistics Corp'). Entity PAN and jurisdictional registration are valid, but manual review is required for entity nomenclature variance.",
    flagged_anomalies: [
      "Minor Entity Name Ambiguity: 'Private Limited' vs 'Corp' (Levenshtein similarity score: 86%)",
      "ISO 9001:2015 Certification expires within 30 days of bid submission",
    ],
    evidence_chain: [
      {
        criterion: "GST Compliance & Active Filing",
        evidence_found: "Active regular registration confirmed with jurisdictional office Ward 101",
        source_doc: "gst_certificate.pdf",
        status: "PASSED",
      },
      {
        criterion: "Entity Nomenclature Match",
        evidence_found: "GST Legal Name: 'Global Trade & Logistics Pvt Ltd' vs Bidder Name: 'Global Trade & Logistics Corp'",
        source_doc: "gst_certificate.pdf",
        status: "NEEDS_REVIEW",
        notes: "Recommended officer approval for trade name alias",
      },
    ],
    submitted_at: "2026-08-29T12:05:00Z",
  },
  {
    id: "BID-2026-083",
    bidder_name: "ACME Technologies India Private Limited",
    tender_ref: "GEM/2026/B/894120",
    status: "VERIFIED",
    risk_level: "LOW",
    match_score: 99.2,
    ai_explanation:
      "All mandatory eligibility criteria fully verified. GSTIN 07AAAAA0000A1Z5 is verified active with clean tax compliance, OEM authorization valid until 2028, and 3-year audited financial turnover exceeds ₹25 Cr requirements.",
    flagged_anomalies: [],
    evidence_chain: [
      {
        criterion: "GST REG-06 Certificate Verification",
        evidence_found: "Valid GSTIN 07AAAAA0000A1Z5 registered to ACME CORP (Delhi)",
        source_doc: "valid_gst.pdf",
        status: "PASSED",
        notes: "100% field parity across Legal Name, GSTIN, and Address",
      },
      {
        criterion: "Turnover & Net Worth Thresholds",
        evidence_found: "Average turnover ₹28.4 Cr verified from audited balance sheets",
        source_doc: "financials_fy25.pdf",
        status: "PASSED",
        notes: "Exceeds minimum criteria threshold (₹10 Cr)",
      },
      {
        criterion: "Non-Blacklisting Undertaking",
        evidence_found: "Notarized affidavit submitted and verified clean against GeM vigilance blacklist database",
        source_doc: "undertaking.pdf",
        status: "PASSED",
      },
    ],
    submitted_at: "2026-08-29T13:40:00Z",
  },
  {
    id: "BID-2026-084",
    bidder_name: "Zenith Solar & Power Equipment Ltd",
    tender_ref: "GEM/2026/B/894120",
    status: "VERIFIED",
    risk_level: "LOW",
    match_score: 97.0,
    ai_explanation:
      "Bidder passed all technical and statutory evaluations. Active GSTIN, valid MNRE enlistment certificate, and past work order execution certificates verified with central database.",
    flagged_anomalies: [],
    evidence_chain: [
      {
        criterion: "MNRE Tier-1 Certification",
        evidence_found: "Certificate verified valid through Dec 2027",
        source_doc: "mnre_cert.pdf",
        status: "PASSED",
      },
      {
        criterion: "Statutory Tax Clearances",
        evidence_found: "GST and PAN records matched perfectly",
        source_doc: "gst_doc.pdf",
        status: "PASSED",
      },
    ],
    submitted_at: "2026-08-29T14:15:00Z",
  },
];

interface ComplianceQueueProps {
  items?: ComplianceItem[];
  title?: string;
  subtitle?: string;
}

export default function ComplianceQueue({
  items = DEFAULT_SAMPLE_QUEUE,
  title = "Procurement Review & Compliance Queue",
  subtitle = "High-impact priority attention queue evaluating bidder evidence, risk levels, and automated reasoning traces.",
}: ComplianceQueueProps) {
  const [expandedId, setExpandedId] = useState<string | number | null>(items[0]?.id || null);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [riskFilter, setRiskFilter] = useState<string>("ALL");

  const toggleExpand = (id: string | number) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  const renderStatusBadge = (status: string) => {
    const s = String(status || "").toUpperCase();

    if (s.includes("VERIFIED") || s === "PASS" || s === "COMPLIANT") {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-green-100 text-green-800 border border-green-300 shadow-2xs">
          <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
          VERIFIED
        </span>
      );
    }

    if (s.includes("NON_COMPLIANT") || s.includes("NON-COMPLIANT") || s === "FAIL" || s === "REJECTED") {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-red-100 text-red-800 border border-red-300 shadow-2xs">
          <XCircle className="w-3.5 h-3.5 text-red-600" />
          NON_COMPLIANT
        </span>
      );
    }

    if (s.includes("REVIEW") || s.includes("PENDING") || s.includes("WARNING")) {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-yellow-100 text-yellow-800 border border-yellow-300 shadow-2xs">
          <AlertTriangle className="w-3.5 h-3.5 text-yellow-600" />
          REVIEW_REQUIRED
        </span>
      );
    }

    return (
      <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-gray-100 text-gray-800 border border-gray-300">
        {status}
      </span>
    );
  };

  const renderRiskBadge = (risk: string) => {
    const r = String(risk || "").toUpperCase();

    if (r === "HIGH" || r === "CRITICAL") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-extrabold bg-red-50 text-red-700 border border-red-200">
          <span className="w-1.5 h-1.5 rounded-full bg-red-600 animate-pulse" />
          HIGH
        </span>
      );
    }

    if (r === "MEDIUM" || r === "MODERATE") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-bold bg-yellow-50 text-yellow-800 border border-yellow-200">
          <span className="w-1.5 h-1.5 rounded-full bg-yellow-500" />
          MEDIUM
        </span>
      );
    }

    if (r === "LOW" || r === "MINIMAL") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          LOW
        </span>
      );
    }

    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-700">
        {risk}
      </span>
    );
  };

  const renderEvidenceStatus = (status: string) => {
    const s = String(status || "").toUpperCase();
    if (s === "PASSED") {
      return (
        <span className="text-[11px] font-bold text-green-700 bg-green-50 px-2 py-0.5 rounded border border-green-200">
          PASSED
        </span>
      );
    }
    if (s === "FAILED") {
      return (
        <span className="text-[11px] font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded border border-red-200">
          FAILED
        </span>
      );
    }
    if (s === "DISCREPANCY" || s === "NEEDS_REVIEW") {
      return (
        <span className="text-[11px] font-bold text-yellow-800 bg-yellow-50 px-2 py-0.5 rounded border border-yellow-200">
          {s}
        </span>
      );
    }
    return <span className="text-[11px] text-gray-600">{status}</span>;
  };

  const filteredItems = items.filter((item) => {
    const matchesSearch =
      item.bidder_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (item.tender_ref && item.tender_ref.toLowerCase().includes(searchTerm.toLowerCase())) ||
      String(item.id).toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus =
      statusFilter === "ALL" ||
      (statusFilter === "VERIFIED" && item.status.toUpperCase().includes("VERIFIED")) ||
      (statusFilter === "NON_COMPLIANT" && item.status.toUpperCase().includes("NON_COMPLIANT")) ||
      (statusFilter === "REVIEW_REQUIRED" && item.status.toUpperCase().includes("REVIEW"));

    const matchesRisk =
      riskFilter === "ALL" || item.risk_level.toUpperCase() === riskFilter;

    return matchesSearch && matchesStatus && matchesRisk;
  });

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden font-sans">
      {/* Header */}
      <div className="p-6 border-b border-gray-200 bg-gradient-to-r from-gray-50 via-white to-gray-50 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-100 mb-2">
            <ShieldCheck className="w-3.5 h-3.5" />
            Vigilance & Compliance Radar
          </div>
          <h2 className="text-2xl font-extrabold text-gray-900 tracking-tight">{title}</h2>
          <p className="text-sm text-gray-500 mt-1 max-w-2xl">{subtitle}</p>
        </div>

        {/* Priority Stats Summary */}
        <div className="flex items-center gap-3">
          <div className="px-3.5 py-2 rounded-lg bg-red-50 border border-red-100 text-center">
            <p className="text-[11px] font-semibold uppercase text-red-600">High Risk</p>
            <p className="text-lg font-extrabold text-red-700">
              {items.filter((i) => i.risk_level.toUpperCase() === "HIGH").length}
            </p>
          </div>
          <div className="px-3.5 py-2 rounded-lg bg-yellow-50 border border-yellow-100 text-center">
            <p className="text-[11px] font-semibold uppercase text-yellow-600">Review</p>
            <p className="text-lg font-extrabold text-yellow-700">
              {items.filter((i) => i.status.toUpperCase().includes("REVIEW")).length}
            </p>
          </div>
          <div className="px-3.5 py-2 rounded-lg bg-green-50 border border-green-100 text-center">
            <p className="text-[11px] font-semibold uppercase text-green-600">Verified</p>
            <p className="text-lg font-extrabold text-green-700">
              {items.filter((i) => i.status.toUpperCase().includes("VERIFIED")).length}
            </p>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-4 bg-gray-50/70 border-b border-gray-200 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search bidder name, ref ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-white border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 bg-white border border-gray-300 rounded-lg text-xs font-medium text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="VERIFIED">Verified</option>
            <option value="REVIEW_REQUIRED">Review Required</option>
            <option value="NON_COMPLIANT">Non Compliant</option>
          </select>

          {/* Risk Filter */}
          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            className="px-3 py-2 bg-white border border-gray-300 rounded-lg text-xs font-medium text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="ALL">All Risk Levels</option>
            <option value="HIGH">High Risk</option>
            <option value="MEDIUM">Medium Risk</option>
            <option value="LOW">Low Risk</option>
          </select>
        </div>
      </div>

      {/* Queue Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
          <thead className="bg-gray-100/70 text-xs font-bold text-gray-600 uppercase tracking-wider">
            <tr>
              <th scope="col" className="px-6 py-3.5">
                Bidder / Entity
              </th>
              <th scope="col" className="px-6 py-3.5">
                Compliance Status
              </th>
              <th scope="col" className="px-6 py-3.5">
                Risk Level
              </th>
              <th scope="col" className="px-6 py-3.5 text-center">
                Match Score
              </th>
              <th scope="col" className="px-6 py-3.5 text-right">
                Reasoning Trace
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {filteredItems.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                  <FileText className="w-8 h-8 mx-auto text-gray-300 mb-2" />
                  <p className="font-semibold text-gray-700">No matching bidders found in review queue</p>
                  <p className="text-xs text-gray-400 mt-1">Try adjusting your search query or filters</p>
                </td>
              </tr>
            ) : (
              filteredItems.map((item) => {
                const isExpanded = expandedId === item.id;

                return (
                  <tr key={item.id} className="group hover:bg-gray-50/60 transition-colors">
                    <td colSpan={5} className="p-0">
                      {/* Main Table Row Content */}
                      <div
                        onClick={() => toggleExpand(item.id)}
                        className={`px-6 py-4 flex flex-wrap items-center justify-between gap-4 cursor-pointer select-none transition-colors ${
                          isExpanded ? "bg-blue-50/40 border-l-4 border-blue-600" : "border-l-4 border-transparent"
                        }`}
                      >
                        {/* 1. Bidder Name & Ref ID */}
                        <div className="min-w-[220px] flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-gray-900 text-sm hover:text-blue-600 transition-colors">
                              {item.bidder_name}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                            <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded text-[11px]">{item.id}</span>
                            {item.tender_ref && (
                              <>
                                <span>•</span>
                                <span>Ref: {item.tender_ref}</span>
                              </>
                            )}
                          </div>
                        </div>

                        {/* 2. Compliance Status Badge */}
                        <div className="w-40 flex-shrink-0">
                          {renderStatusBadge(item.status)}
                        </div>

                        {/* 3. Risk Level */}
                        <div className="w-28 flex-shrink-0">
                          {renderRiskBadge(item.risk_level)}
                        </div>

                        {/* 4. Match Score */}
                        <div className="w-24 text-center flex-shrink-0">
                          {item.match_score !== undefined ? (
                            <span className="font-mono font-bold text-sm text-gray-800">
                              {item.match_score}%
                            </span>
                          ) : (
                            <span className="text-xs text-gray-400">N/A</span>
                          )}
                        </div>

                        {/* 5. Reasoning Trace Drawer Toggle Button */}
                        <div className="w-36 text-right flex-shrink-0">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleExpand(item.id);
                            }}
                            className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                              isExpanded
                                ? "bg-blue-600 text-white shadow-sm"
                                : "bg-gray-100 hover:bg-gray-200 text-gray-700"
                            }`}
                          >
                            <Sparkles className="w-3 h-3" />
                            {isExpanded ? "Hide Trace" : "View Trace"}
                            {isExpanded ? <ChevronUp className="w-3.5 h-3.5 ml-0.5" /> : <ChevronDown className="w-3.5 h-3.5 ml-0.5" />}
                          </button>
                        </div>
                      </div>

                      {/* Expandable Reasoning Trace Drawer */}
                      <AnimatePresence>
                        {isExpanded && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.25, ease: "easeInOut" }}
                            className="overflow-hidden bg-gray-50/90 border-t border-b border-gray-200 px-6 py-6 space-y-6"
                          >
                            {/* AI Explanation Banner */}
                            <div className="bg-white rounded-xl p-5 border border-blue-200/80 shadow-sm space-y-2">
                              <div className="flex items-center gap-2 text-blue-700 font-bold text-sm">
                                <Sparkles className="w-4 h-4 text-blue-600" />
                                <span>AI Evaluation & Compliance Reasoning Trace</span>
                              </div>
                              <p className="text-sm text-gray-800 leading-relaxed bg-blue-50/40 p-3.5 rounded-lg border border-blue-100">
                                {item.ai_explanation}
                              </p>
                            </div>

                            {/* Flagged Anomalies if any */}
                            {item.flagged_anomalies && item.flagged_anomalies.length > 0 && (
                              <div className="bg-red-50 rounded-xl p-5 border border-red-200 space-y-2">
                                <div className="flex items-center gap-2 text-red-800 font-bold text-sm">
                                  <AlertTriangle className="w-4 h-4 text-red-600" />
                                  <span>Flagged Discrepancies & Audit Alerts ({item.flagged_anomalies.length})</span>
                                </div>
                                <ul className="list-disc list-inside space-y-1 text-sm text-red-700">
                                  {item.flagged_anomalies.map((anomaly, idx) => (
                                    <li key={idx} className="leading-relaxed">
                                      <span className="font-medium text-red-900">{anomaly}</span>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}

                            {/* Evidence Chain Table */}
                            {item.evidence_chain && item.evidence_chain.length > 0 && (
                              <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                  <h4 className="text-xs font-bold uppercase tracking-wider text-gray-700 flex items-center gap-1.5">
                                    <Layers className="w-4 h-4 text-indigo-600" />
                                    Evidence Verification Chain ({item.evidence_chain.length} Criteria)
                                  </h4>
                                </div>

                                <div className="border border-gray-200 rounded-lg overflow-hidden bg-white shadow-2xs">
                                  <table className="min-w-full divide-y divide-gray-200 text-xs">
                                    <thead className="bg-gray-50 font-semibold text-gray-600">
                                      <tr>
                                        <th scope="col" className="px-4 py-2.5">
                                          Evaluated Criterion
                                        </th>
                                        <th scope="col" className="px-4 py-2.5">
                                          Extracted Evidence
                                        </th>
                                        <th scope="col" className="px-4 py-2.5">
                                          Source File
                                        </th>
                                        <th scope="col" className="px-4 py-2.5 text-center">
                                          Result
                                        </th>
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-100">
                                      {item.evidence_chain.map((chain, cIdx) => (
                                        <tr key={cIdx} className="hover:bg-gray-50/50">
                                          <td className="px-4 py-3 font-semibold text-gray-900 max-w-xs">
                                            {chain.criterion}
                                            {chain.notes && (
                                              <p className="text-[11px] text-gray-500 font-normal mt-0.5">{chain.notes}</p>
                                            )}
                                          </td>
                                          <td className="px-4 py-3 text-gray-700">
                                            {chain.evidence_found}
                                          </td>
                                          <td className="px-4 py-3 font-mono text-gray-500 text-[11px]">
                                            {chain.source_doc || "N/A"}
                                          </td>
                                          <td className="px-4 py-3 text-center whitespace-nowrap">
                                            {renderEvidenceStatus(chain.status)}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            )}

                            {/* Officer Review Actions */}
                            <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-gray-200">
                              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                                <Clock className="w-3.5 h-3.5 text-gray-400" />
                                <span>
                                  Submitted:{" "}
                                  {item.submitted_at
                                    ? new Date(item.submitted_at).toLocaleString("en-IN", {
                                        dateStyle: "medium",
                                        timeStyle: "short",
                                      })
                                    : "Recent"}
                                </span>
                              </div>

                              <div className="flex items-center gap-2">
                                <button
                                  type="button"
                                  className="px-3 py-1.5 text-xs font-semibold text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 rounded-lg shadow-2xs transition-colors"
                                >
                                  Request Clarification
                                </button>
                                <button
                                  type="button"
                                  className="px-3 py-1.5 text-xs font-semibold text-blue-700 bg-blue-50 border border-blue-200 hover:bg-blue-100 rounded-lg transition-colors"
                                >
                                  Export Audit Report
                                </button>
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
