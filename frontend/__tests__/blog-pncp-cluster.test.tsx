/**
 * SEO-P1-005 (#992) — PNCP Cluster smoke tests
 *
 * Validates:
 * - 8 spoke articles are registered in lib/blog.ts with pillarSlug set
 * - Each spoke renders without error (smoke test)
 * - Each spoke contains valid FAQPage JSON-LD with ≥3 questions
 * - The pillar (pncp-guia-completo-empresas) links to ≥8 spokes
 *   ("Aprenda mais sobre PNCP" section, AC of issue #992)
 * - Schema.org Article injects isPartOf for spokes via BlogArticleLayout
 *   (validated indirectly: BLOG_ARTICLES has pillarSlug field on spokes)
 */

import React from 'react';
import { render } from '@testing-library/react';

// ---------- Mock setup ----------

jest.mock('next/link', () => {
  return ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
});

// ---------- Imports ----------

import { BLOG_ARTICLES, getArticleBySlug } from '../lib/blog';

// ---------- Constants ----------

const PILLAR_SLUG = 'pncp-guia-completo-empresas';

const SPOKE_SLUGS = [
  'pncp-modalidade-pregao-eletronico',
  'pncp-timeline-publicacao-edital',
  'pncp-vs-comprasgov-diferencas',
  'pncp-consulta-contratos-passo-a-passo',
  'pncp-dispensa-licitacao-quando-aplicar',
  'pncp-registro-precos-como-participar',
  'pncp-api-integracao-empresas',
  'pncp-erros-comuns-empresas-iniciantes',
];

// ---------- Registry ----------

describe('SEO-P1-005 PNCP cluster — registry', () => {
  it('pillar exists and is a Guias article', () => {
    const pillar = getArticleBySlug(PILLAR_SLUG);
    expect(pillar).toBeDefined();
    expect(pillar?.category).toBe('Guias');
  });

  it.each(SPOKE_SLUGS)('spoke "%s" is registered', (slug) => {
    expect(getArticleBySlug(slug)).toBeDefined();
  });

  it.each(SPOKE_SLUGS)(
    'spoke "%s" has pillarSlug pointing to the pillar',
    (slug) => {
      const article = getArticleBySlug(slug)!;
      expect(article.pillarSlug).toBe(PILLAR_SLUG);
    },
  );

  it.each(SPOKE_SLUGS)(
    'spoke "%s" wordCount ≥ 800 (issue #992 AC)',
    (slug) => {
      const article = getArticleBySlug(slug)!;
      expect(article.wordCount).toBeGreaterThanOrEqual(800);
    },
  );

  it.each(SPOKE_SLUGS)(
    'spoke "%s" relatedSlugs includes pillar + ≥2 sibling spokes',
    (slug) => {
      const article = getArticleBySlug(slug)!;
      expect(article.relatedSlugs).toContain(PILLAR_SLUG);
      expect(article.relatedSlugs.length).toBeGreaterThanOrEqual(3);
    },
  );

  it('cluster has exactly 8 spokes (Phase 1)', () => {
    const spokesInRegistry = BLOG_ARTICLES.filter(
      (a) => a.pillarSlug === PILLAR_SLUG,
    );
    expect(spokesInRegistry.length).toBe(8);
  });
});

// ---------- Render smoke + FAQ schema ----------

describe('SEO-P1-005 PNCP cluster — render + FAQ schema', () => {
  it.each(SPOKE_SLUGS)('spoke "%s" renders without error', async (slug) => {
    const module = await import(`../app/blog/content/${slug}`);
    const Component = module.default;
    expect(Component).toBeDefined();

    const { container } = render(<Component />);
    expect(container.innerHTML.length).toBeGreaterThan(500);
  });

  it.each(SPOKE_SLUGS)(
    'spoke "%s" emits FAQPage JSON-LD with ≥3 questions',
    async (slug) => {
      const module = await import(`../app/blog/content/${slug}`);
      const Component = module.default;
      const { container } = render(<Component />);

      const scripts = container.querySelectorAll(
        'script[type="application/ld+json"]',
      );
      expect(scripts.length).toBeGreaterThanOrEqual(1);

      let faq: Record<string, unknown> | undefined;
      scripts.forEach((script) => {
        try {
          const parsed = JSON.parse(script.textContent || '{}');
          if (parsed['@type'] === 'FAQPage') {
            faq = parsed;
          }
        } catch {
          // skip
        }
      });

      expect(faq).toBeDefined();
      const mainEntity = faq!.mainEntity as Array<Record<string, unknown>>;
      expect(Array.isArray(mainEntity)).toBe(true);
      expect(mainEntity.length).toBeGreaterThanOrEqual(3);
    },
  );

  it.each(SPOKE_SLUGS)(
    'spoke "%s" includes "Guia Completo do PNCP" inbound link to pillar',
    async (slug) => {
      const module = await import(`../app/blog/content/${slug}`);
      const Component = module.default;
      const { container } = render(<Component />);

      const links = Array.from(
        container.querySelectorAll(`a[href="/blog/${PILLAR_SLUG}"]`),
      );
      expect(links.length).toBeGreaterThanOrEqual(2);
    },
  );
});

// ---------- Pillar smoke (issue AC: ≥8 outbound spoke links) ----------
//
// The pillar (PncpGuiaCompletoEmpresas) embeds an async server component
// (PncpHubPanel) and cannot be rendered with @testing-library/react. We
// validate the spoke-link AC by static source inspection instead.

describe('SEO-P1-005 PNCP cluster — pillar links to spokes (smoke-test AC)', () => {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const fs = require('fs') as typeof import('fs');
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const path = require('path') as typeof import('path');
  const pillarSource = fs.readFileSync(
    path.join(__dirname, '..', 'app', 'blog', 'content', `${PILLAR_SLUG}.tsx`),
    'utf-8',
  );

  it('pillar source contains ≥8 outbound /blog/pncp- links', () => {
    // Issue AC smoke: grep -c "/blog/pncp-" pillar source ≥ 8
    const matches = pillarSource.match(/\/blog\/pncp-/g) || [];
    expect(matches.length).toBeGreaterThanOrEqual(8);
  });

  it.each(SPOKE_SLUGS)('pillar source links to spoke "%s"', (spokeSlug) => {
    expect(pillarSource).toContain(`/blog/${spokeSlug}`);
  });
});
