# ADR-SEO-001: Programmatic SEO routes never `notFound()` on data gap

| Field | Value |
|-------|-------|
| Status | Accepted (2026-05-10) |
| Issue | [#1042](https://github.com/tjsasakifln/SmartLic/issues/1042) |
| Authors | @dev (lead), @architect, @ux-design-expert |
| Stakeholders | @pm, @qa, @devops |
| Supersedes | — |
| Superseded by | — |
| Companion of | #1035 (route sweep), #1039 (sitemap-gate) |

## Context

SmartLic ships ~10 000 programmatic SEO URLs across 16 path prefixes
(`/observatorio`, `/cnpj`, `/fornecedores`, `/orgaos`, `/municipios`,
`/licitacoes`, `/contratos`, `/alertas-publicos`, `/itens`, `/blog`,
`/casos`, `/glossario`, `/guia`, `/masterclass`, `/perguntas`,
`/compliance`). All of them are rendered through Next.js 16 App Router
ISR with `revalidate=3600`. The shared template imports
`{ notFound } from 'next/navigation'` and historically calls it whenever
the upstream fetch returns an empty result, a non-2xx response, or a
caught exception.

Two production incidents proved this pattern is incompatible with ISR
at our scale:

1. **2026-05-10 `/observatorio/raio-x-marco-2026`** — a transient
   backend timeout during regen produced an `is_empty_period:true`
   payload. The page called `notFound()`, ISR cached the 404, and the
   slug stayed de-indexed for ~22 h until the next manual purge.
2. **SEN-FE-001 sitemap.ts recidiva** (memory
   `feedback_sen_fe_001_recidiva_sitemap`) — the same antipattern
   re-emerged after an earlier fix because nothing in CI prevented its
   reintroduction. A grep-only review missed two follow-up call sites.

The shared characteristics:

- `notFound()` in an ISR route renders `not-found.tsx` AND tells the
  cache layer to persist the 404 for the full `revalidate` window
  (1 h–24 h depending on the route). There is no auto-recovery;
  the slug remains 404 to crawlers until the cache key is purged or
  the underlying renderer crashes.
- A 1 % transient blip rate over 10 k URLs = ~100 cached 404s per
  regen wave. Googlebot reads 404 → drops the URL from the index →
  reduces crawl budget for the path prefix → de-indexation cascades
  to siblings. Recovery from de-indexation is measured in weeks.
- The same data layer is re-used by the sitemap. Without a parallel
  filter, the sitemap continues to advertise URLs that will hand
  back 404s, compounding the trust signal damage.

The repository does not currently have a guard that prevents a new
route file from importing `notFound()` and using it on the data-gap
path. The 17-route sweep (#1035) is in flight but is a one-shot
remediation; without a CI gate, the antipattern re-enters via the
next greenfield programmatic route.

## Decision

1. **Programmatic routes never call `notFound()` on data gap.**
   The 16 path prefixes listed above MUST render an
   `<EmptyStateSEO>` component (or equivalent) and emit
   `<meta name="robots" content="noindex,follow" />` whenever the
   data layer reports zero rows for a known catalog slug.

2. **`notFound()` is reserved for malformed slugs and unknown catalog
   entries.** A request for `/cnpj/not-a-cnpj` or
   `/observatorio/zzz-nonexistent-period` is a true 404 and SHOULD be
   served as such. The discriminator is "the slug is not in the
   catalog" — never "the data window happens to be empty right now."

3. **Transient fetch failures re-throw, never `notFound()`.** ISR
   fetchers MUST propagate transient errors so Next.js falls back to
   the previous successful render (`stale-if-error` semantics) instead
   of caching a 404. If no last-good render exists yet,
   `<EmptyStateSEO>` with `noindex,follow` is rendered.

4. **Backend pairs the contract.** Read endpoints powering these
   routes return HTTP 200 with `is_empty_period:true` (or analogous
   field) and an `X-Robots-Tag: noindex` response header on empty
   data. They never return 404 for a known slug.

5. **Sitemap gate (#1039) keeps the sitemap honest.** Slugs whose
   data layer reports no coverage are filtered from
   `frontend/app/sitemap/[id].xml` so the sitemap never advertises
   a URL that will render `<EmptyStateSEO>`.

6. **Explicit allow marker for legitimate `notFound()`.** When the
   route legitimately needs to call `notFound()` (malformed slug
   detection, unknown catalog entry), the line MUST carry the marker
   `// adr-seo-001-allow: <one-line reason>` on the same line or the
   line immediately above. The reason must be specific enough to be
   re-evaluated 6 months later.

7. **CI gate.** `.github/workflows/audit-seo-notfound.yml` runs on
   every PR that touches the 16 protected path prefixes. It greps for
   `notFound()` and fails the PR for any occurrence without the
   `adr-seo-001-allow:` marker, posting a sticky comment with a link
   to this ADR.

## Consequences

### Positive

- A class of de-indexation incidents (transient blip → cached 404 →
  Googlebot drop) is closed at the route layer. Recovery time changes
  from "~24 h until next manual purge" to "next regen tick, ~1 h"
  because `<EmptyStateSEO>` renders on success and Google interprets
  it as a thin-but-valid page rather than a hard 404.
- The CI gate prevents re-entry of the antipattern via greenfield
  programmatic routes. SEN-FE-001 recidiva is bounded.
- The marker convention (`// adr-seo-001-allow: <reason>`) keeps
  legitimate `notFound()` calls (malformed slugs) auditable in
  `git log` next to the rationale.
- Backend contract change (200 + `is_empty_period:true` +
  `X-Robots-Tag: noindex`) is symmetric with the frontend behavior:
  client-side and server-side rendering produce the same noindex
  signal on empty data.

### Negative / Risks

- **R1 (Low): Allow marker drift.** Developers might paste the marker
  without a meaningful reason. Mitigation: PR review explicitly
  challenges any new `// adr-seo-001-allow:` and the marker requires
  a non-empty reason after the colon.
- **R2 (Low): `<EmptyStateSEO>` rendered too often becomes an SEO
  signal of its own.** Mitigation: sitemap gate (#1039) drops empty
  slugs from the sitemap, so Googlebot only visits empty pages via
  internal links — a much smaller surface than the full URL set.
- **R3 (Medium): Backend regression returning 404 on known slugs.**
  Mitigation: contract tests in `backend/tests/` assert 200 +
  `is_empty_period:true` for the empty-data path. Tracked alongside
  the route sweep (#1035).

### Neutral

- The 17-route sweep (#1035) is the implementation arm of this
  decision. This ADR is the durable rule; #1035 is the
  one-shot migration. Future programmatic routes inherit the rule
  via the CI gate without needing to consult #1035.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| **Keep `notFound()` and rely on shorter `revalidate`** | A 1 h cache of a 404 is still long enough for Googlebot to record the URL as missing during a regen wave. Shortening `revalidate` below 1 h spikes backend load (10 k routes × 24 regens/day) without solving the de-indexation cascade. |
| **`notFound()` + `unstable_noStore()`** | Disabling ISR entirely for these routes burns the SEO benefit (slow first paint, no Cloudflare cache hit). The whole point of programmatic SEO is the cached render. |
| **Static grep-only review (no CI gate)** | Recidiva of SEN-FE-001 proved this approach fails. A CI gate is the only durable guard against silent re-entry. |
| **Editing `.aiox-core/constitution.md`** | The constitution is L1 framework-protected per `.claude/CLAUDE.md` boundary rules. Project-specific rules belong in `.claude/rules/` and `docs/adr/`. The rule file `.claude/rules/seo-programmatic.md` carries the same authority for project agents. |
| **Detect data-gap context with a smarter linter** | Building a typed AST analyzer that proves a `notFound()` call is on the data-gap branch is high-effort and brittle. A grep + explicit `// adr-seo-001-allow:` marker gives equivalent enforcement at near-zero implementation cost and stays auditable in `git log`. |

## Compliance

- **PR review checklist:** any `notFound()` added to a protected route
  MUST be either removed or carry the `// adr-seo-001-allow: <reason>`
  marker. The reviewer challenges the reason.
- **CI gate:** `.github/workflows/audit-seo-notfound.yml` runs on PRs
  that touch the 16 path prefixes; failures block merge with a sticky
  comment linking back here.
- **Project rule:** `.claude/rules/seo-programmatic.md` carries the
  same content for AI agents working on the codebase.

## References

- Issue: [#1042](https://github.com/tjsasakifln/SmartLic/issues/1042)
- Companion issues: [#1035](https://github.com/tjsasakifln/SmartLic/issues/1035) (17-route sweep), [#1039](https://github.com/tjsasakifln/SmartLic/issues/1039) (sitemap-gate)
- Rule: `.claude/rules/seo-programmatic.md`
- CI gate: `.github/workflows/audit-seo-notfound.yml`
- Memory: `feedback_sen_fe_001_recidiva_sitemap` (recidiva precedent)
- Incident note: `/observatorio/raio-x-marco-2026` de-indexation, 2026-05-10
