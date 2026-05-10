#!/usr/bin/env node
/**
 * SEO Gate — Title length check (Issue #998 / SEO-P2-012)
 *
 * Scans the source registries that drive on-page <title> for blog posts and
 * Q&A pages, and fails when any title exceeds the configured maximum length.
 *
 * Why source-scan and not a rendered build?
 *   The full Next.js production build (4k+ programmatic pages) consistently
 *   OOMs in WSL/CI runners and takes 6–8 minutes; lighthouse.yml documents
 *   the same trade-off. Scanning the registries gives a deterministic gate
 *   that catches the >95% of titles authored in `frontend/lib/*.ts`. Page
 *   metadata defined inside `generateMetadata` for dynamic routes is *not*
 *   covered here — call that out in PR review when adding such routes.
 *
 * Sources scanned:
 *   - frontend/lib/blog.ts        → BLOG_ARTICLES[].title
 *   - frontend/lib/questions.ts   → QUESTIONS[].title  (and metaDescription)
 *
 * Limits (per issue #998 ACs):
 *   - title: warn when length > WARN_THRESHOLD (default 60)
 *           fail when length > FAIL_THRESHOLD (default 70)
 *   - metaDescription (questions only): warn-only when >170 chars
 *
 * Calibration note: `>60 = fail` would block 61 existing titles on main as
 * of 2026-05-10; `>70 = fail` would still block 26. Gate ships in REPORT
 * mode by default (always exits 0; logs WARN/FAIL annotations) so the
 * existing baseline is surfaced without freezing main. ENFORCE mode
 * (`SEO_TITLE_ENFORCE=1`) exits 1 on any FAIL — flip the switch after the
 * existing titles are rewritten (separate ticket tracked by the WARN log).
 *
 * Thresholds and mode are env-overridable:
 *   - SEO_TITLE_WARN     (default 60)
 *   - SEO_TITLE_FAIL     (default 70)
 *   - SEO_TITLE_ENFORCE  (default 0)
 *
 * Exit codes:
 *   0 = OK or in report mode
 *   1 = ENFORCE mode and at least one title > FAIL_THRESHOLD
 *   2 = bad invocation / unable to read source files
 */

'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const BLOG_FILE = path.join(ROOT, 'frontend', 'lib', 'blog.ts');
const QUESTIONS_FILE = path.join(ROOT, 'frontend', 'lib', 'questions.ts');

const WARN_THRESHOLD = Number(process.env.SEO_TITLE_WARN || 60);
const FAIL_THRESHOLD = Number(process.env.SEO_TITLE_FAIL || 70);
const DESC_WARN = Number(process.env.SEO_DESC_WARN || 170);
const ENFORCE = process.env.SEO_TITLE_ENFORCE === '1';

/**
 * Extract `{ slug, title, metaDescription? }` triples from a TS source file.
 *
 * The registries are plain object literals; we use a tolerant regex that
 * finds each `slug: '...'` and pairs it with the nearest `title: '...'`
 * (and optional `metaDescription`) within a 4 KB lookahead window. This
 * keeps the scan dependency-free (no TS parser).
 */
function extractEntries(source) {
  const entries = [];
  // Match `slug: 'value'` or `slug: "value"`
  const slugRe = /slug:\s*['"]([^'"\n]+)['"]/g;
  let match;
  while ((match = slugRe.exec(source)) !== null) {
    const slug = match[1];
    const window = source.slice(match.index, match.index + 4096);
    const titleMatch = window.match(/title:\s*['"]([^'"\n]+)['"]/);
    const descMatch = window.match(/metaDescription:\s*['"]([^'"\n]+)['"]/);
    if (titleMatch) {
      entries.push({
        slug,
        title: titleMatch[1],
        metaDescription: descMatch ? descMatch[1] : null,
      });
    }
  }
  return entries;
}

function readFileOrExit(file) {
  try {
    return fs.readFileSync(file, 'utf8');
  } catch (err) {
    process.stderr.write(`[title-length-check] cannot read ${file}: ${err.message}\n`);
    process.exit(2);
  }
}

function check({ blogSrc, questionsSrc }) {
  const failures = [];
  const warnings = [];

  const blog = extractEntries(blogSrc).map((e) => ({ ...e, source: 'blog' }));
  const questions = extractEntries(questionsSrc).map((e) => ({ ...e, source: 'questions' }));

  for (const entry of [...blog, ...questions]) {
    const t = (entry.title || '').trim();
    if (!t) {
      failures.push({ ...entry, reason: 'empty title' });
      continue;
    }
    if (t === 'undefined' || t === 'null') {
      failures.push({ ...entry, reason: `literal "${t}" string` });
      continue;
    }
    if (t.length > FAIL_THRESHOLD) {
      failures.push({ ...entry, reason: `title length ${t.length} > FAIL=${FAIL_THRESHOLD}` });
    } else if (t.length > WARN_THRESHOLD) {
      warnings.push({ ...entry, reason: `title length ${t.length} > WARN=${WARN_THRESHOLD}` });
    }
    if (entry.metaDescription && entry.metaDescription.length > DESC_WARN) {
      warnings.push({
        ...entry,
        reason: `metaDescription length ${entry.metaDescription.length} > ${DESC_WARN}`,
      });
    }
  }

  return { failures, warnings, scanned: blog.length + questions.length };
}

function main() {
  const blogSrc = readFileOrExit(BLOG_FILE);
  const questionsSrc = readFileOrExit(QUESTIONS_FILE);

  const { failures, warnings, scanned } = check({ blogSrc, questionsSrc });

  process.stdout.write(`[title-length-check] scanned=${scanned} warn=${WARN_THRESHOLD} fail=${FAIL_THRESHOLD}\n`);
  for (const w of warnings) {
    process.stdout.write(`  WARN  [${w.source}] ${w.slug}: ${w.reason}\n`);
  }
  for (const f of failures) {
    process.stdout.write(`  FAIL  [${f.source}] ${f.slug}: ${f.reason} | "${f.title}"\n`);
  }

  process.stdout.write(`[title-length-check] summary: warn=${warnings.length} fail=${failures.length} enforce=${ENFORCE ? 'on' : 'off'}\n`);
  if (failures.length > 0 && ENFORCE) {
    process.stdout.write(`[title-length-check] FAILED (enforce mode) with ${failures.length} violation(s)\n`);
    process.exit(1);
  }
  if (failures.length > 0) {
    process.stdout.write('[title-length-check] report mode: violations logged but not blocking\n');
  } else {
    process.stdout.write('[title-length-check] OK\n');
  }
  process.exit(0);
}

if (require.main === module) {
  main();
}

module.exports = { extractEntries, check, WARN_THRESHOLD, FAIL_THRESHOLD, DESC_WARN };
