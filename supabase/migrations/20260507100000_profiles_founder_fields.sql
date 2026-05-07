-- ============================================================================
-- Migration: 20260507100000_profiles_founder_fields
-- Issue: #784 — feat(db): add founder fields to profiles + lifetime entitlement marker
-- Date: 2026-05-07
--
-- Purpose:
--   Adds founder-specific columns to profiles for the v2 lifetime one-time
--   offer (BIZ-FOUND-002 v2). These fields enable:
--   - Lifetime entitlement check without joining founding_leads
--   - Webhook handler can mark is_founder=true on checkout.session.completed
--   - Consultoria discount tracking per founder
--   - Attribution tracking (utm_source, checkout_source)
--
-- Notes:
--   - Backfill: existing subscription-based founders (offer v1, -50% monthly)
--     do NOT get is_founder=true — they remain as regular pro subscribers.
--   - Index partial on is_founder=true (max 50 rows by design — tiny).
-- ============================================================================

BEGIN;

-- Add founder columns to profiles
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS is_founder BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS founder_since TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS founder_offer_version TEXT,
    ADD COLUMN IF NOT EXISTS founder_checkout_source TEXT,
    ADD COLUMN IF NOT EXISTS consulting_discount_pct INT
        CHECK (consulting_discount_pct IS NULL OR (consulting_discount_pct >= 0 AND consulting_discount_pct <= 100));

-- Column comments
COMMENT ON COLUMN public.profiles.is_founder IS
    'TRUE if user purchased the v2 lifetime one-time Plano Fundadores (R$997). '
    'NOT set for v1 subscription founders (-50% monthly). Set by webhook handler.';

COMMENT ON COLUMN public.profiles.founder_since IS
    'Timestamp of checkout.session.completed event for lifetime purchase.';

COMMENT ON COLUMN public.profiles.founder_offer_version IS
    'Offer version string from checkout metadata (e.g. ''v2_lifetime''). '
    'Allows future offer versions to be distinguished.';

COMMENT ON COLUMN public.profiles.founder_checkout_source IS
    'utm_source or checkout source param from founding checkout metadata.';

COMMENT ON COLUMN public.profiles.consulting_discount_pct IS
    'Consultoria discount % granted to this founder (default 50 for v2_lifetime). '
    'NULL = no consulting discount. Set by webhook handler alongside is_founder.';

-- Partial index: only indexes founder rows (max 50 by founding cap design)
CREATE INDEX IF NOT EXISTS idx_profiles_founders
    ON public.profiles(id)
    WHERE is_founder = TRUE;

NOTIFY pgrst, 'reload schema';

COMMIT;
