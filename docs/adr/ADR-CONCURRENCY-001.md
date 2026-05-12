---
id: ADR-CONCURRENCY-001
title: ConcurrencyLimiter Pattern for SSG/ISR Build Protection
status: Accepted
authors: [@dev, @architect]
date: 2026-05-12
deciders: [Tiago Sasaki]
---

# ADR-CONCURRENCY-001: ConcurrencyLimiter Pattern for SSG/ISR Build Protection

## Context

SmartLic ships ~10 000 programmatic SEO pages rendered through Next.js 16 App Router ISR with `revalidate=3600`. During `next build`, SSG pages with `generateStaticParams` can concurrently issue hundreds or thousands of fetch requests to the backend.

Two production failure modes drove this ADR:

1. **Build hammers backend cascade** (2026-05): SSG generation for 4146 pages saturated the backend Supabase pool (Hobby tier: 15 connections) when dozens of fetches fired simultaneously. The cascade: pool exhaustion -> DB timeout -> 502 from Railway proxy -> next build failure.

2. **SEN-FE-001 recidiva** (`feedback_sen_fe_001_recidiva_sitemap`): `revalidate=N` combined with `cache:'no-store'` on ISR fetches broke SSG semantics. Next.js treats `no-store` as a signal to skip the persistent cache, defeating the purpose of ISR. This anti-pattern re-emerged after earlier fixes because no CI gate or architectural documentation prevented reintroduction.

The underlying issue is an **NxN concurrency problem**: N pages × M fetches per page can exceed both the backend connection pool and the Railway proxy timeout budget. A semaphore-based concurrency limiter is required to serialize build-time requests without blocking the event loop.

## Decision

1. **ConcurrencyLimiter class** (`frontend/lib/concurrency.ts`): a Promise-based semaphore that limits in-flight asynchronous operations to a configurable maximum. Its `run(fn)` method queues callbacks when the active count exceeds the max, draining the queue as slots free up.

2. **Shared SSG instance** (`ssgFetchLimiter`, max 6 concurrent): a singleton instance reused across all build-time data fetches. Six concurrent requests keep throughput high enough for reasonable build times while staying well below the Supabase Hobby pool (15 connections).

3. **Default fetch timeout** (`AbortSignal.timeout(30_000)`): applied whenever no explicit signal is provided. This prevents a single stuck backend query from holding a semaphore slot for the full build timeout (typically 300s).

4. **Negative cache on DB failure**: when a build-time fetch fails (timeout, 5xx, network error), the ISR page does NOT propagate the error. Instead it renders `<EmptyStateSEO>` with `noindex,follow` metadata, allowing the next revalidation tick to recover. The cached 404 antipattern is explicitly avoided (see ADR-SEO-001).

5. **Backend concurrency protection** (`backend/pipeline/budget.py`): `_run_with_budget` wraps every pipeline execution with a hard budget. This provides defense-in-depth: if the frontend semaphore is misconfigured, the backend's own budget limits prevent unbounded concurrency.

6. **Anti-pattern rule**: `revalidate=N` MUST NOT be combined with `cache:'no-store'` on any ISR route. Cache control headers must align: ISR routes use `next:{revalidate:N}` without `cache:'no-store'`. This is enforced by code review and documented in the CI gate referenced by SEN-FE-001.

### File Locations

| Component | Path | Role |
|-----------|------|------|
| ConcurrencyLimiter class | `frontend/lib/concurrency.ts` | Promise semaphore |
| Shared SSG instance | `frontend/lib/concurrency.ts` (`ssgFetchLimiter`) | 6-concurrent singleton |
| Fetch wrapper | `frontend/lib/concurrency.ts` (`ssgLimitedFetch`) | Timeout + semaphore |
| Backend budget | `backend/pipeline/budget.py` | Server-side timeout waterfall |

## Consequences

### Positive

- SSG build times remain predictable: 6 concurrent fetches fill the pipeline without overwhelming the backend.
- A single stuck request cannot hold the entire build hostage (30s timeout vs 300s build timeout).
- ISR pages self-recover: a transient failure produces `<EmptyStateSEO>` instead of a cached 404. Next revalidate tick restores the content.
- The ConcurrencyLimiter is testable in isolation (unit tests verify queue/drain behavior without network).
- The pattern is reusable: any future batch-fetch scenario (reconciliation, background sync) can use the same semaphore.

### Negative / Risks

- **R1 (Low)**: 6 concurrent fetches may become a bottleneck as the page count grows beyond 10k. Mitigation: `maxConcurrent` is a constructor parameter — bump to 8 or 10 once backend pool is upgraded (Pro tier: 60 connections).
- **R2 (Low)**: `AbortSignal.timeout(30_000)` may false-positive on genuinely slow backend endpoints (e.g. complex DataLake RPCs). Mitigation: endpoints covered by the budget waterfall (`_run_with_budget`) complete in well under 30s at p95. If a new endpoint exceeds this, its fetch call can pass an explicit `signal` override.
- **R3 (Medium)**: The `cache:'no-store'` anti-pattern can re-enter via greenfield ISR routes if reviewers miss it. Mitigation: documented in this ADR; CI grep in `audit-seo-notfound.yml` can be extended to flag `'no-store'` on ISR paths.
- **R4 (Low)**: The negative cache path means a permanently broken endpoint serves `<EmptyStateSEO>` silently. Mitigation: Sentry alert on any fetch failure during build/revalidation (`captureMessage` in the fetch wrapper).

### Neutral

- The backend `_run_with_budget` and the frontend `ConcurrencyLimiter` are independent safeguards. Each can be tuned or removed without affecting the other.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| **No concurrency limit (status quo ante)** | Caused production incidents (build hammers backend cascade). Rejected. |
| **Backend rate limiting only** | Protects the backend but leaves the frontend build exposed to timeouts. A single endpoint can hold N requests in flight, wasting build time on responses that will be 429'd. |
| **`p-limit` npm package** | Equivalent to our 30-line class; avoids an external dependency. Our implementation is simpler, testable, and avoids supply-chain risk. |
| **Batch fetch pages serially** | Would be correct but impractically slow for 10k+ pages (each page fetches 2-5 endpoints). Semaphore gives 6x throughput. |
| **Redis-based distributed semaphore** | Over-engineered for the build-time use case. Builds run on a single machine. The in-process semaphore is sufficient and avoids Redis round-trips. |
| **Decrease `revalidate` instead of adding a semaphore** | More frequent revalidations increase backend load without fixing the concurrency spike during build. Band-aid, not a solution. |

## References

- Memory: `feedback_build_hammers_backend_cascade` (build incident)
- Memory: `feedback_sen_fe_001_recidiva_sitemap` (SEN-FE-001 recidiva)
- ADR-SEO-001: Programmatic SEO routes never `notFound()` on data gap
- `frontend/lib/concurrency.ts` — ConcurrencyLimiter implementation
- `backend/pipeline/budget.py` — `_run_with_budget` server-side budget
- Issue [#1132](https://github.com/tjsasakifln/PNCP-poc/issues/1132) — SSG/ISR build fix
