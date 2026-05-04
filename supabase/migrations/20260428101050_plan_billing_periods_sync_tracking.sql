-- BILL-SYNC-001 (AC8/AC9/AC10): Add sync tracking columns to plan_billing_periods.
--
-- New columns:
--   stripe_product_id        — denormalised; needed by webhook handler
--                              `product.updated` (Stripe sends product_id only).
--   last_forward_synced_at   — set when a Stripe webhook (product/price.*)
--                              writes to this row.
--   last_reverse_synced_at   — set when admin pushes DB → Stripe via the
--                              POST /v1/admin/plans/{id}/sync-to-stripe route.
--   is_archived              — soft-delete flag for `price.deleted` webhook
--                              (we never hard-delete because old subscriptions
--                              may still reference the archived price).
--
-- All columns nullable / default-safe so the migration is non-blocking and
-- can be applied independently from the application code that reads them.

ALTER TABLE public.plan_billing_periods
    ADD COLUMN IF NOT EXISTS stripe_product_id      TEXT,
    ADD COLUMN IF NOT EXISTS last_forward_synced_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_reverse_synced_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS is_archived            BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN public.plan_billing_periods.stripe_product_id IS
    'Denormalised Stripe product id (price -> product). Populated by webhook '
    'handlers and reverse-sync route. Nullable for legacy rows.';
COMMENT ON COLUMN public.plan_billing_periods.last_forward_synced_at IS
    'BILL-SYNC-001: timestamp of the last Stripe -> DB sync (any of '
    'product.updated, price.updated, price.created, price.deleted).';
COMMENT ON COLUMN public.plan_billing_periods.last_reverse_synced_at IS
    'BILL-SYNC-001: timestamp of the last DB -> Stripe push performed by '
    'an admin via the sync-to-stripe endpoint.';
COMMENT ON COLUMN public.plan_billing_periods.is_archived IS
    'Soft-delete flag for Stripe price.deleted. Archived rows are filtered '
    'out of GET /plans but kept for historical billing references.';

-- Lookup by stripe_product_id (webhook handler uses this on product.updated).
CREATE INDEX IF NOT EXISTS idx_plan_billing_periods_stripe_product_id
    ON public.plan_billing_periods (stripe_product_id)
    WHERE stripe_product_id IS NOT NULL;

-- Lookup by stripe_price_id is the hot path for webhook + checkout flows.
-- The UNIQUE(plan_id, billing_period) covers checkout but webhooks need the
-- inverse direction.
CREATE INDEX IF NOT EXISTS idx_plan_billing_periods_stripe_price_id
    ON public.plan_billing_periods (stripe_price_id)
    WHERE stripe_price_id IS NOT NULL;
