-- ============================================================================
-- Migration: 20260428100100_check_founding_availability_rpc
-- Story: BIZ-FOUND-002 — Founding Customer Canonical Policy (Gap-2)
-- Date: 2026-04-28
--
-- Purpose:
--   Creates public.check_founding_availability() — atomic, race-safe RPC
--   that decides whether the next /v1/founding/checkout (or webhook
--   re-check) can proceed.
--
--   Behaviour:
--     SELECT FOR UPDATE on the founding_policy row (id=1) so concurrent
--     callers serialize on the policy row. While holding the lock we count
--     COMPLETED founding_leads and compare against seat_limit, plus check
--     deadline_at vs NOW() and the active/paused flags.
--
--   Returns a single row {available, seats_remaining, seats_total,
--   deadline_at, paused, reason}. Reason is a stable enum the route + admin
--   UI can branch on without parsing free-form strings.
--
-- Reason enum:
--   'available'                  -> available=TRUE
--   'founding_cap_reached'       -> available=FALSE; cohort full
--   'founding_deadline_passed'   -> available=FALSE; NOW() > deadline_at
--   'founding_paused'            -> available=FALSE; paused_at IS NOT NULL
--   'founding_disabled'          -> available=FALSE; active=FALSE
--   'founding_policy_missing'    -> available=FALSE; row id=1 absent
-- ============================================================================

BEGIN;

-- Drop & recreate so re-applying the migration is idempotent. The function
-- signature is stable (no args, single OUT row).
DROP FUNCTION IF EXISTS public.check_founding_availability();

CREATE FUNCTION public.check_founding_availability()
RETURNS TABLE (
    available           BOOLEAN,
    seats_remaining     INT,
    seats_total         INT,
    deadline_at         TIMESTAMPTZ,
    paused              BOOLEAN,
    reason              TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_seat_limit       INT;
    v_deadline         TIMESTAMPTZ;
    v_active           BOOLEAN;
    v_paused_at        TIMESTAMPTZ;
    v_completed_count  INT;
BEGIN
    -- SELECT FOR UPDATE serializes concurrent callers on the policy row.
    -- After this lock, two parallel checkouts always see a consistent
    -- (count, decision) pair — race guard for the cap.
    SELECT
        seat_limit,
        deadline_at,
        active,
        paused_at
    INTO
        v_seat_limit,
        v_deadline,
        v_active,
        v_paused_at
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
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.check_founding_availability() IS
    'BIZ-FOUND-002: race-safe availability check for the founding cohort. '
    'Acquires SELECT FOR UPDATE on founding_policy row before counting '
    'completed founding_leads. Returns single row {available, '
    'seats_remaining, seats_total, deadline_at, paused, reason}. '
    'Called by POST /v1/founding/checkout (gate) and the checkout webhook '
    '(race guard before activating).';

-- Service role and authenticated execute. Anon needs it for the public
-- availability endpoint that powers the landing-page seat counter.
GRANT EXECUTE ON FUNCTION public.check_founding_availability()
    TO service_role, authenticated, anon;

NOTIFY pgrst, 'reload schema';

COMMIT;
