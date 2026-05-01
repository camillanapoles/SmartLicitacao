import type { MetadataRoute } from 'next';

/**
 * SEO-PROG-007: Dynamic robots.ts route handler (Next.js 16 metadata API).
 *
 * Replaces static `frontend/public/robots.txt` with an env-aware route handler.
 * Production serves full Allow/Disallow + AI crawler rules + sitemap reference.
 * Preview/staging blocks indexing entirely to prevent duplicate canonical leaks.
 *
 * `force-static` is correct here: rules are deterministic from build-time env vars.
 * Changing rules requires a redeploy — by design.
 *
 * Note: `frontend/public/robots.txt` is intentionally retained for the +7-day
 * follow-up safety window; Next.js prioritizes `app/robots.ts` over the static
 * file, so the static file is dead code at runtime once this ships.
 */

export const dynamic = 'force-static';

const BASE_URL = process.env.NEXT_PUBLIC_CANONICAL_URL || 'https://smartlic.tech';
// Falls through to production rules if NEXT_PUBLIC_ENVIRONMENT is unset (safe default).
// Wired in Railway via NEXT_PUBLIC_ENVIRONMENT=production|preview|staging|development.
const ENV = process.env.NEXT_PUBLIC_ENVIRONMENT || 'production';
// 'index' (default, post SEO-PROG-006) | 'legacy' (rollback flag)
const SITEMAP_VARIANT = process.env.SITEMAP_USE_INDEX_VARIANT || 'index';

const SITEMAP_URL =
  SITEMAP_VARIANT === 'legacy'
    ? `${BASE_URL}/sitemap.xml`
    : `${BASE_URL}/sitemap_index.xml`;

/**
 * AC6: PRIVATE_PATHS uses path-exact (trailing-slash) form to avoid the
 * prefix-match over-blocking documented in GSC (464 SEO pages bucketed as
 * "Bloqueada pelo robots.txt" on 2026-04-28).
 *
 * Per RFC 9309 §2.2.2, `Disallow: /alertas` blocks `/alertas-publicos/*`
 * (40+ public SEO pages); `Disallow: /alertas/` blocks only `/alertas/...`
 * descendants and leaves `/alertas-publicos/*` allowed.
 *
 * `/buscar` raiz is intentionally listed alongside `/buscar/`: the raiz is an
 * auth-gated SPA shell (`app/buscar/page.tsx` is "use client" with QuotaBadge,
 * UserMenu, TrialCountdown, PlanBadge — no public SEO surface). Removing it
 * would silently flip raiz from blocked → allowed.
 */
const PRIVATE_PATHS = [
  '/admin/',
  '/auth/callback',
  '/api/auth/',
  '/api/admin/',
  '/api/csp-report',
  '/dashboard/',
  '/conta/',
  '/buscar', // raiz — auth-gated SPA shell, not public SEO
  '/buscar/', // subpaths
  '/pipeline/',
  '/historico/',
  '/mensagens/',
  '/alertas/', // path-exact: leaves /alertas-publicos/* allowed
  '/onboarding/',
  '/recuperar-senha',
  '/redefinir-senha',
];

const BLOCKED_AI_CRAWLERS = [
  'Amazonbot',
  'Applebot-Extended',
  'Bytespider',
  'CCBot',
  'ClaudeBot',
  'GPTBot',
  'meta-externalagent',
];

export default function robots(): MetadataRoute.Robots {
  // AC2: preview/staging/dev blocks indexing entirely; no sitemap, no host canonical.
  if (ENV !== 'production') {
    return {
      rules: [{ userAgent: '*', disallow: '/' }],
      host: BASE_URL,
    };
  }

  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: PRIVATE_PATHS,
      },
      // Google-Extended: explicit allow for AI Overviews / SGE eligibility.
      // Per RFC 9309 §2.2.2, more specific rule wins; on equal specificity,
      // Allow takes precedence over Disallow.
      {
        userAgent: 'Google-Extended',
        allow: '/',
      },
      // Block non-Google AI crawlers from training-data scraping.
      ...BLOCKED_AI_CRAWLERS.map((bot) => ({
        userAgent: bot,
        disallow: '/',
      })),
    ],
    sitemap: SITEMAP_URL,
    host: BASE_URL,
  };
}
