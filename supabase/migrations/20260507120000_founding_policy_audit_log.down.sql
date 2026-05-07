BEGIN;
DROP TRIGGER IF EXISTS founding_policy_audit ON public.founding_policy;
DROP FUNCTION IF EXISTS public.founding_policy_audit_trigger();
DROP TABLE IF EXISTS public.founding_policy_audit_log;
COMMIT;
