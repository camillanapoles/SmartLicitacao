-- ============================================================================
-- DOWN: user_sector_affinity — reverses FEEDBACK-001 migration
-- Date: 2026-06-04
-- Author: @dev
-- ============================================================================

DROP TRIGGER IF EXISTS trg_user_sector_affinity_updated_at ON public.user_sector_affinity;
DROP FUNCTION IF EXISTS public.update_user_sector_affinity_updated_at();

DROP POLICY IF EXISTS "service_role_all" ON public.user_sector_affinity;
DROP POLICY IF EXISTS "user_select_own" ON public.user_sector_affinity;

ALTER TABLE public.user_sector_affinity DISABLE ROW LEVEL SECURITY;

DROP INDEX IF EXISTS idx_user_sector_affinity_score;
DROP INDEX IF EXISTS idx_user_sector_affinity_user;

DROP TABLE IF EXISTS public.user_sector_affinity;

NOTIFY pgrst, 'reload schema';
