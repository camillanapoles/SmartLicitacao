-- BIZ-METRIC-001 (AC1) ROLLBACK: drop export_time_saved_survey
--
-- Rolling this back destroys all collected calibration data. Acceptable
-- only in recovery scenarios. The table has no incoming FKs from other
-- application tables, so no cascade considerations beyond CASCADE on
-- auth.users (already declared on the FK).

DROP POLICY IF EXISTS "User can read own surveys"                    ON public.export_time_saved_survey;
DROP POLICY IF EXISTS "User can insert own surveys"                  ON public.export_time_saved_survey;
DROP POLICY IF EXISTS "Service role full access on export surveys"   ON public.export_time_saved_survey;

DROP INDEX IF EXISTS public.idx_export_time_saved_submitted_at;
DROP INDEX IF EXISTS public.idx_export_time_saved_user_submitted;

DROP TABLE IF EXISTS public.export_time_saved_survey;
