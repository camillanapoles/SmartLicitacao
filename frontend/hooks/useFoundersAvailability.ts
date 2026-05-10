"use client";

import useSWR from "swr";

/**
 * Issue #1006 (COPY-CROSS-007): SWR wrapper around `/api/founding/availability`.
 *
 * Note on naming: task description references "/api/founders/availability" + PR #1014,
 * but the actually-shipped endpoint in production is the singular form
 * `/api/founding/availability` (proxied to `/v1/founding/availability`). We standardize
 * on the existing endpoint to avoid duplicating infrastructure. PR #1014 hadn't merged
 * at component implementation time.
 *
 * Schema (matches `frontend/app/api-types.generated.ts::FoundingAvailability`):
 *   { available: boolean, seats_remaining: number, deadline_at: string | null }
 *
 * Cache strategy:
 *  - dedupingInterval 60s (matches backend cache and ISR alignment guidance)
 *  - revalidateOnFocus disabled — counter doesn't need sub-minute freshness
 *  - errorRetryCount 1 — fail fast so callers can show conservative fallback copy
 */

export interface FoundingAvailability {
  available: boolean;
  seats_remaining: number;
  deadline_at: string | null;
}

interface UseFoundersAvailabilityResult {
  data: FoundingAvailability | null;
  isLoading: boolean;
  error: Error | null;
}

const fetcher = async (url: string): Promise<FoundingAvailability | null> => {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
};

export function useFoundersAvailability(): UseFoundersAvailabilityResult {
  const { data, error, isLoading } = useSWR<FoundingAvailability | null>(
    "/api/founding/availability",
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
      errorRetryCount: 1,
      fallbackData: null,
    },
  );

  return {
    data: data ?? null,
    isLoading,
    error: (error as Error) ?? null,
  };
}
