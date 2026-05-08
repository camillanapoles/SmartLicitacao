-- DOWN: 20260507140000_fix_founding_availability_ambiguous_column
-- Restores check_founding_availability() to the broken v2 state (pre-hotfix).
-- Only use to roll back this specific fix — not intended for normal use.

BEGIN;

DROP FUNCTION IF EXISTS public.check_founding_availability();

-- Restore verbatim from 20260507100100 (the broken version with ambiguous deadline_at).
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

    available := FALSE;
    seats_remaining := 0;
    seats_total := 0;
    deadline_at := NULL;
    paused := FALSE;
    reason := 'founding_disabled';
    offer_mode := 'lifetime';
    price_brl_cents := 99700;
    RETURN NEXT;
END;
$$;

GRANT EXECUTE ON FUNCTION public.check_founding_availability()
    TO service_role, authenticated, anon;

NOTIFY pgrst, 'reload schema';

COMMIT;
