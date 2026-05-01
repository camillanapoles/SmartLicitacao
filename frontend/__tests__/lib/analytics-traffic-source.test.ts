/**
 * Unit tests for analytics-traffic-source helpers
 *
 * Covers CONV-INST-001 AC7: 4 required scenarios + edge cases.
 */

import {
  isSearchEngine,
  deriveTrafficSource,
  extractUtmFields,
  SEARCH_ENGINE_DOMAINS,
} from '../../lib/analytics-traffic-source';

describe('isSearchEngine', () => {
  it('returns false for empty string', () => {
    expect(isSearchEngine('')).toBe(false);
  });

  it('returns false for invalid URL', () => {
    expect(isSearchEngine('not-a-url')).toBe(false);
  });

  it('returns true for exact google.com', () => {
    expect(isSearchEngine('https://google.com/search?q=test')).toBe(true);
  });

  it('returns true for www.google.com subdomain', () => {
    expect(isSearchEngine('https://www.google.com/search?q=pncp')).toBe(true);
  });

  it('returns true for news.google.com subdomain', () => {
    expect(isSearchEngine('https://news.google.com/stories')).toBe(true);
  });

  it('returns true for bing.com', () => {
    expect(isSearchEngine('https://www.bing.com/search?q=licitacao')).toBe(true);
  });

  it('returns true for duckduckgo.com', () => {
    expect(isSearchEngine('https://duckduckgo.com/?q=pregao')).toBe(true);
  });

  it('returns true for yahoo.com', () => {
    expect(isSearchEngine('https://search.yahoo.com/search?p=test')).toBe(true);
  });

  it('returns false for non-search referrer', () => {
    expect(isSearchEngine('https://twitter.com/user')).toBe(false);
  });

  it('returns false for site that contains search engine name but is not one', () => {
    // hostname "notgoogle.com" should not match ".google.com" suffix
    expect(isSearchEngine('https://notgoogle.com/page')).toBe(false);
  });

  it('covers all SEARCH_ENGINE_DOMAINS constants', () => {
    for (const domain of SEARCH_ENGINE_DOMAINS) {
      expect(isSearchEngine(`https://www.${domain}/search`)).toBe(true);
    }
  });
});

describe('deriveTrafficSource', () => {
  // AC7 scenario 1: organic_search
  it('AC7-1: Google referrer with no UTM → organic_search', () => {
    const result = deriveTrafficSource(
      'https://www.google.com/search?q=pncp',
      {}
    );
    expect(result).toBe('organic_search');
  });

  // AC7 scenario 2: utm_campaign
  it('AC7-2: UTM params present (no medium) → utm_campaign', () => {
    const result = deriveTrafficSource('', {
      utm_source: 'blog',
      utm_medium: 'cta',
    });
    expect(result).toBe('utm_campaign');
  });

  it('paid_search wins over utm_campaign when utm_medium=cpc', () => {
    const result = deriveTrafficSource('', {
      utm_source: 'google',
      utm_medium: 'cpc',
      utm_campaign: 'trial',
    });
    expect(result).toBe('paid_search');
  });

  it('paid_search when utm_medium=paid (case-insensitive)', () => {
    const result = deriveTrafficSource('', {
      utm_source: 'google',
      utm_medium: 'PAID',
    });
    expect(result).toBe('paid_search');
  });

  it('utm_campaign for any other utm_medium value', () => {
    const result = deriveTrafficSource('', {
      utm_source: 'newsletter',
      utm_medium: 'email',
    });
    expect(result).toBe('utm_campaign');
  });

  it('referral for non-search referrer with no UTM', () => {
    const result = deriveTrafficSource('https://linkedin.com/post/123', {});
    expect(result).toBe('referral');
  });

  it('direct when no referrer and no UTM', () => {
    const result = deriveTrafficSource('', {});
    expect(result).toBe('direct');
  });

  it('organic_search NOT returned when UTM params also present with search engine referrer', () => {
    // UTM takes precedence over organic_search (utm_campaign rule wins)
    const result = deriveTrafficSource('https://www.google.com/search?q=test', {
      utm_source: 'google',
      utm_medium: 'organic',
    });
    expect(result).toBe('utm_campaign');
  });
});

describe('extractUtmFields', () => {
  it('extracts utm fields from URLSearchParams', () => {
    const params = new URLSearchParams(
      'utm_source=google&utm_medium=cpc&utm_campaign=trial&foo=bar'
    );
    const result = extractUtmFields(params);
    expect(result).toEqual({
      utm_source: 'google',
      utm_medium: 'cpc',
      utm_campaign: 'trial',
    });
    expect(result).not.toHaveProperty('foo');
  });

  it('extracts utm fields from plain object', () => {
    const params = {
      utm_source: 'newsletter',
      utm_content: 'header-cta',
      other_param: 'ignored',
    };
    const result = extractUtmFields(params);
    expect(result).toEqual({
      utm_source: 'newsletter',
      utm_content: 'header-cta',
    });
    expect(result).not.toHaveProperty('other_param');
  });

  it('returns empty object when no utm fields present', () => {
    const params = new URLSearchParams('page=1&sort=asc');
    expect(extractUtmFields(params)).toEqual({});
  });

  it('returns empty object for empty plain object', () => {
    expect(extractUtmFields({})).toEqual({});
  });

  it('does not include keys with empty/falsy values from plain object', () => {
    const params = { utm_source: '', utm_medium: 'email' };
    const result = extractUtmFields(params);
    expect(result).toEqual({ utm_medium: 'email' });
  });
});
