'use client';

import { useState } from 'react';
import { SECTORS } from '@/lib/sectors';

/**
 * NewsletterFooter — Email capture component for the landing page footer.
 *
 * COPY-COP-006 (#1127): "Receba alertas semanais de oportunidades para seu setor"
 * with sector dropdown + email input + submit button.
 *
 * Posts to /api/lead-capture with source: "newsletter_footer".
 */
export default function NewsletterFooter() {
  const [email, setEmail] = useState('');
  const [setor, setSetor] = useState('');
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || status === 'loading') return;

    setStatus('loading');
    try {
      const res = await fetch('/api/lead-capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          source: 'newsletter_footer',
          setor: setor || null,
          captured_at: new Date().toISOString(),
        }),
      });
      if (res.ok) {
        setStatus('success');
      } else {
        setStatus('error');
      }
    } catch {
      setStatus('error');
    }
  };

  if (status === 'success') {
    return (
      <section className="bg-surface-1 border-y border-border">
        <div className="max-w-landing mx-auto px-4 sm:px-6 lg:px-8 py-10 text-center">
          <p className="text-lg font-semibold text-ink">
            Pronto! Agora você receberá alertas semanais de oportunidades do seu setor.
          </p>
          <p className="text-sm text-ink-secondary mt-2">
            Fique de olho no seu email — toda semana temos novidades.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="bg-surface-1 border-y border-border">
      <div className="max-w-landing mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-14">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-xl sm:text-2xl font-bold text-ink mb-2">
            Receba alertas semanais de oportunidades para seu setor
          </h2>
          <p className="text-ink-secondary text-sm mb-6">
            Novos editais toda semana filtrados por setor, com análise de viabilidade.
            Sem spam — cancele quando quiser.
          </p>

          <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-xl mx-auto">
            <select
              value={setor}
              onChange={(e) => setSetor(e.target.value)}
              className="px-4 py-3 rounded-lg border border-border bg-surface-0 text-ink
                         focus:outline-none focus:ring-2 focus:ring-brand-blue text-sm
                         appearance-none cursor-pointer sm:w-48"
              aria-label="Selecione seu setor"
            >
              <option value="">Todos os setores</option>
              {SECTORS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>

            <input
              type="email"
              required
              placeholder="seu@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="flex-1 px-4 py-3 rounded-lg border border-border bg-surface-0 text-ink
                         placeholder:text-ink-secondary/50 focus:outline-none focus:ring-2
                         focus:ring-brand-blue min-w-0"
            />

            <button
              type="submit"
              disabled={status === 'loading'}
              className="px-6 py-3 bg-brand-blue text-white font-semibold rounded-lg
                         hover:bg-blue-700 transition-colors disabled:opacity-50
                         whitespace-nowrap"
            >
              {status === 'loading' ? 'Enviando...' : 'Quero receber →'}
            </button>
          </form>

          {status === 'error' && (
            <p className="mt-3 text-sm text-red-600">
              Erro ao enviar. Tente novamente ou envie um email para contato@smartlic.tech.
            </p>
          )}

          <p className="mt-4 text-xs text-ink-muted">
            Seus dados estão seguros. Leia nossa{' '}
            <a href="/privacidade" className="text-brand-blue hover:underline">
              Política de Privacidade
            </a>
            .
          </p>
        </div>
      </div>
    </section>
  );
}
