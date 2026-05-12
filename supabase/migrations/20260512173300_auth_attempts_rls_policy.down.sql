-- Rollback: Remove service_role ALL policy for auth_attempts.

BEGIN;

DROP POLICY IF EXISTS "Service role full access to auth attempts" ON public.auth_attempts;

COMMIT;
