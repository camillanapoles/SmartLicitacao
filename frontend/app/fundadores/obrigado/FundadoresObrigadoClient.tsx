'use client';

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';

type Status = 'loading' | 'has_account' | 'no_account' | 'session_error' | 'pending' | 'error';

type SessionStatus = {
  status: 'completed' | 'pending' | 'not_found' | 'error';
  email?: string;
  has_account?: boolean;
  invite_sent?: boolean;
};

const MAX_POLLS = 20;
const POLL_INTERVAL_MS = 3000;
const REDIRECT_DELAY_MS = 5000;

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

function maskEmail(email: string): string {
  const [local, domain] = email.split('@');
  if (!domain) return email;
  const masked = local.length > 2
    ? local[0] + '*'.repeat(Math.min(local.length - 2, 4)) + local[local.length - 1]
    : local[0] + '*';
  return `${masked}@${domain}`;
}

export function FundadoresObrigadoClient() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get('session_id');
  const [status, setStatus] = useState<Status>('loading');
  const [maskedEmail, setMaskedEmail] = useState<string>('');
  const pollCountRef = useRef(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const redirectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const trackedRef = useRef(false);

  useEffect(() => {
    if (!sessionId) {
      setStatus('error');
      return;
    }

    const stopPolling = () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };

    const fetchSessionStatus = async (sid: string): Promise<void> => {
      try {
        const res = await fetch(`/api/founding/session-status?session_id=${encodeURIComponent(sid)}`);
        if (!res.ok) {
          setStatus('session_error');
          return;
        }
        const data: SessionStatus = await res.json();
        if (data.status === 'error' || data.status === 'not_found') {
          setStatus('session_error');
          return;
        }
        if (data.has_account === true) {
          setStatus('has_account');
          if (!trackedRef.current) {
            trackedRef.current = true;
            trackEvent('fundadores_obrigado_viewed', { has_account: true });
          }
          redirectTimerRef.current = setTimeout(() => {
            window.location.href = '/dashboard';
          }, REDIRECT_DELAY_MS);
        } else {
          if (data.email) {
            setMaskedEmail(maskEmail(data.email));
          }
          setStatus('no_account');
          if (!trackedRef.current) {
            trackedRef.current = true;
            trackEvent('fundadores_obrigado_viewed', { has_account: false });
          }
        }
      } catch {
        setStatus('session_error');
        if (!trackedRef.current) {
          trackedRef.current = true;
          trackEvent('fundadores_obrigado_viewed', { state: 'error' });
        }
      }
    };

    // Poll backend for checkout status (max MAX_POLLS × POLL_INTERVAL_MS)
    const poll = async () => {
      try {
        const res = await fetch(`/api/founding/checkout/status?session_id=${encodeURIComponent(sessionId)}`);
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'complete' || data.payment_status === 'paid') {
            stopPolling();
            await fetchSessionStatus(sessionId);
            return;
          }
        }
      } catch {
        // swallow fetch errors — keep polling
      }

      pollCountRef.current += 1;
      if (pollCountRef.current >= MAX_POLLS) {
        stopPolling();
        setStatus('pending');
      }
    };

    pollCountRef.current = 0;
    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      stopPolling();
      if (redirectTimerRef.current) {
        clearTimeout(redirectTimerRef.current);
      }
    };
  }, [sessionId]);

  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Confirmando seu pagamento...</p>
          <p className="text-sm text-gray-500 dark:text-gray-500 mt-2">Boleto pode levar alguns minutos</p>
        </div>
      </div>
    );
  }

  if (status === 'pending') {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="max-w-md text-center">
          <div className="text-4xl mb-4">&#9203;</div>
          <h1 className="text-2xl font-bold mb-3">Pagamento ainda processando</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Você receberá um email assim que o pagamento for confirmado.
            Para boleto bancário, pode levar até 3 dias úteis.
          </p>
          <a href="/fundadores" className="mt-6 inline-block text-blue-600 hover:underline">
            ← Voltar para o Plano Fundadores
          </a>
        </div>
      </div>
    );
  }

  // Estado A — has_account: true
  if (status === 'has_account') {
    return (
      <div className="min-h-screen bg-gradient-to-b from-white to-gray-50 dark:from-gray-900 dark:to-gray-950 flex items-center justify-center px-4">
        <div className="max-w-md text-center">
          <div className="text-5xl mb-4">&#9989;</div>
          <h1 className="text-3xl font-bold mb-3 text-gray-900 dark:text-white">
            Acesso vitalício ativado!
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Seu acesso Fundador está ativo. Redirecionando para o painel em 5 segundos...
          </p>
          <a
            href="/dashboard"
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors"
          >
            Ir para o painel agora →
          </a>
        </div>
      </div>
    );
  }

  // Estado B — has_account: false
  if (status === 'no_account') {
    return (
      <div className="min-h-screen bg-gradient-to-b from-white to-gray-50 dark:from-gray-900 dark:to-gray-950 flex items-center justify-center px-4">
        <div className="max-w-md text-center">
          <div className="text-5xl mb-4">&#9989;</div>
          <h1 className="text-3xl font-bold mb-3 text-gray-900 dark:text-white">
            Pagamento confirmado! Verifique seu email.
          </h1>
          {maskedEmail ? (
            <p className="text-gray-600 dark:text-gray-400 mb-3">
              Enviamos um link de acesso para{' '}
              <span className="font-semibold text-gray-800 dark:text-gray-200">{maskedEmail}</span>.
            </p>
          ) : (
            <p className="text-gray-600 dark:text-gray-400 mb-3">
              Enviamos um link de acesso para o seu email.
            </p>
          )}
          <p className="text-gray-600 dark:text-gray-400 mb-2">
            Clique no link para criar sua senha e acessar a plataforma.
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-500 mb-6">
            Não recebeu? Verifique a caixa de spam.
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-500">
            Dúvidas?{' '}
            <a href="mailto:tiago@smartlic.tech" className="text-blue-600 dark:text-blue-400 hover:underline">
              tiago@smartlic.tech
            </a>
          </p>
        </div>
      </div>
    );
  }

  // Estado C — session_error (fallback) or generic error state
  if (status === 'session_error') {
    return (
      <div className="min-h-screen bg-gradient-to-b from-white to-gray-50 dark:from-gray-900 dark:to-gray-950 flex items-center justify-center px-4">
        <div className="max-w-md text-center">
          <div className="text-5xl mb-4">&#9989;</div>
          <h1 className="text-3xl font-bold mb-3 text-gray-900 dark:text-white">
            Pagamento confirmado!
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Você receberá um email com instruções de acesso em breve.
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-500">
            Dúvidas? Fale conosco:{' '}
            <a href="mailto:tiago@smartlic.tech" className="text-blue-600 dark:text-blue-400 hover:underline">
              tiago@smartlic.tech
            </a>
          </p>
        </div>
      </div>
    );
  }

  // error state (no session_id or other unrecoverable error)
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="max-w-md text-center">
        <p className="text-gray-600 dark:text-gray-400">
          Algo deu errado. Entre em contato:{' '}
          <a href="mailto:tiago@smartlic.tech" className="text-blue-600 hover:underline">
            tiago@smartlic.tech
          </a>
        </p>
      </div>
    </div>
  );
}
