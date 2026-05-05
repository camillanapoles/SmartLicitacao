-- DATA-CNAE-002 (#710) — CNAE→setor mapping table
--
-- Re-implementation of DATA-CNAE-001 (#679) after revert via #702.
-- The original PR's daemon-thread Redis pubsub listener wedged the
-- Railway healthcheck on cold start. This migration creates ONLY the
-- minimal table; warmup happens in `startup/lifespan._warmup_cnae_mapping`
-- with a non-fatal try/except guard. If the table is empty, missing,
-- or unreachable, lookups still answer from the hardcoded baseline in
-- `backend/utils/cnae_mapping.py::CNAE_TO_SETOR`.
--
-- Schema kept deliberately small — no audit log, no RLS-managed admin
-- CRUD, no Redis invalidation channel. Future stories can extend safely
-- once startup is proven stable.

CREATE TABLE IF NOT EXISTS public.cnae_setores (
    codigo_cnae text PRIMARY KEY,
    setor       text NOT NULL,
    descricao   text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.cnae_setores IS
    'DATA-CNAE-002 (#710): CNAE→setor mapping override. Hardcoded baseline '
    'in backend/utils/cnae_mapping.py is merged with rows from this table '
    'at startup; if this table is empty/missing/unreachable, the baseline '
    'answers all lookups (Gap-8 status quo).';
COMMENT ON COLUMN public.cnae_setores.codigo_cnae IS
    '4-digit IBGE CNAE prefix (e.g. "4781"). Matches the prefix extraction '
    'in utils/cnae_mapping.py::map_cnae_to_setor.';
COMMENT ON COLUMN public.cnae_setores.setor IS
    'SmartLic sector id (e.g. "engenharia"). Must match an id in '
    'backend/sectors_data.yaml or DEFAULT_FALLBACK_SETOR ("geral").';

-- RLS: read-only for authenticated; writes via service_role only.
ALTER TABLE public.cnae_setores ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "cnae_setores_read_authenticated" ON public.cnae_setores;
CREATE POLICY "cnae_setores_read_authenticated"
    ON public.cnae_setores
    FOR SELECT
    TO authenticated
    USING (true);

-- service_role bypasses RLS by default in Supabase; no explicit policy
-- is required for INSERT/UPDATE/DELETE. The backend's startup warmup
-- runs as service_role via supabase_client.get_supabase().
