/**
 * SEO-PROG-007 AC7: Unit tests for `app/robots.ts` route handler.
 *
 * Covers:
 *  - Default production: full Allow/Disallow + Google-Extended + 7 AI blocks + sitemap_index + host
 *  - ENV=preview / ENV=staging: block-all (no sitemap, no host canonical mention)
 *  - SITEMAP_USE_INDEX_VARIANT toggle (legacy | index)
 *  - AC6 path-exact: /alertas-publicos/* allowed, /api/sitemap-* allowed, /admin/seo blocked
 */

import robotsParser from 'robots-parser';

const ROBOTS_MODULE_PATH = '@/app/robots';
const CANONICAL = 'https://smartlic.tech';

// Snapshot env vars touched by app/robots.ts so tests don't leak across files.
const TOUCHED_ENV_KEYS = [
  'NEXT_PUBLIC_ENVIRONMENT',
  'NEXT_PUBLIC_CANONICAL_URL',
  'SITEMAP_USE_INDEX_VARIANT',
];

let envSnapshot: Record<string, string | undefined>;

beforeEach(() => {
  envSnapshot = Object.fromEntries(
    TOUCHED_ENV_KEYS.map((k) => [k, process.env[k]]),
  );
  // Default to production-like state; individual tests override.
  for (const k of TOUCHED_ENV_KEYS) {
    delete process.env[k];
  }
  jest.resetModules();
});

afterEach(() => {
  for (const k of TOUCHED_ENV_KEYS) {
    if (envSnapshot[k] === undefined) {
      delete process.env[k];
    } else {
      process.env[k] = envSnapshot[k];
    }
  }
  jest.resetModules();
});

/**
 * Load app/robots.ts after env mutation and execute its default export.
 * Must reset modules first so the module-level env reads pick up the new values.
 */
function loadRobots() {
  jest.isolateModules(() => {
    // no-op: ensures clean module registry per call
  });
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mod = require(ROBOTS_MODULE_PATH);
  return mod.default();
}

/**
 * Serialize a MetadataRoute.Robots return value to robots.txt text.
 * Mirrors the format Next.js emits so we can feed it to robots-parser
 * for AC6 prefix-match assertions without depending on Next internals.
 */
function serialize(robots: ReturnType<typeof loadRobots>): string {
  const lines: string[] = [];
  const rules = Array.isArray(robots.rules) ? robots.rules : [robots.rules];
  for (const rule of rules) {
    const uaList = Array.isArray(rule.userAgent) ? rule.userAgent : [rule.userAgent];
    for (const ua of uaList) {
      lines.push(`User-agent: ${ua}`);
    }
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
  if (robots.sitemap) {
    const sm = Array.isArray(robots.sitemap) ? robots.sitemap : [robots.sitemap];
    for (const s of sm) lines.push(`Sitemap: ${s}`);
  }
  if (robots.host) {
    lines.push(`Host: ${robots.host}`);
  }
  return lines.join('\n');
}

describe('app/robots.ts — production defaults', () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_ENVIRONMENT = 'production';
  });

  it('returns 9 rule entries: 1 wildcard + Google-Extended + 7 AI blocks', () => {
    const r = loadRobots();
    expect(Array.isArray(r.rules)).toBe(true);
    expect(r.rules).toHaveLength(9);
  });

  it('declares sitemap_index URL by default (SITEMAP_USE_INDEX_VARIANT unset)', () => {
    const r = loadRobots();
    expect(r.sitemap).toBe(`${CANONICAL}/sitemap_index.xml`);
  });

  it('declares host canonical', () => {
    const r = loadRobots();
    expect(r.host).toBe(CANONICAL);
  });

  it('wildcard rule blocks all 16 PRIVATE_PATHS entries', () => {
    const r = loadRobots();
    const wildcard = r.rules.find((rl: { userAgent: string }) => rl.userAgent === '*');
    expect(wildcard).toBeDefined();
    expect(wildcard.allow).toBe('/');
    expect(Array.isArray(wildcard.disallow)).toBe(true);
    // 15 unique paths from AC6 list + /buscar raiz (deliberate addition; see code comment).
    expect(wildcard.disallow).toHaveLength(16);
    expect(wildcard.disallow).toEqual(
      expect.arrayContaining([
        '/admin/',
        '/auth/callback',
        '/api/auth/',
        '/api/admin/',
        '/api/csp-report',
        '/dashboard/',
        '/conta/',
        '/buscar',
        '/buscar/',
        '/pipeline/',
        '/historico/',
        '/mensagens/',
        '/alertas/',
        '/onboarding/',
        '/recuperar-senha',
        '/redefinir-senha',
      ]),
    );
  });

  it('Google-Extended is allow-all for AI Overviews eligibility', () => {
    const r = loadRobots();
    const ge = r.rules.find((rl: { userAgent: string }) => rl.userAgent === 'Google-Extended');
    expect(ge).toBeDefined();
    expect(ge.allow).toBe('/');
    expect(ge.disallow).toBeUndefined();
  });

  it('blocks 7 AI crawlers entirely', () => {
    const r = loadRobots();
    const aiBlocks = [
      'Amazonbot',
      'Applebot-Extended',
      'Bytespider',
      'CCBot',
      'ClaudeBot',
      'GPTBot',
      'meta-externalagent',
    ];
    for (const ua of aiBlocks) {
      const rl = r.rules.find((x: { userAgent: string }) => x.userAgent === ua);
      expect(rl).toBeDefined();
      expect(rl.disallow).toBe('/');
    }
  });
});

