-- Rollback BILL-SYNC-001 sync tracking columns.
-- Idempotent.

DROP INDEX IF EXISTS idx_plan_billing_periods_stripe_price_id;
DROP INDEX IF EXISTS idx_plan_billing_periods_stripe_product_id;

ALTER TABLE public.plan_billing_periods
    DROP COLUMN IF EXISTS is_archived,
    DROP COLUMN IF EXISTS last_reverse_synced_at,
    DROP COLUMN IF EXISTS last_forward_synced_at,
    DROP COLUMN IF EXISTS stripe_product_id;
