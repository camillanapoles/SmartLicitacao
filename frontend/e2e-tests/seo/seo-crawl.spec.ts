/**
 * SEO-E2E-CRAWL-001 (Issue #1043) — Production sitemap crawl.
 *
 * No E2E test crawls sitemap URLs. 404 regressions (like
 * /observatorio/raio-x-marco-2026) only caught when Google de-indexes.
 *
 * Strategy:
 *   1. Fetch sitemap index, extract sub-sitemap URLs.
 *   2. Collect page URLs from the first 5 sub-sitemaps.
 *   3. Sample 50 page URLs at random.
 *   4. HEAD each sampled URL — fail if status >= 400.
 *
 * Runs against production (smartlic.tech) because sitemaps are only
 * meaningful on the production domain.
 */

import { test, expect } from '@playwright/test';

const PROD_URL = process.env.FRONTEND_URL ?? 'https://smartlic.tech';

/** Parse <loc> tags from any sitemap XML. */
function extractUrlsFromSitemap(xml: string): string[] {
  const urls: string[] = [];
  const regex = /<loc>([^<]+)<\/loc>/g;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(xml)) !== null) {
    urls.push(match[1]);
  }
  return urls;
}

/** Fisher-Yates shuffle (returns a new array). */
function shuffle<T>(array: T[]): T[] {
  const result = [...array];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

test.describe('SEO Sitemap Crawl', () => {
  test('fetch and validate sitemap URLs', async ({ request }) => {
    // Fetch main sitemap index
    const sitemapResp = await request.get(`${PROD_URL}/sitemap.xml`, { timeout: 15000 });
    expect(sitemapResp.status()).toBe(200);

    // Parse sitemap XML to get sub-sitemap URLs
    const sitemapText = await sitemapResp.text();
    const subSitemapUrls = extractUrlsFromSitemap(sitemapText);
    expect(subSitemapUrls.length).toBeGreaterThanOrEqual(5);

    // Collect all page URLs from the first 5 sub-sitemaps, tracking which sub-sitemap each came from
    const allEntries: { url: string; source: string }[] = [];
    for (const subSitemapUrl of subSitemapUrls.slice(0, 5)) {
      // eslint-disable-next-line no-await-in-loop
      const resp = await request.get(subSitemapUrl, { timeout: 15000 });
      expect(resp.status()).toBe(200);
      // eslint-disable-next-line no-await-in-loop
      const xml = await resp.text();
      for (const url of extractUrlsFromSitemap(xml)) {
        allEntries.push({ url, source: subSitemapUrl });
      }
    }

    // Sample 50 entries randomly
    const sampled = shuffle(allEntries).slice(0, 50);

    // HEAD each sampled URL — no body downloaded, fail if status >= 400.
    const failures: { url: string; status: number; source: string }[] = [];
    for (const { url, source } of sampled) {
      // eslint-disable-next-line no-await-in-loop
      const resp = await request.fetch(url, { method: 'HEAD', timeout: 30000 });
      if (resp.status() >= 400) {
        failures.push({ url, status: resp.status(), source });
      }
    }

    expect(
      failures,
      failures.length > 0
        ? `SEO crawl failed — ${failures.length}/${sampled.length} URLs returned >= 400:\n${failures
            .map((f) => `  ${f.status} ${f.url} (sub-sitemap: ${f.source})`)
            .join('\n')}`
        : undefined,
    ).toEqual([]);
  });
});
