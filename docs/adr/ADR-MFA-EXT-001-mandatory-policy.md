# ADR-MFA-EXT-001 — MFA Mandatory Policy Extension

**Status:** Accepted
**Date:** 2026-04-28
**Context Story:** [`MFA-EXT-001`](../stories/2026-04/MFA-EXT-001-consultoria-mandatory-and-bruteforce-trigger.story.md)
**Companion:** STORY-317 (TOTP enrollment + admin/master enforcement, Done)

## Context

STORY-317 shipped TOTP MFA with admin/master enforcement only. Reversa Audit
Gap-4 plus a 2026-04-27 CTO decision identified two policy gaps:

1. **Plan-based enforcement.** Plano Consultoria (R$ 997/mês) targets B2B
   buyers who expect enterprise-grade compliance (LGPD + SOC2-leve);
   opt-in MFA is not credible.
2. **Brute-force signal.** A run of failed logins is an attacker tell,
   but the existing rate limiter only throttles — it does not raise the
   subsequent auth bar.

We need both to ride on the existing `require_mfa` middleware so we
don't fork the auth surface area.

## Decision

### 1. Two new enforcement triggers in `require_mfa`

```
enforce_mfa = is_admin
            OR is_master
            OR plan_type == 'consultoria'             # NEW
            OR force_mfa_enrollment_until > NOW()     # NEW
```

A single 403 is raised when `enforce_mfa AND not aal2`. The 403 carries
two response headers:

* `X-MFA-Required: true` (legacy, kept for STORY-317 compat)
* `X-MFA-Reason: admin | consultoria | bruteforce` (new — frontend
  picks banner variant)

Precedence is `admin > consultoria > bruteforce`. Reason is suppressed
once the user has a verified MFA factor and an `aal2` JWT.

### 2. New column `profiles.force_mfa_enrollment_until TIMESTAMPTZ`

Two writers:

* **Consultoria backfill** (migration `20260428100400`): existing
  consultoria users without MFA receive `NOW() + 14d`. New consultoria
  upgrades will get the same window from the upgrade webhook in a
  follow-up story (out of scope here — the column + middleware are the
  durable contract).
* **Bruteforce trigger** (`POST /v1/auth/login-attempt`): on the
  transition `consecutive_failures: 2 -> 3`, set `NOW() + 7d`.

### 3. New table `auth_attempts` (migration `20260428100500`)

Per-user counter with `consecutive_failures`, `last_failure_at`,
`last_success_at`. Reset on:

* **Successful login** — endpoint upserts `consecutive_failures = 0`.
* **24h idle** — both runtime check (in the endpoint, before
  incrementing) and a daily cron in `jobs/cron/auth_cleanup.py`.

Service-role only access; RLS denied for `authenticated` and `anon`.

### 4. New endpoint `POST /v1/auth/login-attempt`

Frontend `AuthProvider.signInWithEmail` calls this fire-and-forget after
every Supabase `signInWithPassword`, posting `{email, success}`.

The endpoint is **unauthenticated by design** — failures happen before
a session exists. This is a deliberate trade-off, mitigated by:

* **No user-existence oracle.** Unknown emails return the same
  `200 {ok: true, force_mfa_triggered: false}` as known emails. We use
  service-role admin SDK to map email->user_id; on miss, silent no-op.
* **Rate-limited.** Reuses `AUTH_RATE_LIMIT_PER_5MIN` (5 req / 5 min /
  IP) — same throttle as `/auth/check-email`.
* **Trust model accepted.** A self-reporting attacker can claim
  `success=true` to reset their own counter, but they gain nothing —
  bypassing the brute-force shield only matters if they could already
  authenticate, in which case the shield wasn't needed.

The endpoint never reflects state back: no "you have 1 attempt left"
hints, no email-existence delta.

### 5. Daily cron `jobs/cron/auth_cleanup.py`

Two cleanup steps run together every 24 h:

1. Reset `consecutive_failures = 0` for rows where
   `last_failure_at < NOW() - 24h`. Belt-and-braces: the runtime path
   already does this on the next attempt; the cron handles users who
   never come back.
2. Clear `profiles.force_mfa_enrollment_until` once it's in the past.
   Without this, a user who blew through the 7-day window stays
   permanently hard-blocked — defeating the **deadline** semantic.

### 6. Frontend `MfaEnforcementBanner` reads `/v1/mfa/status`

The banner now consults the backend (single source of truth) and
renders one of three text variants based on `enforce_reason`:

* `admin` — "MFA obrigatório para sua conta..." (existing copy)
* `consultoria` — "Plano Consultoria requer MFA — configure em N dias"
* `bruteforce` — "Detectamos tentativas suspeitas..."

