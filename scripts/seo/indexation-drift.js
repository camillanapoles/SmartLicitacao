#!/usr/bin/env node
/**
 * SEO Gate (warn-only) — Indexed/generated drift alert (Issue #998 / SEO-P2-012)
 *
 * Compares the count of URLs the site *generates* (from the Next.js sitemap
 * registries) with the count of URLs Google has *indexed* (from a CSV export
 * or the GSC API), and warns when the ratio drops below thresholds.
 *
 * This gate is **non-blocking**. It writes findings to stdout and to the
 * GitHub Actions step summary, but never exits non-zero unless the script
 * itself can't run. Rationale:
 *   - GSC indexed counts arrive with 2–7 day latency, so a single bad day
 *     should not fail merges.
 *   - The GSC API requires `GSC_API_TOKEN` which is not always available in
 *     CI for forks and PRs from external contributors.
 *   - The authoritative weekly check already lives in
 *     `scripts/gsc/weekly-health-check.ts`.
 *
 * Sources:
 *   - Generated count: counts entries in BLOG_ARTICLES, QUESTIONS, AUTHORS,
 *     SECTORS, CITIES, GLOSSARY_TERMS via simple regex over the .ts files
 *     (avoids running a Next.js build).
 *   - Indexed count: read from `docs/seo/indexation-history.csv` (most recent
 *     row) OR from env `GSC_INDEXED_COUNT` (set by the workflow when API
 *     access is available).
 *
 * Thresholds (issue #998):
 *   - Drop in ratio (vs previous CSV row) > 10pp  → WARN
 *   - Absolute ratio < 30%                        → WARN
 *
 * Outputs:
 *   - stdout summary
 *   - JSON to stdout when `--json` flag is passed (consumed by workflow)
 *
 * Exit codes:
 *   0 = always (warn-only) unless --strict and a threshold tripped, or IO error
 */

'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const HISTORY_CSV = path.join(ROOT, 'docs', 'seo', 'indexation-history.csv');

const REGISTRY_FILES = [
  { file: 'frontend/lib/blog.ts', re: /slug:\s*['"][^'"\n]+['"]/g, label: 'blog' },
  { file: 'frontend/lib/questions.ts', re: /slug:\s*['"][^'"\n]+['"]/g, label: 'questions' },
  { file: 'frontend/lib/authors.ts', re: /slug:\s*['"][^'"\n]+['"]/g, label: 'authors' },
  { file: 'frontend/lib/cases.ts', re: /slug:\s*['"][^'"\n]+['"]/g, label: 'cases' },
  { file: 'frontend/lib/cities.ts', re: /slug:\s*['"][^'"\n]+['"]/g, label: 'cities' },
  { file: 'frontend/lib/glossary-terms.ts', re: /slug:\s*['"][^'"\n]+['"]/g, label: 'glossary' },
];

const RATIO_DROP_PP = 10;
const RATIO_FLOOR_PCT = 30;

function countMatches(file, re) {
  const full = path.join(ROOT, file);
  let src;
  try {
    src = fs.readFileSync(full, 'utf8');
  } catch {
    return 0;
  }
  const matches = src.match(re);
  return matches ? matches.length : 0;
}

function countGenerated() {
  const breakdown = {};
  let total = 0;
  for (const reg of REGISTRY_FILES) {
    const n = countMatches(reg.file, reg.re);
    breakdown[reg.label] = n;
    total += n;
  }
  return { total, breakdown };
}

function readHistory() {
  if (!fs.existsSync(HISTORY_CSV)) return [];
  const lines = fs.readFileSync(HISTORY_CSV, 'utf8').split('\n').filter(Boolean);
  if (lines.length === 0) return [];
  // Skip header
  return lines.slice(1).map((line) => {
    const [date, generated, indexed, ratio] = line.split(',');
    return {
      date: date && date.trim(),
      generated: Number(generated),
      indexed: Number(indexed),
      ratio: Number(ratio),
    };
  });
}

function appendHistory(row) {
  const header = 'date,generated,indexed,ratio_pct\n';
  const line = `${row.date},${row.generated},${row.indexed},${row.ratio.toFixed(2)}\n`;
  // Avoid TOCTOU race (CodeQL js/file-system-race): don't `existsSync` then act.
  // Use the file open flag 'ax' (exclusive create) for the first write; on
  // EEXIST fall through to append. mkdirSync(..., recursive: true) is itself
  // race-safe (no-op when dir already exists).
  fs.mkdirSync(path.dirname(HISTORY_CSV), { recursive: true });
  try {
    fs.writeFileSync(HISTORY_CSV, header + line, { flag: 'ax' });
  } catch (err) {
    if (err && err.code === 'EEXIST') {
      fs.appendFileSync(HISTORY_CSV, line);
    } else {
      throw err;
    }
  }
}

function check({ generated, indexed, history }) {
  const findings = [];
  const ratio = generated > 0 ? (indexed / generated) * 100 : 0;
  if (indexed === 0) {
    findings.push({ level: 'info', msg: 'no indexed-count provided (GSC_INDEXED_COUNT env / history CSV); skipping drift evaluation' });
    return { ratio, findings };
  }
  if (ratio < RATIO_FLOOR_PCT) {
    findings.push({
      level: 'warn',
      msg: `absolute ratio ${ratio.toFixed(1)}% is below floor ${RATIO_FLOOR_PCT}% (indexed=${indexed} / generated=${generated})`,
    });
  }
  if (history.length > 0) {
    const last = history[history.length - 1];
    if (Number.isFinite(last.ratio) && Number.isFinite(ratio)) {
      const drop = last.ratio - ratio;
      if (drop > RATIO_DROP_PP) {
        findings.push({
          level: 'warn',
          msg: `ratio dropped ${drop.toFixed(1)}pp vs previous (was ${last.ratio.toFixed(1)}% on ${last.date}, now ${ratio.toFixed(1)}%)`,
        });
      }
    }
  }
  return { ratio, findings };
}

function main() {
  const argv = process.argv.slice(2);
  const isJson = argv.includes('--json');
  const isStrict = argv.includes('--strict');
  const shouldAppend = argv.includes('--append');

  const { total: generated, breakdown } = countGenerated();
  const indexedFromEnv = Number(process.env.GSC_INDEXED_COUNT || 0);
  const history = readHistory();
  const indexed = indexedFromEnv > 0
    ? indexedFromEnv
    : (history.length > 0 ? history[history.length - 1].indexed : 0);

  const { ratio, findings } = check({ generated, indexed, history });

  const result = {
    date: new Date().toISOString().split('T')[0],
    generated,
    breakdown,
    indexed,
    ratio_pct: Number(ratio.toFixed(2)),
    findings,
    thresholds: { drop_pp: RATIO_DROP_PP, floor_pct: RATIO_FLOOR_PCT },
  };

  if (isJson) {
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  } else {
    process.stdout.write(`[indexation-drift] generated=${generated} indexed=${indexed} ratio=${ratio.toFixed(1)}%\n`);
    process.stdout.write(`  breakdown: ${JSON.stringify(breakdown)}\n`);
    for (const f of findings) {
      process.stdout.write(`  ${f.level.toUpperCase()}  ${f.msg}\n`);
    }
  }

  if (shouldAppend && indexed > 0) {
    appendHistory(result);
  }

  const hasWarn = findings.some((f) => f.level === 'warn');
  if (isStrict && hasWarn) {
    process.exit(1);
  }
  process.exit(0);
}

if (require.main === module) {
  main();
}

module.exports = { countGenerated, check, readHistory, RATIO_DROP_PP, RATIO_FLOOR_PCT };
