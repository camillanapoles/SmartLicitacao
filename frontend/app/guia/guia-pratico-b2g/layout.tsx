import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Guia Prático B2G | SmartLic',
  description: 'Baixe o guia gratuito de oportunidades B2G.',
  robots: { index: false, follow: false },
};

export default function GuiaPraticoB2GLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
