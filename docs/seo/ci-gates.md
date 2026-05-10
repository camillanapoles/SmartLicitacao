# SEO CI Gates

Issue [#998](https://github.com/tjsasakifln/pncp-poc/issues/998) — SEO-P2-012.

Three deterministic CI gates plus one nightly drift snapshot, wired in
`.github/workflows/seo-gates.yml`. Scripts live under `scripts/seo/` and
have unit tests under `scripts/seo/__tests__/` runnable via Node’s built-in
test runner (no Jest, no extra deps).

## Gate 1 — Title length (`scripts/seo/title-length-check.js`)

**What it scans.** `frontend/lib/blog.ts` and `frontend/lib/questions.ts`
— the source registries that drive the on-page `<title>` for blog posts
and Q&A pages. Page-metadata generated dynamically inside `generateMetadata`
(programmatic SEO routes under `frontend/app/licitacoes/...`) is *not*
covered; those are validated by the JSON-LD gate plus the existing
`scripts/gsc/rich-results-test.ts`.

**Thresholds.**

| env var | default | meaning |
|---------|---------|---------|
| `SEO_TITLE_WARN`    | 60 | warn when `title.length > WARN`         |
| `SEO_TITLE_FAIL`    | 70 | fail when `title.length > FAIL` (only in enforce mode) |
| `SEO_DESC_WARN`     | 170 | warn when questions metaDescription is too long |
| `SEO_TITLE_ENFORCE` | 0  | when `1`, exit non-zero on any FAIL     |

**Why it ships in report mode.** Auditing the registries on 2026-05-10
flagged 61 titles in the 60–82 char range — `>60 = fail` would block
every PR on day one, and `>70 = fail` would still block 26. The gate
ships logging WARN/FAIL annotations without exiting non-zero. Flip
`SEO_TITLE_ENFORCE=1` after the existing titles are rewritten (separate
ticket).

**Local run.**
```bash
node scripts/seo/title-length-check.js
SEO_TITLE_ENFORCE=1 node scripts/seo/title-length-check.js   # strict
```

## Gate 2 — JSON-LD validate (`scripts/seo/jsonld-validate.js`)

**What it scans.** Every `.ts(x)` / `.js(x)` under
`frontend/components/seo/`, `frontend/components/blog/`, and
`frontend/app/`. For each `<script type="application/ld+json">` it
finds the matching `JSON.stringify({ ... })` literal, parses it (with
TS-syntax tolerance and a placeholder pass for variable references),
and validates against a minimal schema.org schema:

- `@context` must reference `schema.org` (string or array containing).
- `@type` must be present and recognized (typo guard).
- Required fields per type — Article needs `headline` + `author`;
  BlogPosting also needs `datePublished`; FAQPage needs `mainEntity`;
  BreadcrumbList needs `itemListElement`; Organization, Person,
  WebSite, WebPage, Product, Service all need `name`/`url`. See
  `REQUIRED_FIELDS` in the script for the canonical list.

**Why a static scan and not a built render.** The Next.js production
build compiles 4k+ programmatic pages and consistently exhausts the
runner heap; the existing `lighthouse.yml` documents the same trade-off
and runs post-merge only. Static scan catches the >90% breakage class
(typos in `@type`, missing required fields) at PR time. The Google Rich
Results Test still runs on the deployed site via
`scripts/gsc/rich-results-test.ts`.

**Hard fail** on any schema violation. Warns (don’t block) on
unparseable literals or unknown `@type`.

**Local run.**
```bash
node scripts/seo/jsonld-validate.js
```

## Gate 3 — Indexation drift (`scripts/seo/indexation-drift.js`)

**Non-blocking.** Runs on PR + nightly cron (04:30 UTC). Compares the
count of URLs the site generates (counted from registry slugs in
`frontend/lib/*.ts`) with the count of URLs Google has indexed (from
the most-recent row of `docs/seo/indexation-history.csv` or the env
`GSC_INDEXED_COUNT`). Surfaces drift via the workflow step summary;
never red-Xes the merge train.

**Thresholds (issue #998 ACs).**

- Absolute ratio < 30% → WARN.
- Drop > 10pp vs previous CSV row → WARN.

**GSC token caveat.** The drift gate currently reads only env or the
history CSV. Wiring a GSC service-account token into CI is a follow-up
(the existing `scripts/gsc/weekly-health-check.ts` is the manual
analog and uses Playwright). Once wired, the cron workflow can append
fresh rows to the history CSV via `--append`.

**Local run.**
```bash
node scripts/seo/indexation-drift.js
GSC_INDEXED_COUNT=80 node scripts/seo/indexation-drift.js --append --json
```

## Out of scope here

- **Lighthouse**. Lives in `.github/workflows/lighthouse.yml` (push-to-main + weekly cron).
- **Uniqueness audit (≥40% diff vs nearest neighbor)**. Tracked separately under SEO-P0-003.
- **Replacing the manual GSC weekly sync**. Stays in
  `scripts/gsc/weekly-health-check.ts`; the new gate runs in parallel.

## Bypassing a gate

The title gate is already report-only. The JSON-LD gate is intended to
fail builds — there is no override label. If a JSON-LD failure is a
false positive (e.g. the parser fails on a brand-new TS pattern),
either fix the script or move the literal into a constant the parser
can resolve. Don’t add an escape hatch.
