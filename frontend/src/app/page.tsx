import HomeShell from "@/components/HomeShell";
import HomeHero from "@/components/HomeHero";
import LivingVisual from "@/components/LivingVisual";
import OfficerContextPanel from "@/components/OfficerContextPanel";

export default function Home() {
  return (
    <HomeShell
      heroSlot={<HomeHero />}
      livingVisualSlot={<LivingVisual />}
      contextSlot={<OfficerContextPanel />}
    />
  );
}
