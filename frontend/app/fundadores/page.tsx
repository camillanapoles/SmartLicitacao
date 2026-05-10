import type { Metadata } from 'next';
import { Suspense } from 'react';
import FundadoresClient from './FundadoresClient';

export const metadata: Metadata = {
  title: 'SmartLic Plano Fundadores — Pague R$997 uma vez. Use pra sempre.',
  description:
    '50 vagas. R$997 pagamento único. Acesso vitalício à plataforma SmartLic — sem mensalidade. 60 dias de garantia incondicional. Encerra 30/06/2026.',
  robots: { index: true, follow: true },
  alternates: { canonical: 'https://smartlic.tech/fundadores' },
  openGraph: {
    title: 'SmartLic Plano Fundadores — Pague R$997 uma vez. Use pra sempre.',
    description:
      '50 vagas. R$997 pagamento único. Acesso vitalício, sem mensalidade. 60 dias de garantia. Encerra 30/06/2026.',
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
      name: 'E se o SmartLic acabar? Eu perco meus R$997?',
      acceptedAnswer: {
        '@type': 'Answer',
        text: 'Não. Três compromissos formais: (1) 60 dias de garantia incondicional — não gostou em qualquer momento dos primeiros dois meses, devolvemos 100%, sem perguntas. (2) Se um dia o SmartLic precisar fechar, avisamos com 90 dias de antecedência por email. (3) Você consegue exportar todos os seus dados a qualquer momento (buscas, pipeline, contratos analisados) — e a busca multi-fonte é open-source, fica no GitHub para sempre.',
      },
    },
    {
      '@type': 'Question',
      name: 'Vocês não vão começar a cobrar mensalidade depois?',
      acceptedAnswer: {
        '@type': 'Answer',
        text: 'Não para você. Quem entra como fundador paga R$997 uma vez e nunca mais — está escrito no contrato. Os 50 fundadores ficam vitalícios independentemente do que aconteça com o pricing depois de 30/06/2026. Quem entrar pelo plano regular a partir de julho/2026, sim, paga mensal.',
      },
    },
    {
      '@type': 'Question',
      name: 'Vale R$997 mesmo se eu nunca ganhar uma licitação?',
      acceptedAnswer: {
        '@type': 'Answer',
        text: 'Se você nunca participar de licitação, não vale. Se você participa, mesmo de vez em quando, o break-even é uma proposta a mais por ano. Uma única licitação ganha porque você viu o edital antes paga R$997 muitas vezes. E sem mensalidade não tem risco de esquecer de cancelar.',
      },
    },
    {
      '@type': 'Question',
      name: 'Por que essa oferta existe? Onde está a pegadinha?',
      acceptedAnswer: {
        '@type': 'Answer',
        text: 'Sem pegadinha. 50 fundadores × R$997 = R$49.850 — aproximadamente 6 meses de runway para terminar o roadmap (alertas WhatsApp, relatório PDF de viabilidade, integração com proposta comercial). Em troca, os 50 ganham acesso vitalício e influência direta no produto. Pre-revenue, runway é tudo.',
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
      <Suspense>
        <FundadoresClient />
      </Suspense>
    </>
  );
}
