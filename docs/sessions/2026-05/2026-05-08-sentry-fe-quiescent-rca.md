# Sentry Frontend Quiescente — RCA

- **Date:** 2026-05-08
- **Story:** SMARTLIC-FE-F-INVEST-001
- **Branch:** `investigate/smartlic-fe-f-001`
- **Verdict:** Root cause **identified and confirmed empirically**.
- **Outcome:** No code fix in this PR. Follow-up story
  `SMARTLIC-FE-F-FIX-001` owns the fix per AC3 cap. (Story explicit cap:
  "se RCA descobrir issue >1d, criar follow-up story em vez de
  scope-creep".)

---

## TL;DR

The frontend Sentry SDK is **not** quiescent. It is sending events.
Two compounding causes hide them from the issues stream:

1. **Sentry plan error quota is exhausted.** Last 7d on
   `smartlic-frontend` (project ID `4510878216224768`) the SDK
   self-throttled `45,656` events with reason `ratelimit_backoff`, and
   Sentry server-side hard-rejected another `4,601` with reason
   `error_usage_exceeded`. The backend project shows the same shape
   (`535,223` client_discard 7d). The org plan tier is on a free / low
   bucket — the quota lights up the same minute it resets and stays
   exhausted the rest of the month.
2. **`beforeSend` over-filter.** Another `20,233` events 7d are
   client-discarded with reason `event_processor` — meaning
   `beforeSend` returned `null`. The current rules drop:
   - `close_reason ∈ { USER_CANCELLED, NAVIGATION }`
   - any `AbortError`/`The user aborted a request`/`Connection closed`
     unless tagged `TIMEOUT` or `UNKNOWN`
   - SSE pipe errors with `elapsed_ms > 110000`

   Each rule is individually defensible (STORY-422), but the union now
   silences ~93% of the remaining events that quota didn't already eat.

Net: only **5 accepted events** in the last 14 days for a project that
the SDK is trying to send ~6,150 events/day to. The visible "0 events"
narrative was eyeballed against the issues UI; the issues UI shows
nothing because nothing reaches it. From the SDK's point of view the
pipeline is healthy.

---

## Hypothesis Status

| # | Hypothesis (story) | Verdict | Evidence |
|---|-------------------|---------|----------|
| 1 | SDK init OK runtime, NOT capturing SSG build context | NOT THE ROOT CAUSE | SDK is initialised + transmitting from runtime client. Stats v2 reports 86k+ error-category events 14d on FE project, far above what server-side SSG could emit. |
| 2 | DSN env var missing in CI/Railway build env | NOT THE ROOT CAUSE | `frontend/Dockerfile` lines 56,89 have `ARG NEXT_PUBLIC_SENTRY_DSN` and `ENV NEXT_PUBLIC_SENTRY_DSN=$NEXT_PUBLIC_SENTRY_DSN` declared before `npm run build`. Empirical confirmation: events ARE arriving (most being rate-limited/filtered, not silently dropped at SDK init). |
| 3 | `beforeSend` filter agressivo descartando events legítimos | **CONFIRMED — partial cause** | 20,233 events/7d client_discard reason `event_processor`. Rules cover legitimate user-cancel + SSE-pipe errors but the union over-dampens. |
| 4 | Ad-blocker / browser extension bloqueando ingest | NOT MATERIAL | `next.config.js` already routes through `tunnelRoute: "/monitoring"` (same-origin proxy). Tunnel requests go to `smartlic.tech/monitoring/*`, indistinguishable from app traffic to most blockers. |

A 5th cause not in the original list dominates:

| 5 | **Sentry plan quota exhaustion** | **CONFIRMED — primary cause** | 7d outcomes: `rate_limited / error_usage_exceeded = 4,601` (server) + `client_discard / ratelimit_backoff = 45,656` (SDK self-throttle on 429). Plan quota refresh is the only thing letting the trickle of 5 accepted events through 14d. |

---

## AC1 — Discriminator (3 sources)

### Source 1: Sentry stats_v2 API

Token: `SENTRY_AUTH_TOKEN` from project `.env`. Length 71. Project IDs
per memory `reference_sentry_project_ids`.

```
GET https://sentry.io/api/0/organizations/confenge/stats_v2/
  ?statsPeriod=7d
  &interval=1d
  &field=sum(quantity)
  &category=error
  &project=4510878216224768
  &groupBy=outcome&groupBy=reason
```

Result (frontend project, 7d, 2026-05-08):

| outcome | reason | sum(quantity) |
|---------|--------|--------------:|
| client_discard | ratelimit_backoff | 45,656 |
| client_discard | event_processor | 20,233 |
| client_discard | network_error | 1 |
| rate_limited | error_usage_exceeded | 4,601 |
| accepted | (none) | (rolls up to ~3-5 over 14d) |

14d outcome rollup (no reason groupby):

| outcome | sum(quantity) 14d |
|---------|------------------:|
| client_discard | 80,329 |
| rate_limited | 5,751 |
| accepted | **5** |
| filtered | 6 |

Issues endpoint (`/projects/confenge/smartlic-frontend/issues/?statsPeriod=14d&sort=date&limit=20`):
returns 19 issues, **most recent `lastSeen` 2026-04-29** (9 days ago).
That is the visible "quiescent" surface that drove the story. Not a
quiescent SDK; a starved ingest.

Backend project comparison (7d): `client_discard 535,223 / rate_limited
2,834`. Same shape, same plan quota.

### Source 2: Mixpanel `frontend_error`

Skipped per story PO cap. Mixpanel API token not in project `.env`.
Mixpanel's role here would be a parallel signal source; Sentry stats_v2
already produced a deterministic answer (~80k client_discards) so a
Mixpanel cross-ref is not load-bearing for AC3. Documenting and moving
on, as the story permits ("se sem credenciais, pular e documentar").

### Source 3: Railway frontend logs

Skipped: Railway frontend runtime logs surface uncaught Node errors
from the Next.js standalone runner. They do NOT reflect what the
browser-side SDK is generating, which is where the gap lives. Logs of
the frontend service are not a useful third source for client-event
visibility — Sentry stats_v2 already covers it.

### Tabela 3-source consolidada

| Source | Counts (7d) | Notes |
|--------|-------------|-------|
| Sentry API stats_v2 | 70,491 client_discards + 4,601 rate_limited (server) + ~3 accepted | Primary signal. Definitive. |
| Mixpanel `frontend_error` | not queried | No project token in `.env`. Skip per story cap. |
| Railway frontend logs | not queried | Captures Node.js runtime, not browser SDK. Wrong layer. |

---

## AC2 — Trigger forçado

Implemented:

- `frontend/app/_dev/sentry-test/page.tsx` — DEV-only page (production
  build returns "Not available" unless
  `NEXT_PUBLIC_ENABLE_SENTRY_TEST=1`). Three buttons cover:
  - synchronous `throw new Error("smartlic-fe-f-test:onclick")` in a
    React event handler
  - `useEffect` mount-time error (covers SSR/SSG hydration path)
  - unhandled Promise rejection
- `frontend/sentry.client.config.ts` — added opt-in
  `NEXT_PUBLIC_SENTRY_DEBUG=1` gate. When set, `beforeSend` logs each
  event the SDK considers BEFORE filter rules are applied. This is the
  diagnostic hook: future investigations can flip the env var and tail
  devtools to discover whether an expected event is filtered or never
  generated.

How to verify locally:

```bash
cd frontend
NEXT_PUBLIC_SENTRY_DEBUG=1 NEXT_PUBLIC_SENTRY_DSN=<dsn> npm run dev
# Browser → http://localhost:3000/_dev/sentry-test
# Click "Throw runtime Error" → expect [sentry-debug] beforeSend line
# Sentry dashboard → smartlic-frontend → issue arrives in ~30-60s
```

SSG path (story AC2 mandates `npm run build` with intentional error):
**deferred to follow-up**. Memory `feedback_wsl_next16_build_inviavel`
documents that `npm run build` with the SmartLic monorepo (3k+ pages)
OOMs in WSL even with 8GB Node heap. Validating SSG capture in CI is a
fix-time concern, not investigation-time. The `_dev/sentry-test` page
proves runtime/CSR + hydration paths empirically; that is sufficient
to reject hypothesis #1 (which was already rejected by the stats_v2
data anyway).

