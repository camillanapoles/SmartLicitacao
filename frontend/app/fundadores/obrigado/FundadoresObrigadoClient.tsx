'use client';

import { useEffect } from 'react';

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

export default function FundadoresObrigadoClient() {
  useEffect(() => {
    trackEvent('fundadores_checkout_completed', { source: 'obrigado_page' });
  }, []);

  const calendlyUrl =
    process.env.NEXT_PUBLIC_FOUNDING_CALENDLY_URL ||
    'https://cal.com/tiago-sasaki/founding-onboarding';

  return (
    <main className="min-h-screen bg-white">
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <p className="text-sm uppercase tracking-widest text-blue-600 font-semibold mb-3">
          Plano Fundadores
        </p>
        <h1 className="text-3xl sm:text-4xl font-bold text-slate-900">
          Bem-vindo ao SmartLic, Fundador.
        </h1>
        <p className="mt-6 text-lg text-slate-700">
          Seu acesso vitalício foi ativado. Em alguns minutos você receberá um email com:
        </p>
        <ul className="mt-4 text-left inline-block text-slate-700 space-y-1">
          <li>&#x2022; Credenciais de acesso ao dashboard</li>
          <li>&#x2022; Confirmação do seu Plano Fundadores</li>
          <li>&#x2022; Próximos passos para começar</li>
        </ul>

        <section className="mt-10 rounded-lg border border-blue-200 bg-blue-50 p-6 text-left">
          <h2 className="text-xl font-semibold text-slate-900">Próximo passo: agendar seu onboarding</h2>
          <p className="mt-2 text-slate-700">
            Agende uma sessão com o time SmartLic para mapear editais relevantes no seu setor e
            personalizar suas configurações iniciais.
          </p>
          <a
            href={calendlyUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 inline-block rounded bg-blue-600 px-5 py-2 font-medium text-white hover:bg-blue-700"
          >
            Agendar onboarding
          </a>
        </section>

        <p className="mt-10 text-sm text-slate-500">
          Dúvidas imediatas? Escreva para{' '}
          <a className="text-blue-600 underline" href="mailto:tiago@smartlic.tech">
            tiago@smartlic.tech
          </a>
          .
        </p>
      </div>
    </main>
  );
}
