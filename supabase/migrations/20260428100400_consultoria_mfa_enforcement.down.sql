-- MFA-EXT-001: Rollback consultoria MFA enforcement field.
-- Idempotent: drop guarded.

BEGIN;

DROP INDEX IF EXISTS public.idx_profiles_force_mfa_enrollment_until;

ALTER TABLE public.profiles
  DROP COLUMN IF EXISTS force_mfa_enrollment_until;

COMMIT;
