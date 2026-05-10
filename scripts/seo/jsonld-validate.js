#!/usr/bin/env node
/**
 * SEO Gate — JSON-LD validate (Issue #998 / SEO-P2-012)
 *
 * Scans every file under `frontend/components/seo/` and `frontend/app/` for
 * `<script type="application/ld+json">` blocks, extracts the JS expression
 * passed to `dangerouslySetInnerHTML.__html` (typically `JSON.stringify(obj)`),
 * and validates the structured object against a minimal schema.org schema.
 *
 * The validator is intentionally lightweight (no AJV, no schema-dts) because:
 *   1. Adding deps to `frontend/package.json` is out of scope for #998 (touches
 *      the lockfile / dependabot territory).
 *   2. The Google Rich Results Test (`scripts/gsc/rich-results-test.ts`) is the
 *      authoritative schema validator and runs on the deployed site.
 *   3. This gate catches the >90% breakage class — typos in `@type`, missing
 *      `@context`, missing required fields per type — at PR time.
 *
 * Approach:
 *   - Find each `JSON.stringify({ ... })` literal inside a JSON-LD `<script>`.
 *   - Best-effort parse via `Function('"use strict"; return (' + expr + ')')`
 *     in a sandbox-light context (only `process.env.NEXT_PUBLIC_SITE_URL`
 *     and a small set of identifiers are inlined). If parse fails, we still
 *     report a structural finding.
 *   - Validate `@context` is `https://schema.org` (string or array containing).
 *   - Validate `@type` is present and is a known schema.org type.
 *   - Validate per-type required fields (Article, BreadcrumbList, FAQPage,
 *     Organization, Person, WebSite, WebPage, BlogPosting, Product, Service).
 *
 * Exit codes:
 *   0 = OK
 *   1 = at least one schema violation
 *   2 = unable to scan (IO error)
 */

'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const FRONTEND = path.join(ROOT, 'frontend');
const SCAN_ROOTS = [
  path.join(FRONTEND, 'components', 'seo'),
  path.join(FRONTEND, 'components', 'blog'),
  path.join(FRONTEND, 'app'),
];

// Required fields per JSON-LD @type. Conservative — only what Google's Rich
// Results docs flag as REQUIRED, not RECOMMENDED.
const REQUIRED_FIELDS = {
  Article: ['headline', 'author'],
  BlogPosting: ['headline', 'author', 'datePublished'],
  BreadcrumbList: ['itemListElement'],
  FAQPage: ['mainEntity'],
  Organization: ['name'],
  Person: ['name'],
  WebSite: ['url'],
  WebPage: ['name'],
  Product: ['name'],
  Service: ['name'],
  HowTo: ['name', 'step'],
  Event: ['name', 'startDate', 'location'],
  ItemList: ['itemListElement'],
};

const KNOWN_TYPES = new Set([
  ...Object.keys(REQUIRED_FIELDS),
  'CollectionPage',
  'AboutPage',
  'ContactPage',
  'SearchAction',
  'ListItem',
  'Question',
  'Answer',
  'PostalAddress',
  'ImageObject',
  'VideoObject',
  'OfferCatalog',
  'Offer',
  'AggregateRating',
  'Review',
]);

