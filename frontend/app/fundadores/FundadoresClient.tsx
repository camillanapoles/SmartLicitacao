'use client';

import { useEffect, useState } from 'react';
import FundadoresForm from './components/FundadoresForm';
import FundadoresFAQ from './components/FundadoresFAQ';
import FundadoresFeatures from './components/FundadoresFeatures';
import FundadoresCountdown, { FoundingAvailabilitySnapshot } from './components/FundadoresCountdown';

function trackEvent(name: string, props?: Record<string, unknown>) {
  if (typeof window === 'undefined') return;
  const mp = (window as unknown as { mixpanel?: { track: (e: string, p?: Record<string, unknown>) => void } }).mixpanel;
  if (!mp) return;
  try {
    mp.track(name, props ?? {});
  } catch {
    // no-op
  }
}

const REFRESH_INTERVAL_MS = 60_000;

// TODO: remove hardcoded fallback after #782 merges (price_brl_cents in API response)
function formatPrice(priceBrlCents: number | undefined): string {
  if (priceBrlCents !== undefined && priceBrlCents > 0) {
    return (priceBrlCents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  }
  return 'R$997';
}

export default function FundadoresClient() {
  const [snapshot, setSnapshot] = useState<FoundingAvailabilitySnapshot | null>(null);

  useEffect(() => {
    trackEvent('fundadores_page_viewed', { source: 'landing' });
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    async function load() {
      try {
        const res = await fetch('/api/founding/availability', { cache: 'no-store' });
        if (!res.ok) {
          if (!cancelled) {
            setSnapshot({
              available: false,
              seats_total: 50,
              seats_remaining: 0,
              seats_taken: 50,
              deadline_at: null,
              paused: false,
              reason: 'unavailable',
              coupon_code: 'FOUNDING_LIFETIME',
              discount_pct: 0,
            });
          }
          return;
        }
        const data = (await res.json()) as FoundingAvailabilitySnapshot;
        if (!cancelled) setSnapshot(data);
      } catch {
        if (!cancelled) {
          setSnapshot({
            available: false,
            seats_total: 50,
            seats_remaining: 0,
            seats_taken: 50,
            deadline_at: null,
            paused: false,
            reason: 'unavailable',
            coupon_code: 'FOUNDING_LIFETIME',
            discount_pct: 0,
          });
        }
      }
    }

    load();
    timer = setInterval(load, REFRESH_INTERVAL_MS);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, []);

  const price = formatPrice(snapshot?.price_brl_cents);

  return (
    <main className="min-h-screen bg-white">
      {/* Hero */}
      <section className="bg-slate-900 text-white">
        <div className="mx-auto max-w-3xl px-4 py-16">
          <p className="text-sm uppercase tracking-widest text-blue-400 font-semibold mb-3">
            Plano Fundadores — vagas limitadas
          </p>
          <h1 className="text-3xl sm:text-5xl font-bold leading-tight mb-4">
            Entre cedo na infraestrutura de inteligência B2G do SmartLic.
          </h1>
          <p className="text-lg sm:text-xl text-slate-300 mb-8">
            Acesso vitalício antes da estrutura comercial definitiva.
          </p>

          <div className="mb-8">
            <FundadoresCountdown snapshot={snapshot} />
          </div>

          <div className="rounded-xl border border-blue-500/30 bg-blue-950/40 p-6">
            <p className="text-2xl font-bold text-white mb-1">{price} <span className="text-base font-normal text-slate-400">pagamento único</span></p>
            <p className="text-slate-300 text-sm mb-4">Sem mensalidade. Sem renovação. Acesso permanente.</p>
            <FundadoresForm availability={snapshot} price={price} />
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-3xl px-4 py-12">
        {/* Problema */}
        <section aria-labelledby="problema-heading" className="mb-16">
          <h2 id="problema-heading" className="text-2xl font-semibold text-slate-900 mb-4">
            Por que B2G é difícil
          </h2>
          <div className="prose prose-slate max-w-none">
            <p>
              Licitações públicas são publicadas em dezenas de portais diferentes, em formatos
              inconsistentes, com terminologias confusas e prazos que mudam sem aviso. Empresas B2G
              gastam horas toda semana só para descobrir o que está aberto — antes mesmo de
              qualificar se vale a pena participar.
            </p>
            <p className="mt-4">
              <strong>Menos PDF. Mais decisão.</strong> O SmartLic agrega, filtra e classifica
              automaticamente para que sua equipe foque no que importa: construir propostas
              competitivas.
            </p>
            <p className="mt-4">
              <strong>A IA encontra. A inteligência decide.</strong> Classificação setorial por
              GPT-4.1-nano com precisão ≥85%, análise de viabilidade em quatro fatores e histórico
              de 2 milhões de contratos públicos para benchmark de preço.
            </p>
          </div>
        </section>

        {/* Features */}
        <FundadoresFeatures />

        {/* Comparação */}
        <section aria-labelledby="comparacao-heading" className="mt-16">
          <h2 id="comparacao-heading" className="text-2xl font-semibold text-slate-900 mb-6">
            Fundador vs Assinatura recorrente
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-100">
                  <th className="text-left px-4 py-3 font-semibold text-slate-700 border border-slate-200"></th>
                  <th className="text-center px-4 py-3 font-semibold text-blue-700 border border-slate-200">
                    Plano Fundadores
                  </th>
                  <th className="text-center px-4 py-3 font-semibold text-slate-700 border border-slate-200">
                    Pro Recorrente
                  </th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['Modelo de cobrança', 'R$997 único', 'R$397/mês'],
                  ['Custo em 12 meses', 'R$997', 'R$4.764'],
                  ['Acesso', 'Vitalício', 'Enquanto pagar'],
                  ['Todas as funcionalidades', '✓', '✓'],
                  ['Atualizações futuras', '✓ incluídas', '✓ incluídas'],
                  ['Vagas disponíveis', 'Limitadas', 'Ilimitadas'],
                  ['Ajude a financiar a próxima fase', '✓', '—'],
                ].map(([label, founder, regular]) => (
                  <tr key={label} className="border border-slate-200 hover:bg-slate-50">
                    <td className="px-4 py-3 text-slate-700 border border-slate-200">{label}</td>
                    <td className="px-4 py-3 text-center font-medium text-blue-700 border border-slate-200">{founder}</td>
                    <td className="px-4 py-3 text-center text-slate-600 border border-slate-200">{regular}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Sobre o SmartLic */}
        <section aria-labelledby="sobre-heading" className="mt-16 rounded-lg border border-slate-200 bg-slate-50 p-6">
          <h2 id="sobre-heading" className="text-xl font-semibold text-slate-900 mb-3">
            Sobre o SmartLic (v0.5 — beta produtivo)
          </h2>
          <p className="text-slate-700 leading-relaxed">
            2 milhões de contratos públicos indexados. 50 mil licitações abertas em tempo real.
            20 setores com classificação por IA. Infra production-ready (Railway, Supabase).
            Ferramenta é real — estamos abrindo acesso vitalício para os primeiros fundadores que
            ajudam a financiar e moldar a próxima fase do produto.
          </p>
          <p className="mt-3 text-slate-700">
            <strong>Ajude a financiar a próxima fase do SmartLic.</strong> Cada fundador é um
            parceiro estratégico, não apenas um cliente.
          </p>
        </section>

        {/* FAQ */}
        <FundadoresFAQ />

        {/* CTA final */}
        <section
          aria-labelledby="cta-final-heading"
          className="mt-16 rounded-xl border border-blue-200 bg-blue-50 p-8"
        >
          <h2 id="cta-final-heading" className="text-2xl font-semibold text-slate-900 mb-2">
            Reserve sua vaga agora
          </h2>
          <p className="text-slate-700 mb-6">
            Acesso vitalício por {price}. Pagamento único via Stripe — cartão de crédito ou boleto.
          </p>
          <FundadoresForm availability={snapshot} price={price} />
        </section>

        {/* Disclaimer legal */}
        <footer className="mt-12 border-t border-slate-200 pt-6 text-sm text-slate-500">
          <p>
            Ao prosseguir, você concorda com os{' '}
            <a href="/termos/fundadores" className="text-blue-600 underline">
              Termos do Plano Fundadores
            </a>{' '}
            e a{' '}
            <a href="/privacidade" className="text-blue-600 underline">
              Política de Privacidade
            </a>
            . Em caso de dúvida, escreva para{' '}
            <a href="mailto:tiago@smartlic.tech" className="text-blue-600 underline">
              tiago@smartlic.tech
            </a>
            .
          </p>
        </footer>
      </div>
    </main>
  );
}
