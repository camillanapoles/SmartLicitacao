"use client";

// ---------------------------------------------------------------------------
// P2.2: ExpiredCacheBanner — shown when response_state === "degraded_expired"
// All live sources failed; backend is serving data from an expired cache entry.
// More prominent than CacheBanner (red/amber tones) to signal data staleness.
// ---------------------------------------------------------------------------

/** Format a cached_at ISO timestamp as a human-readable age string in pt-BR. */
function formatCacheAge(cachedAt: string): string {
  const now = new Date();
  const past = new Date(cachedAt);
  const diffMs = now.getTime() - past.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffDays > 0) {
    return diffDays === 1 ? "1 dia atrás" : `${diffDays} dias atrás`;
  }
  if (diffHours > 0) {
    return diffHours === 1 ? "1 hora atrás" : `${diffHours} horas atrás`;
  }
  if (diffMinutes > 0) {
    return diffMinutes === 1 ? "1 minuto atrás" : `${diffMinutes} minutos atrás`;
  }
  return "poucos segundos atrás";
}

export interface ExpiredCacheBannerProps {
  /** ISO timestamp of when the expired cache entry was originally created */
  cachedAt: string;
  /** Handler to retry the search with fresh live data */
  onRetry: () => void;
  /** Whether a retry is currently in progress */
  loading: boolean;
}

/**
 * Prominent amber/red warning banner displayed when the backend serves results
 * from an expired cache because all live data sources are currently unavailable.
 *
 * Visually distinct from the normal CacheBanner (amber→red gradient border,
 * larger icon, stronger copy) so users immediately understand data may be stale.
 */
export function ExpiredCacheBanner({
  cachedAt,
  onRetry,
  loading,
}: ExpiredCacheBannerProps) {
  const ageLabel = formatCacheAge(cachedAt);

  return (
    <div
      className="mt-4 rounded-card border-2 border-amber-400 dark:border-amber-600 bg-amber-50 dark:bg-amber-950/60 p-4 sm:p-5 animate-fade-in-up"
      role="alert"
      aria-live="polite"
      data-testid="expired-cache-banner"
    >
      <div className="flex items-start gap-3">
        {/* Warning triangle icon — larger and more prominent than DataQualityBanner */}
        <svg
          className="w-6 h-6 flex-shrink-0 mt-0.5 text-amber-600 dark:text-amber-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>

        <div className="flex-1 min-w-0">
          {/* Primary message */}
          <p className="text-sm sm:text-base font-semibold text-amber-800 dark:text-amber-200">
            Fontes indisponíveis — exibindo dados salvos anteriormente
          </p>

          {/* Secondary explanation */}
          <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
            Dados de <strong>{ageLabel}</strong>. Estes resultados podem não
            refletir publicações recentes. As fontes de dados estão
            temporariamente indisponíveis.
          </p>

          {/* Action row */}
          <button
            onClick={onRetry}
            disabled={loading}
            type="button"
            className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-button text-sm font-medium bg-amber-600 hover:bg-amber-700 text-white disabled:bg-amber-400 disabled:cursor-not-allowed transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-amber-500"
            data-testid="expired-cache-retry-button"
          >
            {loading ? (
              <>
                <svg
                  className="animate-spin h-4 w-4"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Tentando...
              </>
            ) : (
              "Tentar novamente"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ExpiredCacheBanner;
