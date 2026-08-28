"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck, PlusCircle, History } from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();

  return (
    <header className="w-full bg-white border-b border-gray-200 sticky top-0 z-50 shadow-xs">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo / Brand */}
          <Link
            href="/"
            className="flex items-center gap-2.5 font-bold text-gray-900 text-lg hover:opacity-90 transition-opacity"
          >
            <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-sm">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <span className="hidden sm:inline">SIH Evidence Engine</span>
            <span className="sm:hidden">SIH Engine</span>
          </Link>

          {/* Navigation Links */}
          <nav className="flex items-center gap-1 sm:gap-2">
            <Link
              href="/"
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                pathname === "/"
                  ? "bg-blue-50 text-blue-700 font-semibold"
                  : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
              }`}
            >
              <PlusCircle className="w-4 h-4" />
              <span>New Verification</span>
            </Link>

            <Link
              href="/history"
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                pathname === "/history"
                  ? "bg-blue-50 text-blue-700 font-semibold"
                  : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
              }`}
            >
              <History className="w-4 h-4" />
              <span>History Logs</span>
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
}
