-- DATA-CNAE-001: Migrate hardcoded CNAE -> sector mapping into a real table.
--
-- Replaces backend/utils/cnae_mapping.py CNAE_TO_SETOR dict with an
-- editable, audited DB table that admin operators can mutate via the
-- new /v1/admin/cnae-mapping CRUD endpoints (story DATA-CNAE-001 AC7-AC9).
--
-- Storage decisions:
--   * cnae_code is the canonical 4-digit IBGE prefix ("4781") and
--     simultaneously serves as the primary key.  The application layer
--     (utils/cnae_mapping.py::map_cnae_to_setor) extracts the prefix
--     from arbitrary CNAE shapes ("4781-4/00", "47814", etc.) before
--     hitting this table; storing the prefix avoids prefix-search at
--     query time.
--   * setor_id is TEXT (no FK).  There is no `sectors` table — the
--     20 canonical sector ids live in backend/sectors_data.yaml.  A
--     CHECK constraint listing the union of (yaml ids) + (legacy
--     aliases used by the production hardcoded mapping) protects
--     against typos without coupling the schema to a yaml file.  When
--     a future story migrates sectors into a table this CHECK can
--     become a FK in a follow-up migration.
--   * is_active = false instead of DELETE: AC7 mandates soft-delete so
--     audit history survives a row being retired.

CREATE TABLE IF NOT EXISTS public.cnae_setor_mapping (
    cnae_code   TEXT        PRIMARY KEY,
    setor_id    TEXT        NOT NULL,
    confidence  NUMERIC(3,2) NOT NULL DEFAULT 1.0
                CHECK (confidence BETWEEN 0 AND 1),
    notes       TEXT,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by  UUID        REFERENCES auth.users(id) ON DELETE SET NULL,
    CONSTRAINT cnae_setor_mapping_setor_id_chk CHECK (
        setor_id IN (
            -- Canonical ids from backend/sectors_data.yaml (20 sectors).
            'vestuario',
            'alimentos',
            'informatica',
            'mobiliario',
            'papelaria',
            'engenharia',
            'software_desenvolvimento',
            'software_licencas',
            'servicos_prediais',
            'produtos_limpeza',
            'medicamentos',
            'equipamentos_medicos',
            'insumos_hospitalares',
            'vigilancia',
            'transporte_servicos',
            'frota_veicular',
            'manutencao_predial',
            'engenharia_rodoviaria',
            'materiais_eletricos',
            'materiais_hidraulicos',
            -- Legacy aliases used by the production hardcoded mapping.
            -- DATA-CNAE-001 mandates byte-equivalence with the prior
            -- behaviour (AC15 snapshot regression).  Do NOT remove
            -- these without a follow-up migration that also updates
            -- existing rows AND the snapshot fixture.
            'saude',
            'equipamentos',
            'transporte',
            'geral'
        )
    )
);

COMMENT ON TABLE public.cnae_setor_mapping IS
    'CNAE 4-digit prefix -> SmartLic sector mapping (DATA-CNAE-001). '
    'Replaces the hardcoded dict in backend/utils/cnae_mapping.py. '
    'Admin-managed via /v1/admin/cnae-mapping endpoints; mutations '
    'logged to cnae_mapping_audit_log.';
COMMENT ON COLUMN public.cnae_setor_mapping.cnae_code IS
    'IBGE 4-digit CNAE prefix (e.g. "4781"). Application layer extracts '
    'the prefix from arbitrary input shapes before lookup.';
COMMENT ON COLUMN public.cnae_setor_mapping.setor_id IS
    'SmartLic sector identifier. See sectors_data.yaml for canonical ids.';
COMMENT ON COLUMN public.cnae_setor_mapping.confidence IS
    'Mapping confidence in [0,1]. 1.0 = canonical IBGE-aligned mapping. '
    '<1.0 = inferred from sibling CNAE class.';
COMMENT ON COLUMN public.cnae_setor_mapping.is_active IS
    'Soft-delete flag. is_active=false hides the row from production '
    'lookups but preserves audit history.';

-- Lookup index: production hot path filters on is_active.
CREATE INDEX IF NOT EXISTS idx_cnae_setor_mapping_active
    ON public.cnae_setor_mapping (cnae_code)
    WHERE is_active = TRUE;

-- Reverse lookup: list mappings by sector for admin UI filtering.
CREATE INDEX IF NOT EXISTS idx_cnae_setor_mapping_setor_id
    ON public.cnae_setor_mapping (setor_id)
    WHERE is_active = TRUE;

-- Trigger: updated_at maintenance.
CREATE OR REPLACE FUNCTION public.cnae_setor_mapping_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_cnae_setor_mapping_updated_at
    ON public.cnae_setor_mapping;
CREATE TRIGGER trg_cnae_setor_mapping_updated_at
    BEFORE UPDATE ON public.cnae_setor_mapping
    FOR EACH ROW
    EXECUTE FUNCTION public.cnae_setor_mapping_set_updated_at();

-- RLS: admin-only writes; reads happen via service-role from the
-- backend.  We do NOT expose this table to authenticated PostgREST
-- callers directly — onboarding/empresa_publica go through the
-- backend's service-role client.  Defence-in-depth: enable RLS and
-- only allow service_role to do anything.  Admin mutation via
-- /v1/admin/cnae-mapping uses the same service_role client gated by
-- the require_admin FastAPI dependency.
ALTER TABLE public.cnae_setor_mapping ENABLE ROW LEVEL SECURITY;

-- service_role bypass is implicit, but we add an explicit policy so
-- behaviour is identical to other admin-managed tables in this repo
-- (see migrations 20260424180000_trial_email_delivery_tracking and
-- 20260414120000_cron_job_health for the pattern).
DROP POLICY IF EXISTS "cnae_setor_mapping_service_role_all"
    ON public.cnae_setor_mapping;
CREATE POLICY "cnae_setor_mapping_service_role_all"
    ON public.cnae_setor_mapping
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Block authenticated/anon entirely.  Onboarding flows that read CNAE
-- mappings go through the backend's service-role client, never via
-- PostgREST.
DROP POLICY IF EXISTS "cnae_setor_mapping_no_public_read"
    ON public.cnae_setor_mapping;
CREATE POLICY "cnae_setor_mapping_no_public_read"
    ON public.cnae_setor_mapping
    FOR SELECT
    TO authenticated, anon
    USING (false);
