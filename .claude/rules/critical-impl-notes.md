---
paths:
  - "backend/**"
  - "supabase/**"
---

# Critical Implementation Notes — SmartLic

## Ingestion Pipeline (Layer 1)
- **Schedule:** Full crawl daily 5 UTC (2am BRT), incremental 11/17/23 UTC, purge 7 UTC
- **Scope:** 27 UFs × 6 modalidades (4,5,6,7,8,12), 10-day window (full), 3-day (incremental)
- **Concurrency:** 5 UFs parallel, 2s delay between batches, max 50 pages per (UF, modalidade)
- **Upsert:** 500 rows/batch via `upsert_pncp_raw_bids` RPC with content_hash dedup
- **Retention:** 400 days (STORY-OBS-001 — hard-delete via `purge_old_bids(400)` pg_cron daily 07 UTC). Previously 12d; bumped because `/observatorio/raio-x-*` and other programmatic SEO routes (alertas, municipios, orgao) query historical windows and were rendering 200 OK with zero data.
- **Tables:** `pncp_raw_bids` (data), `ingestion_checkpoints` (progress), `ingestion_runs` (audit)
- **Worker:** `PROCESS_TYPE=worker` → `arq job_queue.WorkerSettings`
- **pg_cron backup (STORY-1.2):** `purge-old-bids` scheduled via `cron.schedule('purge-old-bids', '0 7 * * *', ...)` — runs server-side even if Railway worker is offline. Monitored by STORY-1.1.

## pg_cron Monitoring (STORY-1.1 EPIC-TD-2026Q2)

All scheduled pg_cron jobs (purge-old-bids, cleanup-search-cache, cleanup-search-store, and any future additions) are monitored end-to-end:

- **View:** `public.cron_job_health` joins `cron.job` + `cron.job_run_details` over a 7-day window.
- **RPC:** `public.get_cron_health()` (SECURITY DEFINER) — invoked by backend only.
- **Endpoint:** `GET /v1/admin/cron-status` (admin-only) returns JSON snapshot — shape `{status, count, jobs: [{jobname, last_status, last_run_at, runs_24h, failures_24h, latency_avg_ms}]}`.
- **Alerting:** hourly ARQ cron `cron_monitoring_job` (in `backend/jobs/cron/cron_monitor.py`) emits a Sentry `capture_message(level="error")` for any job that is `failed` or stale (>25h since last run). Fingerprint `["cron_job", jobname, reason]` dedups across runs.

**To add a new scheduled cron:**
1. Create a migration `supabase/migrations/YYYYMMDDHHMMSS_schedule_<name>.sql` calling `cron.schedule(...)`.
2. That's it — the existing monitor will start checking the new job on the next hourly tick. No code changes required unless you want custom thresholds.

## PNCP API (used by ingestion + legacy fallback)
- **Max tamanhoPagina = 50** (reduced from 500 in Feb 2026, >50 -> HTTP 400 silent)
- Search period default: 10 days (frontend + backend)
- Phased UF batching: PNCP_BATCH_SIZE=5, PNCP_BATCH_DELAY_S=2.0
- Retry: exponential backoff, HTTP 422 is retryable (max 1 retry)
- Circuit breaker: 15 failures threshold, 60s cooldown
- Fast health canary (`backend/health.py`) validates `tamanhoPagina=50` succeeds (production value) + delegates to `pncp_canary.validate_page_size_limit` to probe `tamanhoPagina=51` on every health cycle.

## PNCP Breaking Change Canary (STORY-4.5)

Background ARQ cron in `backend/jobs/cron/pncp_canary.py` runs every `PNCP_CANARY_INTERVAL_S` seconds (default 600s = 10 min) and triggers Sentry fatal alerts when:

| Reason | Probe | Sentry gate |
|--------|-------|-------------|
| `max_page_size_changed` | `tamanhoPagina=51` accepted (HTTP < 400) | immediate (1 occurrence) |
| `canary_3x_failed` | `tamanhoPagina=50` fails or returns non-JSON for 3 consecutive runs | threshold gated |
| `shape_drift` | `tamanhoPagina=50` payload fails `backend/contracts/schemas/pncp_search_response.schema.json` | immediate |

