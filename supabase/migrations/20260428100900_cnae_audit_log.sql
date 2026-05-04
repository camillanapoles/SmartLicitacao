-- DATA-CNAE-001 (AC3): Audit log for cnae_setor_mapping mutations.
--
-- Each create/update/delete/restore performed via the admin endpoint
-- (/v1/admin/cnae-mapping) inserts a row here with the actor's user
-- id and the JSONB before/after state.  The cnae_code column does
-- NOT have an FK reference back to cnae_setor_mapping so that hard
-- deletes (escape hatch — soft-delete is the supported flow) do not
-- erase the history.

CREATE TABLE IF NOT EXISTS public.cnae_mapping_audit_log (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    cnae_code       TEXT,
    action          TEXT        NOT NULL
                                CHECK (action IN ('create', 'update', 'delete', 'restore', 'bulk_import')),
    old_value       JSONB,
    new_value       JSONB,
    actor_user_id   UUID        REFERENCES auth.users(id) ON DELETE SET NULL,
    actor_email     TEXT,
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.cnae_mapping_audit_log IS
    'Audit trail for cnae_setor_mapping mutations (DATA-CNAE-001 AC8). '
    'Append-only: rows are never UPDATEd or DELETEd by application code.';
COMMENT ON COLUMN public.cnae_mapping_audit_log.action IS
    'create | update | delete (soft) | restore | bulk_import';
COMMENT ON COLUMN public.cnae_mapping_audit_log.old_value IS
    'Snapshot of the row BEFORE the mutation (NULL for create).';
COMMENT ON COLUMN public.cnae_mapping_audit_log.new_value IS
    'Snapshot of the row AFTER the mutation (NULL for hard delete).';
COMMENT ON COLUMN public.cnae_mapping_audit_log.actor_email IS
    'Denormalised admin email at time of mutation. Survives auth.users '
    'deletion thanks to ON DELETE SET NULL on actor_user_id.';

-- Per-CNAE history lookup (admin UI Audit Log view).
CREATE INDEX IF NOT EXISTS idx_cnae_mapping_audit_log_cnae_code
    ON public.cnae_mapping_audit_log (cnae_code, created_at DESC);

-- Time-range scans (e.g. "all mutations last 30 days").
CREATE INDEX IF NOT EXISTS idx_cnae_mapping_audit_log_created_at
    ON public.cnae_mapping_audit_log (created_at DESC);

-- Per-actor scans (compliance: "show everything Tiago changed").
CREATE INDEX IF NOT EXISTS idx_cnae_mapping_audit_log_actor
    ON public.cnae_mapping_audit_log (actor_user_id, created_at DESC)
    WHERE actor_user_id IS NOT NULL;

ALTER TABLE public.cnae_mapping_audit_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "cnae_mapping_audit_log_service_role_all"
    ON public.cnae_mapping_audit_log;
CREATE POLICY "cnae_mapping_audit_log_service_role_all"
    ON public.cnae_mapping_audit_log
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Block direct PostgREST access from authenticated/anon.
DROP POLICY IF EXISTS "cnae_mapping_audit_log_no_public_read"
    ON public.cnae_mapping_audit_log;
CREATE POLICY "cnae_mapping_audit_log_no_public_read"
    ON public.cnae_mapping_audit_log
    FOR SELECT
    TO authenticated, anon
    USING (false);
