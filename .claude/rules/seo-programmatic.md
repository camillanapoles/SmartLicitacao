---
paths:
  - "frontend/app/observatorio/**"
  - "frontend/app/cnpj/**"
  - "frontend/app/fornecedores/**"
  - "frontend/app/orgaos/**"
  - "frontend/app/municipios/**"
  - "frontend/app/licitacoes/**"
  - "frontend/app/contratos/**"
  - "frontend/app/alertas-publicos/**"
  - "frontend/app/itens/**"
  - "frontend/app/blog/**"
  - "frontend/app/casos/**"
  - "frontend/app/glossario/**"
  - "frontend/app/guia/**"
  - "frontend/app/masterclass/**"
  - "frontend/app/perguntas/**"
  - "frontend/app/compliance/**"
  - "frontend/app/sitemap*"
---

# SEO-PROG-001: Programmatic SEO routes never `notFound()` on data gap

**Severity:** MUST
**Source:** ADR-SEO-001 (`docs/adr/ADR-SEO-001-programmatic-routes-no-notfound-on-data-gap.md`)
**CI gate:** `.github/workflows/audit-seo-notfound.yml`
**Companion issues:** #1035 (17-route sweep), #1039 (sitemap-gate), #1042 (this ADR)

## Rule

Routes under the 16 protected path prefixes — `/observatorio`,
`/cnpj`, `/fornecedores`, `/orgaos`, `/municipios`, `/licitacoes`,
`/contratos`, `/alertas-publicos`, `/itens`, `/blog`, `/casos`,
`/glossario`, `/guia`, `/masterclass`, `/perguntas`, `/compliance` —
MUST NOT call `notFound()` on empty data, fetch failure, or any
transient backend condition.

`notFound()` is reserved exclusively for:

1. **Malformed slugs** — `/cnpj/not-a-cnpj`, `/observatorio/zzz-bad`.
2. **Unknown catalog entries** — slug not present in the static
   catalog or canonical list.

Every other code path renders `<EmptyStateSEO>` (or equivalent) plus
`<meta name="robots" content="noindex,follow" />`. The backend pairs
this with HTTP 200 + `is_empty_period: true` + an `X-Robots-Tag:
noindex` response header — never 404 for a known slug.

## Why

Next.js 16 ISR caches `notFound()` responses for the full `revalidate`
window (1 h–24 h depending on the route). With ~10 000 programmatic
URLs, even a 1 % transient blip rate during a regen wave produces
~100 cached 404s. Googlebot:

1. Reads the 404.
2. Drops the URL from the index.
3. Reduces crawl budget for the path prefix.
4. De-indexation cascades to siblings.

Recovery from de-indexation is measured in weeks. Recovery from
`<EmptyStateSEO>` + `noindex` is measured in regen ticks (~1 h):
Google interprets the noindex signal as "skip for now, retry later"
rather than "this URL is gone."

Two precedents back this rule:

- **2026-05-10 incident** — `/observatorio/raio-x-marco-2026` cached a
  404 for ~22 h after a transient backend timeout.
- **SEN-FE-001 sitemap.ts recidiva** — the same antipattern re-emerged
  weeks after an earlier fix because nothing in CI guarded against
  re-entry.

## How to apply

- **Empty data on a known slug** → render `<EmptyStateSEO>` with
  `robots: 'noindex,follow'`. Do not call `notFound()`.
- **Transient fetch failure inside an ISR fetcher** → re-throw the
  error (or return a sentinel that the page handles by rendering
  `<EmptyStateSEO>`). Never swallow into `notFound()`. Re-throwing
  preserves last-good ISR semantics; `notFound()` poisons the cache.
- **Malformed slug / unknown catalog entry** → `notFound()` is
  correct. Mark the line with `// adr-seo-001-allow: <reason>` so the
  CI gate accepts it.
- **Sitemap entries** — slugs whose data layer reports no coverage
  MUST be filtered from `frontend/app/sitemap/[id].xml` (issue
  #1039). The sitemap never advertises a slug that will render
  `<EmptyStateSEO>`.

## Allow marker

When `notFound()` is genuinely correct (malformed slug, unknown
catalog), annotate the line:

```ts
// adr-seo-001-allow: cnpj fails Mod-11 checksum — true 404
notFound();
```

Or on the line itself (compact form, accepted by the gate):

```ts
notFound(); // adr-seo-001-allow: catalog miss for /observatorio/[period]
```

The gate detects the marker on the same line OR on the immediately
preceding line. The reason after the colon must be non-empty and
specific enough to re-evaluate 6 months later. Reviewers challenge
generic reasons.

## CI enforcement

`.github/workflows/audit-seo-notfound.yml` triggers on every pull
request that touches a file under the 16 protected prefixes. It greps
for `notFound()` (and `notFound (` to catch the destructured form) and
fails the PR if any occurrence lacks the `adr-seo-001-allow:` marker.
On failure it posts (or updates) a sticky PR comment that links back
to ADR-SEO-001.

The gate is intentionally simple (grep + marker) rather than an AST
analyzer. Equivalent enforcement, near-zero implementation cost, and
the marker stays auditable in `git log` next to the rationale.