describe('app/robots.ts — non-production envs (AC2)', () => {
  for (const env of ['preview', 'staging', 'development']) {
    it(`ENV=${env}: returns block-all and no sitemap`, () => {
      process.env.NEXT_PUBLIC_ENVIRONMENT = env;
      const r = loadRobots();
      expect(r.rules).toEqual([{ userAgent: '*', disallow: '/' }]);
      expect(r.sitemap).toBeUndefined();
      // host is still declared so non-prod deploys announce their canonical
      expect(r.host).toBe(CANONICAL);
    });
  }
});

describe('app/robots.ts — SITEMAP_USE_INDEX_VARIANT flag (AC3)', () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_ENVIRONMENT = 'production';
  });

  it("variant=legacy points to /sitemap.xml", () => {
    process.env.SITEMAP_USE_INDEX_VARIANT = 'legacy';
    const r = loadRobots();
    expect(r.sitemap).toBe(`${CANONICAL}/sitemap.xml`);
  });

  it("variant=index points to /sitemap_index.xml", () => {
    process.env.SITEMAP_USE_INDEX_VARIANT = 'index';
    const r = loadRobots();
    expect(r.sitemap).toBe(`${CANONICAL}/sitemap_index.xml`);
  });

  it('unset (default) points to /sitemap_index.xml', () => {
    const r = loadRobots();
    expect(r.sitemap).toBe(`${CANONICAL}/sitemap_index.xml`);
  });
});

describe('app/robots.ts — AC6 path-exact prefix-match audit', () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_ENVIRONMENT = 'production';
  });

  function getParser() {
    const r = loadRobots();
    return robotsParser(`${CANONICAL}/robots.txt`, serialize(r));
  }

  it.each([
    ['/alertas-publicos/ti/SP', true],
    ['/alertas-publicos/saude/RJ', true],
    ['/api/sitemap-1.xml', true],
    ['/api/sitemap-2.xml', true],
    ['/blog/programmatic/saude/RJ', true],
    ['/cnpj/00000000000191', true],
    ['/observatorio/raio-x-marco-2026', true],
    ['/orgaos/some-slug', true],
    ['/contratos/saude/SP', true],
    ['/indice-municipal/sao-paulo-sp', true],
  ])('public SEO URL %s is allowed for Googlebot', (path, expected) => {
    const parser = getParser();
    expect(parser.isAllowed(`${CANONICAL}${path}`, 'Googlebot')).toBe(expected);
  });

  it.each([
    '/admin/seo',
    '/admin/users',
    '/dashboard/analytics',
    '/conta/billing',
    '/pipeline/kanban',
    '/historico/2026',
    '/api/auth/login',
    '/api/admin/users',
    '/buscar',
    '/buscar/historico',
    '/onboarding/welcome',
    '/auth/callback',
    '/recuperar-senha',
    '/redefinir-senha',
    '/api/csp-report',
    '/alertas/notify',
  ])('private path %s is disallowed for Googlebot', (path) => {
    const parser = getParser();
    expect(parser.isAllowed(`${CANONICAL}${path}`, 'Googlebot')).toBe(false);
  });

  it('Googlebot: /alertas-publicos/* is NOT caught by /alertas/ rule (regression guard)', () => {
    const parser = getParser();
    expect(parser.isAllowed(`${CANONICAL}/alertas-publicos/`, 'Googlebot')).toBe(true);
    expect(parser.isAllowed(`${CANONICAL}/alertas-publicos/ti/SP`, 'Googlebot')).toBe(true);
  });

  it('Googlebot: /api/sitemap-1.xml is NOT caught by /api/auth/ or /api/admin/ rules', () => {
    const parser = getParser();
    expect(parser.isAllowed(`${CANONICAL}/api/sitemap-1.xml`, 'Googlebot')).toBe(true);
  });
});
