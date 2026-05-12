-- RBAC-SEC-002: Add service_role ALL policy for auth_attempts.
--
-- auth_attempts was created with RLS enabled but no policies, which
-- means only service_role (RLS bypass) can access it — correct security
-- but the RLS audit (ADR-RLS-MANDATORY-001) requires at least one
-- explicit policy. Add a service_role ALL policy matching the
-- mfa_recovery_attempts pattern.
--
-- Tracked by: #1152 RBAC-SEC-002

BEGIN;

CREATE POLICY "Service role full access to auth attempts"
    ON public.auth_attempts FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

COMMIT;
