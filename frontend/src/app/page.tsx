import Link from "next/link";
import { ArrowUpRight, FileText, ShieldCheck, CircleAlert, Terminal } from "lucide-react";
import Navbar from "@/components/Navbar";

export default function Home() {
  return (
    <div className="min-h-screen bg-[#f7f6f2]">
      <Navbar />
      <main className="mx-auto max-w-6xl px-5 py-12 sm:px-8 sm:py-20">
        <section className="max-w-3xl">
          <p className="eyebrow">Procurement Review Layer</p>
          <h1 className="mt-4 text-4xl font-medium tracking-[-.045em] text-[#162333] sm:text-6xl">
            Review the procurement.<br />We’ll bring the evidence.
          </h1>
          <p className="mt-6 max-w-xl text-base leading-7 text-[#5d6872] sm:text-lg">
            Procurement cases appear automatically upon ingestion. OPAL organizes requirements, reconciles submitted evidence, and surfaces what requires an officer’s human judgment.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link
              href="/procurements"
              className="focus-ring inline-flex items-center gap-3 bg-[#163a5f] px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-[#204b76] rounded"
            >
              Open Procurement Workspace <ArrowUpRight className="h-4 w-4" />
            </Link>
            <Link
              href="/history"
              className="focus-ring inline-flex items-center gap-3 border border-[#cfd5d5] bg-[#fffefa] px-5 py-3 text-sm font-medium text-[#263746] transition-colors hover:bg-white rounded"
            >
              View review history
            </Link>
            <Link
              href="/mock-gem"
              className="focus-ring inline-flex items-center gap-2 border border-dashed border-[#cbd2d5] bg-[#fbfbf9] px-4 py-3 text-xs font-mono text-[#586774] transition-colors hover:bg-white rounded"
            >
              <Terminal className="h-3.5 w-3.5" /> Mock-GeM Simulator (Dev)
            </Link>
          </div>
        </section>
        <section className="mt-20 border-y border-[#d9ddd9] py-7 sm:grid sm:grid-cols-3 sm:gap-8">
          <Feature
            icon={<FileText className="mt-0.5 h-5 w-5 shrink-0 text-[#2e638d]" />}
            title="Procurements, not file uploads"
            text="Tenders and submissions are ingested seamlessly into canonical cases from authorized sources."
          />
          <Feature
            icon={<CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-[#a85e31]" />}
            title="Exceptions come first"
            text="Straightforward evidence stays quiet; ambiguities and discrepancies are surfaced clearly."
            extra
          />
          <Feature
            icon={<ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-[#2e638d]" />}
            title="The officer decides"
            text="Structured requirements preserve page and clause provenance for transparent audit replay."
            extra
          />
        </section>
      </main>
    </div>
  );
}

function Feature({
  icon,
  title,
  text,
  extra = false,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
  extra?: boolean;
}) {
  return (
    <div className={`flex gap-4 py-4 sm:py-0 ${extra ? "border-t border-[#e0e2de] sm:border-t-0" : ""}`}>
      {icon}
      <div>
        <p className="text-sm font-medium text-[#162333]">{title}</p>
        <p className="mt-1 text-sm leading-6 text-[#68737c]">{text}</p>
      </div>
    </div>
  );
}

