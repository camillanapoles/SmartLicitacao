-- ============================================================================
-- DOWN: Revert cleanup-stripe-webhooks to single-shot DELETE
-- Reverses 20260512190000_fix_cleanup_stripe_webhooks_batched.sql
-- Date: 2026-05-12
-- ============================================================================
-- Context:
--   The up migration replaced the single-shot DELETE with a batched function
--   cleanup_old_stripe_events(). This down script:
--     1. Unschedules the pg_cron job
--     2. Reschedules it with the original single-shot DELETE
--     3. Drops the batched function
-- ============================================================================

-- 1. Unschedule the current job
SELECT cron.unschedule('cleanup-stripe-webhooks')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'cleanup-stripe-webhooks');

-- 2. Reschedule with the original single-shot DELETE (pre-fix behavior)
SELECT cron.schedule(
    'cleanup-stripe-webhooks',
    '30 4 * * *',
    $$DELETE FROM public.stripe_webhook_events WHERE processed_at < now() - interval '90 days'$$
);

-- 3. Drop the batched function
DROP FUNCTION IF EXISTS public.cleanup_old_stripe_events(INTEGER, INTEGER);
