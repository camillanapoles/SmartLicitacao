-- Rollback BILL-SYNC-001 reconciliation runs table.
-- Idempotent.

DROP POLICY IF EXISTS "billing_reconciliation_runs_service_all"
    ON public.billing_reconciliation_runs;
DROP POLICY IF EXISTS "billing_reconciliation_runs_no_public_read"
    ON public.billing_reconciliation_runs;

DROP INDEX IF EXISTS idx_billing_reconciliation_runs_status_started_at;
DROP INDEX IF EXISTS idx_billing_reconciliation_runs_started_at;

DROP TABLE IF EXISTS public.billing_reconciliation_runs;
