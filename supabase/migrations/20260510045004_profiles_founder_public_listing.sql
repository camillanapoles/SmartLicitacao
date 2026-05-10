-- ============================================================================
-- Migration: 20260510045004_profiles_founder_public_listing
-- Issue: #1008 — feat(db): add public listing fields for /fundadores/hall
-- Date: 2026-05-10
--
-- Purpose:
--   Adds opt-in public listing columns to profiles for the Hall of Founders
--   page (/fundadores/hall). LGPD-compliant: default FALSE, requires explicit
--   user consent via the toggle in /conta/perfil.
--
--   Columns:
--   - founder_public_listing_consent: BOOLEAN, default FALSE — opt-in flag.
--   - founder_listing_display_name:   TEXT — optional display name (nullable;
--                                     falls back to razao_social or "Empresa
--                                     Fundadora" when null).
--   - founder_company_logo_url:       TEXT — optional logo URL (nullable).
--   - founder_consent_changed_at:     TIMESTAMPTZ — last toggle timestamp,
--                                     used by the consent endpoint as a
--                                     lightweight audit trail.
--
-- Notes:
--   - Forward-compatible with PR #1014: the GET /api/founders/availability
--     endpoint already queries founder_public_listing_consent under a
--     try/except, so applying this migration before or after PR #1014 ships
--     is safe.
--   - Partial index reuses the same predicate as the listing query.
-- ============================================================================

BEGIN;

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS founder_public_listing_consent BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS founder_listing_display_name TEXT,
    ADD COLUMN IF NOT EXISTS founder_company_logo_url TEXT,
    ADD COLUMN IF NOT EXISTS founder_consent_changed_at TIMESTAMPTZ;

COMMENT ON COLUMN public.profiles.founder_public_listing_consent IS
    'LGPD opt-in flag (issue #1008). TRUE = user consented to public listing on /fundadores/hall. Default FALSE.';
COMMENT ON COLUMN public.profiles.founder_listing_display_name IS
    'Optional display name on /fundadores/hall. Falls back to razao_social or generic label when null.';
COMMENT ON COLUMN public.profiles.founder_company_logo_url IS
    'Optional company logo URL shown on /fundadores/hall.';
COMMENT ON COLUMN public.profiles.founder_consent_changed_at IS
    'Timestamp of the last consent toggle. Used as a lightweight LGPD audit trail.';

-- Partial index to make the public Hall query (is_founder=TRUE AND consent=TRUE)
-- cheap. Founders cap is ~50 — this index stays tiny.
CREATE INDEX IF NOT EXISTS idx_profiles_founders_public_listing
    ON public.profiles(founder_consent_changed_at DESC)
    WHERE is_founder = TRUE AND founder_public_listing_consent = TRUE;

NOTIFY pgrst, 'reload schema';

COMMIT;
