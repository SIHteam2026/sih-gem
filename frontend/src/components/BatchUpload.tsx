"use client";

import { useState } from "react";
import {
  UploadCloud,
  FileArchive,
  FileText,
  AlertCircle,
  CheckCircle2,
  Tag,
  Sparkles,
  Search,
  Layers,
  ChevronDown,
  ChevronUp,
  FolderArchive,
  Eye,
  FileCheck,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { batchClassifyDocuments } from "@/services/api";

export interface DocumentInventoryItem {
  filename?: string;
  name?: string;
  category?: string;
  document_type?: string;
  doc_type?: string;
  text_preview?: string;
  preview?: string;
  extracted_text?: string;
  confidence?: number;
  confidence_score?: number;
  file_size?: string | number;
  [key: string]: any;
}

export default function BatchUpload() {
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [inventory, setInventory] = useState<DocumentInventoryItem[] | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [expandedPreviewIndex, setExpandedPreviewIndex] = useState<number | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      setZipFile(file);
      setError(null);
      setInventory(null);
    }
  };

  const handleBatchClassify = async () => {
    if (!zipFile) {
      setError("Please select a ZIP archive containing bidder documents first.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setInventory(null);

    try {
      const data = await batchClassifyDocuments(zipFile);
      if (Array.isArray(data)) {
        setInventory(data);
      } else if (data && Array.isArray(data.documents)) {
        setInventory(data.documents);
      } else if (data && Array.isArray(data.files)) {
        setInventory(data.files);
      } else if (data && Array.isArray(data.results)) {
        setInventory(data.results);
      } else if (data && Array.isArray(data.inventory)) {
        setInventory(data.inventory);
      } else {
        setInventory([]);
      }
    } catch (err: any) {
      setError(err?.message || "An unexpected error occurred during batch document classification.");
    } finally {
      setIsLoading(false);
    }
  };

  const getCategoryBadge = (category: string | undefined) => {
    const cat = String(category || "UNKNOWN_DOCUMENT").trim().toUpperCase();

    if (cat.includes("GST")) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-bold font-mono bg-emerald-100 text-emerald-800 border border-emerald-300">
          <FileCheck className="w-3 h-3 text-emerald-600" />
          {cat}
        </span>
      );
    }

    if (cat.includes("PAN") || cat.includes("TAX") || cat.includes("ITR")) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-bold font-mono bg-blue-100 text-blue-800 border border-blue-300">
          <Tag className="w-3 h-3 text-blue-600" />
          {cat}
        </span>
      );
    }

    if (cat.includes("OEM") || cat.includes("AUTH") || cat.includes("MANUFACTURER")) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-bold font-mono bg-purple-100 text-purple-800 border border-purple-300">
          <Tag className="w-3 h-3 text-purple-600" />
          {cat}
        </span>
      );
    }

    if (cat.includes("FINANCIAL") || cat.includes("BALANCE") || cat.includes("TURNOVER") || cat.includes("AUDIT")) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-bold font-mono bg-amber-100 text-amber-800 border border-amber-300">
          <Tag className="w-3 h-3 text-amber-600" />
          {cat}
        </span>
      );
    }

    if (cat.includes("INELIGIBLE") || cat.includes("INVALID") || cat.includes("MENU") || cat.includes("UNKNOWN")) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-bold font-mono bg-rose-100 text-rose-800 border border-rose-300">
          <AlertCircle className="w-3 h-3 text-rose-600" />
          {cat}
        </span>
      );
    }

    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-bold font-mono bg-indigo-100 text-indigo-800 border border-indigo-300">
        <Tag className="w-3 h-3 text-indigo-600" />
        {cat}
      </span>
    );
  };

  const getFilename = (item: DocumentInventoryItem): string => {
    return item.filename || item.name || "document.pdf";
  };

  const getTextPreview = (item: DocumentInventoryItem): string => {
    return item.text_preview || item.preview || item.extracted_text || item.summary || "No text preview extracted.";
  };

  const formatFileSize = (bytes?: number | string): string => {
    if (!bytes) return "";
    const n = Number(bytes);
    if (isNaN(n)) return String(bytes);
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  };

  const categoriesList = inventory
    ? Array.from(new Set(inventory.map((i) => String(i.category || i.document_type || "UNKNOWN").toUpperCase())))
    : [];

  const filteredInventory = (inventory || []).filter((item) => {
    const fname = getFilename(item).toLowerCase();
    const cat = String(item.category || item.document_type || "").toUpperCase();
    const preview = getTextPreview(item).toLowerCase();

    const matchesSearch =
      fname.includes(searchTerm.toLowerCase()) || preview.includes(searchTerm.toLowerCase());
    const matchesCat = selectedCategory === "ALL" || cat === selectedCategory;

    return matchesSearch && matchesCat;
  });

  return (
    <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200 space-y-6 font-sans">
      {/* Header */}
      <div className="border-b border-gray-100 pb-4">
        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-violet-50 text-violet-700 border border-violet-100 mb-2">
          <FolderArchive className="w-3.5 h-3.5" />
          Bulk Procurement Ingestion
        </div>
        <h2 className="text-2xl font-extrabold text-gray-900 tracking-tight">
          Batch Archive Classification
        </h2>
        <p className="text-sm text-gray-500 mt-1">
          Upload a compressed <code>.zip</code> archive of bidder evidence packages to automatically unpack, categorize, and extract document previews.
        </p>
      </div>

      {/* ZIP Upload Dropzone */}
      <div className="flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-lg p-10 text-center hover:bg-gray-50 transition-colors">
        <FileArchive className="w-12 h-12 text-violet-400 mb-3" />
        <div className="flex text-sm text-gray-600">
          <label
            htmlFor="batch-zip-upload"
            className="relative cursor-pointer bg-white rounded-md font-medium text-violet-600 hover:text-violet-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-violet-500"
          >
            <span>Upload ZIP archive</span>
            <input
              id="batch-zip-upload"
              name="batch-zip-upload"
              type="file"
              accept=".zip,application/zip,application/x-zip-compressed"
              className="sr-only"
              onChange={handleFileChange}
            />
          </label>
          <p className="pl-1">containing bidder PDFs</p>
        </div>
        <p className="text-xs text-gray-500 mt-2">Supports .zip archives containing multiple document PDFs</p>
      </div>

      {/* Selected File Details */}
      {zipFile && (
        <div className="flex items-center justify-between p-4 bg-violet-50/70 rounded-lg text-violet-900 border border-violet-100">
          <div className="flex items-center gap-3 truncate">
            <FileArchive className="w-5 h-5 text-violet-600 flex-shrink-0" />
            <span className="font-semibold text-sm truncate">{zipFile.name}</span>
          </div>
          <span className="text-xs font-mono text-violet-700 bg-violet-100/80 px-2 py-1 rounded">
            {formatFileSize(zipFile.size)}
          </span>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="flex items-start p-4 bg-red-50 rounded-lg text-red-700 border border-red-200">
          <AlertCircle className="w-5 h-5 mr-3 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-sm">Batch Processing Error</p>
            <p className="text-sm mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Action Button */}
      <div className="flex justify-center pt-2">
        <button
          onClick={handleBatchClassify}
          disabled={!zipFile || isLoading}
          className={`flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-white transition-all shadow-sm ${
            !zipFile || isLoading
              ? "bg-gray-400 cursor-not-allowed"
              : "bg-violet-600 hover:bg-violet-700 active:bg-violet-800 cursor-pointer"
          }`}
        >
          {isLoading ? (
            <>
              <svg
                className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Unpacking & Classifying Archive...
            </>
          ) : (
            <>
              <Layers className="w-5 h-5 mr-2" />
              Batch Classify Documents
            </>
          )}
        </button>
      </div>

      {/* Returned Document Inventory Table */}
      {inventory && (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="mt-8 rounded-xl border border-gray-200 overflow-hidden bg-white shadow-sm space-y-4"
        >
          {/* Table Header Controls */}
          <div className="p-5 bg-gradient-to-r from-gray-50 via-white to-gray-50 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h3 className="font-extrabold text-gray-900 text-lg flex items-center gap-2">
                <FileCheck className="w-5 h-5 text-violet-600" />
                Document Inventory ({inventory.length} Files Discovered)
              </h3>
              <p className="text-xs text-gray-500 mt-0.5">
                Automated classification & OCR text extraction summary across the uploaded package
              </p>
            </div>

            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Filter files..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-8 pr-3 py-1.5 bg-white border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-violet-500"
                />
              </div>

              {categoriesList.length > 0 && (
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="px-2.5 py-1.5 bg-white border border-gray-300 rounded-lg text-xs font-medium text-gray-700 focus:outline-none focus:ring-2 focus:ring-violet-500"
                >
                  <option value="ALL">All Types</option>
                  {categoriesList.map((cat, idx) => (
                    <option key={idx} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {/* Data Table */}
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
              <thead className="bg-gray-50 text-xs font-bold text-gray-600 uppercase tracking-wider">
                <tr>
                  <th scope="col" className="px-6 py-3.5">
                    File Name
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    Classification Category
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    Extracted Text Preview
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {filteredInventory.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="px-6 py-10 text-center text-gray-500 text-sm">
                      No documents found matching the filter criteria.
                    </td>
                  </tr>
                ) : (
                  filteredInventory.map((item, index) => {
                    const fname = getFilename(item);
                    const category = item.category || item.document_type || item.doc_type || item.type;
                    const preview = getTextPreview(item);
                    const isExpanded = expandedPreviewIndex === index;

                    return (
                      <tr key={index} className="hover:bg-gray-50/70 transition-colors">
                        {/* 1. File Name */}
                        <td className="px-6 py-4 whitespace-nowrap text-gray-900 font-medium max-w-[220px]">
                          <div className="flex items-center gap-2.5 truncate">
                            <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0 text-gray-600">
                              <FileText className="w-4 h-4" />
                            </div>
                            <div className="truncate">
                              <p className="text-sm font-bold text-gray-900 truncate">{fname}</p>
                              {item.file_size && (
                                <p className="text-[11px] text-gray-400 font-mono">{formatFileSize(item.file_size)}</p>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* 2. Detected Classification Category Badge */}
                        <td className="px-6 py-4 whitespace-nowrap">
                          {getCategoryBadge(category)}
                        </td>

                        {/* 3. Text Preview */}
                        <td className="px-6 py-4 text-xs text-gray-700 max-w-md">
                          <div className="bg-gray-50 p-3 rounded-lg border border-gray-200/80 font-mono text-[11px] leading-relaxed relative">
                            <p className={isExpanded ? "whitespace-pre-wrap" : "line-clamp-2"}>
                              {preview}
                            </p>
                            {preview.length > 90 && (
                              <button
                                type="button"
                                onClick={() => setExpandedPreviewIndex(isExpanded ? null : index)}
                                className="mt-1.5 text-violet-600 hover:text-violet-800 font-sans font-semibold flex items-center gap-1 text-[11px]"
                              >
                                {isExpanded ? (
                                  <>
                                    <ChevronUp className="w-3 h-3" /> Show less
                                  </>
                                ) : (
                                  <>
                                    <ChevronDown className="w-3 h-3" /> Expand preview
                                  </>
                                )}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}
    </div>
  );
}
