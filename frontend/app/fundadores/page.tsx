import type { Metadata } from 'next';
import FundadoresClient from './FundadoresClient';

export const metadata: Metadata = {
  title: 'SmartLic Plano Fundadores — Acesso vitalício à inteligência B2G',
  description:
    'Entre cedo na infraestrutura de inteligência B2G do SmartLic. Acesso vitalício por R$997 — pagamento único, sem mensalidade. Vagas limitadas.',
  robots: { index: true, follow: true },
  alternates: { canonical: 'https://smartlic.tech/fundadores' },
  openGraph: {
    title: 'SmartLic Plano Fundadores — Acesso vitalício à inteligência B2G',
    description:
      'Menos PDF. Mais decisão. A IA encontra. A inteligência decide. Acesso vitalício por R$997.',
    url: 'https://smartlic.tech/fundadores',
    siteName: 'SmartLic',
    locale: 'pt_BR',
    type: 'website',
  },
};

const jsonLdProduct = {
  '@context': 'https://schema.org',
  '@type': 'Product',
  name: 'SmartLic Plano Fundadores',
  description:
    'Acesso vitalício à plataforma de inteligência B2G SmartLic — busca multi-fonte, classificação por IA, pipeline kanban e relatórios.',
  brand: {
    '@type': 'Organization',
    name: 'CONFENGE Avaliações e Inteligência Artificial LTDA',
  },
  offers: {
    '@type': 'Offer',
    price: '997',
    priceCurrency: 'BRL',
    availability: 'https://schema.org/LimitedAvailability',
    url: 'https://smartlic.tech/fundadores',
    priceValidUntil: '2026-12-31',
  },
};

const jsonLdFaq = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: [
    {
      '@type': 'Question',
      name: 'O que está incluído no Plano Fundadores?',
      acceptedAnswer: {
        '@type': 'Answer',
        text: 'Acesso vitalício à plataforma SmartLic (busca multi-fonte, classificação IA, pipeline kanban, relatórios Excel, análise de viabilidade). Pagamento único de R$997 — sem mensalidade.',
      },
    },
    {
      '@type': 'Question',
      name: 'Qual a diferença entre Fundador e assinante regular?',
      acceptedAnswer: {
        '@type': 'Answer',
        text: 'O assinante regular paga R$397/mês recorrente. O Fundador paga R$997 uma única vez e tem acesso permanente, incluindo todas as atualizações futuras.',
      },
    },
    {
      '@type': 'Question',
      name: 'Posso cancelar ou pedir reembolso?',
      acceptedAnswer: {
        '@type': 'Answer',
        text: 'Sim. Oferecemos 7 dias de garantia. Se não ficar satisfeito por qualquer motivo dentro deste prazo, devolvemos 100% do valor pago.',
      },
    },
  ],
};

export default function FundadoresPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdProduct) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdFaq) }}
      />
      <FundadoresClient />
    </>
  );
}
