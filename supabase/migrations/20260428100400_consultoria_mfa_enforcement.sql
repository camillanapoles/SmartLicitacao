-- MFA-EXT-001 AC2: Consultoria mandatory MFA + force enrollment field.
--
-- Adds `profiles.force_mfa_enrollment_until` (TIMESTAMPTZ) used by
-- backend/auth.py::require_mfa to enforce a hard MFA gate during a
-- bounded enrollment window. Two writers:
--
--   1. Plan-based enforcement (this file): existing `plan_type='consultoria'`
--      users without MFA receive a 14-day grace window so they can enroll
--      before being hard-blocked.
--   2. Brute-force trigger (sibling migration 20260428100500): users who
--      hit 3 consecutive password-fails get a 7-day enrollment window.
--
-- NOTE on naming: the story doc references `'smartlic_consultoria'` but the
-- actual schema value (since 20260301300000_consultoria_stripe_ids.sql) is
-- `'consultoria'`. We use the canonical schema value and document the
-- alias in the ADR.
--
-- Idempotent: safe to re-apply (column existence guarded, backfill skips
-- already-set rows).

BEGIN;

-- 1. Column: force_mfa_enrollment_until
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS force_mfa_enrollment_until TIMESTAMPTZ;

COMMENT ON COLUMN public.profiles.force_mfa_enrollment_until IS
  'MFA-EXT-001: hard-enforce MFA enrollment until this timestamp. NULL means no time-bounded enforcement (admin/master/consultoria use plan-based logic). Set by (a) consultoria backfill (14d), (b) bruteforce trigger (7d). Reset by daily auth_cleanup cron after expiry.';

-- 2. Optional partial index for fast lookup of in-flight enforcements
--    (cron query: WHERE force_mfa_enrollment_until < NOW() AND mfa_enrolled = false).
CREATE INDEX IF NOT EXISTS idx_profiles_force_mfa_enrollment_until
  ON public.profiles (force_mfa_enrollment_until)
  WHERE force_mfa_enrollment_until IS NOT NULL;

-- 3. Backfill: existing consultoria users without MFA → 14d grace window.
--    Conservative WHERE clause: only set if currently NULL (idempotent).
--    Joins auth.mfa_factors via service-role visibility.
UPDATE public.profiles AS p
SET force_mfa_enrollment_until = NOW() + INTERVAL '14 days'
WHERE p.plan_type = 'consultoria'
  AND p.force_mfa_enrollment_until IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM auth.mfa_factors f
    WHERE f.user_id = p.id AND f.status = 'verified'
  );

COMMIT;
