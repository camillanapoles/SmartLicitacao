-- ============================================================================
-- DOWN: competitor_territory_map — reverts 20260531120000_competitor_territory_map.sql
-- Issue: #1272
-- ============================================================================

DROP FUNCTION IF EXISTS public.competitor_territory_map(text, int);
DROP INDEX IF EXISTS idx_psc_cnpj_vencedor_data;
