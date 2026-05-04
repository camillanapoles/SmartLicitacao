-- Rollback BILL-SYNC-001 admin billing audit log table.
-- Idempotent.

DROP POLICY IF EXISTS "admin_billing_audit_log_service_all"
    ON public.admin_billing_audit_log;
DROP POLICY IF EXISTS "admin_billing_audit_log_no_public_read"
    ON public.admin_billing_audit_log;

DROP INDEX IF EXISTS idx_admin_billing_audit_log_actor;
DROP INDEX IF EXISTS idx_admin_billing_audit_log_created_at;
DROP INDEX IF EXISTS idx_admin_billing_audit_log_pbp_id;
DROP INDEX IF EXISTS idx_admin_billing_audit_log_plan_id;

DROP TABLE IF EXISTS public.admin_billing_audit_log;
