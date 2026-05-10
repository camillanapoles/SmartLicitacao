'use client';

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { trackFoundersCheckoutAbandoned } from '@/lib/analytics/founders';
import FundadoresForm from './components/FundadoresForm';
import FundadoresFAQ from './components/FundadoresFAQ';
import FundadoresFeatures from './components/FundadoresFeatures';
import FundadoresCountdown, { FoundingAvailabilitySnapshot } from './components/FundadoresCountdown';
import FundadoresFounderLetter from './components/FundadoresFounderLetter';
import FundadoresComparisonTable from './components/FundadoresComparisonTable';
import FundadoresDoNotBuy from './components/FundadoresDoNotBuy';
import FundadoresGuarantee from './components/FundadoresGuarantee';
import FundadoresLegalFooter from './components/FundadoresLegalFooter';

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

const UNAVAILABLE_SNAPSHOT: FoundingAvailabilitySnapshot = {
  available: false,
  seats_total: 50,
  seats_remaining: 0,
  seats_taken: 50,
  deadline_at: null,
  paused: false,
  reason: 'unavailable',
  coupon_code: 'FOUNDING_LIFETIME',
  discount_pct: 0,
};

// TODO: remove hardcoded fallback after #782 merges (price_brl_cents in API response)
function formatPrice(priceBrlCents: number | undefined): string {
  if (priceBrlCents !== undefined && priceBrlCents > 0) {
    return (priceBrlCents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  }
  return 'R$997';
}

export default function FundadoresClient() {
  const [snapshot, setSnapshot] = useState<FoundingAvailabilitySnapshot | null>(null);
  const searchParams = useSearchParams();
  const abandonedTrackedRef = useRef(false);

  useEffect(() => {
    trackEvent('fundadores_page_viewed', { source: 'landing' });
  }, []);

  // Track checkout abandoned when user returns from Stripe with ?cancelled=true
  useEffect(() => {
    if (!abandonedTrackedRef.current && searchParams?.get('cancelled') === 'true') {
      abandonedTrackedRef.current = true;
      trackFoundersCheckoutAbandoned({ src: searchParams?.get('src') });
    }
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    async function load() {
      try {
        const res = await fetch('/api/founding/availability', { cache: 'no-store' });
        if (!res.ok) {
          if (!cancelled) setSnapshot(UNAVAILABLE_SNAPSHOT);
          return;
        }
        const data = (await res.json()) as FoundingAvailabilitySnapshot;
        if (!cancelled) setSnapshot(data);
      } catch {
        if (!cancelled) setSnapshot(UNAVAILABLE_SNAPSHOT);
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
  const seatsRemaining = snapshot?.seats_remaining ?? null;
  const seatsRemainingText = seatsRemaining !== null ? `${seatsRemaining}` : '50';

  return (
    <main className="min-h-screen bg-white">
      {/* Hero — founder pact framing */}
      <section className="bg-slate-900 text-white">
        <div className="mx-auto max-w-3xl px-4 py-16">
          <p className="text-sm uppercase tracking-widest text-blue-400 font-semibold mb-3">
            Plano Fundadores · 50 vagas · Encerra 30/06/2026
          </p>
          <h1 className="text-3xl sm:text-5xl font-bold leading-tight mb-4">
            Pague {price} uma vez. Use o SmartLic pra sempre.
          </h1>
          <p className="text-lg sm:text-xl text-slate-300 mb-8">
            50 empresas. {price} pagamento único. Acesso vitalício a tudo que existe e tudo
            que vier. Sem mensalidade. Encerra 30 de junho de 2026 — ou quando as 50 vagas
            acabarem (faltam {seatsRemainingText}).
          </p>

          <div className="mb-8">
            <FundadoresCountdown snapshot={snapshot} />
          </div>

          <div className="rounded-xl border border-blue-500/30 bg-blue-950/40 p-6">
            <p className="text-2xl font-bold text-white mb-1">
              {price} <span className="text-base font-normal text-slate-400">pagamento único</span>
            </p>
            <p className="text-slate-300 text-sm mb-4">
              Pagamento único no Pix ou cartão. 60 dias de garantia incondicional.
            </p>
            <FundadoresForm availability={snapshot} price={price} />
            <p className="mt-3 text-xs text-slate-400">
              Prefere testar antes?{' '}
              <a href="/planos" className="text-blue-300 underline hover:text-blue-200">
                Comece com 14 dias grátis →
              </a>
            </p>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-3xl px-4 py-12">
        <FundadoresFounderLetter />
        <FundadoresComparisonTable />

        {/* O que está incluído (9 bullets) */}
        <FundadoresFeatures />

        {/* As 4 perguntas que todo mundo me faz */}
        <FundadoresFAQ />

        <FundadoresDoNotBuy />
        <FundadoresGuarantee />

        {/* Vagas em tempo real */}
        <section
          aria-labelledby="vagas-heading"
          className="mt-16 rounded-lg border border-slate-200 bg-slate-50 p-6"
        >
          <h2 id="vagas-heading" className="text-xl font-semibold text-slate-900 mb-3">
            Vagas em tempo real
          </h2>
          <p className="text-slate-700">
            <strong className="text-blue-700 text-2xl">{seatsRemainingText}</strong>{' '}
            <span className="text-slate-600">de 50 vagas restantes.</span>
          </p>
          <p className="text-sm text-slate-500 mt-2">
            Contador atualiza a cada minuto direto do banco — não é counter de marketing.
            Quando zerar, encerra antes de 30/06/2026.
          </p>
        </section>

        {/* CTA final */}
        <section
          aria-labelledby="cta-final-heading"
          className="mt-16 rounded-xl border border-blue-200 bg-blue-50 p-8"
        >
          <h2 id="cta-final-heading" className="text-2xl font-semibold text-slate-900 mb-2">
            Quero uma das {seatsRemainingText} vagas — {price}
          </h2>
          <p className="text-slate-700 mb-6">
            Pagamento único no Pix ou cartão. 60 dias de garantia incondicional. Acesso
            ativado na hora.
          </p>
          <FundadoresForm availability={snapshot} price={price} />
          <p className="mt-4 text-sm text-slate-600">
            Prefere testar antes?{' '}
            <a href="/planos" className="text-blue-700 underline hover:text-blue-800 font-medium">
              Comece com 14 dias grátis →
            </a>
          </p>
        </section>

        <FundadoresLegalFooter />
      </div>
    </main>
  );
}
