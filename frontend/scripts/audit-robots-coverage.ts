/**
 * SEO-PROG-007 AC6: Audit script — verify no public SEO programmatic URL
 * is blocked by `app/robots.ts` Disallow rules.
 *
 * Usage:
 *   npx tsx scripts/audit-robots-coverage.ts
 *   BACKEND_URL=https://api.smartlic.tech npx tsx scripts/audit-robots-coverage.ts
 *
 * Behavior:
 *   1. Force production-mode env so we exercise the real Disallow rules.
 *   2. Try to fetch sample public URLs from the backend sitemap endpoints;
 *      fall back to a hardcoded sample if backend is unreachable.
 *   3. Build robots.txt text from the route handler's default export and feed
 *      it to robots-parser.
 *   4. Check each public URL with `parser.isAllowed(url, 'Googlebot')`.
 *      Exit 1 on any block; print a (rule, count, samples) report.
 */

import robotsParser from 'robots-parser';

// Force production rules regardless of the host shell's env.
process.env.NEXT_PUBLIC_ENVIRONMENT = 'production';
process.env.NEXT_PUBLIC_CANONICAL_URL =
  process.env.NEXT_PUBLIC_CANONICAL_URL || 'https://smartlic.tech';

// eslint-disable-next-line @typescript-eslint/no-require-imports
const robotsModule = require('../app/robots');
const robots = robotsModule.default();

const CANONICAL =
  process.env.NEXT_PUBLIC_CANONICAL_URL || 'https://smartlic.tech';
const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  'http://localhost:8000';

const FALLBACK_SAMPLE: string[] = [
  '/alertas-publicos/ti/SP',
  '/alertas-publicos/saude/RJ',
  '/api/sitemap-1.xml',
  '/api/sitemap-2.xml',
  '/blog/programmatic/saude/RJ',
  '/cnpj/00000000000191',
  '/orgaos/some-slug',
  '/observatorio/raio-x-marco-2026',
  '/contratos/saude/SP',
  '/indice-municipal/sao-paulo-sp',
  '/licitacoes/saude',
];

function serialize(r: ReturnType<typeof robotsModule.default>): string {
  const lines: string[] = [];
  const rules = Array.isArray(r.rules) ? r.rules : [r.rules];
  for (const rule of rules) {
    const uaList = Array.isArray(rule.userAgent) ? rule.userAgent : [rule.userAgent];
    for (const ua of uaList) lines.push(`User-agent: ${ua}`);
    if (rule.allow) {
      const allows = Array.isArray(rule.allow) ? rule.allow : [rule.allow];
      for (const a of allows) lines.push(`Allow: ${a}`);
    }
    if (rule.disallow) {
      const disallows = Array.isArray(rule.disallow) ? rule.disallow : [rule.disallow];
      for (const d of disallows) lines.push(`Disallow: ${d}`);
    }
    lines.push('');
  }
  if (r.sitemap) {
    const sm = Array.isArray(r.sitemap) ? r.sitemap : [r.sitemap];
    for (const s of sm) lines.push(`Sitemap: ${s}`);
  }
  if (r.host) lines.push(`Host: ${r.host}`);
  return lines.join('\n');
}

async function fetchSampleFromBackend(): Promise<string[] | null> {
  const endpoints = [
    '/v1/sitemap/licitacoes-indexable',
    '/v1/sitemap/orgaos',
  ];
  const collected: string[] = [];
  for (const ep of endpoints) {
    try {
      const url = `${BACKEND_URL}${ep}`;
      const resp = await fetch(url, {
        signal: AbortSignal.timeout(8000),
      });
      if (!resp.ok) continue;
      const data = (await resp.json()) as unknown;
      // Best-effort extraction: support {urls: [...]}, [...] arrays of strings or {url}/{loc}.
      const items = Array.isArray(data)
        ? data
        : Array.isArray((data as { urls?: unknown[] })?.urls)
          ? (data as { urls: unknown[] }).urls
          : [];
      for (const item of items.slice(0, 25)) {
        if (typeof item === 'string') collected.push(item);
        else if (item && typeof item === 'object') {
          const u =
            (item as { url?: string; loc?: string; path?: string }).url ||
            (item as { url?: string; loc?: string; path?: string }).loc ||
            (item as { url?: string; loc?: string; path?: string }).path;
          if (u) collected.push(u);
        }
      }
    } catch {
      // Try next endpoint
    }
  }
  if (collected.length === 0) return null;
  // Strip absolute URLs to paths for parser consumption
  return collected.map((u) => {
    try {
      return new URL(u, CANONICAL).pathname + (new URL(u, CANONICAL).search || '');
    } catch {
      return u.startsWith('/') ? u : `/${u}`;
    }
  });
}

async function main() {
  const robotsTxt = serialize(robots);
  const parser = robotsParser(`${CANONICAL}/robots.txt`, robotsTxt);

  let sample = await fetchSampleFromBackend();
  let source = 'backend';
  if (!sample || sample.length === 0) {
    sample = FALLBACK_SAMPLE;
    source = 'fallback (backend unreachable)';
  }

  console.log(`# SEO-PROG-007 AC6 — robots.txt coverage audit`);
  console.log(`# canonical: ${CANONICAL}`);
  console.log(`# sample source: ${source} (n=${sample.length})`);
  console.log('');

  const blocked: { url: string }[] = [];
  for (const path of sample) {
    const url = `${CANONICAL}${path.startsWith('/') ? path : `/${path}`}`;
    const allowed = parser.isAllowed(url, 'Googlebot');
    if (!allowed) blocked.push({ url });
  }

  if (blocked.length === 0) {
    console.log(`OK: 0 / ${sample.length} sample URLs blocked by Disallow rules.`);
    console.log('');
    console.log('Sample (first 5):');
    for (const p of sample.slice(0, 5)) {
      console.log(`  allowed  ${p}`);
    }
    process.exit(0);
  }

  console.error(`FAIL: ${blocked.length} / ${sample.length} public URLs blocked.`);
  console.error('');
  console.error('Blocked URLs:');
  for (const b of blocked) console.error(`  blocked  ${b.url}`);
  console.error('');
  console.error('Robots.txt rendered:');
  console.error(robotsTxt);
  process.exit(1);
}

main().catch((err) => {
  console.error('audit-robots-coverage.ts crashed:', err);
  process.exit(2);
});
