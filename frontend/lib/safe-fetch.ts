/**
 * safeFetch + fetchWithBudget — observable fetch wrappers with Sentry instrumentation.
 *
 * FOUND-SCALE-002: foundation para SEN-FE-002 (consolidação) + SEN-FE-003 (SSG decouple).
 * Generaliza o pattern proven em `frontend/app/sitemap.ts::fetchSitemapJson` (STORY-SEO-001 +
 * SEN-BE-007) para uso em qualquer SSG/ISR fetch fora do sitemap.
 *
 * Memory references:
 *   - feedback_frontend_sentry_silent_buildtime — 0 events em 24h apesar de sitemap-4=0
 *     em prod; observability gap blind durante outage.
 *   - feedback_build_hammers_backend_cascade — SSG 4146 pages sem timeout/abort saturou
 *     backend hobby DB pool; AbortSignal.timeout obrigatório.
 *   - feedback_isr_fetch_cache_alignment_next16 — `revalidate=N` + `cache: 'no-store'`
 *     quebra SSG; usar `next: { revalidate: N }`.
 */
import * as Sentry from '@sentry/nextjs';

export type SafeFetchOutcome =
  | 'success'
  | 'http_error'
  | 'timeout'
  | 'network_error';

export interface SafeFetchOptions extends RequestInit {
  /** Sentry tag for this call site (e.g. "cnpj-profile", "orgao-list"). */
  label?: string;
  /** Timeout in ms (default 15000ms). */
  timeout?: number;
  /**
   * When true, HTTP 5xx responses throw an Error instead of returning null.
   * Use this in ISR pages so transient backend errors preserve last-good cache
   * (stale-while-revalidate) rather than caching an empty state.
   */
  throwOn5xx?: boolean;
}

/**
 * Fetch wrapper with AbortSignal timeout, Sentry exception capture, and structured
 * breadcrumb. Returns null on any failure (HTTP error, timeout, network error).
 *
 * Use this as the building block. For typed JSON responses with retry/fallback,
 * use {@link fetchWithBudget}.
 */
export async function safeFetch(
  url: string,
  options: SafeFetchOptions = {},
): Promise<Response | null> {
  const { label = url, timeout = 15000, throwOn5xx = false, ...init } = options;
  const startedAt = Date.now();
  let outcome: SafeFetchOutcome = 'success';
  let statusCode = 0;

  try {
    const resp = await fetch(url, {
      signal: AbortSignal.timeout(timeout),
      ...init,
    });
    statusCode = resp.status;
    if (!resp.ok) {
      outcome = 'http_error';
      Sentry.captureMessage(`safeFetch ${label} HTTP ${resp.status}`, {
        level: 'warning',
        tags: { fetch_label: label, fetch_outcome: 'http_error' },
        contexts: { fetch: { url, status: resp.status } },
      });
      // ISR stale-while-revalidate: throw on 5xx so Next.js preserves last-good cache
      // instead of caching an empty/error state for the full revalidate window.
      if (throwOn5xx && resp.status >= 500) {
        throw new Error(`safeFetch ${label} server error ${resp.status}`);
      }
      return null;
    }
    return resp;
  } catch (err) {
    const errName = (err as Error)?.name || '';
    outcome =
      errName === 'TimeoutError' || errName === 'AbortError'
        ? 'timeout'
        : 'network_error';
    Sentry.captureException(err, {
      tags: { fetch_label: label, fetch_outcome: outcome },
      contexts: { fetch: { url } },
    });
    return null;
  } finally {
    Sentry.addBreadcrumb({
      category: 'fetch',
      message: `safeFetch ${label}`,
      level: outcome === 'success' ? 'info' : 'warning',
      data: {
        fetch_outcome: outcome,
        status_code: statusCode,
        latency_ms: Date.now() - startedAt,
        url,
      },
    });
  }
}

export interface FetchBudgetOptions<T> {
  /** Timeout per attempt in ms (default 10000ms). */
  timeout?: number;
  /** Retry count after first failure (default 1 — total 2 attempts). */
  retries?: number;
  /** Fallback value if all attempts fail (default null). */
  fallback?: T | null;
  /** Next.js ISR revalidate window in seconds (default 3600). */
  revalidate?: number;
  /** Sentry tag (default url). */
  label?: string;
  /**
   * When true, HTTP 5xx responses are re-thrown instead of being swallowed.
   * Use in ISR pages to preserve last-good stale-while-revalidate cache on
   * transient backend errors (vs caching an empty/error state for the full
   * revalidate window).
   */
  throwOn5xx?: boolean;
  /**
   * Optional response shape transformer. Receives parsed JSON, must return
   * the typed value or throw on shape mismatch.
   */
  extract?: (data: unknown) => T;
}

/**
 * Typed JSON fetch wrapper with retry, fallback, and Sentry observability.
 *
 * Defaults to Next.js ISR-friendly cache: `next: { revalidate: 3600 }`.
 * NEVER pass `cache: 'no-store'` in conjunction with `revalidate` — quebra SSG
 * (memory `feedback_isr_fetch_cache_alignment_next16`).
 *
 * Returns the typed value, or `fallback` if all attempts fail.
 *
 * @example
 *   const profile = await fetchWithBudget<Profile>(
 *     `${getBackendUrl()}/v1/empresa/${cnpj}/perfil-b2g`,
 *     { timeout: 10000, retries: 1, fallback: null, label: 'cnpj-profile' }
 *   );
 */
export async function fetchWithBudget<T>(
  url: string,
  opts: FetchBudgetOptions<T> = {},
): Promise<T | null> {
  const {
    timeout = 10000,
    retries = 1,
    fallback = null,
    revalidate = 3600,
    label = url,
    throwOn5xx = false,
    extract,
  } = opts;

  const totalAttempts = retries + 1;

  for (let attempt = 1; attempt <= totalAttempts; attempt++) {
    const attemptLabel = attempt === 1 ? label : `${label}-retry-${attempt - 1}`;
    const resp = await safeFetch(url, {
      label: attemptLabel,
      timeout,
      throwOn5xx,
      next: { revalidate },
    });

    if (resp !== null) {
      try {
        const data = (await resp.json()) as unknown;
        return extract ? extract(data) : (data as T);
      } catch (err) {
        // JSON parse error — treat as failure attempt.
        Sentry.captureException(err, {
          tags: { fetch_label: attemptLabel, fetch_outcome: 'parse_error' },
          contexts: { fetch: { url } },
        });
      }
    }

    if (attempt < totalAttempts) {
      // Exponential backoff: 2s, 4s, 8s, ...
      const backoffMs = 2000 * 2 ** (attempt - 1);
      await new Promise((resolve) => setTimeout(resolve, backoffMs));
    }
  }

  Sentry.captureMessage(`fetchWithBudget_exhausted_${label}`, {
    level: 'warning',
    tags: { fetch_label: label, fetch_outcome: 'budget_exhausted' },
    contexts: { fetch: { url, total_attempts: totalAttempts } },
  });
  return fallback;
}
