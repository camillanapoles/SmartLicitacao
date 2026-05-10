-- Rollback for 20260510045004_profiles_founder_public_listing (issue #1008).
-- Drops the public-listing columns + partial index added by the up migration.
-- Note: data in these columns is destroyed irrecoverably; back up first if needed.

BEGIN;

DROP INDEX IF EXISTS public.idx_profiles_founders_public_listing;

ALTER TABLE public.profiles
    DROP COLUMN IF EXISTS founder_consent_changed_at,
    DROP COLUMN IF EXISTS founder_company_logo_url,
    DROP COLUMN IF EXISTS founder_listing_display_name,
    DROP COLUMN IF EXISTS founder_public_listing_consent;

NOTIFY pgrst, 'reload schema';

COMMIT;
