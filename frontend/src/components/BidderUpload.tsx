"use client";

import { useState } from "react";
import {
  UploadCloud,
  FileText,
  AlertCircle,
  CheckCircle2,
  Tag,
  Sparkles,
  Search,
  FileCheck,
  Percent,
  Layers,
} from "lucide-react";
import { motion } from "framer-motion";
import { classifyDocument } from "@/services/api";

interface ClassificationResult {
  category?: string;
  document_type?: string;
  doc_type?: string;
  type?: string;
  confidence?: number;
  confidence_score?: number;
  score?: number;
  is_valid?: boolean;
  summary?: string;
  details?: Record<string, any>;
  metadata?: Record<string, any>;
  [key: string]: any;
}

export default function BidderUpload() {
  const [document, setDocument] = useState<File | null>(null);
  const [isClassifying, setIsClassifying] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [classificationResult, setClassificationResult] = useState<ClassificationResult | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setDocument(e.target.files[0]);
      setError(null);
      setClassificationResult(null);
    }
  };

  const handleClassify = async () => {
    if (!document) {
      setError("Please select a bidder evidence PDF document first.");
      return;
    }

    setIsClassifying(true);
    setError(null);
    setClassificationResult(null);

    try {
      const data = await classifyDocument(document);
      setClassificationResult(data);
    } catch (err: any) {
      setError(err?.message || "An unexpected error occurred while classifying the document.");
    } finally {
      setIsClassifying(false);
    }
  };

  const getCategoryName = (res: ClassificationResult): string => {
    return (
      res.category ||
      res.document_type ||
      res.doc_type ||
      res.type ||
      "UNKNOWN_DOCUMENT"
    ).toUpperCase();
  };

  const getConfidencePercentage = (res: ClassificationResult): number => {
    const val =
      res.confidence !== undefined
        ? res.confidence
        : res.confidence_score !== undefined
        ? res.confidence_score
        : res.score !== undefined
        ? res.score
        : null;

    if (val === null || val === undefined) return 100;
    const num = Number(val);
    if (isNaN(num)) return 0;
    // If fractional 0.0 - 1.0, convert to 0 - 100
    const pct = num <= 1 && num > 0 ? num * 100 : num;
    return Math.min(100, Math.max(0, Math.round(pct * 10) / 10));
  };

  return (
    <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200 space-y-6">
      {/* Section Header */}
      <div className="border-b border-gray-100 pb-4">
        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-100 mb-2">
          <Sparkles className="w-3 h-3" />
          AI Document Classifier
        </div>
        <h2 className="text-2xl font-extrabold text-gray-900 tracking-tight">
          Step 2: Upload Bidder Evidence
        </h2>
        <p className="text-sm text-gray-500 mt-1">
          Upload bidder supporting documents to automatically classify document type and verify requirement eligibility.
        </p>
      </div>

      {/* File Upload Area */}
      <div className="flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-lg p-10 text-center hover:bg-gray-50 transition-colors">
        <UploadCloud className="w-10 h-10 text-gray-400 mb-3" />
        <div className="flex text-sm text-gray-600">
          <label
            htmlFor="bidder-document-upload"
            className="relative cursor-pointer bg-white rounded-md font-medium text-blue-600 hover:text-blue-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-blue-500"
          >
            <span>Upload bidder document</span>
            <input
              id="bidder-document-upload"
              name="bidder-document-upload"
              type="file"
              accept=".pdf,application/pdf"
              className="sr-only"
              onChange={handleFileChange}
            />
          </label>
          <p className="pl-1">or drag and drop</p>
        </div>
        <p className="text-xs text-gray-500 mt-2">PDF documents only (e.g. GST Certificate, OEM Authorization, Balance Sheet)</p>
      </div>

      {/* Selected File Preview */}
      {document && (
        <div className="flex items-center p-4 bg-indigo-50/70 rounded-lg text-indigo-800 border border-indigo-100">
          <FileText className="w-5 h-5 mr-3 flex-shrink-0 text-indigo-600" />
          <span className="font-medium truncate text-sm">{document.name}</span>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="flex items-start p-4 bg-red-50 rounded-lg text-red-700 border border-red-200">
          <AlertCircle className="w-5 h-5 mr-3 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-sm">Classification Error</p>
            <p className="text-sm mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Submit Button */}
      <div className="flex justify-center pt-2">
        <button
          onClick={handleClassify}
          disabled={!document || isClassifying}
          className={`flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-white transition-all shadow-sm
            ${
              !document || isClassifying
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 cursor-pointer"
            }
          `}
        >
          {isClassifying ? (
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
              Classifying Document...
            </>
          ) : (
            <>
              <Search className="w-5 h-5 mr-2" />
              Classify Document
            </>
          )}
        </button>
      </div>

      {/* Sleek Classification Result Card */}
      {classificationResult && (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="mt-6 rounded-xl border border-indigo-200 overflow-hidden bg-white shadow-md"
        >
          {/* Card Top Banner */}
          <div className="px-6 py-4 bg-gradient-to-r from-indigo-50 via-blue-50 to-white border-b border-indigo-100 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center shadow-xs">
                <FileCheck className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-extrabold text-gray-900 text-base">Document Classification</h3>
                <p className="text-xs text-gray-500">Automated AI categorization and confidence evaluation</p>
              </div>
            </div>

            {/* Detected Category Bold Badge */}
            <div className="flex items-center">
              <span className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold font-mono tracking-wide bg-indigo-100 text-indigo-900 border border-indigo-300 shadow-xs uppercase">
                <Tag className="w-3.5 h-3.5 text-indigo-700" />
                {getCategoryName(classificationResult)}
              </span>
            </div>
          </div>

          <div className="p-6 space-y-6">
            {/* Metric & Progress Bar Section */}
            <div className="bg-gray-50/90 rounded-xl p-5 border border-gray-200/80 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Percent className="w-4 h-4 text-indigo-600" />
                  <span className="text-sm font-bold text-gray-800">Confidence Score</span>
                </div>
                <span className="text-base font-extrabold text-indigo-700 font-mono">
                  {getConfidencePercentage(classificationResult)}%
                </span>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${getConfidencePercentage(classificationResult)}%` }}
                  transition={{ duration: 0.6, ease: "easeOut" }}
                  className={`h-3 rounded-full ${
                    getConfidencePercentage(classificationResult) >= 80
                      ? "bg-gradient-to-r from-indigo-500 to-indigo-600"
                      : getConfidencePercentage(classificationResult) >= 50
                      ? "bg-gradient-to-r from-yellow-500 to-yellow-600"
                      : "bg-gradient-to-r from-red-500 to-red-600"
                  }`}
                />
              </div>
            </div>

            {/* Category & Details Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 bg-white rounded-lg border border-gray-200 shadow-2xs">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Detected Category</p>
                <p className="text-sm font-extrabold text-indigo-900 mt-1 font-mono">
                  {getCategoryName(classificationResult)}
                </p>
              </div>

              <div className="p-4 bg-white rounded-lg border border-gray-200 shadow-2xs">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Source Document</p>
                <p className="text-sm font-medium text-gray-800 mt-1 truncate">
                  {document?.name || "Uploaded PDF"}
                </p>
              </div>
            </div>

            {classificationResult.summary && (
              <div className="p-4 bg-white rounded-lg border border-gray-200 shadow-2xs">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Document Summary</p>
                <p className="text-sm text-gray-700 leading-relaxed">{classificationResult.summary}</p>
              </div>
            )}

            {/* Raw JSON Payload */}
            <div className="bg-gray-900 rounded-lg overflow-hidden border border-gray-800 shadow-inner">
              <div className="px-4 py-2 bg-gray-800/90 border-b border-gray-700 flex items-center justify-between">
                <span className="text-xs font-mono text-gray-300">Raw Classification Payload</span>
                <span className="text-[11px] font-mono text-gray-400">application/json</span>
              </div>
              <div className="p-4 overflow-x-auto">
                <pre className="text-xs text-green-400 font-mono leading-relaxed">
                  {JSON.stringify(classificationResult, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}
