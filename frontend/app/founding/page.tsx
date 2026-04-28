import type { Metadata } from 'next';
import FoundingClient from './FoundingClient';

export const metadata: Metadata = {
  title: 'SmartLic Founding Partners — Os primeiros 50 clientes moldam o produto',
  description:
    '50% off vitalício, linha direta com o fundador e voz no roadmap para os primeiros 50 clientes pagantes do SmartLic. Vagas limitadas até 30/05/2026.',
  robots: { index: false, follow: false },
};

export default function FoundingPage() {
  return <FoundingClient />;
}
