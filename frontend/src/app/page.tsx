"use client";

import { useState } from "react";
import {
  UploadCloud,
  CheckCircle,
  FileText,
  AlertCircle,
  AlertTriangle,
  Info,
  Check,
  XCircle,
  Clock,
} from "lucide-react";
import { motion } from "framer-motion";
import { verifyGSTDocument } from "@/services/api";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, any> | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError(null);
      setResult(null);
    }
  };

  const handleSubmit = async () => {
    if (!file) {
      setError("Please select a PDF document before submitting.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await verifyGSTDocument(file);
      setResult(data);
    } catch (err: any) {
      setError(err?.message || "An unexpected error occurred during verification.");
    } finally {
      setIsLoading(false);
    }
  };

  // Helper to render colored status badge based on result.status
  const renderStatusBadge = (statusValue: any) => {
    const rawStatus = String(statusValue || "").trim().toUpperCase();

    if (rawStatus.includes("VERIFIED") || rawStatus === "SUCCESS") {
      return (
        <span className="inline-flex items-center px-3.5 py-1.5 rounded-full text-sm font-bold bg-green-100 text-green-800 border border-green-300 shadow-sm">
          ✅ VERIFIED
        </span>
      );
    }

    if (rawStatus.includes("MISMATCH") || rawStatus === "FAILED" || rawStatus === "FAIL") {
      return (
        <span className="inline-flex items-center px-3.5 py-1.5 rounded-full text-sm font-bold bg-red-100 text-red-800 border border-red-300 shadow-sm">
          🔴 MISMATCH
        </span>
      );
    }

    if (rawStatus.includes("REVIEW") || rawStatus === "WARNING" || rawStatus === "PENDING") {
      return (
        <span className="inline-flex items-center px-3.5 py-1.5 rounded-full text-sm font-bold bg-yellow-100 text-yellow-800 border border-yellow-300 shadow-sm">
          🟡 REVIEW
        </span>
      );
    }

    // Default badge fallback
    return (
      <span className="inline-flex items-center px-3.5 py-1.5 rounded-full text-sm font-bold bg-gray-100 text-gray-800 border border-gray-300 shadow-sm">
        {statusValue || "PROCESSED"}
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center py-12 px-4 sm:px-6 lg:px-8 font-sans">
      <div className="w-full max-w-3xl space-y-8">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight sm:text-5xl">
            SIH26100 Evidence Engine
          </h1>
          <p className="mt-4 text-lg text-gray-600">
            Upload a GST PDF document to extract, verify, and evaluate evidence.
          </p>
        </div>

        {/* Upload Form Card */}
        <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200">
          <div className="flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:bg-gray-50 transition-colors">
            <UploadCloud className="w-12 h-12 text-gray-400 mb-4" />
            <div className="flex text-sm text-gray-600">
              <label
                htmlFor="file-upload"
                className="relative cursor-pointer bg-white rounded-md font-medium text-blue-600 hover:text-blue-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-blue-500"
              >
                <span>Upload a file</span>
                <input
                  id="file-upload"
                  name="file-upload"
                  type="file"
                  accept=".pdf,application/pdf"
                  className="sr-only"
                  onChange={handleFileChange}
                />
              </label>
              <p className="pl-1">or drag and drop</p>
            </div>
            <p className="text-xs text-gray-500 mt-2">PDF files only (e.g. GST Certificate)</p>
          </div>

          {/* Selected File Preview */}
          {file && (
            <div className="mt-4 flex items-center p-4 bg-blue-50 rounded-lg text-blue-700 border border-blue-100">
              <FileText className="w-5 h-5 mr-3 flex-shrink-0" />
              <span className="font-medium truncate">{file.name}</span>
            </div>
          )}

          {/* Network/API Error Banner */}
          {error && (
            <div className="mt-4 flex items-start p-4 bg-red-50 rounded-lg text-red-700 border border-red-200">
              <AlertCircle className="w-5 h-5 mr-3 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-sm">Verification Error</p>
                <p className="text-sm mt-1">{error}</p>
              </div>
            </div>
          )}

          {/* Submit Button */}
          <div className="mt-6 flex justify-center">
            <button
              onClick={handleSubmit}
              disabled={!file || isLoading}
              className={`flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-white transition-all shadow-sm
                ${
                  !file || isLoading
                    ? "bg-gray-400 cursor-not-allowed"
                    : "bg-blue-600 hover:bg-blue-700 active:bg-blue-800 cursor-pointer"
                }
              `}
            >
              {isLoading ? (
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
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                  Processing...
                </>
              ) : (
                <>
                  <CheckCircle className="w-5 h-5 mr-2" />
                  Verify Document
                </>
              )}
            </button>
          </div>
        </div>

        {/* Dynamic Verification Results Section */}
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="bg-white rounded-xl shadow-md border border-gray-200 overflow-hidden"
          >
            {/* Result Header with Status Badge */}
            <div className="px-6 py-5 bg-gray-50 border-b border-gray-200 flex flex-wrap items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-bold text-gray-900">Verification Result</h3>
                <p className="text-xs text-gray-500 mt-0.5">Automated GST extraction & validation summary</p>
              </div>
              <div className="flex items-center">
                {renderStatusBadge(result.status)}
              </div>
            </div>

            <div className="p-6 space-y-6">
              {/* Errors List in Red Alert Box */}
              {Array.isArray(result.errors) && result.errors.length > 0 && (
                <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-red-800">
                  <div className="flex items-center mb-2">
                    <AlertTriangle className="w-5 h-5 mr-2 flex-shrink-0 text-red-600" />
                    <span className="font-semibold text-sm text-red-900">
                      Errors & Discrepancies Detected ({result.errors.length})
                    </span>
                  </div>
                  <ul className="list-disc list-inside space-y-1 text-sm text-red-700 ml-1">
                    {result.errors.map((item: any, idx: number) => (
                      <li key={idx} className="leading-relaxed">
                        {typeof item === "string"
                          ? item
                          : item?.message || JSON.stringify(item)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Key Summary Cards if available */}
              {(result.gstin || result.entityName || result.legal_name || result.matchScore !== undefined) && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {(result.gstin || result.GSTIN) && (
                    <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">GSTIN</p>
                      <p className="text-sm font-bold text-gray-900 mt-1 font-mono">{result.gstin || result.GSTIN}</p>
                    </div>
                  )}

                  {(result.entityName || result.legal_name || result.tradeName) && (
                    <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Legal / Entity Name</p>
                      <p className="text-sm font-bold text-gray-900 mt-1">{result.entityName || result.legal_name || result.tradeName}</p>
                    </div>
                  )}

                  {result.matchScore !== undefined && (
                    <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Match Score</p>
                      <p className="text-sm font-bold text-gray-900 mt-1">{result.matchScore}%</p>
                    </div>
                  )}

                  {result.isVerified !== undefined && (
                    <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Verification State</p>
                      <p className="text-sm font-bold text-gray-900 mt-1">
                        {result.isVerified ? "Confirmed" : "Unverified / Mismatch"}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Raw JSON Data Viewer */}
              <div className="bg-gray-900 rounded-lg overflow-hidden border border-gray-800">
                <div className="px-4 py-2.5 bg-gray-800/80 border-b border-gray-700/60 flex items-center justify-between">
                  <span className="text-xs font-mono font-medium text-gray-300">Raw Response Payload</span>
                  <span className="text-[11px] font-mono text-gray-400">application/json</span>
                </div>
                <div className="p-4 overflow-x-auto">
                  <pre className="text-xs text-green-400 font-mono leading-relaxed">
                    {JSON.stringify(result, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
