'use client';

import { useState } from 'react';
import Link from 'next/link';

/**
 * COPY-COP-006: Lead Magnet 1 gate page — "Guia Prático B2G".
 *
 * User must submit their email to access the PDF download.
 * Posts to /api/lead-capture with source='lead_magnet_1'.
 */
export default function GuiaPraticoB2G() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || loading) return;

    setLoading(true);
    setError(false);
    try {
      const res = await fetch('/api/lead-capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          source: 'lead_magnet_1',
          origin_url: typeof window !== 'undefined' ? window.location.href : '/guia/guia-pratico-b2g',
        }),
      });

      if (res.ok) {
        setSubmitted(true);
      } else {
        setError(true);
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-canvas">
      {/* Simple header */}
      <header className="border-b border-border">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold text-ink">
            SmartLic
          </Link>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="max-w-lg w-full">
          {submitted ? (
            <div className="text-center bg-surface-1 rounded-2xl border border-border p-8 sm:p-12">
              <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <svg
                  className="w-8 h-8 text-green-600 dark:text-green-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
              <h1 className="text-2xl font-bold text-ink mb-3">
                Guia enviado!
              </h1>
              <p className="text-ink-secondary mb-6">
                Seu guia foi enviado para <strong>{email}</strong>. Verifique sua caixa de entrada
                (e a pasta de spam) para baixar o PDF.
              </p>
              <Link
                href="/"
                className="inline-block px-6 py-3 bg-brand-blue text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors"
              >
                Voltar para o início
              </Link>
            </div>
          ) : (
            <>
              {/* Hero section */}
              <div className="text-center mb-8">
                <span className="inline-block px-3 py-1 text-xs font-semibold uppercase tracking-wider text-brand-blue bg-brand-blue-subtle rounded-full mb-4">
                  Material Gratuito
                </span>
                <h1 className="text-3xl sm:text-4xl font-bold text-ink mb-4">
                  Guia Prático: Como encontrar editais compatíveis com sua empresa em 2026
                </h1>
                <p className="text-lg text-ink-secondary">
                  Descubra oportunidades B2G que sua empresa pode estar perdendo. Um guia prático
                  com estratégias testadas para filtrar, avaliar e priorizar licitações públicas.
                </p>
              </div>

              {/* What's inside */}
              <div className="bg-surface-1 rounded-xl border border-border p-6 mb-8">
                <h2 className="font-bold text-ink mb-3">O que você vai aprender:</h2>
                <ul className="space-y-2 text-sm text-ink-secondary">
                  <li className="flex items-start gap-2">
                    <svg className="w-4 h-4 mt-0.5 text-brand-blue shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Onde encontrar editais públicos por setor e região
                  </li>
                  <li className="flex items-start gap-2">
                    <svg className="w-4 h-4 mt-0.5 text-brand-blue shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Como avaliar a viabilidade de um edital em 5 minutos
                  </li>
                  <li className="flex items-start gap-2">
                    <svg className="w-4 h-4 mt-0.5 text-brand-blue shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Os 5 sinais de que um edital vale a pena (antes de ler 100 páginas)
                  </li>
                  <li className="flex items-start gap-2">
                    <svg className="w-4 h-4 mt-0.5 text-brand-blue shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Ferramentas gratuitas para automatizar sua busca de licitações
                  </li>
                </ul>
              </div>

              {/* Gate form */}
              <div className="bg-surface-1 rounded-2xl border-2 border-brand-blue/20 p-8">
                <h2 className="text-xl font-bold text-ink mb-2">
                  Baixe seu guia gratuito
                </h2>
                <p className="text-ink-secondary text-sm mb-6">
                  Preencha seu email para receber o link de download.
                </p>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <input
                    type="email"
                    required
                    placeholder="seu@email.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full px-4 py-3 rounded-lg border border-border bg-surface-0 text-ink placeholder:text-ink-secondary/50 focus:outline-none focus:ring-2 focus:ring-brand-blue"
                  />
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full px-6 py-3 bg-brand-blue text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 text-lg"
                  >
                    {loading ? 'Enviando...' : 'Baixar Guia Gratuito'}
                  </button>
                </form>
                {error && (
                  <p className="mt-3 text-sm text-red-600 text-center">
                    Erro ao enviar. Tente novamente.
                  </p>
                )}
                <p className="mt-4 text-xs text-ink-muted text-center">
                  Seus dados estao seguros. Sem spam, cancele a qualquer momento.
                </p>
              </div>
            </>
          )}
        </div>
      </main>

      {/* Simple footer */}
      <footer className="border-t border-border py-6">
        <div className="max-w-4xl mx-auto px-4 text-center text-sm text-ink-secondary">
          <p>&copy; 2026 SmartLic.tech — CONFENGE Avaliações e Inteligência Artificial LTDA</p>
        </div>
      </footer>
    </div>
  );
}
