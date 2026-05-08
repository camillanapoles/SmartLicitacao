-- ============================================================================
-- Migration: 20260507140000_fix_founding_availability_ambiguous_column
-- Hotfix for BIZ-FOUND-002: PG 42702 — column reference "deadline_at" is
-- ambiguous between the RETURNS TABLE out-param and the founding_policy
-- table column in the SELECT ... INTO statement.
-- Fix: use table alias `fp` to qualify the column in the SELECT list.
-- ============================================================================

BEGIN;

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
    -- Table alias avoids 42702 ambiguity between the RETURNS TABLE out-param
    -- "deadline_at" and the founding_policy column of the same name.
    SELECT
        fp.seat_limit,
        fp.deadline_at,
        fp.active,
        fp.paused_at,
        fp.offer_mode,
        fp.price_brl_cents
    INTO
        v_seat_limit,
        v_deadline,
        v_active,
        v_paused_at,
        v_offer_mode,
        v_price_brl_cents
    FROM public.founding_policy fp
    WHERE fp.id = 1
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

GRANT EXECUTE ON FUNCTION public.check_founding_availability()
    TO service_role, authenticated, anon;

NOTIFY pgrst, 'reload schema';

COMMIT;
