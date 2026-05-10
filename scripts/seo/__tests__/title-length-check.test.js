/**
 * Unit tests for scripts/seo/title-length-check.js (Issue #998 / SEO-P2-012).
 *
 * Run with: node --test scripts/seo/__tests__/
 *
 * No external test runner — uses node:test (Node ≥18) so the gate stays
 * dependency-free and matches how the workflow exercises the scripts.
 */

'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { extractEntries, check } = require('../title-length-check');

test('extractEntries: parses slug + title from object literals', () => {
  const src = `
    export const X = [
      { slug: 'foo', title: 'Foo Title', description: 'whatever' },
      { slug: "bar", title: "Bar Title" },
    ];
  `;
  const entries = extractEntries(src);
  assert.equal(entries.length, 2);
  assert.equal(entries[0].slug, 'foo');
  assert.equal(entries[0].title, 'Foo Title');
  assert.equal(entries[1].slug, 'bar');
});

test('extractEntries: captures metaDescription when present', () => {
  const src = `{ slug: 'q1', title: 'Q1', metaDescription: 'A descriptive answer.' }`;
  const entries = extractEntries(src);
  assert.equal(entries[0].metaDescription, 'A descriptive answer.');
});

test('extractEntries: returns null metaDescription when absent', () => {
  const src = `{ slug: 'q1', title: 'Q1' }`;
  const entries = extractEntries(src);
  assert.equal(entries[0].metaDescription, null);
});

test('check: flags titles exceeding the FAIL threshold', () => {
  const long = 'x'.repeat(75); // > 70
  const blogSrc = `{ slug: 'a', title: '${long}' }`;
  const { failures } = check({ blogSrc, questionsSrc: '' });
  assert.equal(failures.length, 1);
  assert.equal(failures[0].slug, 'a');
  assert.match(failures[0].reason, /FAIL=70/);
});

test('check: flags titles in the warn band (>60, ≤70) as warnings, not failures', () => {
  const med = 'x'.repeat(65);
  const blogSrc = `{ slug: 'a', title: '${med}' }`;
  const { failures, warnings } = check({ blogSrc, questionsSrc: '' });
  assert.equal(failures.length, 0);
  assert.ok(warnings.some((w) => w.slug === 'a' && /WARN=60/.test(w.reason)));
});

test('check: passes titles within the safe band', () => {
  const ok = 'x'.repeat(50);
  const blogSrc = `{ slug: 'a', title: '${ok}' }`;
  const { failures, warnings } = check({ blogSrc, questionsSrc: '' });
  assert.equal(failures.length, 0);
  assert.equal(warnings.filter((w) => /title length/.test(w.reason)).length, 0);
});

test('check: flags empty titles as failures', () => {
  const blogSrc = `{ slug: 'a', title: '   ' }`;
  const { failures } = check({ blogSrc, questionsSrc: '' });
  assert.equal(failures.length, 1);
  assert.equal(failures[0].reason, 'empty title');
});

test('check: flags literal "undefined" / "null" titles', () => {
  const blogSrc = `
    { slug: 'a', title: 'undefined' }
    { slug: 'b', title: 'null' }
  `;
  const { failures } = check({ blogSrc, questionsSrc: '' });
  assert.equal(failures.length, 2);
  assert.match(failures[0].reason, /literal/);
});

test('check: warns on long metaDescription in questions', () => {
  const longDesc = 'd'.repeat(180);
  const questionsSrc = `{ slug: 'q1', title: 'short', metaDescription: '${longDesc}' }`;
  const { warnings } = check({ blogSrc: '', questionsSrc });
  assert.ok(warnings.some((w) => /metaDescription/.test(w.reason)));
});

test('check: counts entries from both blog and questions sources', () => {
  const blogSrc = `{ slug: 'b1', title: 'okay' }`;
  const questionsSrc = `{ slug: 'q1', title: 'okay' }`;
  const { scanned } = check({ blogSrc, questionsSrc });
  assert.equal(scanned, 2);
});
