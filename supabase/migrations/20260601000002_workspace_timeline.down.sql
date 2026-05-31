-- B2GOPS-003 (Wave 0): Rollback workspace_timeline schema + RPCs
--
-- Order: DROP FUNCTION before DROP TABLE (functions depend on tables at runtime,
-- but DROP TABLE CASCADE handles function dependency at the Postgres level).
-- We drop functions explicitly first for clarity and safety.

DROP FUNCTION IF EXISTS public.ops_upcoming_events(INT);
DROP FUNCTION IF EXISTS public.ops_get_timeline(TEXT);
DROP FUNCTION IF EXISTS public.ops_add_timeline_event(TEXT, TEXT, TEXT, DATE, DATE, TEXT, TEXT, TEXT);

DROP TRIGGER IF EXISTS trg_workspace_timeline_overdue ON public.workspace_timeline;
DROP TRIGGER IF EXISTS trg_workspace_timeline_updated_at ON public.workspace_timeline;

DROP FUNCTION IF EXISTS public.set_overdue_timeline_status();
DROP FUNCTION IF EXISTS public.set_workspace_timeline_updated_at();

DROP TABLE IF EXISTS public.workspace_timeline CASCADE;
