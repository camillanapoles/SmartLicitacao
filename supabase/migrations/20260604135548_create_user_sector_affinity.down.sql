-- FEEDBACK-001: Rollback user_sector_affinity schema
-- Reverses 20260604135548_create_user_sector_affinity.sql
-- Date: 2026-06-04
--
-- Drops table, policies, trigger, and function in reverse order.

DROP TRIGGER IF EXISTS trg_user_sector_affinity_updated_at ON public.user_sector_affinity;
DROP FUNCTION IF EXISTS public.set_user_sector_affinity_updated_at();

DROP POLICY IF EXISTS "usa_owner_all" ON public.user_sector_affinity;

DROP TABLE IF EXISTS public.user_sector_affinity CASCADE;
