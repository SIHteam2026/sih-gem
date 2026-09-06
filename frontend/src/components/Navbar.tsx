"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, ChevronDown } from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();

  return (
    <header className="w-full bg-transparent sticky top-0 z-30 border-b border-transparent select-none">
      <div className="mx-auto flex h-16 max-w-[1360px] items-center justify-between px-6 sm:px-10 lg:px-12">
        {/* Left: Brand Identity with Diamond/Gem Icon */}
        <Link href="/" className="focus-ring flex items-center gap-2.5 rounded-sm" aria-label="OPAL Home">
          <svg
            className="h-5 w-5 text-[#111827]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            {/* Faceted Gem / Diamond */}
            <path d="M6 3h12l4 6-10 12L2 9z" />
            <path d="M11 3 8 9l4 12 4-12-3-6" />
            <path d="M2 9h20" />
          </svg>
          <span className="text-base font-bold tracking-tight text-[#111827]">
            Opal
          </span>
        </Link>

        {/* Center: Quiet Floating Navigation Pill */}
        <nav
          className="hidden md:flex items-center gap-1 rounded-full bg-[#f3f4f6] px-3.5 py-1.5 border border-[#e5e7eb]/60"
          aria-label="Main navigation"
        >
          <Link
            href="/procurements"
            className={`focus-ring flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              pathname.startsWith("/procurements") || pathname.startsWith("/tenders") || pathname.startsWith("/submissions")
                ? "bg-white text-[#111827] shadow-xs"
                : "text-[#4b5563] hover:text-[#111827]"
            }`}
          >
            <span>Procurements</span>
            <ChevronDown className="h-3 w-3 opacity-60" />
          </Link>

          <Link
            href="/history"
            className={`focus-ring flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              pathname === "/history"
                ? "bg-white text-[#111827] shadow-xs"
                : "text-[#4b5563] hover:text-[#111827]"
            }`}
          >
            <span>Activity</span>
            <ChevronDown className="h-3 w-3 opacity-60" />
          </Link>

          <Link
            href="/tender"
            className={`focus-ring flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              pathname === "/tender"
                ? "bg-white text-[#111827] shadow-xs"
                : "text-[#4b5563] hover:text-[#111827]"
            }`}
          >
            <span>Insights</span>
            <ChevronDown className="h-3 w-3 opacity-60" />
          </Link>

          <Link
            href="/mock-gem"
            className={`focus-ring flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              pathname === "/mock-gem"
                ? "bg-white text-[#111827] shadow-xs font-mono"
                : "text-[#4b5563] hover:text-[#111827]"
            }`}
          >
            <span>More</span>
            <ChevronDown className="h-3 w-3 opacity-60" />
          </Link>
        </nav>

        {/* Right: Notifications & Officer Profile Context */}
        <div className="flex items-center gap-4 text-xs">
          <button
            type="button"
            className="focus-ring rounded-full p-1.5 text-[#6b7280] hover:text-[#111827] transition-colors"
            aria-label="Notifications"
          >
            <Bell className="h-4 w-4" />
          </button>

          <div className="flex items-center gap-2">
            <span className="grid h-6 w-6 place-items-center rounded-full bg-[#111827] text-[10px] font-bold text-white select-none">
              AS
            </span>
            <span className="font-semibold text-[#111827] text-xs">
              A. Srivastav
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
