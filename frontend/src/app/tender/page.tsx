"use client";

import { useState } from "react";
import {
  UploadCloud,
  FileText,
  AlertCircle,
  CheckCircle2,
  FileSearch,
  Sparkles,
  ClipboardList,
  CheckSquare,
  ShieldAlert,
  Tag,
} from "lucide-react";
import { motion } from "framer-motion";
import { analyzeTender } from "@/services/api";
import Navbar from "@/components/Navbar";

interface TenderRequirement {
  requirement_id?: string;
  id?: string;
  category?: string;
  description?: string;
  mandatory?: boolean;
  is_mandatory?: boolean;
  evidence_required?: string[] | string;
  [key: string]: any;
}

export default function TenderPage() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<any | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError(null);
      setAnalysisResult(null);
    }
  };

  const handleProcessTender = async () => {
    if (!file) {
      setError("Please select a tender PDF document before processing.");
      return;
    }

    setLoading(true);
    setError(null);
    setAnalysisResult(null);

    try {
      const data = await analyzeTender(file);
      setAnalysisResult(data);
    } catch (err: any) {
      setError(err?.message || "An unexpected error occurred while analyzing the tender.");
    } finally {
      setLoading(false);
    }
  };

  // Helper to extract requirements array from various API response shapes
  const getRequirements = (): TenderRequirement[] => {
    if (!analysisResult) return [];
    if (Array.isArray(analysisResult)) return analysisResult;
    if (Array.isArray(analysisResult.requirements)) return analysisResult.requirements;
    if (Array.isArray(analysisResult.clauses)) return analysisResult.clauses;
    if (Array.isArray(analysisResult.data)) return analysisResult.data;
    if (Array.isArray(analysisResult.results)) return analysisResult.results;
    return [];
  };

  const requirements = getRequirements();

  // Helper to normalize evidence_required into a list of strings
  const getEvidenceList = (evidence: any): string[] => {
    if (!evidence) return [];
    if (Array.isArray(evidence)) return evidence.map((e) => String(e));
    if (typeof evidence === "string") return [evidence];
    return [JSON.stringify(evidence)];
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <Navbar />

      <main className="flex-1 max-w-5xl w-full mx-auto py-10 px-4 sm:px-6 lg:px-8 space-y-8">
        {/* Header */}
        <div className="text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-xs font-semibold uppercase tracking-wider mb-3 border border-blue-100">
            <Sparkles className="w-3.5 h-3.5" />
            AI Tender Intelligence
          </div>
          <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight sm:text-5xl">
            Tender Document Analyzer
          </h1>
          <p className="mt-3 text-lg text-gray-600 max-w-2xl mx-auto">
            Upload GeM or public procurement tender PDFs to automatically extract requirements, evaluate criteria, and inspect compliance evidence.
          </p>
        </div>

        {/* Upload Card */}
        <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200">
          <div className="flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:bg-gray-50 transition-colors">
            <UploadCloud className="w-12 h-12 text-gray-400 mb-4" />
            <div className="flex text-sm text-gray-600">
              <label
                htmlFor="tender-file-upload"
                className="relative cursor-pointer bg-white rounded-md font-medium text-blue-600 hover:text-blue-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-blue-500"
              >
                <span>Upload a tender file</span>
                <input
                  id="tender-file-upload"
                  name="tender-file-upload"
                  type="file"
                  accept=".pdf,application/pdf"
                  className="sr-only"
                  onChange={handleFileChange}
                />
              </label>
              <p className="pl-1">or drag and drop</p>
            </div>
            <p className="text-xs text-gray-500 mt-2">PDF documents only (e.g. GeM Bid / RFP / NIT)</p>
          </div>

          {/* Selected File Preview */}
          {file && (
            <div className="mt-4 flex items-center p-4 bg-blue-50 rounded-lg text-blue-700 border border-blue-100">
              <FileText className="w-5 h-5 mr-3 flex-shrink-0" />
              <span className="font-medium truncate">{file.name}</span>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="mt-4 flex items-start p-4 bg-red-50 rounded-lg text-red-700 border border-red-200">
              <AlertCircle className="w-5 h-5 mr-3 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-sm">Analysis Error</p>
                <p className="text-sm mt-1">{error}</p>
              </div>
            </div>
          )}

          {/* Submit Button */}
          <div className="mt-6 flex justify-center">
            <button
              onClick={handleProcessTender}
              disabled={!file || loading}
              className={`flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-white transition-all shadow-sm
                ${
                  !file || loading
                    ? "bg-gray-400 cursor-not-allowed"
                    : "bg-blue-600 hover:bg-blue-700 active:bg-blue-800 cursor-pointer"
                }
              `}
            >
              {loading ? (
                <>
                  <svg
                    className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  Processing Tender...
                </>
              ) : (
                <>
                  <FileSearch className="w-5 h-5 mr-2" />
                  Process Tender
                </>
              )}
            </button>
          </div>
        </div>

        {/* Results Section: Conditionally Rendered if analysisResult exists */}
        {analysisResult && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="space-y-6"
          >
            {/* Header Summary Banner */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center flex-shrink-0">
                  <ClipboardList className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-xl font-extrabold text-gray-900">Extracted Tender Requirements</h3>
                  <p className="text-sm text-gray-500 mt-0.5">
                    Found {requirements.length} requirement {requirements.length === 1 ? "criterion" : "criteria"} in document
                  </p>
                </div>
              </div>
              <span className="self-start sm:self-auto px-3 py-1 rounded-full text-xs font-bold bg-green-100 text-green-800 border border-green-300">
                ✅ Analysis Complete
              </span>
            </div>

            {/* Requirements Cards Grid / List */}
            {requirements.length > 0 ? (
              <div className="grid grid-cols-1 gap-5">
                {requirements.map((req: TenderRequirement, index: number) => {
                  const reqId = req.requirement_id || req.id || `REQ-${String(index + 1).padStart(3, "0")}`;
                  const category = req.category || "General Requirement";
                  const isMandatory = req.mandatory === true || req.is_mandatory === true;
                  const evidenceList = getEvidenceList(req.evidence_required);

                  return (
                    <div
                      key={reqId || index}
                      className="bg-white rounded-xl shadow-sm border border-gray-200 hover:border-gray-300 hover:shadow-md transition-all overflow-hidden p-6 space-y-4"
                    >
                      {/* Card Header: requirement_id, category, and mandatory badge */}
                      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-gray-100">
                        <div className="flex items-center gap-2.5">
                          <span className="font-mono font-bold text-xs px-2.5 py-1 rounded-md bg-blue-50 text-blue-700 border border-blue-200">
                            {reqId}
                          </span>
                          <span className="text-base font-bold text-gray-900 flex items-center gap-1.5">
                            <Tag className="w-4 h-4 text-gray-400" />
                            {category}
                          </span>
                        </div>

                        {/* Bold Badge if Mandatory is true */}
                        {isMandatory ? (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300 shadow-xs uppercase tracking-wide">
                            <ShieldAlert className="w-3.5 h-3.5 text-rose-600" />
                            Mandatory
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-600 border border-gray-200">
                            Optional
                          </span>
                        )}
                      </div>

                      {/* Description Text Block */}
                      <div>
                        <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                          Description
                        </h5>
                        <p className="text-sm text-gray-700 leading-relaxed bg-gray-50/80 p-3.5 rounded-lg border border-gray-100">
                          {req.description || "No specific description text provided."}
                        </p>
                      </div>

                      {/* Evidence Required: Bulleted List */}
                      {evidenceList.length > 0 && (
                        <div>
                          <h5 className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                            <CheckSquare className="w-4 h-4 text-blue-600" />
                            Evidence Required ({evidenceList.length})
                          </h5>
                          <ul className="list-disc list-inside space-y-1.5 text-sm text-gray-800 bg-blue-50/40 p-4 rounded-lg border border-blue-100/80">
                            {evidenceList.map((evidenceItem: string, idx: number) => (
                              <li key={idx} className="leading-relaxed">
                                <span className="font-medium text-gray-900">{evidenceItem}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              /* Fallback if analysisResult format does not have explicit requirements array */
              <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200 text-center">
                <p className="text-sm text-gray-600">
                  No individual requirement items parsed. Raw response is available below:
                </p>
              </div>
            )}

            {/* Raw JSON Payload Viewer */}
            <div className="bg-gray-900 rounded-xl overflow-hidden shadow-sm border border-gray-800">
              <div className="px-5 py-3 bg-gray-800/90 border-b border-gray-700 flex items-center justify-between">
                <span className="text-xs font-mono font-medium text-gray-300">Raw JSON Analysis Payload</span>
                <span className="text-[11px] font-mono text-gray-400">application/json</span>
              </div>
              <div className="p-5 overflow-x-auto">
                <pre className="text-xs text-green-400 font-mono leading-relaxed">
                  {JSON.stringify(analysisResult, null, 2)}
                </pre>
              </div>
            </div>
          </motion.div>
        )}
      </main>
    </div>
  );
}
