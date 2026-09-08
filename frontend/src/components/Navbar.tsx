"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, ChevronDown } from "lucide-react";

export default function Navbar() {
  const rawPathname = usePathname();
  const pathname = rawPathname || "";
  const [scrolled, setScrolled] = useState<boolean>(false);

  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 10) {
        setScrolled(true);
      } else {
        setScrolled(false);
      }
    };

    // Initialize state on mount
    handleScroll();

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header
      className={`w-full sticky top-0 z-30 transition-all duration-300 select-none ${
        scrolled
          ? "bg-[#f7f6f2]/75 backdrop-blur-md shadow-xs border-b border-[#e5e8e5]/50"
          : "bg-transparent border-none"
      }`}
    >
      <div className="mx-auto flex h-16 max-w-[1360px] items-center justify-between px-6 sm:px-10 lg:px-12">
        {/* Left: Brand Identity & Home Link with Diamond/Gem Icon */}
        <Link
          href="/"
          className="focus-ring group flex items-center gap-2 rounded-xl px-2.5 py-1.5 hover:bg-slate-100 transition-all cursor-pointer"
          aria-label="OPAL Home Workspace"
          title="Return to OPAL Home Workspace"
        >
          <div className="grid h-7 w-7 place-items-center rounded-lg bg-[#111827] text-white shadow-2xs group-hover:bg-[#163a5f] transition-colors">
            <svg
              className="h-4 w-4 text-white"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M6 3h12l4 6-10 12L2 9z" />
              <path d="M11 3 8 9l4 12 4-12-3-6" />
              <path d="M2 9h20" />
            </svg>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-base font-bold tracking-tight text-[#111827]">
              Opal
            </span>
            <span className="text-[11px] font-medium text-slate-500 bg-slate-100 border border-slate-200/80 px-2 py-0.5 rounded-full group-hover:bg-white group-hover:text-[#111827] transition-all">
              Home
            </span>
          </div>
        </Link>

        {/* Center: Quiet Floating Navigation Pill */}
        <nav
          className={`hidden md:flex items-center gap-1 rounded-full px-3 py-1.5 transition-all duration-300 ${
            scrolled
              ? "bg-[#eaecea]/80 border border-[#daddda]/70"
              : "bg-[#f3f4f6] border border-[#e5e7eb]/60"
          }`}
          aria-label="Main navigation"
        >
          <Link
            href="/"
            className={`focus-ring flex items-center gap-1 rounded-full px-3.5 py-1 text-xs font-medium transition-all ${
              pathname === "/"
                ? "bg-white text-[#111827] shadow-xs font-bold"
                : "text-[#4b5563] hover:text-[#111827]"
            }`}
          >
            <span>Home</span>
          </Link>

          <Link
            href="/procurements"
            className={`focus-ring flex items-center gap-1 rounded-full px-3.5 py-1 text-xs font-medium transition-all ${
              pathname.startsWith("/procurements") || pathname.startsWith("/tenders") || pathname.startsWith("/submissions")
                ? "bg-white text-[#111827] shadow-xs font-bold"
                : "text-[#4b5563] hover:text-[#111827]"
            }`}
          >
            <span>Procurements</span>
          </Link>

          <Link
            href="/history"
            className={`focus-ring flex items-center gap-1 rounded-full px-3.5 py-1 text-xs font-medium transition-all ${
              pathname === "/history"
                ? "bg-white text-[#111827] shadow-xs font-bold"
                : "text-[#4b5563] hover:text-[#111827]"
            }`}
          >
            <span>Audit Trail</span>
          </Link>

          <Link
            href="/tender"
            className={`focus-ring flex items-center gap-1 rounded-full px-3.5 py-1 text-xs font-medium transition-all ${
              pathname === "/tender"
                ? "bg-white text-[#111827] shadow-xs font-bold"
                : "text-[#4b5563] hover:text-[#111827]"
            }`}
          >
            <span>Quick Audit</span>
          </Link>

          <Link
            href="/mock-gem"
            className={`focus-ring flex items-center gap-1 rounded-full px-3.5 py-1 text-xs font-medium transition-all ${
              pathname === "/mock-gem"
                ? "bg-white text-[#111827] shadow-xs font-bold"
                : "text-[#4b5563] hover:text-[#111827]"
            }`}
          >
            <span>GeM Gateway</span>
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
