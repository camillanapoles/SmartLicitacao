-- ============================================================================
-- Down Migration: 20260507130000_founding_leads_tracking_fields
-- Reverts: STORY-791 founding_leads tracking fields
-- ============================================================================

BEGIN;

DROP INDEX IF EXISTS public.idx_founding_leads_welcome_pending;

ALTER TABLE public.founding_leads
    DROP COLUMN IF EXISTS welcome_sent_at,
    DROP COLUMN IF EXISTS checkout_source,
    DROP COLUMN IF EXISTS offer_version;

COMMIT;
