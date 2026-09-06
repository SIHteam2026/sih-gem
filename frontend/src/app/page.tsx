import { FileText, ShieldCheck, CircleAlert } from "lucide-react";
import Navbar from "@/components/Navbar";
import HomeHero from "@/components/HomeHero";

export default function Home() {
  return (
    <div className="min-h-screen bg-[#f7f6f2]">
      <Navbar />
      <main className="mx-auto max-w-6xl px-5 py-12 sm:px-8 sm:py-20">
        <HomeHero />
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

