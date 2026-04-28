/**
 * SEO-PROG-007 AC7 E2E: validate the live `/robots.txt` endpoint.
 *
 * Production case is always run; the preview-env case is skipped unless
 * PREVIEW_BASE_URL is configured (no preview pipeline today).
 */

import { test, expect } from '@playwright/test';
import robotsParser from 'robots-parser';

const PROD_URL = 'https://smartlic.tech';
const PREVIEW_URL = process.env.PREVIEW_BASE_URL || '';

test.describe('SEO-PROG-007 — robots.txt route handler', () => {
  test('production: GET /robots.txt returns 200 + text/plain + parseable rules', async ({
    request,
  }) => {
    const resp = await request.get(`${PROD_URL}/robots.txt`);
    expect(resp.status()).toBe(200);
    const ct = resp.headers()['content-type'] || '';
    expect(ct).toContain('text/plain');

    const body = await resp.text();
    expect(body).toContain('User-agent: *');
    expect(body).toMatch(/Sitemap:\s*https:\/\/smartlic\.tech\/sitemap(_index)?\.xml/);
    expect(body).toContain(`Host: ${PROD_URL}`);

    const parser = robotsParser(`${PROD_URL}/robots.txt`, body);

    // AC6: public SEO programmatic URLs must be allowed.
    expect(parser.isAllowed(`${PROD_URL}/alertas-publicos/ti/SP`, 'Googlebot')).toBe(true);
    expect(parser.isAllowed(`${PROD_URL}/api/sitemap-1.xml`, 'Googlebot')).toBe(true);
    expect(parser.isAllowed(`${PROD_URL}/blog/programmatic/saude/RJ`, 'Googlebot')).toBe(true);

    // Private routes must remain disallowed.
    expect(parser.isAllowed(`${PROD_URL}/admin/seo`, 'Googlebot')).toBe(false);
    expect(parser.isAllowed(`${PROD_URL}/dashboard/analytics`, 'Googlebot')).toBe(false);

    // Google-Extended must remain allowed (AI Overviews opt-in).
    expect(parser.isAllowed(`${PROD_URL}/`, 'Google-Extended')).toBe(true);

    // Non-Google AI crawlers must remain blocked.
    expect(parser.isAllowed(`${PROD_URL}/`, 'GPTBot')).toBe(false);
    expect(parser.isAllowed(`${PROD_URL}/`, 'CCBot')).toBe(false);
  });

  test('preview env: GET /robots.txt is block-all', async ({ request }) => {
    test.skip(!PREVIEW_URL, 'PREVIEW_BASE_URL not configured');
    const resp = await request.get(`${PREVIEW_URL}/robots.txt`);
    expect(resp.status()).toBe(200);
    const body = await resp.text();
    expect(body).toMatch(/User-agent:\s*\*/);
    expect(body).toMatch(/Disallow:\s*\//);
    // No sitemap declaration in preview.
    expect(body).not.toMatch(/Sitemap:/);
  });
});
