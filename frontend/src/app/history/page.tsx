"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Clock, RefreshCw, AlertCircle, FileSpreadsheet } from "lucide-react";
import { fetchVerificationHistory } from "@/services/api";
import Navbar from "@/components/Navbar";

interface VerificationRecord {
  id?: string | number;
  created_at?: string;
  date?: string;
  timestamp?: string;
  verified_at?: string;
  gstin?: string;
  GSTIN?: string;
  company_name?: string;
  companyName?: string;
  entity_name?: string;
  entityName?: string;
  legal_name?: string;
  trade_name?: string;
  status?: string;
  matchScore?: number;
  [key: string]: any;
}

export default function HistoryPage() {
  const [history, setHistory] = useState<VerificationRecord[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchVerificationHistory();
      if (Array.isArray(data)) {
        setHistory(data);
      } else if (data && Array.isArray((data as any).history)) {
        setHistory((data as any).history);
      } else if (data && Array.isArray((data as any).data)) {
        setHistory((data as any).data);
      } else {
        setHistory([]);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load verification history.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const renderStatusBadge = (statusValue: any) => {
    const rawStatus = String(statusValue || "").trim().toUpperCase();

    if (rawStatus.includes("VERIFIED") || rawStatus === "SUCCESS") {
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold bg-green-100 text-green-800 border border-green-300">
          ✅ VERIFIED
        </span>
      );
    }

    if (rawStatus.includes("MISMATCH") || rawStatus === "FAILED" || rawStatus === "FAIL") {
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold bg-red-100 text-red-800 border border-red-300">
          🔴 MISMATCH
        </span>
      );
    }

    if (rawStatus.includes("REVIEW") || rawStatus === "WARNING" || rawStatus === "PENDING") {
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold bg-yellow-100 text-yellow-800 border border-yellow-300">
          🟡 REVIEW
        </span>
      );
    }

    return (
      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold bg-gray-100 text-gray-800 border border-gray-300">
        {statusValue || "UNKNOWN"}
      </span>
    );
  };

  const formatDate = (record: VerificationRecord) => {
    const dateVal = record.created_at || record.date || record.timestamp || record.verified_at;
    if (!dateVal) return "N/A";
    try {
      const parsed = new Date(dateVal);
      if (isNaN(parsed.getTime())) return String(dateVal);
      return parsed.toLocaleString("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
      });
    } catch {
      return String(dateVal);
    }
  };

  const getCompanyName = (record: VerificationRecord) => {
    return (
      record.company_name ||
      record.companyName ||
      record.entity_name ||
      record.entityName ||
      record.legal_name ||
      record.trade_name ||
      "N/A"
    );
  };

  const getGSTIN = (record: VerificationRecord) => {
    return record.gstin || record.GSTIN || record.extracted_gstin || "N/A";
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <Navbar />

      <main className="flex-1 max-w-6xl w-full mx-auto py-10 px-4 sm:px-6 lg:px-8 space-y-8">
        {/* Navigation & Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
              Verification History Logs
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              Audit log of all previously processed and verified GST PDF certificates
            </p>
          </div>

          <button
            onClick={loadHistory}
            disabled={isLoading}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-sm font-medium rounded-lg shadow-sm transition-all disabled:opacity-50 cursor-pointer self-start sm:self-auto"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh Logs
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-semibold">Unable to load history</p>
              <p className="mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {/* Table Container */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          {isLoading ? (
            <div className="py-20 flex flex-col items-center justify-center text-center">
              <svg
                className="animate-spin h-8 w-8 text-blue-600 mb-4"
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
              <p className="text-sm font-medium text-gray-600">Loading verification records...</p>
            </div>
          ) : history.length === 0 ? (
            <div className="py-16 flex flex-col items-center justify-center text-center px-4">
              <FileSpreadsheet className="w-12 h-12 text-gray-300 mb-3" />
              <h3 className="text-base font-semibold text-gray-900">No verification history yet</h3>
              <p className="text-sm text-gray-500 mt-1 max-w-sm">
                Documents verified through the main dashboard will automatically appear in this audit log.
              </p>
              <Link
                href="/"
                className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
              >
                Verify a Document Now
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th scope="col" className="px-6 py-3.5 font-semibold text-gray-900">
                      Date
                    </th>
                    <th scope="col" className="px-6 py-3.5 font-semibold text-gray-900">
                      GSTIN
                    </th>
                    <th scope="col" className="px-6 py-3.5 font-semibold text-gray-900">
                      Company Name
                    </th>
                    <th scope="col" className="px-6 py-3.5 font-semibold text-gray-900">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {history.map((record, index) => (
                    <tr
                      key={record.id || index}
                      className="hover:bg-gray-50/80 transition-colors"
                    >
                      {/* Date */}
                      <td className="px-6 py-4 whitespace-nowrap text-gray-600 flex items-center gap-2">
                        <Clock className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        <span>{formatDate(record)}</span>
                      </td>

                      {/* GSTIN */}
                      <td className="px-6 py-4 whitespace-nowrap font-mono font-medium text-gray-900">
                        {getGSTIN(record)}
                      </td>

                      {/* Company Name */}
                      <td className="px-6 py-4 whitespace-nowrap font-medium text-gray-800">
                        {getCompanyName(record)}
                      </td>

                      {/* Status */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        {renderStatusBadge(record.status)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
