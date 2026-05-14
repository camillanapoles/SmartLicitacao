'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * COPY-COP-005: Exit-intent popup (Cialdini — Reciprocidade)
 *
 * Detects when the user is about to leave the page and offers a free guide
 * in exchange for their email. Demonstrates reciprocity by giving value
 * before asking for commitment.
 *
 * - Desktop: triggers on mouse leaving the viewport (top edge)
 * - Mobile: triggers on scroll-up toward the top of the page
 * - Only shows once per session (localStorage key: sl_exit_intent_shown)
 * - Mobile-friendly: bottom sheet style
 * - POSTs email to /v1/lead-capture
 */
const LS_KEY = 'sl_exit_intent_shown';

export default function ExitIntentPopup() {
  const [visible, setVisible] = useState(false);
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [dismissed, setDismissed] = useState(false);
  const checkDoneRef = useRef(false);

  // Check localStorage on mount
  useEffect(() => {
    const shown = localStorage.getItem(LS_KEY);
    if (shown === 'true') {
      checkDoneRef.current = true;
    }
  }, []);

  // Desktop: mouse leaving the viewport (top edge)
  const handleMouseLeave = useCallback((e: MouseEvent) => {
    if (checkDoneRef.current) return;
    if (e.clientY <= 0) {
      checkDoneRef.current = true;
      setVisible(true);
    }
  }, []);

  // Mobile: scroll-up detection — user scrolls back toward top after scrolling down
  const handleScroll = useCallback(() => {
    if (checkDoneRef.current) return;
    // Only trigger on mobile-ish widths (below 768px)
    if (window.innerWidth >= 768) return;
    // If user has scrolled down at least 400px and then scrolls back up past 300px
    const scrollY = window.scrollY;
    // We store the max scroll position to know they've scrolled down
    if (scrollY > 500) {
      // They've scrolled down enough — if they come back up near the top, show popup
      if (scrollY < 250) {
        checkDoneRef.current = true;
        setVisible(true);
      }
    }
  }, []);

  useEffect(() => {
    if (checkDoneRef.current) return;
    document.addEventListener('mouseleave', handleMouseLeave);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      document.removeEventListener('mouseleave', handleMouseLeave);
      window.removeEventListener('scroll', handleScroll);
    };
  }, [handleMouseLeave, handleScroll]);

  const handleDismiss = useCallback(() => {
    setVisible(false);
    setDismissed(true);
    localStorage.setItem(LS_KEY, 'true');
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!email || status === 'loading') return;
      setStatus('loading');
      try {
        const res = await fetch('/api/lead-capture', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email,
            source: 'exit_intent',
          }),
        });
        if (res.ok) {
          setStatus('success');
          localStorage.setItem(LS_KEY, 'true');
        } else {
          setStatus('error');
        }
      } catch {
        setStatus('error');
      }
    },
    [email, status],
  );

  // Don't render anything if not visible or already dismissed
  if (!visible || dismissed) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
        onClick={handleDismiss}
        aria-hidden="true"
      />

      {/* Modal — bottom sheet on mobile, centered on desktop */}
      <div
        className="fixed inset-x-0 bottom-0 z-50 md:inset-auto md:top-1/2 md:left-1/2 md:-translate-x-1/2 md:-translate-y-1/2 md:max-w-lg"
        role="dialog"
        aria-modal="true"
        aria-label="Antes de sair"
      >
        <div className="bg-surface-0 rounded-t-2xl md:rounded-2xl shadow-2xl border border-border p-6 md:p-8">
          {/* Close button */}
          <button
            onClick={handleDismiss}
            className="absolute top-4 right-4 p-2 text-ink-muted hover:text-ink transition-colors"
            aria-label="Fechar"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          {status === 'success' ? (
            <div className="text-center py-6">
              <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <p className="text-lg font-semibold text-ink mb-1">Guia enviado!</p>
              <p className="text-sm text-ink-secondary">
                Verifique sua caixa de entrada para baixar o material.
              </p>
            </div>
          ) : (
            <>
              <div className="text-center mb-6">
                <div className="w-12 h-12 rounded-full bg-brand-blue-subtle flex items-center justify-center mx-auto mb-4">
                  <svg className="w-6 h-6 text-brand-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-ink">
                  Antes de ir, baixe nosso guia gratuito
                </h3>
                <p className="text-sm text-ink-secondary mt-2">
                  &quot;Como ganhar licitações públicas em 2026&quot; — estratégias práticas baseadas em dados oficiais.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                <input
                  type="email"
                  required
                  placeholder="seu@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-4 py-3 rounded-lg border border-border bg-surface-1 text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-blue"
                  autoComplete="email"
                />
                <button
                  type="submit"
                  disabled={status === 'loading'}
                  className="w-full px-6 py-3 bg-brand-blue text-white font-semibold rounded-lg hover:bg-brand-blue-hover transition-colors disabled:opacity-50"
                >
                  {status === 'loading' ? 'Enviando...' : 'Baixar guia →'}
                </button>
              </form>

              {status === 'error' && (
                <p className="mt-2 text-sm text-red-600 text-center">Erro ao enviar. Tente novamente.</p>
              )}

              <button
                onClick={handleDismiss}
                className="w-full mt-3 text-sm text-ink-muted hover:text-ink-secondary transition-colors py-2"
              >
                Não, obrigado
              </button>
            </>
          )}
        </div>
      </div>
    </>
  );
}
