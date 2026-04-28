# ADR — BIZ-FOUND-002: Founding Customer Canonical Policy

- **Status:** Accepted
- **Date:** 2026-04-28
- **Story:** [`docs/stories/2026-04/BIZ-FOUND-002-founding-canonical-policy.story.md`](../stories/2026-04/BIZ-FOUND-002-founding-canonical-policy.story.md)
- **Source gap:** `_reversa_sdd/review-report.md` — Gap-2 (Founding plan details).
- **Related stories:** STORY-BIZ-001 (Founding customer Stripe coupon — Done).

## Context

STORY-BIZ-001 shipped the `/founding` landing page + `POST /v1/founding/checkout` route with a `FOUNDING30` Stripe coupon (30% off / 12 months / first-transaction restriction, 10 uses). The story did **not** fix the canonical policy — there was no DB-backed cap, no deadline, no race guard, no admin UI, and no documented commitment on lifetime pricing. Reversa Audit flagged this as Gap-2: "pricing? deadline? cap (early-adopter limitada)?".

We need a single source of truth for:

1. How many founding seats exist (fixed cap).
2. Until when checkouts are accepted (deadline).
3. What discount founders keep (lifetime, not promotional).
4. Who can pause/resume the program operationally.
5. How concurrent checkouts are prevented from over-selling the cohort.

## Decision

Adopt a **single-row canonical policy table** + **race-safe RPC** + **post-completion webhook re-check**.

### Canonical numbers

| Setting       | Value                       | Rationale |
|---------------|-----------------------------|-----------|
| Seat cap      | **50**                      | 5x the original 10-seat cap from STORY-BIZ-001 — gives runway through the deadline window without diluting the "founder" relationship (still small enough that I, as founder, can do every onboarding 1:1). |
| Deadline      | **2026-05-30 23:59:59 -03:00** | 32 days from story start. Hard cutoff; the "we're committing to a date" forcing function is what makes early-adopter pricing credible. |
| Discount      | **50% off forever**         | Replaces the 30% / 12-month STORY-BIZ-001 default. Lifetime is the right ergonomic promise for founding partners — it removes the "what happens in month 13?" anxiety and aligns founder LTV with company LTV. |
| Coupon id     | `FOUNDING_LIFETIME`         | Stripe coupon, `percent_off=50`, `duration='forever'`, no `restrictions.first_time_transaction`. |
| Pause toggle  | `paused_at`/`paused_by`     | Operational kill switch (rate-limit, fraud, capacity issue) without flipping the structural `active` flag. |

### Storage