Dedup: each reason uses a Redis flag with 6h TTL so operators get one Sentry event per incident, not 36/day. Tags: `pncp_breaking_change={reason}`, `source=pncp`. Fingerprint: `["pncp_canary", reason]`.

Metrics (Prometheus): `smartlic_pncp_max_page_size_changed_total`, `smartlic_pncp_canary_consecutive_failures`, `smartlic_pncp_canary_shape_drift_total`. Disable the cron with `PNCP_CANARY_INTERVAL_S=0`; raise/lower the threshold via `PNCP_CANARY_FAIL_THRESHOLD` (default 3).

## PCP v2 (Secondary)
- No auth required (fully public v2 API)
- Fixed 10/page pagination (`pageCount`/`nextPage`)
- Client-side UF filtering only (no server-side UF param)
- `valor_estimado=0.0` (v2 has no value data)

## ComprasGov v3 (Tertiary)
- Dual-endpoint: legacy + Lei 14.133
- Base URL: `dadosabertos.compras.gov.br`

## Filtering Pipeline (order matters — fail-fast)
1. UF check (fastest)
2. Value range check
3. Keyword matching (density scoring)
4. LLM zero-match classification (for 0% keyword density)
5. Status/date validation
6. Viability assessment (post-filter)

**Feature Flags:** `DATALAKE_ENABLED`, `DATALAKE_QUERY_ENABLED`, `LLM_ZERO_MATCH_ENABLED`, `LLM_ARBITER_ENABLED`, `VIABILITY_ASSESSMENT_ENABLED`, `SYNONYM_MATCHING_ENABLED`

## LLM Integration
- GPT-4.1-nano for classification + summaries
- Zero-match prompt: `_build_zero_match_prompt()` in `llm_arbiter/zero_match.py` (`llm_arbiter/` is a package — classification.py, zero_match.py, async_runtime.py, batch_api.py, prompt_builder.py)
- Fallback = PENDING_REVIEW on failure (gray zone + zero-match) when `LLM_FALLBACK_PENDING_ENABLED=true`; REJECT when disabled
- ARQ background jobs for summaries (immediate fallback response)
- ThreadPoolExecutor(max_workers=10) for parallel LLM calls

## Cache Strategy (Layer 3 — caches search results, NOT raw bids)
- L1 InMemoryCache: 4h TTL, hot/warm/cold priority
- L2 Supabase `search_results_cache`: 24h TTL, persistent
- Fresh (0-6h) -> Stale (6-24h, served + background refresh) -> Expired (>24h, not served)
- Patch `supabase_client.get_supabase` for cache tests (not `search_cache.get_supabase`)

## Billing & Auth
- **Pricing (STORY-277/360):** SmartLic Pro R$397/mes (mensal), R$357/mes (semestral, 10% off), R$297/mes (anual, 25% off). Consultoria R$997/mes, R$897/sem (10%), R$797/anual (20%). Source of truth: `plan_billing_periods` table (synced from Stripe)
- **Trial:** 14 dias gratis (STORY-264/277/319), sem cartao
- Stripe handles proration automatically — NO custom prorata code
- "Fail to last known plan": never fall back to free_trial on DB errors
- 3-day grace period for subscription gaps (`SUBSCRIPTION_GRACE_DAYS`)
- ALL Stripe webhook handlers sync `profiles.plan_type`
- Frontend localStorage plan cache (1hr TTL) prevents UI downgrades
- Tests mocking `/buscar` MUST also mock `check_and_increment_quota_atomic`

## Railway/Gunicorn Critical Notes
- **Railway hard timeout: ~120s** — requests exceeding this are killed by Railway proxy
- Gunicorn timeout: 180s (env var `GUNICORN_TIMEOUT` overrides)
- Sync PNCPClient fallback wrapped in `asyncio.to_thread()` — never blocks event loop
- Gunicorn keep-alive: 75s (> Railway proxy 60s) prevents intermittent 502s

