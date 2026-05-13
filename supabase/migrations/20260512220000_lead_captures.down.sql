-- Rollback lead_captures table

BEGIN;

DROP INDEX IF EXISTS idx_lead_captures_source_created;

DROP POLICY IF EXISTS lead_captures_anon_insert ON public.lead_captures;
DROP POLICY IF EXISTS lead_captures_service_all ON public.lead_captures;
DROP POLICY IF EXISTS lead_captures_admin_select ON public.lead_captures;

DROP TABLE IF EXISTS public.lead_captures;

COMMIT;
