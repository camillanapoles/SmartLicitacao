-- ============================================================================
-- FIX: cleanup-stripe-webhooks pg_cron — batched deletion
-- Context: Sentry SMARTLIC-BACKEND-NH | 47x | cleanup-stripe-webhooks
--          last_status=failed (lock contention / timeout on single-shot DELETE)
-- Root cause: Single unbounded DELETE FROM stripe_webhook_events WHERE
--             processed_at < now() - 90d holds row locks on all matching rows
--             simultaneously, causing contention with concurrent webhook
--             INSERTs and/or hitting statement_timeout as the table grows.
-- Fix: Replace single DELETE with a batched PL/pgSQL function that deletes
--      1000 rows at a time with a 100ms pause between batches.
-- AC1: CREATE OR REPLACE FUNCTION cleanup_old_stripe_events(p_retention_days, p_batch_size)
-- AC2: Reschedule cleanup-stripe-webhooks to call the new function
-- AC3: Zero downtime — existing rows in cron.job don't block function creation
-- ============================================================================

-- ════════════════════════════════════════════════════════════════════════════
-- AC1: Batched cleanup function
-- ════════════════════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION public.cleanup_old_stripe_events(
    p_retention_days INTEGER DEFAULT 90,
    p_batch_size INTEGER DEFAULT 1000
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_deleted INTEGER;
    v_total INTEGER := 0;
    v_cutoff TIMESTAMPTZ;
BEGIN
    -- Input validation
    IF p_retention_days < 1 THEN
        RAISE EXCEPTION 'p_retention_days must be >= 1, got: %', p_retention_days;
    END IF;
    IF p_batch_size < 1 OR p_batch_size > 10000 THEN
        RAISE EXCEPTION 'p_batch_size must be between 1 and 10000, got: %', p_batch_size;
    END IF;

    v_cutoff := now() - (p_retention_days || ' days')::INTERVAL;

    -- Batched deletion: each iteration deletes up to p_batch_size rows
    -- using ordered subquery (oldest first) for index-friendliness.
    -- The 100ms sleep reduces lock pressure on the table.
    LOOP
        DELETE FROM public.stripe_webhook_events
        WHERE id IN (
            SELECT id FROM public.stripe_webhook_events
            WHERE processed_at < v_cutoff
            ORDER BY processed_at ASC
            LIMIT p_batch_size
        );

        GET DIAGNOSTICS v_deleted = ROW_COUNT;
        v_total := v_total + v_deleted;

        EXIT WHEN v_deleted = 0;

        PERFORM pg_sleep(0.1);  -- 100ms between batches
    END LOOP;

    RETURN v_total;
END;
$$;

COMMENT ON FUNCTION public.cleanup_old_stripe_events(INTEGER, INTEGER) IS
    'Batched cleanup of old stripe_webhook_events. Deletes rows with processed_at '
    'older than p_retention_days in batches of p_batch_size, sleeping 100ms between '
    'batches to reduce lock pressure. Returns total deleted rows. '
    'SECURITY DEFINER: caller needs only EXECUTE privilege. '
    'Replaces single-shot DELETE that was failing 47x (SMARTLIC-BACKEND-NH).';

GRANT EXECUTE ON FUNCTION public.cleanup_old_stripe_events(INTEGER, INTEGER) TO service_role;

-- ════════════════════════════════════════════════════════════════════════════
-- AC2: Reschedule pg_cron job to use the batched function
-- ════════════════════════════════════════════════════════════════════════════
SELECT cron.unschedule('cleanup-stripe-webhooks')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'cleanup-stripe-webhooks');

SELECT cron.schedule(
    'cleanup-stripe-webhooks',
    '30 4 * * *',
    $$SELECT public.cleanup_old_stripe_events(90, 1000)$$
);