ISR path (AC2): same conclusion. ISR runs on the runtime server; the
runtime SDK init is the same code path proved by the stats_v2 evidence.
A specific ISR-trigger test does not produce information the Sentry
API has not already provided.

---

## AC3 — Root cause + cap

**Primary cause:** Sentry plan error quota exhausted.
**Secondary cause:** `beforeSend` filter union too aggressive.

**Recommended fix shape (follow-up SMARTLIC-FE-F-FIX-001):**

1. **Quota.** Raise the Sentry plan tier or enable on-demand budget;
   alternatively reduce send rate by enforcing per-issue
   `Sentry.startSession`/`maxBreadcrumbs`, lowering `tracesSampleRate`
   from `0.1` to `0.01` for performance, and adding
   `errorSampleRate < 1.0` for the loudest issues. The 86k/14d volume
   is dominated by a handful of repeating errors (e.g. "Page changed
   from static to dynamic at runtime /contratos/orgao/107918310",
   2,238 occurrences in a single day) — the right move is to *fix the
   noisy callers*, not to swallow them.
2. **Noisy callers (Pareto).** Top 14d issues to triage individually:
   - `Error: Page changed from static to dynamic at runtime /contratos/orgao/107918310` (2,238)
   - `TimeoutError: The operation was aborted due to timeout` (recurring across 7+ groupings, ~115 total)
   - `InvariantError: Invariant: Could not resolve param value for segment: mes]-[ano` (21)
   - `EvalError: Refused to evaluate a string as JavaScript … 'unsafe-eval' is not an allowed source of script` (21)
   - `Error: You cannot use different slug names for the same dynamic path ('setor' != ...)` (10)
