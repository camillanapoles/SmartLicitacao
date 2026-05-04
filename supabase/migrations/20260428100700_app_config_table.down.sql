-- BIZ-METRIC-001 (AC2) ROLLBACK: drop app_config
--
-- Rolling this back removes the runtime config table; backend code
-- consuming app_config.hours_saved_per_search will fall back to the
-- in-process constant (2.0) — see backend/utils/app_config.py.

DROP POLICY IF EXISTS "Service role full access on app_config" ON public.app_config;

DROP TRIGGER IF EXISTS app_config_updated_at_trg ON public.app_config;
DROP FUNCTION IF EXISTS public.app_config_set_updated_at();

DROP TABLE IF EXISTS public.app_config;
