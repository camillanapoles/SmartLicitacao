-- BILL-SYNC-001 (AC8): Audit log for admin-initiated billing sync mutations.
--
-- Every reverse-sync (DB -> Stripe) writes a row here capturing:
--   - which admin acted (actor_user_id + actor_email)
--   - which plan_billing_periods row was the target
--   - old/new stripe_price_id (Stripe prices are immutable, so a "reverse
--     sync" always means "create new price + archive old price").
--   - Optional payload (full Stripe Price objects) for forensic replay.
--
-- Forward webhook events are tracked separately in stripe_webhook_events;
-- this table is only for human-driven, audit-relevant operations.

CREATE TABLE IF NOT EXISTS public.admin_billing_audit_log (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_billing_period_id UUID,
    plan_id         TEXT,
    billing_period  TEXT,
    action          TEXT        NOT NULL
                                CHECK (action IN (
                                    'reverse_sync_create_price',
                                    'reverse_sync_archive_price',
                                    'reverse_sync_skipped_race_guard',
                                    'reverse_sync_failed'
                                )),
    old_stripe_price_id TEXT,
    new_stripe_price_id TEXT,
    actor_user_id   UUID        REFERENCES auth.users(id) ON DELETE SET NULL,
    actor_email     TEXT,
    note            TEXT,
    payload         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.admin_billing_audit_log IS
    'BILL-SYNC-001 (AC8): append-only audit trail for admin reverse-sync '
    '(DB -> Stripe) operations. Survives FK deletion of plan_billing_periods '
    'because we deliberately do NOT have an FK constraint — historical record '
    'must outlive its target row.';
COMMENT ON COLUMN public.admin_billing_audit_log.action IS
    'reverse_sync_create_price | reverse_sync_archive_price | '
    'reverse_sync_skipped_race_guard | reverse_sync_failed';
COMMENT ON COLUMN public.admin_billing_audit_log.old_stripe_price_id IS
    'Stripe price id active before the operation (NULL on first sync).';
COMMENT ON COLUMN public.admin_billing_audit_log.new_stripe_price_id IS
    'Stripe price id active after the operation (NULL on archive-only / failed).';
COMMENT ON COLUMN public.admin_billing_audit_log.actor_email IS
    'Denormalised admin email at time of mutation. Survives auth.users '
    'deletion thanks to ON DELETE SET NULL on actor_user_id.';

-- Per-plan history lookup (admin UI Audit Log view).
CREATE INDEX IF NOT EXISTS idx_admin_billing_audit_log_plan_id
    ON public.admin_billing_audit_log (plan_id, created_at DESC);

-- Per-row history (when admin drills into a single billing period).
CREATE INDEX IF NOT EXISTS idx_admin_billing_audit_log_pbp_id
    ON public.admin_billing_audit_log (plan_billing_period_id, created_at DESC)
    WHERE plan_billing_period_id IS NOT NULL;

-- Time-range scans (e.g. "all reverse syncs last 30 days").
CREATE INDEX IF NOT EXISTS idx_admin_billing_audit_log_created_at
    ON public.admin_billing_audit_log (created_at DESC);

-- Per-actor scans (compliance: "show everything Tiago changed").
CREATE INDEX IF NOT EXISTS idx_admin_billing_audit_log_actor
    ON public.admin_billing_audit_log (actor_user_id, created_at DESC)
    WHERE actor_user_id IS NOT NULL;

ALTER TABLE public.admin_billing_audit_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "admin_billing_audit_log_service_all"
    ON public.admin_billing_audit_log;
CREATE POLICY "admin_billing_audit_log_service_all"
    ON public.admin_billing_audit_log
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Block direct PostgREST access from authenticated/anon.
DROP POLICY IF EXISTS "admin_billing_audit_log_no_public_read"
    ON public.admin_billing_audit_log;
CREATE POLICY "admin_billing_audit_log_no_public_read"
    ON public.admin_billing_audit_log
    FOR SELECT
    TO authenticated, anon
    USING (false);
