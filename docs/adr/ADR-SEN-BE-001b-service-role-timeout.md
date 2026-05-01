# ADR SEN-BE-001b: service_role `statement_timeout = 60s`

**Status:** Accepted (2026-04-28)
**Story:** [SEN-BE-001b](../stories/SEN-BE-001b-service-role-statement-timeout.story.md)
**Supersedes:** none
**Superseded by:** none
**Companion of:** SEN-BE-001 (per-query budget timeouts in Python)

> Note on convention: this is the first ADR filed under `docs/adr/` (per the SEN-BE-001b task brief). Prior ADRs live under `docs/decisions/` and `docs/architecture/`. We are introducing the canonical `docs/adr/` location going forward — older ADRs will not be relocated retroactively.

## Context

Default Supabase role configurations expose a sharp asymmetry on `statement_timeout`:

| Role | `statement_timeout` default | Surface |
|------|------------------------------|---------|
| `anon` | 3s | Public unauthenticated reads |
| `authenticated` | 8s | Authenticated end-user reads/writes |
| `service_role` | **NULL (no limit)** | Backend admin client — bypasses RLS |

The SmartLic backend uses `SUPABASE_SERVICE_ROLE_KEY` in `backend/supabase_client.py::get_supabase()` for every server-side path: admin endpoints, ARQ workers, ingestion, RPCs, cron jobs, reconciliation. Because the role had no statement timeout, any query — accidentally unindexed, runaway loop, lock contention — could:

1. Hold connections from the pool indefinitely (Hobby tier hard cap: 60 connections).
2. Saturate the event loop when invoked through synchronous `.execute()` calls inside async handlers.
3. Cascade past Railway's proxy hard kill at 120s, leaving zombie work and triggering 502 storms.

This is exactly the failure shape we observed in the **2026-04-27 Stage 2 outage** (`docs/sessions/2026-04/2026-04-27-...`). Googlebot crawl waves hit `/v1/perfil-b2g/*` and `/v1/fornecedor-publico/*` (unbudgeted, no negative cache), ran a slow trigram lookup, drained the pool, and stayed there. PR #529 patched the symptom in Python (`asyncio.wait_for`, negative cache); this ADR closes the **defense-in-depth gap** at the database role layer.

## Decision

Apply `ALTER ROLE service_role SET statement_timeout = '60s';` via paired migrations:

- `supabase/migrations/20260427213410_service_role_statement_timeout.sql` (up)
- `supabase/migrations/20260427213410_service_role_statement_timeout.down.sql` (down)

Backend `supabase_client.sb_execute` translates the resulting `SQLSTATE 57014` (`query_canceled`) into:

- **Sentry breadcrumb:** `sentry_sdk.set_tag("query_timeout", "true")` + `set_tag("supabase_category", <read|write|rpc>)` + `capture_message(level="warning")`. Distinct from generic 500s on the dashboard so on-call can differentiate "real outage" from "single bad query."
- **HTTP surface:** `HTTPException(status_code=504, detail="Database query timed out (SQLSTATE 57014). Please retry.")` — 504 is the correct semantic (gateway timeout) versus 500 (server fault).
- **Structured log:** `logger.warning("[supabase] query_timeout SQLSTATE=57014 category=...")` — picked up by log search.
- **Circuit-breaker accounting:** the failure IS recorded against the per-category CB streak. A real timeout is a real Supabase-side problem; the streak guard should see it. The CB does not open on a single timeout (window=10, threshold=70%, streak per category 3-5).

A non-FastAPI helper exception `QueryTimeoutError` is exported alongside so background workers / cron jobs can introspect without importing FastAPI.

### Why 60s

- The pipeline budget waterfall caps inner work at 100s (Pipeline → Consolidation 90s → PerSource 70s → PerUF 25s — see `_reversa_sdd/architecture-detail.md`). 60s on the role leaves ~40s for serialization + Railway proxy padding (120s hard kill).
- Empirically every legitimate server-side query in the audit completes in <2s (datalake p95 <100ms, RPCs <5s, ingestion bulk upserts <30s). 60s is **30x** the realistic worst-case — generous enough that we will not page on healthy traffic, tight enough that runaway queries die before they take the pool with them.
- 60s aligns with the CTO heuristic: "Queries legitimately needing >60s indicate a regression worth fixing, not a tolerance to grant."

