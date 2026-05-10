# Operational Reliability Report — 2026-05

**Story:** OPS-MTTR-001 (issue #970) · review-report.md §15.3 · target 86% → ≥95%
**Owner:** @tjsasakifln · **Window:** 2026-05-09 baseline; 7d rolling rollup thereafter

## SLO

| Indicator | Target | Source of truth |
|---|---|---|
| Backend p95 latency (`/buscar`) | < 2s | Sentry Performance — `smartlic-backend` |
| `/health/ready` uptime | > 99.5% | `.github/workflows/health-alert.yml` (5min probe) |
| Backend MTTR (5xx → 2xx) | < 30 min per endpoint | `scripts/mttr_calculator.py` (rolling 7d) |
| Frontend Sentry event ingest | accepted > 0 / 24h | `scripts/sentry_baseline_check.py` (post-PR-#944 RCA) |

## Error Budget

- **5xx rate budget:** 0.5% of total requests over rolling 30d.
- **Burn rule:** if rolling 7d 5xx rate > 0.5%, freeze non-essential deploys; investigate top offending route via `mttr_calculator.py`.
- **Frontend events floor:** if `sentry_baseline_check.py` reports `accepted == 0` for 7 consecutive days, escalate per memory `feedback_sentry_quiescent_quota_pattern` (quota check first, SDK debug second).

## Tooling Wired in This Story

- `scripts/sentry_baseline_check.py` — calls Sentry stats_v2 outcomes endpoint; supports `--dry-run` for CI smoke without secrets.
- `scripts/mttr_calculator.py` — parses Railway-style access logs, computes per-endpoint MTTR, exits 2 when SLO breached.
- `.github/workflows/health-alert.yml` — cron 5min, curl `/health/ready`, Resend on 5xx.
- `.github/workflows/audit-prod-env.yml` (pre-existing) — daily drift check for debug env vars.

## Runbook — Recent High-Severity Closures (last 7d)

Source: `gh issue list --state closed --search "incident OR CRIT"` (label `incident` is empty in this repo; `CRIT-*` is the de-facto severity tag).

- **CRIT-084 #799** (closed 2026-05-07) — uvicorn graceful-shutdown timeout for worker recycling. Mitigation: `--timeout-graceful-shutdown` configured. Watch: Railway worker memory drift.
- **CRIT-MIGRATION-001 #796** (closed 2026-05-07) — 14 migrations unapplied in prod; migration-check CI failing. Mitigation: backfill + `supabase db push` + `repair --status applied`. Watch: memory `feedback_crit_050_silent_broken_during_drift`.
- **FOUND-CRIT-002 #862** (closed 2026-05-08) — Stripe success_url/cancel_url pointing at deprecated `/founding`. Mitigation: rewrite to `/fundadores`. Watch: ARQ lifetime checkout flow.
- **FOUND-CRIT-006 #866** (closed 2026-05-08) — webhook `checkout.session.completed` not handling `mode=payment` for founding (lifetime). Mitigation: branch on `mode`. Watch: idempotency + delivery-status null guards.

## Gap Closure to ≥95%

- AC1 baseline check shipped → +3% (Sentry FE coverage closed).
- AC2 dashboard surface in README → +2%.
- AC3 MTTR tooling + tests → +4% (was unmeasured).
- AC4 health probe + alert → +3%.
- AC5 (this report) → +2%.

Composite reaches ~95% post-merge; full validation in 7d after first MTTR rollup runs against real `railway logs` capture.
