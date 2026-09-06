import HomeShell from "@/components/HomeShell";
import HomeHero from "@/components/HomeHero";
import OfficerContextPanel from "@/components/OfficerContextPanel";

export default function Home() {
  return (
    <HomeShell
      heroSlot={<HomeHero />}
      contextSlot={<OfficerContextPanel />}
    />
  );
}

