import React, { ReactNode } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import StatusBadge from "./StatusBadge";
import SourceBadge from "./SourceBadge";

export interface BreadcrumbItem {
  label: string;
  href?: string;
  active?: boolean;
}

interface WorkspaceHeaderProps {
  breadcrumbs?: BreadcrumbItem[];
  eyebrow?: string;
  title: string;
  reference?: string;
  organization?: string;
  sourceSystem?: string;
  status?: string;
  updatedAt?: string;
  actions?: ReactNode;
}

export default function WorkspaceHeader({
  breadcrumbs,
  eyebrow = "Procurement Workspace",
  title,
  reference,
  organization,
  sourceSystem,
  status,
  updatedAt,
  actions,
}: WorkspaceHeaderProps) {
  return (
    <header className="border-b border-[#d9ddd9] pb-6 mb-8">
      {/* Breadcrumbs */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="mb-4">
          <ol className="flex flex-wrap items-center gap-1.5 text-xs text-[#62707c]">
            {breadcrumbs.map((item, index) => {
              const isLast = index === breadcrumbs.length - 1;
              return (
                <li key={index} className="flex items-center gap-1.5">
                  {index > 0 && (
                    <ChevronRight className="w-3.5 h-3.5 text-[#919ea9]" aria-hidden="true" />
                  )}
                  {item.href && !isLast ? (
                    <Link
                      href={item.href}
                      className="focus-ring hover:text-[#163a5f] hover:underline underline-offset-2 transition-colors"
                    >
                      {item.label}
                    </Link>
                  ) : (
                    <span className={isLast ? "font-semibold text-[#162333]" : ""}>
                      {item.label}
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
        </nav>
      )}

      {/* Eyebrow & Badges */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="eyebrow">{eyebrow}</span>
          {reference && (
            <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-[#edf2f5] text-[#1c3850] border border-[#cbd9e2]">
              {reference}
            </span>
          )}
          {sourceSystem && <SourceBadge source={sourceSystem} />}
        </div>
        {status && <StatusBadge status={status} />}
      </div>

      {/* Main Title & Organization */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div className="max-w-3xl">
          <h1 className="text-2xl sm:text-3xl font-medium tracking-tight text-[#162333] leading-snug">
            {title}
          </h1>
          {organization && (
            <p className="mt-1.5 text-sm font-medium text-[#4f5f6e]">
              Issuing Organization: <span className="text-[#1b2b3b]">{organization}</span>
            </p>
          )}
        </div>

        {/* Actions & Timestamps */}
        <div className="flex flex-col items-start md:items-end gap-2 shrink-0">
          {actions}
          {updatedAt && (
            <span className="text-[11px] text-[#71808b]">
              Last updated:{" "}
              <time dateTime={updatedAt}>
                {new Date(updatedAt).toLocaleString("en-IN", {
                  dateStyle: "medium",
                  timeStyle: "short",
                })}
              </time>
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
