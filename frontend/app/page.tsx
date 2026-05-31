// Landing Page Institucional — REPO-COMMS #1289
// Route: / (root)
// Reposicionamento B2G: "terminal de inteligência" — dark theme, sem IA/monitoramento/alerta
import B2GIntelTheme from './components/landing/B2GIntelTheme';
import LandingNavbar from './components/landing/LandingNavbar';
import HeroB2GIntel from './components/landing/HeroB2GIntel';
import AntecipeDecidaExecute from './components/landing/AntecipeDecidaExecute';
import TerminalComparison from './components/landing/TerminalComparison';
import SocialProofMetrics from './components/landing/SocialProofMetrics';
import PersonasSection from './components/landing/PersonasSection';
import PricingSectionB2G from './components/landing/PricingSectionB2G';
import MarketSocialProof from './components/landing/MarketSocialProof';
import Footer from './components/Footer';
import NewsletterFooter from './components/landing/NewsletterFooter';
import { HomeFaqStructuredData } from './components/HomeFaqStructuredData';
import { ExitIntentPopup } from './components/ExitIntentPopup';

export default function LandingPage() {
  return (
    <B2GIntelTheme>
      <HomeFaqStructuredData />
      <LandingNavbar />

      <main id="main-content">
        <HeroB2GIntel />
        <AntecipeDecidaExecute />
        <TerminalComparison />
        <SocialProofMetrics />
        <PersonasSection />
        <PricingSectionB2G />
        <MarketSocialProof />
      </main>

      <NewsletterFooter />
      <Footer />
      <ExitIntentPopup />
    </B2GIntelTheme>
  );
}