```sql
CREATE TABLE public.founding_policy (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- single-row
    seat_limit INT NOT NULL,
    deadline_at TIMESTAMPTZ NOT NULL,
    discount_pct INT NOT NULL,
    coupon_code TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    paused_at TIMESTAMPTZ,
    paused_by UUID REFERENCES auth.users(id),
    paused_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

Single-row enforcement (`id = 1` CHECK) means cap-counting code never has to disambiguate versions.

### Cap counting basis — **founding_leads.checkout_status='completed'**

The existing flow activates founding subscribers as `profiles.plan_type='smartlic_pro'` (priced via Stripe coupon). `profiles.plan_type` is now an FK to `plans.id` (DEBT-05, migration 20260408230000), and we don't want to introduce a `'founding'` plan row just for cap counting — that would couple billing taxonomy to cohort marketing.

Instead, we count `founding_leads WHERE checkout_status='completed'`. The lead row is the canonical signal that someone went through the founding-specific funnel; counting it keeps the cohort decoupled from the billing plan.

**Trade-off:** if a founding lead row is deleted (LGPD, accidental admin), the count drops and the cap can be over-shot via subsequent checkouts. Mitigated by: (a) RLS lets only service-role mutate `founding_leads`; (b) admin endpoints read-only (no delete); (c) operator manual review before any retention-driven delete.

### Race guard — two layers

**Layer 1 (pre-checkout):** `check_founding_availability()` RPC takes `SELECT FOR UPDATE` on the `founding_policy` row + `COUNT(founding_leads WHERE checkout_status='completed')` in one PL/pgSQL transaction. Concurrent callers serialize on the row lock so the (count, decision) pair is consistent.

**Layer 2 (post-completion):** The Stripe `checkout.session.completed` webhook re-runs the RPC AFTER flipping the lead row to `completed`. If the RPC reports `founding_cap_reached`, the handler:
1. Sets `checkout_status='cap_violated'` (new enum value).
2. Issues a Stripe `Refund` against the `payment_intent`.
3. Queues an apology email to the customer.
4. Logs `level=error` so Sentry alerts the operator.

The webhook only refunds on `founding_cap_reached`. Other `available=false` reasons (paused, deadline, disabled, missing) trigger a `level=warning` log but **never** a refund — those are structural changes that are operator's responsibility to communicate, not race conditions.

### API surface

| Method | Path                              | Auth     | Purpose |
|--------|-----------------------------------|----------|---------|
| GET    | `/v1/founding/availability`       | Public   | Seat counter + countdown feed for landing page. |
| POST   | `/v1/founding/checkout`           | Public   | Existing route — now gates on RPC and returns 410 + `error_code` when unavailable. |
| GET    | `/v1/admin/founding/policy`       | Admin    | Snapshot of policy + live seat usage. |
| GET    | `/v1/admin/founding/leads`        | Admin    | List founding leads with filter/pagination. |
| POST   | `/v1/admin/founding/pause`        | Admin    | Soft-pause checkouts. |
| POST   | `/v1/admin/founding/resume`       | Admin    | Clear pause. |

### Frontend changes

- `frontend/app/founding/page.tsx` (landing): added countdown timer to deadline, X/50 seat counter, CTA disabled when `available=false`. Body copy refreshed for new policy (50 vagas, 50% off vitalício).
- `frontend/app/admin/founding/page.tsx` (admin): progress bar, lead list, pause/resume toggle.

## Consequences

### Positive

- **Clear contractual commitment.** "50 vagas, 50% off vitalício, até 30/05" is unambiguous.
- **Race-safe by construction.** `SELECT FOR UPDATE` + post-completion re-check is the standard pattern for fixed-cap inventory.
- **Operator override available.** Pause/resume without DB access.
- **Decoupled from billing plan.** Counting via `founding_leads` keeps `plans` table clean.

### Negative / risks

- **`founding_leads` deletion is now load-bearing.** Documented above; mitigated by RLS + admin no-delete, but the operator must understand this when running LGPD scripts.
- **Stripe coupon migration.** The old `FOUNDING30` coupon stays valid in Stripe (Stripe doesn't delete coupons attached to past subscriptions); new sign-ups use `FOUNDING_LIFETIME`. The `.env` default flipped from `FOUNDING30` to `FOUNDING_LIFETIME`. Operator must run `python scripts/create_founding_lifetime_coupon.py` once per environment before deploy. The coupon is provisioned out-of-band (not in code) because Stripe is the authoritative source for coupon configuration.
- **No grandfathering of in-flight 30%-off carts.** Customers who left a `pending` cart from STORY-BIZ-001 days will, on retry, find it expired and need to re-checkout against the new coupon. Acceptable because: (a) the new discount is better for the customer, (b) cart abandonment beyond 24h is already stale.

### Operational

- Monitoring: existing `webhooks.handlers.founding` logs go to Sentry. Add to runbook: `founding race guard: CAP VIOLATION DETECTED` + `REFUND FAILED` are P1-level alerts.
- Alerts on stuck `pending` rows: out of scope here; consider STORY-BIZ-003 if the manual review SLA slips.

## Alternatives considered

1. **Per-row `is_founding` flag on `profiles`.** Rejected: would require touching 1.6M existing profile rows just for a 50-row signal; counting via `founding_leads` is the same source of truth as the conversion funnel.
2. **Separate `founding_seats` ledger table.** Rejected: redundant with `founding_leads` once we adopt completed-leads as the cap signal.
3. **Stripe-only cap (use coupon `max_redemptions=50`).** Rejected: doesn't enforce our deadline, doesn't pause, doesn't surface seat counter on the landing page without a Stripe API roundtrip per page load.
4. **Optimistic concurrency (count + insert + recount + revert if mismatch).** Rejected: harder to reason about than `SELECT FOR UPDATE` and the lock duration is bounded (millisecond-scale at our volume).

## References

- Migration up: [`supabase/migrations/20260428100000_founding_canonical_policy.sql`](../../supabase/migrations/20260428100000_founding_canonical_policy.sql)
- Migration down: [`supabase/migrations/20260428100000_founding_canonical_policy.down.sql`](../../supabase/migrations/20260428100000_founding_canonical_policy.down.sql)
- RPC up: [`supabase/migrations/20260428100100_check_founding_availability_rpc.sql`](../../supabase/migrations/20260428100100_check_founding_availability_rpc.sql)
- RPC down: [`supabase/migrations/20260428100100_check_founding_availability_rpc.down.sql`](../../supabase/migrations/20260428100100_check_founding_availability_rpc.down.sql)
- Coupon provisioner: [`scripts/create_founding_lifetime_coupon.py`](../../scripts/create_founding_lifetime_coupon.py)
- Reversa source: `_reversa_sdd/review-report.md` Gap-2; `_reversa_sdd/sm-briefing.md` §2.4.