### Why `ALTER ROLE` and not `SET LOCAL`

- `ALTER ROLE` applies to **every** session opened by `service_role`, including third-party tools, background scripts, and CLI access. `SET LOCAL` requires every callsite to remember.
- Per-query overrides remain available: a long-running ingestion script can wrap a transaction with `SET LOCAL statement_timeout = '180s'` for that session only. The role-level default is a floor, not a ceiling.

## Consequences

### Positive

- **Outage prevention:** A class of failures (runaway query → pool exhaustion → 502 cascade) is now bounded at 60s instead of unbounded. The failure mode that drove the 2026-04-27 incident is closed at the role layer.
- **Operational clarity:** `query_timeout=true` Sentry tag separates "single bad query" from "Supabase outage." On-call rotation can stop debugging the wrong layer.
- **HTTP semantic correctness:** 504 to the client instead of 500 when the timeout fires — clients can implement intelligent retry/backoff.

### Negative / Risks

- **R1 (Medium): Legitimate long server-side queries clipped at 60s.** Mitigation: ARQ batch jobs and ingestion full-crawl backfills can use `SET LOCAL statement_timeout = '180s'` inside their own transactions (documented in their respective story files). Reconciliation Stripe scripts likewise.
- **R2 (Low): `ALTER ROLE` only affects new sessions.** Existing pooled connections retain their old config until recycled. **Mitigation:** Railway worker restarts on deploy effectively recycle the pool; for forced refresh, run `pg_terminate_backend(pid)` on idle service_role sessions or wait for the keep-alive expiry (~75s).
- **R3 (Low): Migration relies on `ALTER ROLE`.** Cannot be applied via PostgREST or anon/authenticated keys — requires Supabase Dashboard SQL editor or a CLI call against a connection that has `ALTER ROLE` privilege. Same constraint applies to the rollback `RESET`.

### Neutral

- The migration uses `NOTIFY pgrst, 'reload config'` so the change becomes visible to PostgREST without a restart. PostgREST itself does not enforce `statement_timeout`; the value flows directly from the Postgres role config when sessions are opened.

## Alternatives considered

| Alternative | Why rejected |
|-------------|--------------|
| **`SET LOCAL` per query in Python** | Brittle. Every new callsite is a chance to forget. Does not protect against tools (psql, supabase CLI, third-party integrations) that bypass our wrapper. Rejected by anti-requirements in the story. |
| **`statement_timeout = 30s`** | Too aggressive. Some legitimate ingestion paths (initial backfill, stripe reconciliation full sweep) measured at 40-50s in tail. Would generate false 504s on healthy traffic. |
| **`statement_timeout = 120s`** | Equal to Railway proxy hard kill — pointless (timeout fires after the request is already dead). |
| **`statement_timeout = 0` (disabled, current state)** | Status quo — caused the 2026-04-27 outage. Rejected. |
| **Per-route `SET LOCAL` only on hot paths** | Closes the symptom path that PR #529 already patched, but leaves every other server-side path (admin, cron, jobs) unprotected. Defeats the purpose of defense-in-depth. |

## Verification

After deploy, the orchestrator runs the following SQL against production to confirm the migration took effect:

```sql
-- Expect: rolconfig contains "statement_timeout=60s"
SELECT rolname, rolconfig
FROM pg_roles
WHERE rolname = 'service_role';
```

Live probe (gated by `RUN_INTEGRATION=1` env var, see `backend/tests/integration/test_service_role_timeout.py::test_live_pg_sleep_65_aborts_within_62s`):

```sql
-- Expect: cancellation with SQLSTATE 57014 in ~60s (tolerance: 62s)
SELECT pg_sleep(65);
```

## References

- Story: `docs/stories/SEN-BE-001b-service-role-statement-timeout.story.md`
- Companion: SEN-BE-001 (Python-side budget timeouts)
- Incident pos-mortem: `docs/sessions/2026-04/2026-04-27-supabase-disk-io-consolidation-handoff.md`
- Memory: `reference_supabase_service_role_no_timeout_default.md`
- PR #529 (symptom-side patch): `fix(sitemap): hard budget + asyncio.to_thread + negative cache`
- Reversa Audit Gap-10: `_reversa_sdd/review-report.md`
