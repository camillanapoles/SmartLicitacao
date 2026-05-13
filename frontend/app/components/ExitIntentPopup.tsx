'use client';

import { useState, useEffect, useCallback } from 'react';

/**
 * COPY-COP-006: Exit-intent popup for lead capture.
 *
 * Triggers when:
 * - Desktop: mouse leaves the viewport (top edge)
 * - Mobile: scroll reaches 60% of page
 *
 * Shows once per visitor every 7 days (cookie-gated).
 * Posts to /api/lead-capture with source='exit_intent'.
 */
const EXIT_COOKIE_KEY = 'smartlic_exit_intent_seen';
const EXIT_COOKIE_DAYS = 7;

function getExitCookie(): boolean {
  if (typeof document === 'undefined') return true;
  try {
    const match = document.cookie.match(
      new RegExp(`(?:^|;\\s*)${EXIT_COOKIE_KEY}=([^;]*)`)
    );
    if (!match) return false;
    const data = JSON.parse(decodeURIComponent(match[1]));
    const elapsed = Date.now() - (data.t || 0);
    return elapsed < EXIT_COOKIE_DAYS * 86400000;
  } catch {
    return false;
  }
}

function setExitCookie(): void {
  try {
    const data = { t: Date.now() };
    const encoded = encodeURIComponent(JSON.stringify(data));
    document.cookie = `${EXIT_COOKIE_KEY}=${encoded}; path=/; max-age=${EXIT_COOKIE_DAYS * 86400}; SameSite=Lax`;
  } catch {
    // Cookie failure is non-blocking
  }
}

export function ExitIntentPopup() {
  const [visible, setVisible] = useState(false);
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  // Track whether user has already seen the popup this session
  const [dismissed, setDismissed] = useState(false);

  const show = useCallback(() => {
    if (getExitCookie() || dismissed) return;
    setVisible(true);
  }, [dismissed]);

  const hide = useCallback(() => {
    setVisible(false);
    setDismissed(true);
    setExitCookie();
  }, []);

  useEffect(() => {
    if (getExitCookie()) return;

    let mouseLeft = false;

    const handleMouseLeave = (e: MouseEvent) => {
      // Only trigger when mouse exits through the top edge
      if (e.clientY <= 0 && !mouseLeft) {
        mouseLeft = true;
        show();
      }
    };

    const handleScroll = () => {
      const scrollPercent =
        window.scrollY / (document.documentElement.scrollHeight - window.innerHeight);
      if (scrollPercent >= 0.6) {
        show();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        hide();
      }
    };

    document.addEventListener('mouseleave', handleMouseLeave);
    window.addEventListener('scroll', handleScroll, { passive: true });
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mouseleave', handleMouseLeave);
      window.removeEventListener('scroll', handleScroll);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [show, hide]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || loading) return;

    setLoading(true);
    try {
      const res = await fetch('/api/lead-capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          source: 'exit_intent',
          origin_url: window.location.href,
        }),
      });

      if (res.ok) {
        setSubmitted(true);
      }
    } catch {
      // Fail silently
    } finally {
      setLoading(false);
      setExitCookie();
    }
  };

  if (!visible) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
      onClick={hide}
      role="dialog"
      aria-modal="true"
      aria-label="Antes de sair"
    >
      <div
        className="bg-surface-1 rounded-2xl shadow-2xl max-w-md w-full p-8 relative"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={hide}
          className="absolute top-4 right-4 text-ink-secondary hover:text-ink transition-colors"
          aria-label="Fechar"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>

        {submitted ? (
          <div className="text-center py-4">
            <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
              <svg
                className="w-6 h-6 text-green-600 dark:text-green-400"
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
            <h3 className="text-lg font-bold text-ink mb-2">Guia enviado!</h3>
            <p className="text-ink-secondary text-sm">
              Verifique seu email para baixar o guia gratuito de oportunidades B2G.
            </p>
          </div>
        ) : (
          <>
            <h3 className="text-lg font-bold text-ink mb-2">
              Antes de ir, baixe nosso guia gratuito:
            </h3>
            <p className="text-ink-secondary text-sm mb-6">
              &ldquo;Como ganhar licita&ccedil;&otilde;es p&uacute;blicas em 2026&rdquo; — guia pr&aacute;tico
              para encontrar oportunidades B2G que sua empresa pode estar perdendo.
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <input
                type="email"
                required
                placeholder="Seu melhor email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 rounded-lg border border-border bg-surface-0 text-ink placeholder:text-ink-secondary/50 focus:outline-none focus:ring-2 focus:ring-brand-blue"
              />
              <button
                type="submit"
                disabled={loading}
                className="w-full px-6 py-3 bg-brand-blue text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {loading ? 'Enviando...' : 'Baixar Guia Grátis'}
              </button>
            </form>

            <button
              onClick={hide}
              className="mt-4 w-full text-center text-sm text-ink-secondary hover:text-ink transition-colors"
            >
              Não, obrigado
            </button>
          </>
        )}
      </div>
    </div>
  );
}
