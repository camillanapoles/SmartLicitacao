/**
 * Unit tests for scripts/seo/jsonld-validate.js (Issue #998 / SEO-P2-012).
 * Run with: node --test scripts/seo/__tests__/
 */

'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { extractJsonLdLiterals, validateLd, REQUIRED_FIELDS } = require('../jsonld-validate');

test('extractJsonLdLiterals: extracts a literal object passed to JSON.stringify', () => {
  const src = `
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify({ "@context": "https://schema.org", "@type": "Article" }) }}
    />
  `;
  const literals = extractJsonLdLiterals(src);
  assert.equal(literals.length, 1);
  assert.match(literals[0].expr, /@context/);
  assert.match(literals[0].expr, /@type/);
});

test('extractJsonLdLiterals: handles multiple JSON-LD blocks in one file', () => {
  const src = `
    <script type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify({ "@type": "Article" }) }}
    />
    <script type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify({ "@type": "FAQPage" }) }}
    />
  `;
  const literals = extractJsonLdLiterals(src);
  assert.equal(literals.length, 2);
});

test('extractJsonLdLiterals: respects nested braces inside object literals', () => {
  const src = `
    <script type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify({
        "@type": "BreadcrumbList",
        itemListElement: [{ "@type": "ListItem", position: 1, name: "Home" }],
      }) }}
    />
  `;
  const literals = extractJsonLdLiterals(src);
  assert.equal(literals.length, 1);
  assert.match(literals[0].expr, /itemListElement/);
  const open = (literals[0].expr.match(/\{/g) || []).length;
  const close = (literals[0].expr.match(/\}/g) || []).length;
  assert.equal(open, close);
});

test('extractJsonLdLiterals: returns empty when no JSON-LD script tag is present', () => {
  assert.deepEqual(extractJsonLdLiterals('<div>no schema here</div>'), []);
});

test('validateLd: passes a fully-formed Article', () => {
  const obj = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: 'My Title',
    author: { '@type': 'Person', name: 'X' },
  };
  const findings = validateLd(obj, 'fake.tsx');
  assert.deepEqual(findings, []);
});

test('validateLd: flags missing @context as fail', () => {
  const findings = validateLd({ '@type': 'Article', headline: 'h', author: 'a' }, 'fake.tsx');
  assert.ok(findings.some((f) => f.level === 'fail' && /@context/.test(f.msg)));
});

test('validateLd: flags missing @type as fail', () => {
  const findings = validateLd({ '@context': 'https://schema.org' }, 'fake.tsx');
  assert.ok(findings.some((f) => f.level === 'fail' && /@type/.test(f.msg)));
});

test('validateLd: flags missing required fields per type', () => {
  const findings = validateLd(
    { '@context': 'https://schema.org', '@type': 'BlogPosting', headline: 'h' },
    'fake.tsx',
  );
  const fails = findings.filter((f) => f.level === 'fail');
  assert.ok(fails.some((f) => /author/.test(f.msg)));
  assert.ok(fails.some((f) => /datePublished/.test(f.msg)));
});

test('validateLd: warns on unknown @type (likely typo)', () => {
  const findings = validateLd(
    { '@context': 'https://schema.org', '@type': 'BlogPostingTypo' },
    'fake.tsx',
  );
  assert.ok(findings.some((f) => f.level === 'warn' && /unknown @type/.test(f.msg)));
});

test('validateLd: accepts @context as array containing schema.org', () => {
  const obj = {
    '@context': ['https://schema.org', { custom: 'http://example.com/ns#' }],
    '@type': 'Organization',
    name: 'CONFENGE',
  };
  const findings = validateLd(obj, 'fake.tsx');
  assert.deepEqual(findings, []);
});

test('validateLd: handles arrays of LD entities', () => {
  const arr = [
    { '@context': 'https://schema.org', '@type': 'Organization', name: 'A' },
    { '@context': 'https://schema.org', '@type': 'WebSite', url: 'https://x' },
  ];
  const findings = validateLd(arr, 'fake.tsx');
  assert.deepEqual(findings, []);
});

test('validateLd: flags parse errors as warnings (not blocking failures)', () => {
  const findings = validateLd({ __parseError: 'syntax error' }, 'fake.tsx');
  assert.equal(findings.length, 1);
  assert.equal(findings[0].level, 'warn');
});

test('REQUIRED_FIELDS: declares the canonical set of types', () => {
  assert.ok(REQUIRED_FIELDS.Article.includes('headline'));
  assert.ok(REQUIRED_FIELDS.BlogPosting.includes('datePublished'));
  assert.ok(REQUIRED_FIELDS.FAQPage.includes('mainEntity'));
  assert.ok(REQUIRED_FIELDS.BreadcrumbList.includes('itemListElement'));
});
