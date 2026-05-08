-- ============================================================================
-- DOWN: sector_uf_intel_rpc — revertes 20260508120000_sector_uf_intel_rpc.sql
-- Date: 2026-05-08
-- Issue: #826
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   DROP RPC `sector_uf_intel(text, text[], text, integer)`.
--   Operação puramente DDL (sem dados); idempotente via IF EXISTS.
-- ============================================================================

DROP FUNCTION IF EXISTS public.sector_uf_intel(TEXT, TEXT[], TEXT, INTEGER);
