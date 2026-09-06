import HomeShell from "@/components/HomeShell";
import HomeHero from "@/components/HomeHero";
import LivingVisual from "@/components/LivingVisual";
import OfficerContextPanel from "@/components/OfficerContextPanel";
import RecentProcurementsSection from "@/components/procurement/RecentProcurementsSection";

export default function Home() {
  return (
    <HomeShell
      heroSlot={<HomeHero />}
      livingVisualSlot={<LivingVisual />}
      contextSlot={<OfficerContextPanel />}
      recentProcurementSlot={<RecentProcurementsSection />}
    />
  );
}
