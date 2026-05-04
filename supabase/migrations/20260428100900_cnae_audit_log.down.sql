-- Rollback DATA-CNAE-001 audit log table.
-- Idempotent.

DROP POLICY IF EXISTS "cnae_mapping_audit_log_service_role_all"
    ON public.cnae_mapping_audit_log;
DROP POLICY IF EXISTS "cnae_mapping_audit_log_no_public_read"
    ON public.cnae_mapping_audit_log;

DROP INDEX IF EXISTS idx_cnae_mapping_audit_log_actor;
DROP INDEX IF EXISTS idx_cnae_mapping_audit_log_created_at;
DROP INDEX IF EXISTS idx_cnae_mapping_audit_log_cnae_code;

DROP TABLE IF EXISTS public.cnae_mapping_audit_log;