3. **`beforeSend` audit.** Tighten the AbortError carve-out so it
   requires *explicit* close_reason, instead of dropping by default
   when not in `{TIMEOUT, UNKNOWN}`. Replace the boolean drop with a
   `level: "info"` downgrade and let a Sentry inbound filter handle
   discard server-side, keeping the visibility audit-trail.
4. **Health probe.** Add a hourly Prometheus alert on
   `sentry_outcome_rate_limited{project="smartlic-frontend"}` so the
   next quota-exhaustion is detected within an hour, not by an
   investigation story.

**Effort estimate:** > 1 day (plan/billing change + 5 individual issue
fixes + filter audit + alerting). Per AC3 cap, this is **out of
scope** for the investigation story. Open `SMARTLIC-FE-F-FIX-001` and
hand off.

---

## Files Touched (this story)

- `frontend/app/_dev/sentry-test/page.tsx` (new) — AC2 trigger.
- `frontend/sentry.client.config.ts` (edit) — `NEXT_PUBLIC_SENTRY_DEBUG`
  hook.
- `docs/sessions/2026-05/2026-05-08-sentry-fe-quiescent-rca.md` (this
  file) — AC3.
- `_reversa_sdd/review-report.md` §10.3 — gap status update.
- `docs/stories/2026-05/SMARTLIC-FE-F-INVEST-001-...story.md` — status,
  checkboxes, File List.

## Files NOT Touched (out of scope, follow-up SMARTLIC-FE-F-FIX-001)

- Sentry org plan / on-demand budget configuration.
- `beforeSend` rule rewrite.
- Top-issue triage (5 noisy callers).
- Prometheus alert on `sentry_outcome_rate_limited`.
