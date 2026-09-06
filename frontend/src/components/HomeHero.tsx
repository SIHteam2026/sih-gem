import Link from "next/link";
import { ArrowRight, History, Terminal } from "lucide-react";

interface HomeHeroProps {
  className?: string;
  showSecondaryActions?: boolean;
}

export default function HomeHero({
  className = "",
  showSecondaryActions = true,
}: HomeHeroProps) {
  return (
    <section className={`max-w-3xl ${className}`}>
      <p className="eyebrow">Procurement Review</p>

      <h1 className="mt-4 text-4xl font-medium tracking-tight text-[#162333] sm:text-5xl lg:text-[3.5rem] lg:leading-[1.12] text-balance">
        Review the procurement.<br className="hidden sm:inline" /> We’ll bring the evidence.
      </h1>

      <p className="mt-6 max-w-xl text-base leading-relaxed text-[#586574] sm:text-lg text-pretty">
        Opal brings together tender requirements, bidder claims, supporting
        evidence, and verification findings—surfacing ambiguities and discrepancies
        so officers can focus on decisions that require human judgment.
      </p>

      <div className="mt-8 flex flex-wrap items-center gap-3">
        <Link
          href="/procurements"
          className="focus-ring group inline-flex items-center gap-2 rounded bg-[#163a5f] px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-[#1f4e7e]"
        >
          Open Procurement Workspace
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
        </Link>

        {showSecondaryActions && (
          <>
            <Link
              href="/history"
              className="focus-ring inline-flex items-center gap-2 rounded border border-[#cfd5d5] bg-[#fffefa] px-4 py-3 text-sm font-medium text-[#263746] transition-colors hover:bg-white hover:border-[#b8c2c2]"
            >
              <History className="h-4 w-4 text-[#697987]" />
              Review history
            </Link>
            <Link
              href="/mock-gem"
              className="focus-ring inline-flex items-center gap-1.5 rounded border border-dashed border-[#cbd2d5] bg-[#fbfbf9] px-3.5 py-3 font-mono text-xs text-[#586774] transition-colors hover:bg-white hover:text-[#162333]"
            >
              <Terminal className="h-3.5 w-3.5 text-[#7e8e9c]" />
              Mock-GeM Simulator
            </Link>
          </>
        )}
      </div>
    </section>
  );
}
