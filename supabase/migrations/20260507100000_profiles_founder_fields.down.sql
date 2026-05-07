-- Rollback: 20260507100000_profiles_founder_fields
BEGIN;

DROP INDEX IF EXISTS idx_profiles_founders;

ALTER TABLE public.profiles
    DROP COLUMN IF EXISTS consulting_discount_pct,
    DROP COLUMN IF EXISTS founder_checkout_source,
    DROP COLUMN IF EXISTS founder_offer_version,
    DROP COLUMN IF EXISTS founder_since,
    DROP COLUMN IF EXISTS is_founder;

NOTIFY pgrst, 'reload schema';

COMMIT;
