'use client';

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';

type Status = 'loading' | 'success' | 'pending' | 'error';

const MAX_POLLS = 20;
const POLL_INTERVAL_MS = 3000;

export function FundadoresObrigadoClient() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get('session_id');
  const [status, setStatus] = useState<Status>('loading');
  const pollCountRef = useRef(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

    // Poll backend for checkout status (max MAX_POLLS × POLL_INTERVAL_MS)
    const poll = async () => {
      try {
        const res = await fetch(`/api/founding/checkout/status?session_id=${encodeURIComponent(sessionId)}`);
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'complete' || data.payment_status === 'paid') {
            stopPolling();
            setStatus('success');
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

    return stopPolling;
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

  if (status === 'success') {
    return (
      <div className="min-h-screen bg-gradient-to-b from-white to-gray-50 dark:from-gray-900 dark:to-gray-950">
        <div className="container mx-auto px-4 py-16 max-w-2xl">
          <div className="text-center mb-12">
            <div className="text-6xl mb-4">&#127881;</div>
            <h1 className="text-4xl font-bold mb-3 text-gray-900 dark:text-white">
              Você está dentro!
            </h1>
            <p className="text-lg text-gray-600 dark:text-gray-400">
              Seu acesso vitalício ao SmartLic foi ativado.
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8 mb-8">
            <h2 className="text-xl font-semibold mb-6 text-gray-900 dark:text-white">
              Próximos passos
            </h2>
            <ol className="space-y-4">
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-green-500 text-white rounded-full flex items-center justify-center text-sm font-bold">&#10003;</span>
                <div>
                  <span className="font-medium text-gray-900 dark:text-white">Acesso vitalício ativado</span>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Seu plano self-service está ativo</p>
                </div>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-blue-500 text-white rounded-full flex items-center justify-center text-sm font-bold">2</span>
                <div>
                  <a href="/buscar" className="font-medium text-blue-600 dark:text-blue-400 hover:underline">
                    Faça sua primeira busca de editais →
                  </a>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Busca multi-fonte PNCP + ComprasGov</p>
                </div>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-blue-500 text-white rounded-full flex items-center justify-center text-sm font-bold">3</span>
                <div>
                  <span className="font-medium text-gray-900 dark:text-white">Resgate 50% de desconto em consultoria</span>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    <a href="mailto:tiago@smartlic.tech" className="text-blue-600 dark:text-blue-400 hover:underline">
                      tiago@smartlic.tech
                    </a>{' '}— mencione que é Fundador
                  </p>
                </div>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-gray-400 text-white rounded-full flex items-center justify-center text-sm font-bold">4</span>
                <div>
                  <span className="font-medium text-gray-900 dark:text-white">Como você nos descobriu?</span>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    <a href="mailto:tiago@smartlic.tech?subject=Como+descobri+o+SmartLic" className="text-blue-600 dark:text-blue-400 hover:underline">
                      Responda em 1 frase
                    </a>
                  </p>
                </div>
              </li>
            </ol>
          </div>

          <div className="text-center">
            <a href="/buscar"
               className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors">
              Começar a buscar editais →
            </a>
          </div>
        </div>
      </div>
    );
  }

  // error state
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
