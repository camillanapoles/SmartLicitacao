/**
 * Analytics Traffic Source Derivation
 *
 * Pure helper module for deriving traffic_source from referrer + UTM params.
 * Used by AnalyticsProvider to enrich page_load events.
 *
 * Implements CONV-INST-001 AC1.
 */

export const SEARCH_ENGINE_DOMAINS = [
  'google.com',
  'bing.com',
  'duckduckgo.com',
  'yahoo.com',
] as const;

export type TrafficSource =
  | 'organic_search'
  | 'paid_search'
  | 'referral'
  | 'direct'
  | 'utm_campaign';

/**
 * Check if a referrer hostname belongs to a known search engine.
 * Uses hostname suffix matching to handle subdomains (e.g. www.google.com, news.google.com).
 */
export function isSearchEngine(referrer: string): boolean {
  if (!referrer) return false;
  try {
    const hostname = new URL(referrer).hostname;
    return SEARCH_ENGINE_DOMAINS.some(
      (domain) => hostname === domain || hostname.endsWith(`.${domain}`)
    );
  } catch {
    return false;
  }
}

/**
 * Derive traffic_source from referrer and UTM params.
 *
 * Priority order (first match wins):
 * 1. paid_search  — utm_medium is 'cpc' or 'paid'
 * 2. utm_campaign — any utm_* param present
 * 3. organic_search — referrer is a search engine AND no UTM
 * 4. referral — referrer non-empty, not search engine, no UTM
 * 5. direct — default (no referrer, no UTM)
 *
 * @param referrer  - value of document.referrer (empty string if direct)
 * @param utmParams - UTM params captured from URL (via getStoredUTMParams or URLSearchParams)
 */
export function deriveTrafficSource(
  referrer: string,
  utmParams: Record<string, string>
): TrafficSource {
  const hasUtm = Object.keys(utmParams).length > 0;
  const utmMedium = utmParams['utm_medium']?.toLowerCase() ?? '';

  // 1. Paid search: explicit paid medium
  if (hasUtm && (utmMedium === 'cpc' || utmMedium === 'paid')) {
    return 'paid_search';
  }

  // 2. UTM campaign: any UTM param present (catches all other UTM traffic)
  if (hasUtm) {
    return 'utm_campaign';
  }

  // 3. Organic search: search engine referrer, no UTM
  if (referrer && isSearchEngine(referrer)) {
    return 'organic_search';
  }

  // 4. Referral: non-search referrer, no UTM
  if (referrer) {
    return 'referral';
  }

  // 5. Direct: no referrer, no UTM
  return 'direct';
}

/**
 * Extract UTM params from a URLSearchParams or plain object.
 * Returns a subset with only keys matching utm_*.
 */
export function extractUtmFields(params: URLSearchParams | Record<string, string>): Record<string, string> {
  const result: Record<string, string> = {};
  const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];

  if (params instanceof URLSearchParams) {
    for (const key of UTM_KEYS) {
      const val = params.get(key);
      if (val) result[key] = val;
    }
  } else {
    for (const key of UTM_KEYS) {
      if (params[key]) result[key] = params[key];
    }
  }

  return result;
}