function walk(dir, out = []) {
  let stat;
  try {
    stat = fs.statSync(dir);
  } catch {
    return out;
  }
  if (!stat.isDirectory()) return out;
  for (const entry of fs.readdirSync(dir)) {
    const full = path.join(dir, entry);
    const s = fs.statSync(full);
    if (s.isDirectory()) {
      // Skip node_modules / .next / build artifacts.
      if (entry === 'node_modules' || entry.startsWith('.')) continue;
      walk(full, out);
    } else if (/\.(tsx?|jsx?)$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

/**
 * Extract object literals passed to JSON.stringify(...) inside JSON-LD scripts.
 * Uses brace-matching (not regex) to handle nested braces correctly.
 */
function extractJsonLdLiterals(source) {
  const literals = [];
  // Find each occurrence of `application/ld+json`.
  const tagRe = /type=['"]application\/ld\+json['"]/g;
  let m;
  while ((m = tagRe.exec(source)) !== null) {
    // Look ahead up to 4 KB for `JSON.stringify(`
    const window = source.slice(m.index, m.index + 4096);
    const stringifyIdx = window.indexOf('JSON.stringify(');
    if (stringifyIdx < 0) continue;
    const startAbs = m.index + stringifyIdx + 'JSON.stringify('.length;
    // Brace-match starting from first `{` after the call.
    let cursor = startAbs;
    while (cursor < source.length && source[cursor] !== '{' && source[cursor] !== '[') {
      // Allow whitespace / comments / variable references; bail on closing paren.
      if (source[cursor] === ')') break;
      cursor++;
    }
    if (source[cursor] !== '{' && source[cursor] !== '[') continue;
    const open = source[cursor];
    const close = open === '{' ? '}' : ']';
    let depth = 0;
    let inString = false;
    let stringChar = '';
    let inTemplate = false;
    let endAbs = cursor;
    for (let i = cursor; i < source.length; i++) {
      const ch = source[i];
      const prev = source[i - 1];
      if (inTemplate) {
        if (ch === '`' && prev !== '\\') inTemplate = false;
        continue;
      }
      if (inString) {
        if (ch === stringChar && prev !== '\\') inString = false;
        continue;
      }
      if (ch === '`') { inTemplate = true; continue; }
      if (ch === '"' || ch === "'") { inString = true; stringChar = ch; continue; }
      if (ch === open) depth++;
      else if (ch === close) {
        depth--;
        if (depth === 0) { endAbs = i + 1; break; }
      }
    }
    const expr = source.slice(cursor, endAbs);
    literals.push({ index: m.index, expr });
  }
  return literals;
}

/**
 * Best-effort eval of an object expression. Returns `null` if unsafe / fails.
 * We do NOT want to execute arbitrary code from the codebase — but these
 * literals are object expressions with simple variable refs (props from the
 * surrounding component). We treat unresolved identifiers as opaque strings
 * by replacing them before evaluation.
 */
function tryEvaluate(expr) {
  // Replace TS-specific syntax that breaks plain JS eval.
  let cleaned = expr
    // Remove `as const` / `as Type` casts.
    .replace(/\s+as\s+(?:const\b|[A-Za-z_$][\w$.<>[\]|&,\s]*)/g, '')
    // Remove non-null assertions.
    .replace(/!(?=[.,)\]}\s])/g, '');
  // Replace bare identifiers used as values (e.g. `name: article.title`)
  // with placeholder strings. We keep object shape so required-field checks
  // work even when actual content depends on runtime props.
  // Match `key: identifier[.path]` and replace identifier path with "<expr>".
  cleaned = cleaned.replace(/:\s*([A-Za-z_$][\w$]*)((?:\?\.|\.|\[[^\]]+\])[\w$.\[\]'"?]*)/g, ': "<expr>"');
  cleaned = cleaned.replace(/:\s*([A-Za-z_$][\w$]*)\s*([,}\]])/g, (full, ident, tail) => {
    if (ident === 'true' || ident === 'false' || ident === 'null' || ident === 'undefined') return full;
    if (/^\d/.test(ident)) return full;
    return `: "<expr>"${tail}`;
  });
  // Replace template literals with placeholder.
  cleaned = cleaned.replace(/`[^`]*`/g, '"<tpl>"');
  // Replace ternary + spread syntax inside arrays / objects with placeholders.
  cleaned = cleaned.replace(/\.\.\.[\w$.()[\]{}'"\s?:]+?(?=[,}\]])/g, '"<spread>": "<expr>"');
  try {
    // eslint-disable-next-line no-new-func
    const fn = new Function(`"use strict"; return (${cleaned});`);
    return fn();
  } catch (err) {
    return { __parseError: err.message };
  }
}

function validateLd(obj, fileLabel) {
  const findings = [];
  const items = Array.isArray(obj) ? obj : [obj];
  for (const item of items) {
    if (!item || typeof item !== 'object') continue;
    if (item.__parseError) {
      findings.push({ level: 'warn', file: fileLabel, msg: `unparseable JSON-LD literal: ${item.__parseError}` });
      continue;
    }
    const ctx = item['@context'];
    if (!ctx) {
      findings.push({ level: 'fail', file: fileLabel, msg: 'missing @context' });
    } else {
      const ctxArr = Array.isArray(ctx) ? ctx : [ctx];
      // Strict match: scheme + exact host (with optional path). Avoids the
      // "incomplete URL substring sanitization" CodeQL alert — `c.includes`
      // would let `https://attacker.example/schema.org/...` slip through.
      const ok = ctxArr.some((c) => {
        if (typeof c !== 'string') return false;
        return (
          c === 'https://schema.org' ||
          c === 'http://schema.org' ||
          c.startsWith('https://schema.org/') ||
          c.startsWith('http://schema.org/')
        );
      });
      if (!ok) {
        findings.push({ level: 'fail', file: fileLabel, msg: `@context does not reference schema.org (got ${JSON.stringify(ctx)})` });
      }
    }
    const t = item['@type'];
    if (!t) {
      findings.push({ level: 'fail', file: fileLabel, msg: 'missing @type' });
      continue;
    }
    const types = Array.isArray(t) ? t : [t];
    for (const type of types) {
      if (typeof type !== 'string') continue;
      if (!KNOWN_TYPES.has(type)) {
        findings.push({ level: 'warn', file: fileLabel, msg: `unknown @type "${type}" — typo? not in known schema.org list` });
      }
      const required = REQUIRED_FIELDS[type] || [];
      for (const field of required) {
        if (item[field] === undefined || item[field] === null || item[field] === '') {
          findings.push({ level: 'fail', file: fileLabel, msg: `@type=${type} missing required field "${field}"` });
        }
      }
    }
  }
  return findings;
}

