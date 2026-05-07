-- ============================================================================
-- Migration: 20260507130000_founding_leads_tracking_fields
-- Story: STORY-791 — Founders welcome email + founding_leads segmentation
-- Date: 2026-05-07
--
-- Purpose:
--   Adds tracking fields to founding_leads to support:
--     * welcome_sent_at  — idempotency gate for founders welcome email
--     * checkout_source  — UTM source / src query param from checkout URL
--     * offer_version    — offer version from Stripe metadata (e.g. v2_lifetime)
--
-- Down migration: 20260507130000_founding_leads_tracking_fields.down.sql
-- ============================================================================

BEGIN;

ALTER TABLE public.founding_leads
    ADD COLUMN IF NOT EXISTS welcome_sent_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS checkout_source TEXT NULL,
    ADD COLUMN IF NOT EXISTS offer_version TEXT NULL;

COMMENT ON COLUMN public.founding_leads.welcome_sent_at IS
    'STORY-791: Timestamp when founders welcome email was sent. NULL = not sent yet. '
    'Used as idempotency gate — job skips send if NOT NULL.';

COMMENT ON COLUMN public.founding_leads.checkout_source IS
    'STORY-791: UTM source or src param from checkout URL (e.g. "email", "landing", "direct").';

COMMENT ON COLUMN public.founding_leads.offer_version IS
    'STORY-791: Offer version from Stripe metadata (e.g. "v2_lifetime"). '
    'Enables segmented email copy per cohort.';

-- Partial index for efficient email idempotency queries.
-- Only completed leads that have not yet received a welcome email.
CREATE INDEX IF NOT EXISTS idx_founding_leads_welcome_pending
    ON public.founding_leads (email)
    WHERE checkout_status = 'completed' AND welcome_sent_at IS NULL;

NOTIFY pgrst, 'reload schema';

COMMIT;
