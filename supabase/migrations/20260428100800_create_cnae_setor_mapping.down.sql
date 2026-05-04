-- Rollback DATA-CNAE-001 cnae_setor_mapping schema.
--
-- Drops the lookup table, its trigger, and its triggering function.
-- Idempotent: safe to apply against a database where the migration
-- was never applied or partially applied.

DROP TRIGGER IF EXISTS trg_cnae_setor_mapping_updated_at
    ON public.cnae_setor_mapping;
DROP FUNCTION IF EXISTS public.cnae_setor_mapping_set_updated_at();

DROP POLICY IF EXISTS "cnae_setor_mapping_service_role_all"
    ON public.cnae_setor_mapping;
DROP POLICY IF EXISTS "cnae_setor_mapping_no_public_read"
    ON public.cnae_setor_mapping;

DROP INDEX IF EXISTS idx_cnae_setor_mapping_setor_id;
DROP INDEX IF EXISTS idx_cnae_setor_mapping_active;

DROP TABLE IF EXISTS public.cnae_setor_mapping;
