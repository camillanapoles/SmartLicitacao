/**
 * Unit tests for scripts/seo/indexation-drift.js (Issue #998 / SEO-P2-012).
 * Run with: node --test scripts/seo/__tests__/
 */

'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { check, RATIO_DROP_PP, RATIO_FLOOR_PCT } = require('../indexation-drift');

test('check: emits info (not warn) when no indexed count is available', () => {
  const { findings } = check({ generated: 100, indexed: 0, history: [] });
  assert.equal(findings.length, 1);
  assert.equal(findings[0].level, 'info');
});

test('check: warns when ratio is below the absolute floor', () => {
  const { findings, ratio } = check({ generated: 100, indexed: 20, history: [] });
  assert.equal(Math.round(ratio), 20);
  assert.ok(findings.some((f) => f.level === 'warn' && /below floor/.test(f.msg)));
});

test('check: does not warn when ratio is at the floor', () => {
  const { findings } = check({ generated: 100, indexed: 30, history: [] });
  assert.equal(findings.filter((f) => f.level === 'warn').length, 0);
});

test('check: warns when current ratio dropped > RATIO_DROP_PP vs previous', () => {
  const history = [{ date: '2026-04-01', generated: 100, indexed: 80, ratio: 80 }];
  const { findings } = check({ generated: 100, indexed: 50, history });
  assert.ok(findings.some((f) => f.level === 'warn' && /dropped/.test(f.msg)));
});

test('check: does not warn for small dips below the drop threshold', () => {
  const history = [{ date: '2026-04-01', generated: 100, indexed: 80, ratio: 80 }];
  const { findings } = check({ generated: 100, indexed: 75, history });
  assert.equal(findings.filter((f) => /dropped/.test(f.msg)).length, 0);
});

test('check: handles zero generated without crashing', () => {
  const { ratio, findings } = check({ generated: 0, indexed: 50, history: [] });
  assert.equal(ratio, 0);
  // 0% < 30% floor → warn expected
  assert.ok(findings.some((f) => /below floor/.test(f.msg)));
});

test('thresholds: calibrated values exposed', () => {
  assert.equal(RATIO_DROP_PP, 10);
  assert.equal(RATIO_FLOOR_PCT, 30);
});
