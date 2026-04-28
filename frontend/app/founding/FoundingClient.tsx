'use client';

import { useEffect, useState } from 'react';
import FoundingForm from './components/FoundingForm';
import FoundingFAQ from './components/FoundingFAQ';
import FoundingCountdown, { FoundingAvailabilitySnapshot } from './components/FoundingCountdown';

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

export default function FoundingClient() {
  const [snapshot, setSnapshot] = useState<FoundingAvailabilitySnapshot | null>(null);

  useEffect(() => {
    trackEvent('founding_page_viewed', { source: 'landing' });
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    async function load() {
      try {
        const res = await fetch('/api/founding/availability', { cache: 'no-store' });
        if (!res.ok) {
          // Endpoint should always 200; if it doesn't, fall closed (CTA disabled).
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
              discount_pct: 50,
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
            discount_pct: 50,
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

  return (
    <main className="min-h-screen bg-white">
      <div className="mx-auto max-w-3xl px-4 py-12">
        <header className="mb-10">
          <p className="text-sm uppercase tracking-wide text-blue-600 font-semibold">
            SmartLic Founding Partners
          </p>
          <h1 className="mt-2 text-3xl sm:text-4xl font-bold text-slate-900 leading-tight">
            Os 50 primeiros clientes do SmartLic moldam o produto. Você pode ser um deles.
          </h1>
          <p className="mt-4 text-lg text-slate-700">
            50% de desconto vitalício, voz direta no roadmap, prazo até 30/05/2026.
          </p>
        </header>

        <div className="mb-8">
          <FoundingCountdown snapshot={snapshot} />
        </div>

        <section aria-labelledby="deal-heading" className="mb-10 prose prose-slate max-w-none">
          <h2 id="deal-heading" className="text-2xl font-semibold text-slate-900">
            O que você ganha
          </h2>
          <ul>
            <li>
              <strong>50% off vitalício</strong> no plano SmartLic Pro (R$ 198,50/mês vs R$ 397
              cheio — desconto que nunca expira).
            </li>
            <li>
              <strong>Onboarding 1:1 comigo</strong> (Tiago Sasaki, fundador) em 30 min por Zoom.
            </li>
            <li>
              <strong>Prioridade em feature requests</strong> — o roadmap é construído junto, com
              ritual quinzenal de priorização.
            </li>
            <li>
              <strong>Trial 14 dias grátis</strong> antes da primeira cobrança. Cancele a qualquer
              momento sem multa.
            </li>
          </ul>

          <h2 className="text-2xl font-semibold text-slate-900 mt-8">Por que apenas 50?</h2>
          <p>
            Não é gimmick de escassez. É disciplina: founding partners recebem atenção individual, e
            acima de 50 eu não consigo entregar o 1:1 prometido. Os próximos clientes pagam preço
            regular (R$ 397/mês), que continua competitivo vs concorrentes.
          </p>

          <h2 className="text-2xl font-semibold text-slate-900 mt-8">
            Sobre o SmartLic (v0.5 — beta produtivo)
          </h2>
          <p>
            2 milhões de contratos públicos indexados. 50 mil licitações abertas. 20 setores com
            classificação por IA. Infra production-ready (Railway, Supabase, SOC-2 ready).
            Ferramenta é real — estamos escolhendo os primeiros 50 parceiros para moldar o que vem
            a seguir.
          </p>
        </section>

        <section aria-labelledby="form-heading" className="mb-8 rounded-lg border border-slate-200 bg-slate-50 p-6">
          <h2 id="form-heading" className="text-xl font-semibold text-slate-900 mb-1">
            Quero ser um founding partner
          </h2>
          <p className="text-sm text-slate-700 mb-4">
            Preencha o formulário. Validamos manualmente antes do checkout (leva até 24h úteis) —
            isso garante que as 50 vagas founding vão para empresas com fit real.
          </p>
          <FoundingForm availability={snapshot} />
        </section>

        <FoundingFAQ />

        <footer className="mt-12 border-t border-slate-200 pt-6 text-sm text-slate-500">
          <p>
            Cupom <code>FOUNDING_LIFETIME</code> — 50% off vitalício, máximo 50 partners. Em caso de
            dúvida, escreva para{' '}
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
