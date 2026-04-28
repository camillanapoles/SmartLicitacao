-- ============================================================================
-- Migration: 20260428100000_founding_canonical_policy
-- Story: BIZ-FOUND-002 — Founding Customer Canonical Policy (Gap-2)
-- Date: 2026-04-28
--
-- Purpose:
--   Materializes the canonical policy for the SmartLic founding cohort:
--     * cap = 50 seats total
--     * deadline = 2026-05-30 23:59:59 -03:00
--     * lifetime pricing = 50% off forever (Stripe coupon FOUNDING_LIFETIME)
--     * admin pause/resume toggle (paused_at + paused_by)
--
--   Single-row enforcement (id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1))
--   guarantees there is one and only one canonical policy row, so the cap-
--   counting RPC + admin endpoints never have to disambiguate between
--   versions.
--
-- Cap counting basis:
--   Counts COMPLETED founding_leads (checkout_status='completed') instead of
--   profiles.plan_type='founding'. The existing /v1/founding/checkout flow
--   activates founding subscribers as plan_type='smartlic_pro' (priced via
--   Stripe coupon), so the founding-cohort signal lives in founding_leads.
--   Documented in docs/adr/ADR-BIZ-FOUND-002-founding-policy.md.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.founding_policy (
    id              INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    seat_limit      INT NOT NULL CHECK (seat_limit > 0),
    deadline_at     TIMESTAMPTZ NOT NULL,
    discount_pct    INT NOT NULL CHECK (discount_pct > 0 AND discount_pct < 100),
    coupon_code     TEXT NOT NULL,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    paused_at       TIMESTAMPTZ,
    paused_by       UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    paused_reason   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.founding_policy IS
    'BIZ-FOUND-002: canonical policy for SmartLic founding cohort. '
    'Single-row table (id=1 enforced via CHECK). Cap counts completed '
    'founding_leads — see check_founding_availability() RPC.';

COMMENT ON COLUMN public.founding_policy.seat_limit IS
    'Hard cap for founding seats. 50 per BIZ-FOUND-002 ADR. Updates require admin.';

COMMENT ON COLUMN public.founding_policy.deadline_at IS
    'Cutoff after which checkout is rejected with 410 Gone. 2026-05-30 23:59:59-03:00.';

COMMENT ON COLUMN public.founding_policy.discount_pct IS
    'Lifetime discount in percent (50). Mirrors Stripe coupon for audit only — Stripe is source of truth.';

COMMENT ON COLUMN public.founding_policy.coupon_code IS
    'Stripe coupon id (FOUNDING_LIFETIME). Set up via scripts/create_founding_lifetime_coupon.py.';

COMMENT ON COLUMN public.founding_policy.active IS
    'Hard kill switch. FALSE => block all checkouts even before cap/deadline.';

COMMENT ON COLUMN public.founding_policy.paused_at IS
    'Soft pause toggle from admin UI. Distinct from active=false (operational vs structural disable).';

-- Seed canonical policy row (idempotent; never overwrites operator changes).
INSERT INTO public.founding_policy
    (id, seat_limit, deadline_at, discount_pct, coupon_code, active)
VALUES
    (1, 50, '2026-05-30T23:59:59-03:00'::TIMESTAMPTZ, 50, 'FOUNDING_LIFETIME', TRUE)
ON CONFLICT (id) DO NOTHING;

-- updated_at autotrigger (mirrors pattern used elsewhere — see organizations).
CREATE OR REPLACE FUNCTION public.founding_policy_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS founding_policy_updated_at ON public.founding_policy;
CREATE TRIGGER founding_policy_updated_at
    BEFORE UPDATE ON public.founding_policy
    FOR EACH ROW
    EXECUTE FUNCTION public.founding_policy_set_updated_at();

-- RLS: read = anyone (public availability counter on landing page is anonymous);
-- write = service-role only (admin endpoint goes through service_role).
ALTER TABLE public.founding_policy ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "founding_policy_public_read" ON public.founding_policy;
CREATE POLICY "founding_policy_public_read" ON public.founding_policy
    FOR SELECT
    USING (TRUE);

DROP POLICY IF EXISTS "founding_policy_service_write" ON public.founding_policy;
CREATE POLICY "founding_policy_service_write" ON public.founding_policy
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Helpful counted index for the cap query inside check_founding_availability().
-- Partial index on completed leads only — keeps it tiny (max 50 entries by design).
CREATE INDEX IF NOT EXISTS idx_founding_leads_completed
    ON public.founding_leads (created_at)
    WHERE checkout_status = 'completed';

-- Extend founding_leads.checkout_status CHECK to include 'cap_violated'.
-- Webhook race guard sets this status when a checkout completes after the
-- cap was already reached. Drop + re-add is idempotent and avoids the
-- "duplicate constraint" error if the migration is re-applied.
ALTER TABLE public.founding_leads
    DROP CONSTRAINT IF EXISTS founding_leads_checkout_status_check;

ALTER TABLE public.founding_leads
    ADD CONSTRAINT founding_leads_checkout_status_check
    CHECK (checkout_status IN ('pending', 'completed', 'abandoned', 'failed', 'cap_violated'));

NOTIFY pgrst, 'reload schema';

COMMIT;
