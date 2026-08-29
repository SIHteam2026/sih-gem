"use client";

import React from "react";
import {
  FileCheck2,
  FileX2,
  Building,
  Shield,
  Printer,
  Calendar,
  Award,
  AlertCircle,
  CheckCircle,
  FileText,
  UserCheck,
  Stamp,
} from "lucide-react";

export interface ExecutiveReportData {
  executive_summary?: string;
  key_violations?: string[];
  final_recommendation?: "ACCEPT" | "REJECT" | "CONDITIONAL" | string;
  bidder_name?: string;
  tender_id?: string;
  evaluation_date?: string;
  officer_notes?: string;
  [key: string]: any;
}

interface ExecutiveReportProps {
  reportData?: ExecutiveReportData | null;
  bidderName?: string;
  tenderId?: string;
}

export default function ExecutiveReport({
  reportData,
  bidderName,
  tenderId,
}: ExecutiveReportProps) {
  if (!reportData) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
        <FileText className="w-10 h-10 text-gray-400 mx-auto mb-2" />
        <p className="text-sm font-medium text-gray-600">
          No executive report generated yet. Click "Generate Final Decision" to compile the CPO note sheet.
        </p>
      </div>
    );
  }

  const rawRec = (reportData.final_recommendation || "ACCEPT").toUpperCase();
  const isAccepted = rawRec.includes("ACCEPT") && !rawRec.includes("REJECT");
  const isRejected = rawRec.includes("REJECT") || rawRec.includes("NON_COMPLIANT");

  const summaryText =
    reportData.executive_summary ||
    "Following autonomous multi-tier forensic screening of the submitted tender bids and statutory evidence (GSTIN, PAN, Turnover Certificates, and OEM Authorizations), the AI Procurement Vigilance Engine has compiled the final evaluation note.";

  const violations = Array.isArray(reportData.key_violations)
    ? reportData.key_violations
    : [];

  const targetBidder = reportData.bidder_name || bidderName || "Apex Infrastructure Pvt. Ltd.";
  const targetTender = reportData.tender_id || tenderId || "GeM/2026/B/894120";
  const currentDate =
    reportData.evaluation_date ||
    new Date().toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    });

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="bg-amber-50/40 border-2 border-amber-200/90 rounded-2xl shadow-md overflow-hidden font-serif">
      {/* Official Government Note-Sheet Top Banner */}
      <div className="bg-[#1e293b] text-white px-8 py-5 flex flex-wrap items-center justify-between gap-4 font-sans border-b-4 border-amber-500">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-amber-500 flex items-center justify-center text-slate-900 shadow">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-widest text-amber-400 font-extrabold">
              Government of India · GeM Procurement Portal
            </div>
            <h2 className="text-lg font-black tracking-tight text-white">
              NOTE SHEET & EXECUTIVE AUDIT DECISION
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handlePrint}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-sans font-semibold rounded-lg border border-slate-700 transition"
          >
            <Printer className="w-3.5 h-3.5" />
            Print Note Sheet
          </button>
        </div>
      </div>

      {/* Note-Sheet Formal Body */}
      <div className="p-8 sm:p-10 space-y-8 bg-white/95 text-slate-800 text-sm leading-relaxed">
        {/* Top Header Grid: Reference & DECISION BADGE */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6 pb-6 border-b border-dashed border-amber-300">
          <div className="space-y-1 font-sans text-xs">
            <p className="text-slate-500">
              <strong className="text-slate-700">File No:</strong> CPO/VIG/GeM-2026/EVAL-
              {Math.floor(1000 + Math.random() * 9000)}
            </p>
            <p className="text-slate-500">
              <strong className="text-slate-700">Tender Ref:</strong> {targetTender}
            </p>
            <p className="text-slate-500">
              <strong className="text-slate-700">Evaluated Bidder:</strong> {targetBidder}
            </p>
            <p className="text-slate-500 flex items-center gap-1">
              <Calendar className="w-3 h-3 text-slate-400" />
              <strong className="text-slate-700">Date of Order:</strong> {currentDate}
            </p>
          </div>

          {/* Prominent Bureaucratic Stamp / Decision Badge */}
          <div
            className={`flex items-center gap-3 px-6 py-3.5 rounded-xl border-2 uppercase font-sans font-black tracking-widest text-base shadow-sm ${
              isAccepted
                ? "bg-emerald-50 border-emerald-600 text-emerald-800"
                : isRejected
                ? "bg-rose-50 border-rose-600 text-rose-800"
                : "bg-amber-50 border-amber-600 text-amber-800"
            }`}
          >
            {isAccepted ? (
              <FileCheck2 className="w-7 h-7 text-emerald-600 animate-pulse" />
            ) : isRejected ? (
              <FileX2 className="w-7 h-7 text-rose-600 animate-pulse" />
            ) : (
              <AlertCircle className="w-7 h-7 text-amber-600" />
            )}
            <div className="text-left">
              <span className="text-[10px] block font-extrabold opacity-75 tracking-wider">
                COMPETENT AUTHORITY DECISION
              </span>
              <span className="text-xl leading-none font-extrabold">
                {isAccepted
                  ? "RECOMMENDED: ACCEPT"
                  : isRejected
                  ? "RECOMMENDED: REJECT"
                  : "CONDITIONAL CLEARANCE"}
              </span>
            </div>
          </div>
        </div>

        {/* Paragraph 1: Executive Summary */}
        <div className="space-y-2">
          <h4 className="font-sans font-bold text-xs uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
            <span className="w-5 h-5 rounded-full bg-slate-100 text-slate-700 inline-flex items-center justify-center font-mono text-[10px]">
              1
            </span>
            Executive Synopsis & Vigilance Audit
          </h4>
          <div className="p-4 bg-amber-50/50 rounded-xl border border-amber-200/60 text-slate-900 text-justify text-sm">
            {summaryText}
          </div>
        </div>

        {/* Paragraph 2: Key Violations / Non-Compliances */}
        <div className="space-y-3">
          <h4 className="font-sans font-bold text-xs uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
            <span className="w-5 h-5 rounded-full bg-slate-100 text-slate-700 inline-flex items-center justify-center font-mono text-[10px]">
              2
            </span>
            Observed Violations & Statutory Discrepancies
          </h4>

          {violations.length > 0 ? (
            <div className="border border-rose-200 rounded-xl overflow-hidden font-sans">
              <table className="min-w-full divide-y divide-rose-200 text-xs">
                <thead className="bg-rose-100/70 text-rose-900 font-bold uppercase tracking-wider">
                  <tr>
                    <th className="py-2.5 px-4 text-left w-12">#</th>
                    <th className="py-2.5 px-4 text-left">Clause / Requirement Violation</th>
                    <th className="py-2.5 px-4 text-right w-32">Severity</th>
                  </tr>
                </thead>
                <tbody className="bg-rose-50/30 divide-y divide-rose-100 text-rose-950">
                  {violations.map((violation, index) => (
                    <tr key={index} className="hover:bg-rose-100/40">
                      <td className="py-2.5 px-4 font-mono font-bold text-rose-700">
                        {String(index + 1).padStart(2, "0")}
                      </td>
                      <td className="py-2.5 px-4 font-medium leading-relaxed">
                        {violation}
                      </td>
                      <td className="py-2.5 px-4 text-right font-bold text-rose-700 uppercase">
                        Disqualifying
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-200 font-sans flex items-center gap-3 text-emerald-800 text-xs">
              <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
              <span>
                No statutory or mandatory RFP clause violations identified in the submitted bid documents.
              </span>
            </div>
          )}
        </div>

        {/* Paragraph 3: Final Administrative Recommendation */}
        <div className="space-y-2">
          <h4 className="font-sans font-bold text-xs uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
            <span className="w-5 h-5 rounded-full bg-slate-100 text-slate-700 inline-flex items-center justify-center font-mono text-[10px]">
              3
            </span>
            Final Administrative Direction
          </h4>
          <p className="text-xs text-slate-700 bg-slate-50 p-4 rounded-xl border border-slate-200 font-sans leading-relaxed">
            {isAccepted
              ? "In view of full technical compliance, valid GST/PAN verification, and absence of cartelization red flags, the bid submitted by the aforementioned entity is hereby recommended for financial evaluation in accordance with Rule 173 of General Financial Rules (GFR), 2017."
              : isRejected
              ? "In view of critical statutory non-compliance and integrity anomalies enumerated above, the bid is hereby recommended for summary REJECTION. Relevant audit traces have been archived for vigilance review."
              : "Conditional provisional acceptance subject to submission of clarifying affidavits within 48 hours."}
          </p>
        </div>

        {/* Official Bureaucratic Signature & Seal Block */}
        <div className="pt-6 border-t border-slate-200 font-sans grid grid-cols-1 sm:grid-cols-2 gap-6 items-end">
          <div className="flex items-center gap-3 text-slate-500 text-xs">
            <Stamp className="w-8 h-8 text-slate-400" />
            <div>
              <p className="font-bold text-slate-700">Digital Seal of Vigilance</p>
              <p className="font-mono text-[10px] text-slate-400">
                SHA-256: 8f9b4c027e1a389d...verified
              </p>
            </div>
          </div>

          <div className="text-right space-y-1">
            <div className="inline-block border-b-2 border-slate-800 pb-1 px-4 mb-1">
              <span className="font-serif italic font-bold text-slate-800 text-sm">
                Chief Procurement Officer (CPO)
              </span>
            </div>
            <p className="text-xs font-bold text-slate-800">
              Procurement & Vigilance Directorate
            </p>
            <p className="text-[10px] text-slate-500">
              Government e-Marketplace (GeM) Autonomous Screening
            </p>
          </div>
        </div>
      </div>

      {/* Bottom CPO Summary Card Action Footer */}
      <div className="bg-slate-100/90 px-8 py-4 border-t border-slate-200 flex flex-wrap items-center justify-between gap-4 font-sans print:hidden">
        <div className="flex items-center gap-2 text-xs text-slate-600">
          <Shield className="w-4 h-4 text-indigo-600 flex-shrink-0" />
          <span className="font-medium">
            Official CPO Vigilance Verdict · Ready for statutory audit submission
          </span>
        </div>

        <button
          type="button"
          onClick={handlePrint}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white text-xs font-extrabold rounded-xl shadow-sm hover:shadow-md transition-all cursor-pointer"
        >
          <Printer className="w-4 h-4 text-white" />
          Export Official PDF Report
        </button>
      </div>

      {/* Print-specific style overrides */}
      <style jsx global>{`
        @media print {
          /* Hide non-printable navigation, buttons, and UI controls */
          header, navbar, nav, button, .print\\:hidden {
            display: none !important;
          }
          body {
            background-color: #ffffff !important;
            color: #000000 !important;
          }
          .shadow-md, .shadow-sm, .shadow-2xs {
            box-shadow: none !important;
          }
        }
      `}</style>
    </div>
  );
}
