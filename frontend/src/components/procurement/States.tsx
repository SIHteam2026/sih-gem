import React, { ReactNode } from "react";
import { Loader2, AlertCircle, Inbox, RefreshCw, ArrowLeft } from "lucide-react";
import Link from "next/link";

interface LoadingStateProps {
  message?: string;
  className?: string;
}

export function LoadingState({
  message = "Loading procurement workspace data…",
  className = "",
}: LoadingStateProps) {
  return (
    <div
      className={`min-h-64 flex flex-col items-center justify-center p-8 text-center rounded border border-[#d9ddd9] bg-[#fffefa] ${className}`}
      role="status"
      aria-live="polite"
    >
      <Loader2 className="h-6 w-6 animate-spin text-[#163a5f]" aria-hidden="true" />
      <p className="mt-3 text-sm font-medium text-[#2d3e4f]">{message}</p>
      <p className="mt-1 text-xs text-[#71808a]">Querying canonical procurement records</p>
    </div>
  );
}

interface EmptyStateProps {
  title?: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
}

export function EmptyState({
  title = "No procurements available",
  description = "Procurements arrive automatically when ingested from authorized sources (such as GeM). Use the Mock-GeM development simulator to ingest sample data.",
  action,
  icon,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`min-h-72 flex flex-col items-center justify-center p-8 text-center rounded border border-dashed border-[#cbd2d1] bg-[#fffefa] ${className}`}
    >
      <div className="p-3 rounded-full bg-[#f2f4f2] text-[#556977] mb-3">
        {icon || <Inbox className="h-6 w-6" aria-hidden="true" />}
      </div>
      <h3 className="text-base font-semibold text-[#162333]">{title}</h3>
      <p className="mt-2 max-w-md text-xs leading-5 text-[#65717b]">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  backHref?: string;
  backLabel?: string;
  className?: string;
}

export function ErrorState({
  title = "Unable to load workspace",
  message,
  onRetry,
  backHref,
  backLabel = "Return to procurements",
  className = "",
}: ErrorStateProps) {
  return (
    <div
      className={`p-6 rounded border border-[#e8c7be] bg-[#fff7f5] text-[#783626] ${className}`}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="h-5 w-5 shrink-0 text-[#b54632] mt-0.5" aria-hidden="true" />
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-[#66281b]">{title}</h3>
          <p className="mt-1 text-xs leading-relaxed text-[#783626]">{message}</p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="focus-ring inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#fff] bg-[#913b28] hover:bg-[#7b3121] rounded transition-colors cursor-pointer"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                Retry query
              </button>
            )}
            {backHref && (
              <Link
                href={backHref}
                className="focus-ring inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#5a271c] bg-[#fff] border border-[#e0bcb1] hover:bg-[#faf4f2] rounded transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
                {backLabel}
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
