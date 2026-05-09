# Recovery Test Coverage

**Story:** TEST-ERR-RECOVERY-2026-001 (substitui #236 stale)
**Last updated:** 2026-05-09
**Reversa anchor:** `_reversa_sdd/review-report.md §10.4`

## Purpose

Document which error-recovery paths have explicit regression coverage,
which are deferred, and the rationale for each — so future incidents
can be triaged against a known coverage map instead of "did we ever
test this?".

## Paths covered

### Backend

| Path | Test file | Origin incident |
|------|-----------|-----------------|
| Pipeline timeout → ``TimeoutError`` re-raised + worker recycles | `backend/tests/recovery/test_pipeline_timeout_recovery.py` | CRIT-084 + RES-BE-016 (route timeout middleware) |
| Pool exhaustion → semaphore sheds, recovers on burst clear | `backend/tests/recovery/test_pool_exhaustion_recovery.py` | POOL-LEAK-001 (chief-pool-semaphore-001) |
| Redis ConnectionError on cache read/write → fallback to compute | `backend/tests/recovery/test_redis_down_fallback.py` | LLM cache resilience (Issue #160) |
| Stripe webhook retry with same `event.id` → idempotent (no double-handler) | `backend/tests/integration/test_stripe_webhook_retry.py` | STORY-307 (atomic INSERT ON CONFLICT) |
| OpenAI 503 / TimeoutError → ARQ job falls back to deterministic summary | `backend/tests/integration/test_openai_fallback.py` | 2026-04 OpenAI 15-min outage |

### Frontend

| Path | Test file | Origin |
|------|-----------|--------|
| SSE EventSource closes mid-stream → reconnect, partial state preserved | `frontend/__tests__/recovery/sse-reconnect.test.tsx` | STORY-2.4 EPIC-TD (Railway 60s idle kill) |
| API 503 / 504 → exponential backoff retry, surfaces to caller after cap | `frontend/__tests__/recovery/api-retry.test.tsx` | RES-BE-016 route timeout middleware |

## Counts

- Backend recovery + integration: **16 tests across 5 files**
- Frontend recovery: **8 tests across 2 files**
- Total: **24 tests across 7 files**

## Paths deferred (rationale)

| Path | Why deferred | Re-evaluation trigger |
|------|--------------|----------------------|
| Supabase total outage end-to-end | Already covered by `tests/integration/test_supabase_total_outage.py` | If new outage uncovers a gap not in that file |
| Service-role pool timeout drift | Covered by `tests/integration/test_service_role_timeout.py` | Schedule annual review aligned with `feedback_supabase_service_role_no_timeout_default` |
| Frontend network offline detection (`navigator.onLine`) | Browser-API surface — minimal logic to test, covered better by E2E | Only if a real incident shows offline UX broken |
| ARQ worker crash mid-job | Requires multi-process orchestration; covered by Sentry alerts + ARQ job retry config | If we observe stuck jobs in production with no Sentry signal |
| Cron job missed run (pg_cron) | Covered by `cron_monitor.py` Sentry alerting (STORY-1.1) — alerting layer, not unit test | Only if monitor itself has a regression |
| PNCP API breaking change | Covered by `pncp_canary` Sentry alert (STORY-4.5) | Only if canary itself regresses |

## How to extend

When a new incident reveals an uncovered recovery path:

1. Open a follow-up story `TEST-ERR-RECOVERY-2026-002+` referencing
   the incident.
2. Add the test file to the appropriate directory (`backend/tests/recovery/`,
   `frontend/__tests__/recovery/`, or `backend/tests/integration/`).
3. Update this document — move the row from "deferred" or add a new row
   under "covered".
4. Bump `_reversa_sdd/review-report.md §10.4` if the addition meaningfully
   changes test/CI coverage.

## Anti-pattern reference

This story explicitly avoided:

- **Comprehensive coverage** — original #236 scope. The 3-paths cap is
  intentional: chase real incidents, not theoretical surfaces.
- **Mock-heavy tests that re-implement production logic** — every test
  here exercises the actual production handler / wrapper, with surgical
  mocks at the I/O boundary (Redis, OpenAI, EventSource, fetch).
- **Tests that depend on infra** — all 24 tests run offline. CI matrix
  matches local invocation.
