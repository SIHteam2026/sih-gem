"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CircleHelp } from "lucide-react";

const links = [
  { href: "/procurements", label: "Procurements" },
  { href: "/history", label: "History" },
  { href: "/mock-gem", label: "Mock-GeM (Dev)" },
];

export default function Navbar() {
  const pathname = usePathname();
  return (
    <header className="border-b border-[#d9ddd9] bg-[#fffefa]/95 backdrop-blur-sm sticky top-0 z-30">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8">
        <Link href="/procurements" className="focus-ring flex items-center gap-3 rounded-sm">
          <span className="grid h-8 w-8 place-items-center border border-[#163a5f] bg-[#163a5f] text-xs font-bold tracking-tight text-white rounded">
            OP
          </span>
          <span className="text-sm font-semibold tracking-[-0.01em] text-[#162333]">
            OPAL <span className="text-xs font-normal text-[#6c7b88]">| Procurement Review</span>
          </span>
        </Link>
        <nav className="hidden items-center gap-1 sm:flex" aria-label="Main navigation">
          {links.map((link) => {
            const isProcurementGroup =
              link.href === "/procurements" &&
              (pathname.startsWith("/procurements") ||
                pathname.startsWith("/tenders") ||
                pathname.startsWith("/submissions"));
            const current =
              pathname === link.href ||
              isProcurementGroup ||
              (link.href !== "/procurements" && pathname.startsWith(link.href));

            return (
              <Link
                key={link.href}
                href={link.href}
                className={`focus-ring rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                  current
                    ? "bg-[#edf2f5] font-semibold text-[#163a5f]"
                    : "text-[#586570] hover:text-[#162333]"
                } ${link.href === "/mock-gem" ? "font-mono text-[11px] text-[#71808b]" : ""}`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center gap-3 text-sm text-[#586570]">
          <button
            type="button"
            className="focus-ring hidden rounded-sm p-2 hover:text-[#162333] sm:inline-flex"
            aria-label="Help"
          >
            <CircleHelp className="h-4 w-4" />
          </button>
          <div className="flex items-center gap-2 rounded px-2 py-1 bg-[#f4f5f2] border border-[#d9ddd9]">
            <span className="grid h-6 w-6 place-items-center rounded-full bg-[#163a5f] text-[10px] font-semibold text-white">
              PO
            </span>
            <span className="hidden sm:inline text-xs font-medium text-[#2f4050]">
              Review Officer
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}

