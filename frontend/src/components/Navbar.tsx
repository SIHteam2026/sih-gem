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
    <header className="w-full bg-transparent sticky top-0 z-30">
      <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between px-6 sm:px-10 lg:px-14">
        <Link href="/" className="focus-ring flex items-center gap-2.5 rounded-sm">
          <span className="grid h-7 w-7 place-items-center bg-[#163a5f] text-[11px] font-bold tracking-tight text-white rounded">
            OP
          </span>
          <span className="text-xs font-semibold tracking-[-0.01em] text-[#162333]">
            OPAL <span className="font-normal text-[#6c7b88]">| Procurement Review</span>
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
                className={`focus-ring rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                  current
                    ? "bg-[#edf2f5] font-semibold text-[#163a5f]"
                    : "text-[#586570] hover:text-[#162333]"
                } ${link.href === "/mock-gem" ? "font-mono text-[11px] text-[#8c9ba5] hover:text-[#586570]" : ""}`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center gap-3 text-xs text-[#586570]">
          <button
            type="button"
            className="focus-ring hidden rounded-sm p-1.5 hover:text-[#162333] sm:inline-flex"
            aria-label="Help"
          >
            <CircleHelp className="h-4 w-4 text-[#71808b]" />
          </button>
          <div className="flex items-center gap-2 rounded px-2 py-1 bg-[#f4f6f8]/80 border border-[#e2e6e8]">
            <span className="grid h-5 w-5 place-items-center rounded-full bg-[#163a5f] text-[9px] font-semibold text-white">
              PO
            </span>
            <span className="hidden sm:inline font-medium text-[#2f4050]">
              Review Officer
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}

