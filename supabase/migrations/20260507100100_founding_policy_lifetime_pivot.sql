-- ============================================================================
-- Migration: 20260507100100_founding_policy_lifetime_pivot
-- Story: BIZ-FOUND-002 v2 — Pivot founding to one-time lifetime R$997
-- Date: 2026-05-07
--
-- Purpose:
--   Pivots the founding policy from a subscription model to a one-time
--   lifetime purchase at R$997 (99700 cents) with:
--     * offer_mode = 'lifetime'           (replaces subscription model)
--     * price_brl_cents = 99700           (R$997 one-time)
--     * consulting_discount_pct = 50      (50% off consulting tier forever)
--     * deadline_at extended to 2026-06-30 23:59:59-03:00
--
--   Updates check_founding_availability() RPC to return the new columns
--   offer_mode and price_brl_cents so the frontend can render the correct
--   pricing copy without extra queries.
--
-- Down migration: 20260507100100_founding_policy_lifetime_pivot.down.sql
-- ============================================================================

BEGIN;

-- Add new columns to founding_policy (idempotent via IF NOT EXISTS).
ALTER TABLE public.founding_policy
    ADD COLUMN IF NOT EXISTS offer_mode TEXT NOT NULL DEFAULT 'lifetime'
        CHECK (offer_mode IN ('subscription', 'lifetime'));

ALTER TABLE public.founding_policy
    ADD COLUMN IF NOT EXISTS price_brl_cents INT NOT NULL DEFAULT 99700;

ALTER TABLE public.founding_policy
    ADD COLUMN IF NOT EXISTS consulting_discount_pct INT NOT NULL DEFAULT 50
        CHECK (consulting_discount_pct BETWEEN 0 AND 100);

-- Update comments for new columns.
COMMENT ON COLUMN public.founding_policy.offer_mode IS
    'BIZ-FOUND-002 v2: offer type — lifetime (one-time payment) or subscription.';

COMMENT ON COLUMN public.founding_policy.price_brl_cents IS
    'BIZ-FOUND-002 v2: price in BRL cents for one-time lifetime offer. 99700 = R$997.';

COMMENT ON COLUMN public.founding_policy.consulting_discount_pct IS
    'BIZ-FOUND-002 v2: lifetime discount % on consulting tier for founding members. Default 50%.';

-- Update canonical policy row id=1 with new deadline and lifetime values.
UPDATE public.founding_policy
SET
    deadline_at           = '2026-06-30T23:59:59-03:00'::TIMESTAMPTZ,
    offer_mode            = 'lifetime',
    price_brl_cents       = 99700,
    consulting_discount_pct = 50
WHERE id = 1;

-- ============================================================================
-- Recreate check_founding_availability() RPC with 2 extra return columns.
-- DROP + CREATE is idempotent; the new signature includes offer_mode and
-- price_brl_cents so callers get pricing info in one atomic call.
-- ============================================================================

DROP FUNCTION IF EXISTS public.check_founding_availability();

CREATE FUNCTION public.check_founding_availability()
RETURNS TABLE (
    available           BOOLEAN,
    seats_remaining     INT,
    seats_total         INT,
    deadline_at         TIMESTAMPTZ,
    paused              BOOLEAN,
    reason              TEXT,
    offer_mode          TEXT,
    price_brl_cents     INT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_seat_limit           INT;
    v_deadline             TIMESTAMPTZ;
    v_active               BOOLEAN;
    v_paused_at            TIMESTAMPTZ;
    v_completed_count      INT;
    v_offer_mode           TEXT;
    v_price_brl_cents      INT;
BEGIN
    -- SELECT FOR UPDATE serializes concurrent callers on the policy row.
    -- After this lock, two parallel checkouts always see a consistent
    -- (count, decision) pair — race guard for the cap.
    SELECT
        seat_limit,
        deadline_at,
        active,
        paused_at,
        offer_mode,
        price_brl_cents
    INTO
        v_seat_limit,
        v_deadline,
        v_active,
        v_paused_at,
        v_offer_mode,
        v_price_brl_cents
    FROM public.founding_policy
    WHERE id = 1
    FOR UPDATE;

    IF NOT FOUND THEN
        available       := FALSE;
        seats_remaining := 0;
        seats_total     := 0;
        deadline_at     := NULL;
        paused          := FALSE;
        reason          := 'founding_policy_missing';
        offer_mode      := 'lifetime';
        price_brl_cents := 99700;
        RETURN NEXT;
        RETURN;
    END IF;

    -- Hard kill switch (structural disable).
    IF NOT v_active THEN
        available       := FALSE;
        seats_remaining := 0;
        seats_total     := v_seat_limit;
        deadline_at     := v_deadline;
        paused          := v_paused_at IS NOT NULL;
        reason          := 'founding_disabled';
        offer_mode      := v_offer_mode;
        price_brl_cents := v_price_brl_cents;
        RETURN NEXT;
        RETURN;
    END IF;

    -- Soft pause from admin UI (operational disable).
    IF v_paused_at IS NOT NULL THEN
        available       := FALSE;
        seats_remaining := 0;
        seats_total     := v_seat_limit;
        deadline_at     := v_deadline;
        paused          := TRUE;
        reason          := 'founding_paused';
        offer_mode      := v_offer_mode;
        price_brl_cents := v_price_brl_cents;
        RETURN NEXT;
        RETURN;
    END IF;

    -- Deadline passed.
    IF NOW() > v_deadline THEN
        available       := FALSE;
        seats_remaining := 0;
        seats_total     := v_seat_limit;
        deadline_at     := v_deadline;
        paused          := FALSE;
        reason          := 'founding_deadline_passed';
        offer_mode      := v_offer_mode;
        price_brl_cents := v_price_brl_cents;
        RETURN NEXT;
        RETURN;
    END IF;

    -- Count completed founding_leads (canonical cap signal).
    SELECT COUNT(*)::INT
    INTO v_completed_count
    FROM public.founding_leads
    WHERE checkout_status = 'completed';

    IF v_completed_count >= v_seat_limit THEN
        available       := FALSE;
        seats_remaining := 0;
        seats_total     := v_seat_limit;
        deadline_at     := v_deadline;
        paused          := FALSE;
        reason          := 'founding_cap_reached';
        offer_mode      := v_offer_mode;
        price_brl_cents := v_price_brl_cents;
        RETURN NEXT;
        RETURN;
    END IF;

    -- Available path.
    available       := TRUE;
    seats_remaining := v_seat_limit - v_completed_count;
    seats_total     := v_seat_limit;
    deadline_at     := v_deadline;
    paused          := FALSE;
    reason          := 'available';
    offer_mode      := v_offer_mode;
    price_brl_cents := v_price_brl_cents;
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.check_founding_availability() IS
    'BIZ-FOUND-002 v2: race-safe availability check for the founding cohort. '
    'Acquires SELECT FOR UPDATE on founding_policy row before counting '
    'completed founding_leads. Returns single row {available, '
    'seats_remaining, seats_total, deadline_at, paused, reason, '
    'offer_mode, price_brl_cents}. '
    'Called by POST /v1/founding/checkout (gate) and the checkout webhook '
    '(race guard before activating). Also used by GET /v1/founding/availability '
    'to expose pricing copy to the landing page.';

-- Restore grants (DROP + CREATE resets them).
GRANT EXECUTE ON FUNCTION public.check_founding_availability()
    TO service_role, authenticated, anon;

NOTIFY pgrst, 'reload schema';

COMMIT;
