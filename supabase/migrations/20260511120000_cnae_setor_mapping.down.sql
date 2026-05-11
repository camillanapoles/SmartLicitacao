-- ============================================================================
-- DOWN: cnae_setor_mapping — reverses 20260511120000_cnae_setor_mapping.sql
-- Date: 2026-05-11
-- Author: @dev / @data-engineer (DATA-CNAE-001)
-- ============================================================================
-- Context:
--   Up migration created public.cnae_setor_mapping table, RLS policies,
--   index, and seeded 59 rows from backend/utils/cnae_mapping.py.
--
--   Reverting drops the entire table (CASCADE removes policies, index and
--   seed data atomically). The hardcoded CNAE_TO_SETOR dict in
--   backend/utils/cnae_mapping.py remains as fallback in code, so the
--   lookup_cnae_setor() function continues to work after rollback.
--
--   NO BACKUP NEEDED: the source-of-truth dict still lives in code.
-- ============================================================================

BEGIN;

DROP POLICY IF EXISTS "cnae_admin_write" ON public.cnae_setor_mapping;
DROP POLICY IF EXISTS "cnae_public_read" ON public.cnae_setor_mapping;
DROP INDEX IF EXISTS public.idx_cnae_setor_mapping_setor;
DROP TABLE IF EXISTS public.cnae_setor_mapping;

COMMIT;
