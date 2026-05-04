-- BILL-SYNC-001 (AC6): Reconciliation run history.
--
-- The daily ARQ cron `billing_reconciliation` writes one row per execution
-- summarising: rows checked, drifts detected, drifts auto-fixed, drifts
-- requiring manual review, optional dry-run flag, and the full JSON drift
-- report for forensic inspection.
--
-- The Admin UI consumes the latest 30 rows via:
--     GET /v1/admin/plans/reconciliation-runs

CREATE TABLE IF NOT EXISTS public.billing_reconciliation_runs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT        NOT NULL
                                CHECK (status IN ('running', 'completed', 'failed', 'skipped')),
    dry_run         BOOLEAN     NOT NULL DEFAULT FALSE,
    rows_checked    INTEGER     NOT NULL DEFAULT 0,
    drifts_detected INTEGER     NOT NULL DEFAULT 0,
    drifts_fixed    INTEGER     NOT NULL DEFAULT 0,
    drifts_manual   INTEGER     NOT NULL DEFAULT 0,
    drift_report    JSONB,
    error_message   TEXT
);

COMMENT ON TABLE public.billing_reconciliation_runs IS
    'BILL-SYNC-001 (AC6): one row per daily reconciliation cron execution. '
    'Append-only audit table (never UPDATEd by application code except to '
    'set finished_at + status when the run completes).';
COMMENT ON COLUMN public.billing_reconciliation_runs.status IS
    'running | completed | failed | skipped';
COMMENT ON COLUMN public.billing_reconciliation_runs.dry_run IS
    'When true the cron only logs differences and never mutates DB or Stripe.';
COMMENT ON COLUMN public.billing_reconciliation_runs.drift_report IS
    'JSON array of drift descriptors: '
    '[{type, plan_id, billing_period, db_value, stripe_value, action}, ...]';

CREATE INDEX IF NOT EXISTS idx_billing_reconciliation_runs_started_at
    ON public.billing_reconciliation_runs (started_at DESC);

-- Pull-down to "latest run" with one composite index hit (covering query).
CREATE INDEX IF NOT EXISTS idx_billing_reconciliation_runs_status_started_at
    ON public.billing_reconciliation_runs (status, started_at DESC);

ALTER TABLE public.billing_reconciliation_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "billing_reconciliation_runs_service_all"
    ON public.billing_reconciliation_runs;
CREATE POLICY "billing_reconciliation_runs_service_all"
    ON public.billing_reconciliation_runs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Block direct PostgREST access from authenticated/anon — admin reads go
-- through the backend with service_role.
DROP POLICY IF EXISTS "billing_reconciliation_runs_no_public_read"
    ON public.billing_reconciliation_runs;
CREATE POLICY "billing_reconciliation_runs_no_public_read"
    ON public.billing_reconciliation_runs
    FOR SELECT
    TO authenticated, anon
    USING (false);
