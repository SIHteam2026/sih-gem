"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CircleHelp, ChevronDown } from "lucide-react";

const links = [{ href: "/tender", label: "Reviews" }, { href: "/", label: "Tenders" }, { href: "/history", label: "History" }];

export default function Navbar() {
  const pathname = usePathname();
  return <header className="border-b border-[#d9ddd9] bg-[#fffefa]/95 backdrop-blur-sm"><div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8"><Link href="/" className="focus-ring flex items-center gap-3 rounded-sm"><span className="grid h-8 w-8 place-items-center border border-[#163a5f] bg-[#163a5f] text-xs font-semibold tracking-tight text-white">IS</span><span className="text-sm font-semibold tracking-[-0.01em] text-[#162333]">IShowSolution</span></Link><nav className="hidden items-center gap-1 sm:flex" aria-label="Main navigation">{links.map((link) => { const current = pathname === link.href || (link.href === "/tender" && pathname.startsWith("/tender")); return <Link key={link.href} href={link.href} className={`focus-ring rounded-sm px-3 py-2 text-sm transition-colors ${current ? "bg-[#edf2f3] font-medium text-[#163a5f]" : "text-[#586570] hover:text-[#162333]"}`}>{link.label}</Link>; })}</nav><div className="flex items-center gap-3 text-sm text-[#586570]"><button className="focus-ring hidden rounded-sm p-2 hover:text-[#162333] sm:inline-flex" aria-label="Help"><CircleHelp className="h-4 w-4" /></button><button className="focus-ring inline-flex items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-[#f1f2ef]"><span className="grid h-6 w-6 place-items-center rounded-full bg-[#e5e6e1] text-[10px] font-semibold text-[#344554]">PO</span><span className="hidden sm:inline">Officer</span><ChevronDown className="h-3.5 w-3.5" /></button></div></div></header>;
}
