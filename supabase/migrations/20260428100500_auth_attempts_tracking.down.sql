-- MFA-EXT-001: Rollback auth_attempts table.

BEGIN;

DROP TRIGGER IF EXISTS auth_attempts_updated_at ON public.auth_attempts;
DROP FUNCTION IF EXISTS public.update_auth_attempts_updated_at();
DROP INDEX IF EXISTS public.idx_auth_attempts_last_failure_at;
DROP TABLE IF EXISTS public.auth_attempts;

COMMIT;
