'use client';
import Link from 'next/link';
import { trackCTAClick } from '@/lib/analytics-events';

const tiers = [
  {
    id: 'saas',
    name: 'SmartLic SaaS',
    price: 'R$297–397/mês',
    description:
      'Você opera. A plataforma filtra editais, mapeia concorrentes e entrega análise por edital. Para times comerciais que já sabem o que fazem.',
    cta: 'Testar plataforma',
    href: '/signup?source=tier-saas',
    highlight: false,
    ctaType: 'self-service' as const,
  },
  {
    id: 'radar',
    name: 'Radar B2G',
    price: 'a partir R$1.500/mês',
    description:
      'Briefing diário com os editais que importam para sua empresa, concorrência mapeada e recomendação de disputa. Você acorda sabendo onde atuar.',
    cta: 'Receber radar da minha empresa',
    href: '/consultoria-b2g?modalidade=radar#diagnostico',
    highlight: true,
    ctaType: 'consultive' as const,
  },
  {
    id: 'consultoria',
    name: 'Consultoria B2G',
    price: 'sob consulta',
    description:
      'Núcleo externo de inteligência operando para sua empresa. Estratégia setorial, dossiê de concorrência, defesa em impugnação. Quando o jogo é grande demais para errar.',
    cta: 'Falar com especialista B2G',
    href: '/consultoria-b2g#diagnostico',
    highlight: false,
    ctaType: 'consultive' as const,
  },
];

export default function ThreeTiersSection() {
  return (
    <section className="max-w-landing mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-16">
      <div className="text-center mb-10">
        <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white">
          Três formas de operar com inteligência B2G
        </h2>
        <p className="mt-3 text-slate-600 dark:text-slate-400 max-w-xl mx-auto">
          Do autoatendimento à consultoria completa — cada empresa tem seu ritmo.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {tiers.map((tier) => (
          <div
            key={tier.id}
            data-cta-tier={tier.id}
            className={`flex flex-col rounded-2xl border p-6 ${
              tier.highlight
                ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30 dark:border-blue-400 shadow-lg'
                : 'border-slate-200 bg-white dark:bg-slate-900 dark:border-slate-700'
            }`}
          >
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{tier.name}</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">{tier.price}</p>
            </div>
            <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed flex-1">
              {tier.description}
            </p>
            <Link
              href={tier.href}
              onClick={() =>
                trackCTAClick({
                  label: tier.cta,
                  source: `tier-${tier.id}`,
                  destination: tier.href,
                  cta_type: tier.ctaType,
                })
              }
              className={`mt-6 inline-block rounded-lg px-5 py-2.5 text-sm font-semibold text-center transition-colors ${
                tier.highlight
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-slate-900 text-white hover:bg-slate-800 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100'
              }`}
            >
              {tier.cta}
            </Link>
          </div>
        ))}
      </div>
    </section>
  );
}
