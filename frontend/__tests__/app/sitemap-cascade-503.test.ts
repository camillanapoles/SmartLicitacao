/**
 * @jest-environment node
 *
 * SEO-SITEMAP-CASCADE-001: Regression tests for 503-aware retry logic.
 *
 * Root cause: backend returned 200+[] on DB timeout → frontend treated as
 * legitimate empty → ISR cached empty sitemap for 1h → Google GSC error.
 *
 * Fix: backend now raises 503 on timeout; frontend retries 503 with exponential
 * backoff (up to 3×) and THROWS on exhaustion so ISR preserves last known-good.
 *
 * Tests:
 *  - 503 → retry 3× → throw (ISR stale-while-revalidate kicks in)
 *  - 200+[] → return [] immediately (legitimate empty, no retry)
 *  - 503 × 2 then 200+data → eventual success after backoff
 *  - non-503 http_error → return null (callers default to [])
 */

// Mock fetch globally
global.fetch = jest.fn();
// Disable real setTimeout delays in tests
jest.useFakeTimers();

process.env.BACKEND_URL = 'http://mock-backend';
process.env.NEXT_PUBLIC_CANONICAL_URL = 'https://smartlic.tech';

// Helper: fresh module import with all filesystem deps mocked
async function importFreshFetchHelper() {
  jest.resetModules();
  jest.mock('@/lib/blog', () => ({ getAllSlugs: () => [], getArticleBySlug: () => null }));
  jest.mock('@/lib/sectors', () => ({ SECTORS: [] }));
  jest.mock('@/lib/programmatic', () => ({
    generateSectorParams: () => [],
    generateLicitacoesParams: () => [],
    generateSectorUfParams: () => [],
    backendIdToFrontendSlug: (s: string) => s,
  }));
  jest.mock('@/lib/cases', () => ({ getAllCaseSlugs: () => [] }));
  jest.mock('@/lib/cities', () => ({ CITIES: [] }));
  jest.mock('@/lib/glossary-terms', () => ({ GLOSSARY_TERMS: [] }));
  jest.mock('@/lib/authors', () => ({ getAllAuthorSlugs: () => [] }));
  jest.mock('@/lib/questions', () => ({ getAllQuestionSlugs: () => [] }));
  jest.mock('@/lib/masterclasses', () => ({ getAllMasterclassTemas: () => [] }));
  jest.mock('@/lib/seo/noindex', () => ({ filterNoindexedSitemap: (urls: unknown[]) => urls }));

  const mod = await import('../../app/sitemap');
  return mod.default;
}

function make503Response() {
  return Promise.resolve({ ok: false, status: 503, json: () => Promise.resolve({ detail: 'sitemap_source_timeout' }) } as Response);
}

function make200Response(payload: object) {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(payload) } as Response);
}

function make404Response() {
  return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) } as Response);
}

function makeHealthLiveOk() {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ ok: true }) } as Response);
}

describe('fetchSitemapJsonWithRetry — 503 cascade fix (SEO-SITEMAP-CASCADE-001)', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockReset();
    jest.clearAllTimers();
  });

  afterEach(() => {
    jest.runAllTimers();
  });

  it('503 exhausted after 3 attempts throws error (ISR preserves stale sitemap)', async () => {
    // Import module BEFORE activating fake timers to avoid dynamic import freeze
    const sitemap = await importFreshFetchHelper();

    // Now set up fetch mock and start the sitemap call
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/health/live')) return makeHealthLiveOk();
      return make503Response();
    });

    // The id:4 sitemap fetches cnpjs first; after 3×503 it should throw
    const sitemapPromise = sitemap({ id: Promise.resolve('4') });

    // Register the rejection handler BEFORE advancing timers to avoid unhandled rejection.
    // If the handler is registered after runAllTimersAsync(), the promise may already have
    // rejected by the time the .rejects assertion is attached, causing an UnhandledRejection.
    const assertion = expect(sitemapPromise).rejects.toThrow('sitemap_cnpjs_503_exhausted');

    // Advance timers for exponential backoff: 1s + 2s between retries
    await jest.runAllTimersAsync();

    await assertion;
  });

  it('200+[] returns empty array immediately without retry', async () => {
    // Backend returns 200 with empty cnpjs — legitimate (no data yet)
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/health/live')) return makeHealthLiveOk();
      if (url.includes('/v1/sitemap/cnpjs')) return make200Response({ cnpjs: [], total: 0 });
      if (url.includes('/v1/sitemap/contratos-orgao-indexable')) return make200Response({ orgaos: [] });
      if (url.includes('/v1/sitemap/orgaos')) return make200Response({ orgaos: [] });
      if (url.includes('/v1/sitemap/fornecedores-cnpj')) return make200Response({ cnpjs: [] });
      if (url.includes('/v1/sitemap/municipios')) return make200Response({ slugs: [] });
      if (url.includes('/v1/sitemap/itens')) return make200Response({ catmats: [] });
      return make200Response({});
    });

    const sitemap = await importFreshFetchHelper();
    jest.runAllTimers();

    const result = await sitemap({ id: Promise.resolve('4') });
    // Result is an empty sitemap array (no URLs) — not an error
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(0);

    // Verify fetch was called exactly once per endpoint (no retry)
    const cnpjsCalls = (global.fetch as jest.Mock).mock.calls.filter(([url]: [string]) =>
      url.includes('/v1/sitemap/cnpjs'),
    );
    expect(cnpjsCalls).toHaveLength(1);
  });

  it('503 then 200+data → eventual success after backoff', async () => {
    // Import module BEFORE activating fake timers to avoid dynamic import freeze
    const sitemap = await importFreshFetchHelper();

    let cnpjsCallCount = 0;
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/health/live')) return makeHealthLiveOk();
      if (url.includes('/v1/sitemap/cnpjs')) {
        cnpjsCallCount++;
        if (cnpjsCallCount === 1) return make503Response();
        return make200Response({ cnpjs: ['11111111000100'], total: 1 });
      }
      if (url.includes('/v1/sitemap/contratos-orgao-indexable')) return make200Response({ orgaos: [] });
      if (url.includes('/v1/sitemap/orgaos')) return make200Response({ orgaos: [] });
      if (url.includes('/v1/sitemap/fornecedores-cnpj')) return make200Response({ cnpjs: [] });
      if (url.includes('/v1/sitemap/municipios')) return make200Response({ slugs: [] });
      if (url.includes('/v1/sitemap/itens')) return make200Response({ catmats: [] });
      return make200Response({});
    });

    const sitemapPromise = sitemap({ id: Promise.resolve('4') });
    await jest.runAllTimersAsync();

    const result = await sitemapPromise;
    // Should succeed with the CNPJ data from second attempt
    expect(Array.isArray(result)).toBe(true);
    const cnpjUrls = result.filter((entry: { url: string }) => entry.url.includes('/cnpj/'));
    expect(cnpjUrls).toHaveLength(1);
    expect(cnpjUrls[0].url).toContain('11111111000100');
  });

  it('non-503 http error (404) returns null — callers default to empty array', async () => {
    // id:2 uses licitacoes-indexable; test that 404 → empty array (not throw)
    (global.fetch as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/v1/sitemap/licitacoes-indexable')) return make404Response();
      return make200Response({});
    });

    const sitemap = await importFreshFetchHelper();
    jest.runAllTimers();

    // id:2 should return [] (not throw) when endpoint returns 404
    const result = await sitemap({ id: Promise.resolve('2') });
    expect(Array.isArray(result)).toBe(true);
    // No routes generated when licitacoes-indexable is unavailable
  });
});
