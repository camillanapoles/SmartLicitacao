-- Rollback for DATA-CNAE-002 (#710): drop the cnae_setores table.
-- Safe at any time — the backend falls back to the hardcoded CNAE_TO_SETOR
-- baseline when this table is missing.
DROP POLICY IF EXISTS "cnae_setores_read_authenticated" ON public.cnae_setores;
DROP TABLE IF EXISTS public.cnae_setores;
