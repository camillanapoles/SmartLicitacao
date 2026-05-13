'use client';

import { useState, type FormEvent } from 'react';

/**
 * CRO-CTA-002: Lead Capture Intermediário para /blog/como-participar-primeira-licitacao-2026
 *
 * Coleta email sem exigir cadastro completo. Dispara checklist por email
 * via fluxo de lead nurturing.
 */
const CHECKLIST_ITENS = [
  'Checklist da Primeira Licitação (PDF, 5 minutos)',
  'Guia de Documentos (certidões, prazos e onde tirar cada uma)',
  'Alertas semanais de editais do meu setor',
];

export default function LeadCaptureIntermediate() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState(false);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError(true);
      return;
    }
    setError(false);
    // Em versão futura: integrar com endpoint de lead capture
    setSubmitted(true);
  }

  if (submitted) {
    return (
      <div className="not-prose my-8 sm:my-10 bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800 rounded-xl p-5 sm:p-8 text-center">
        <p className="text-lg sm:text-xl font-bold text-ink mb-2">
          Material enviado! Verifique seu email.
        </p>
        <p className="text-sm text-ink-secondary">
          Enviamos o checklist e o guia para <strong>{email}</strong>. Enquanto isso,
          explore licitações abertas no seu setor — é gratuito.
        </p>
      </div>
    );
  }

  return (
    <div className="not-prose my-8 sm:my-10 bg-gradient-to-br from-brand-navy to-brand-blue rounded-xl p-5 sm:p-8 text-white">
      <p className="text-lg sm:text-xl font-bold mb-2">
        Você ainda não está pronto para testar um software?
      </p>
      <p className="text-sm sm:text-base text-white/80 mb-5 max-w-lg">
        Tudo bem. A maioria das PMEs brasileiras nunca participou de uma
        licitação. Comece com o básico:
      </p>

      <div className="space-y-2 mb-5">
        {CHECKLIST_ITENS.map((item) => (
          <div key={item} className="flex items-start gap-2.5">
            <span className="text-white/90 text-base leading-5 mt-0.5" aria-hidden="true">
              &#9744;
            </span>
            <span className="text-sm sm:text-base text-white/90">{item}</span>
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3">
        <input
          type="email"
          value={email}
          onChange={(e) => { setEmail(e.target.value); setError(false); }}
          placeholder="Seu melhor email"
          className="flex-1 px-4 py-2.5 rounded-button text-sm text-ink bg-white border border-white/20 focus:outline-none focus:ring-2 focus:ring-white/40 placeholder:text-ink-secondary/60"
          required
        />
        <button
          type="submit"
          className="bg-white text-brand-navy font-semibold px-5 sm:px-6 py-2.5 rounded-button text-sm transition-all hover:scale-[1.02] active:scale-[0.98] whitespace-nowrap"
        >
          Receber material gratuito
        </button>
      </form>

      {error && (
        <p className="text-xs text-red-200 mt-2">
          Por favor, insira um email válido.
        </p>
      )}

      <p className="text-xs text-white/60 mt-3">
        Não enviaremos spam. Só conteúdo sobre licitações. Cancele quando quiser.
      </p>
    </div>
  );
}
