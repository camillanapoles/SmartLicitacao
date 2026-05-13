// Landing Page Institucional - STORY-168 + STORY-173 + STORY-273 + SAB-006 + DEBT-122
// Route: / (root)
// SAB-006: Condensed to 7 sections — Hero → Problema → Solução → Como Funciona → Stats → Testimonials → CTA
import LandingNavbar from './components/landing/LandingNavbar';
import HeroSection from './components/landing/HeroSection';
import OpportunityCost from './components/landing/OpportunityCost';
import ThreeTiersSection from './components/landing/ThreeTiersSection';
import BeforeAfter from './components/landing/BeforeAfter';
import HowItWorks from './components/landing/HowItWorks';
import StatsSection from './components/landing/StatsSection';
import FounderTransparencySection from './components/landing/FounderTransparencySection';
import CredibilitySection from './components/landing/CredibilitySection';
import FinalCTA from './components/landing/FinalCTA';
import OpportunityPreview from './components/landing/OpportunityPreview';
import { TrendingEditais } from './components/landing/TrendingEditais';
import Footer from './components/Footer';
import { HomeFaqStructuredData } from './components/HomeFaqStructuredData';
import { ExitIntentPopup } from './components/ExitIntentPopup';

export default function LandingPage() {
  return (
    <>
      <HomeFaqStructuredData />
      <LandingNavbar />

      <main id="main-content">
        <HeroSection />
        <OpportunityCost />
        <ThreeTiersSection />
        <BeforeAfter />
        <HowItWorks />
        <StatsSection />
        <FounderTransparencySection />
        <CredibilitySection />
        <OpportunityPreview />
        <TrendingEditais />

        <section id="suporte">
          <FinalCTA />
        </section>
      </main>

      <Footer />
      <ExitIntentPopup />
    </>
  );
}