Countdown comes from `grace_days_remaining` (computed server-side from
`force_mfa_enrollment_until`). Falls back to the legacy Supabase-direct
listFactors() probe if the proxy fails (admin variant only) so banner
still renders during transient backend outages.

## Consequences

### Positive

* **One code path.** All new triggers ride `require_mfa`; no new
  middleware, no new decorators on routes. STORY-317 callers keep
  working unchanged.
* **Observable.** Sentry warning `auth.bruteforce.mfa_forced` fires
  with `fingerprint=["auth.bruteforce.mfa_forced", user_id]` so a
  single user's repeated trips dedupe to one issue instead of flooding.
* **Async-safe.** All new DB calls go through `sb_execute`
  (`asyncio.to_thread` wrapper). The 2026-04-27 prod outage was rooted
  in sync `.execute()` inside async handlers — we explicitly avoid
  recreating that footgun in `auth.py`.
* **Reversible.** Both migrations have idempotent `.down.sql`. The
  feature degrades gracefully: if `auth_attempts` is unreachable we log
  and pass through (we never want the brute-force shield to *cause*
  outages).

### Negative

* **The login-attempt endpoint is unauthenticated.** A self-reporting
  attacker can lie about outcomes. Mitigation documented above; net
  attacker value remains zero.
* **`plan_type='consultoria'` is the canonical schema value.** Story
  doc references `'smartlic_consultoria'` — they collide because the
  story author tracked Stripe product naming, not the DB constraint
  added in `20260301300000_consultoria_stripe_ids.sql`. We match the
  schema. If billing ever introduces a separate `smartlic_consultoria`
  variant, both literals would need to be added to the trigger
  predicate.
* **Brute-force threshold = 3 is a UX/security tradeoff.** Industry
  ranges from 3 (NIST SP 800-63B "high assurance") to 10 (account
  lockout). 3 favors security on a security-product surface; 24 h idle
  reset and clear messaging mitigate the "I forgot my password"
  failure mode.
* **Hard-block after window expires (Story AC10) deferred.** The 403
  from `require_mfa` already produces hard-block on protected routes.
  A dedicated "Enrollment expirou" modal is a follow-up; current
  behavior gates user access without a custom modal.

### Neutral

* **No password verification webhook.** Supabase's
  `password-verification-attempt` Auth Hook (preview) would let the
  backend track failures without a frontend callback. We use the
  callback approach because (a) Auth Hook config + HMAC verify isn't
  in DoD, (b) the callback works locally without Supabase dashboard
  access. A swap to Auth Hooks is a transparent migration when ready.

## Alternatives Considered

| Alternative | Rejected because |
|---|---|
| New `require_mfa_strict` middleware | Doubles the auth surface; routes already on `require_mfa` would silently miss the new triggers. |
| Track failures in Redis (TTL-based) | Loses the audit trail that `auth_attempts` provides; cron cleanup story stops working. |
| Threshold = 5 | Five fails is far enough into "definitely under attack" that the bar should be higher than just rate-limiting. NIST recommends ≤ 5; 3 leaves margin. |
| Webhook-based Supabase Auth hook | Requires dashboard config + HMAC verify infra not yet in place; also adds dependence on a beta Supabase feature. Defer until both are stable. |
| Permanent ban after threshold | Violates the "deadline, not punishment" semantic — users who legitimately forgot their password and never come back would be unable to recover without support. |

## Verification

| Check | Mechanism |
|---|---|
| Consultoria + no MFA -> 403 reason=consultoria | `tests/test_mfa_consultoria_enforcement.py::test_consultoria_without_mfa_is_blocked` |
| 3 consecutive 401 -> force_mfa flag set | `tests/test_auth_attempts_bruteforce.py::test_three_failures_trigger_force_mfa` |
| Counter resets on success | `tests/test_auth_attempts_bruteforce.py::test_success_resets_counter` |
| 24h idle reset | `tests/test_auth_attempts_bruteforce.py::test_idle_24h_reset_counter` |
| No re-fire on repeat | `tests/test_auth_attempts_bruteforce.py::test_threshold_does_not_re_fire_when_already_at_3` |
| Cron resets stale rows | `tests/test_mfa_extended_policy.py::test_cron_resets_stale_auth_attempts` |
| Cron clears expired force_mfa | `tests/test_mfa_extended_policy.py::test_cron_clears_expired_force_mfa` |
| Frontend banner variants | `frontend/__tests__/auth/mfa-flow.test.tsx::MfaEnforcementBanner` (extended) |

## References

* STORY-317 — TOTP MFA enrollment + admin/master enforcement (Done).
* `_reversa_sdd/review-report.md` Gap-4 — auth coverage gaps.
* NIST SP 800-63B Section 5.2.2 — Memorized Secret Verifiers (rate
  limits + step-up).
* OWASP ASVS 4.0 V2.2.3 — Anti-Automation Controls.