### Runner History (CRIT-083 → CRIT-084 → RES-BE-016)
- **CRIT-083:** Gunicorn prefork (os.fork) + `cryptography>=46` OpenSSL C bindings = SIGSEGV on POST requests (TLS handshake in forked child). GET worked; POST crashed.
- **CRIT-084 (active):** Switched to `RUNNER=uvicorn` with `--workers` flag. uvicorn uses `multiprocessing.spawn()` not `os.fork()`, eliminating the SIGSEGV. Gunicorn config still present in `start.sh` but NOT active.
- **RES-BE-016 AC4 (active):** Route-level asyncio timeout middleware at 60s (`ROUTE_TIMEOUT_S`). Returns 503 + Retry-After:5 before Railway's 120s proxy kill, freeing the event loop. **Underlying threads continue** until Supabase `statement_timeout=15s` kills the query — this is expected. SSE/search-polling/health/webhooks exempt via `_ROUTE_TIMEOUT_EXEMPT_PREFIXES`.
- **AC1 (NOT executed):** Gunicorn staging validation requires `cryptography` to be fork-safe. `requirements.txt` explicitly marks it NOT fork-safe — skip AC1, AC4 is the correct path.
- **Rollback:** Set `ROUTE_TIMEOUT_S=0` in Railway env to disable middleware without deploy.
- **Re-validation cadence:** If `cryptography` drops its OpenSSL fork restriction in a future release (check release notes), re-run AC1 staging test before switching back to Gunicorn.
- **Sentry alert:** `rate(smartlic_route_timeout_total[1h]) > 10` indicates routes not covered by `_run_with_budget` (budget module should catch these first).

## Time Budget Waterfall (STORY-4.4 TD-SYS-003)

Defaults tightened in `backend/config/pncp.py` so the inner timeout always expires before Railway kills the request — leaving ~20s headroom for response serialization:

```
Railway proxy     [========================== 120s ==========================]
Gunicorn worker   [======================= 110s ========================]
Pipeline budget   [==================== 100s ====================]
  Consolidation   [================== 90s ===================]
    PerSource     [============= 70s =============]
      PerUF       [===== 25s =====]
        httpx r/w [10c+15r]
```

Invariant (enforced by `backend/tests/test_timeout_invariants.py`): `pipeline(100) > consolidation(90) > per_source(70) > per_uf(25) > (per_modality 20 + httpx 15)`.

Pipeline call sites go through `backend/pipeline/budget.py::_run_with_budget` so every TimeoutError increments `smartlic_pipeline_budget_exceeded_total{phase,source}`.

To unblock a specific deploy (emergency), override via Railway vars: `PIPELINE_TIMEOUT=110`, `CONSOLIDATION_TIMEOUT=100`, `PNCP_TIMEOUT_PER_SOURCE=80`, etc. — no code change needed.

## Type Safety
- **Python:** Type hints on all functions, Pydantic for API contracts, pattern validation for dates
- **TypeScript:** Interfaces over types, no `any`, strict null checks enabled

## Resilience CI Gates (EPIC-RES-BE-2026-Q2)

Determinístic gates derived from the 2026-04-27 → 2026-04-30 outage cycle (Stages 2–8).

| Gate | Workflow | Origem | Failure mode |
|---|---|---|---|
| `.execute()` without `_run_with_budget` | `audit-execute-without-budget.yml` (RES-BE-001/015) | Stage 2-8 wedge (sync `.execute()` in async route) | Hard fail on PR; sticky comment + inline annotations |
| Railway prod env vars drift | `audit-prod-env.yml` (RES-BE-013) | Stage 2 — `PYTHONASYNCIODEBUG=1` in prod with no PR trail | Daily cron + manual dispatch; advisory only — see `docs/runbooks/audit-prod-env.md` |

Both gates accept decremental baselines: shrinking the violation set is always allowed; growing it fails the gate. Adding entries to `prod-env-blocklist.txt` requires `@architect` + `@devops` review.
