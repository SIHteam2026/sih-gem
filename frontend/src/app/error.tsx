"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, RefreshCw, ArrowLeft, Home } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("App Error Boundary caught:", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-[#f7f6f2] text-[#162333] flex flex-col items-center justify-center p-6 font-sans">
      <div className="max-w-md w-full bg-white rounded-2xl border border-[#cbd5e1] p-8 shadow-sm text-center space-y-6">
        <div className="w-12 h-12 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center mx-auto">
          <AlertTriangle className="w-6 h-6" />
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-bold tracking-tight text-[#0f172a]">
            Unable to Load Workspace
          </h2>
          <p className="text-xs text-[#64748b] leading-relaxed">
            {error?.message || "An unexpected error occurred while rendering this procurement view."}
          </p>
        </div>

        {error?.digest && (
          <div className="bg-[#f8fafc] border border-[#e2e8f0] rounded-lg p-2.5 font-mono text-[10px] text-[#64748b]">
            Digest: {error.digest}
          </div>
        )}

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <button
            type="button"
            onClick={() => reset()}
            className="w-full sm:w-auto focus-ring inline-flex items-center justify-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-[#163a5f] hover:bg-[#204c78] rounded-lg transition-colors cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Try Again
          </button>

          <Link
            href="/procurements"
            className="w-full sm:w-auto focus-ring inline-flex items-center justify-center gap-2 px-4 py-2 text-xs font-semibold text-[#163a5f] bg-[#edf2f7] hover:bg-[#e2e8f0] rounded-lg transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Procurements
          </Link>

          <Link
            href="/"
            className="w-full sm:w-auto focus-ring inline-flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-[#64748b] hover:text-[#0f172a] rounded-lg transition-colors"
          >
            <Home className="w-3.5 h-3.5" /> Home
          </Link>
        </div>
      </div>
    </div>
  );
}
