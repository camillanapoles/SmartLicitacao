'use client';

import { useState } from 'react';
import type { FoundingAvailabilitySnapshot } from './FundadoresCountdown';

type Status = 'idle' | 'loading' | 'success' | 'error';

interface FundadoresCheckoutResponse {
  checkout_url: string;
  lead_id: string;
}

interface Props {
  /**
   * Live availability snapshot. When `available=false` the CTA is disabled
   * and a contextual message replaces the form footer.
   * Optional so unit tests keep working without parent wiring.
   */
  availability?: FoundingAvailabilitySnapshot | null;
  /** Display price derived from API (price_brl_cents). Fallback: R$997. */
  price?: string;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const REASON_MESSAGES: Record<string, string> = {
  founding_cap_reached:
    'As vagas fundadores já foram preenchidas. Obrigado pelo interesse — escreva para tiago@smartlic.tech para entrar na lista de espera.',
  founding_deadline_passed:
    'O período de inscrição fundadores encerrou. O plano regular SmartLic Pro continua disponível em /pricing.',
  founding_paused:
    'Inscrições fundadores temporariamente pausadas. Tente novamente em algumas horas.',
  founding_disabled: 'O programa fundadores não está aceitando novas inscrições no momento.',
  founding_policy_missing:
    'Configuração fundadores indisponível. Tente novamente em instantes.',
  unavailable: 'Não foi possível validar disponibilidade agora. Tente novamente em instantes.',
};

function trackEvent(name: string, props?: Record<string, unknown>) {
  if (typeof window === 'undefined') return;
  const mp = (window as unknown as { mixpanel?: { track: (e: string, p?: Record<string, unknown>) => void } }).mixpanel;
  if (!mp) return;
  try {
    mp.track(name, props ?? {});
  } catch {
    // best-effort; never break UX on analytics failure.
  }
}

export default function FundadoresForm({ availability, price = 'R$997' }: Props = {}) {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<Status>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  function validate(): string | null {
    if (!email.trim() || !EMAIL_RE.test(email.trim())) return 'Informe um email válido.';
    return null;
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const v = validate();
    if (v) {
      setErrorMsg(v);
      setStatus('error');
      return;
    }

    setStatus('loading');
    setErrorMsg('');
    trackEvent('fundadores_form_submitted', { source: 'fundadores_landing' });

    try {
      const res = await fetch('/api/founding/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
        }),
      });

      if (!res.ok) {
        let msg = 'Não foi possível iniciar seu checkout. Tente novamente em instantes.';
        try {
          const data = await res.json();
          if (typeof data?.detail === 'string') {
            msg = data.detail;
          } else if (data?.detail && typeof data.detail === 'object') {
            if (typeof data.detail.message === 'string') msg = data.detail.message;
          }
        } catch {
          // ignore JSON parse errors — keep default message
        }
        setErrorMsg(msg);
        setStatus('error');
        return;
      }

      const data = (await res.json()) as FundadoresCheckoutResponse;
      trackEvent('fundadores_checkout_started', { lead_id: data.lead_id });
      window.location.href = data.checkout_url;
    } catch {
      setErrorMsg('Falha de rede. Verifique sua conexão e tente novamente.');
      setStatus('error');
    }
  }

  const loading = status === 'loading';
  const unavailable = availability !== undefined && availability !== null && !availability.available;
  const unavailableMessage = unavailable
    ? REASON_MESSAGES[availability!.reason] ?? REASON_MESSAGES.unavailable
    : null;
  const submitDisabled = loading || unavailable;

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <div>
        <label htmlFor="fundadores-email" className="block text-sm font-medium text-slate-900">
          Seu email
        </label>
        <input
          id="fundadores-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          maxLength={320}
          placeholder="voce@empresa.com"
          className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 focus:border-blue-500 focus:ring-2 focus:ring-blue-500"
          disabled={loading}
        />
      </div>

      {status === 'error' && errorMsg && (
        <div role="alert" className="rounded bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-800">
          {errorMsg}
        </div>
      )}

      {unavailable && unavailableMessage && (
        <div
          role="status"
          data-testid="fundadores-form-unavailable"
          className="rounded bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-900"
        >
          {unavailableMessage}
        </div>
      )}

      <button
        type="submit"
        disabled={submitDisabled}
        data-testid="fundadores-form-submit"
        aria-disabled={submitDisabled}
        className="w-full rounded bg-blue-700 px-4 py-3 font-semibold text-white text-base hover:bg-blue-800 disabled:bg-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
      >
        {loading
          ? 'Processando...'
          : unavailable
            ? 'Programa fechado'
            : `Garantir acesso vitalício por ${price}`}
      </button>

      <p className="text-xs text-slate-500 text-center">
        Sem compromisso até a confirmação do pagamento. Dados enviados por conexão segura.
      </p>
    </form>
  );
}