function scan() {
  const allFiles = [];
  for (const root of SCAN_ROOTS) {
    walk(root, allFiles);
  }
  const findings = [];
  let scannedFiles = 0;
  let scannedBlocks = 0;
  for (const file of allFiles) {
    let src;
    try {
      src = fs.readFileSync(file, 'utf8');
    } catch {
      continue;
    }
    if (!src.includes('application/ld+json')) continue;
    scannedFiles++;
    const literals = extractJsonLdLiterals(src);
    for (const lit of literals) {
      scannedBlocks++;
      const obj = tryEvaluate(lit.expr);
      const rel = path.relative(ROOT, file);
      findings.push(...validateLd(obj, rel));
    }
  }
  return { findings, scannedFiles, scannedBlocks };
}

function main() {
  let result;
  try {
    result = scan();
  } catch (err) {
    process.stderr.write(`[jsonld-validate] scan failure: ${err.message}\n`);
    process.exit(2);
  }
  const { findings, scannedFiles, scannedBlocks } = result;
  const fails = findings.filter((f) => f.level === 'fail');
  const warns = findings.filter((f) => f.level === 'warn');
  process.stdout.write(`[jsonld-validate] files=${scannedFiles} blocks=${scannedBlocks} fail=${fails.length} warn=${warns.length}\n`);
  for (const w of warns) {
    process.stdout.write(`  WARN  ${w.file}: ${w.msg}\n`);
  }
  for (const f of fails) {
    process.stdout.write(`  FAIL  ${f.file}: ${f.msg}\n`);
  }
  if (fails.length > 0) {
    process.stdout.write(`[jsonld-validate] FAILED with ${fails.length} schema violation(s)\n`);
    process.exit(1);
  }
  process.stdout.write('[jsonld-validate] OK\n');
  process.exit(0);
}

if (require.main === module) {
  main();
}

module.exports = {
  extractJsonLdLiterals,
  validateLd,
  REQUIRED_FIELDS,
  KNOWN_TYPES,
  tryEvaluate,
};
