-- ============================================================================
-- Migration: 20260511120000_cnae_setor_mapping
-- Story: DATA-CNAE-001 — Migrate utils/cnae_mapping.py hardcoded -> DB table
-- Date: 2026-05-11
--
-- Purpose:
--   Replaces hardcoded CNAE -> sector dict (backend/utils/cnae_mapping.py)
--   with a DB-backed table so admins can update mappings at runtime without
--   redeploying the backend. Drives onboarding wizard (US-006 Reversa) where
--   user provides CNAE -> sector inferred -> first analysis dispatch.
--
--   Columns:
--   - cnae_code:           4-digit CNAE prefix (PK).
--   - setor_id:            SmartLic sector id (matches sectors_data.yaml).
--   - confidence:          0.00-1.00 confidence score.
--   - fallback_setor_id:   secondary sector if primary unmatched downstream.
--   - notes:               free-text rationale / audit trail.
--   - updated_by:          auth.users(id) — set by admin CRUD endpoint.
--
-- RLS:
--   - Public SELECT (cnae_code is not PII; setor exposed via /setores anyway).
--   - Write restricted to authenticated admins (profiles.is_admin = true).
--
-- Seed:
--   Bulk INSERT of 59 entries (snapshot 2026-05-07) from CNAE_TO_SETOR dict.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.cnae_setor_mapping (
    cnae_code        TEXT PRIMARY KEY,
    setor_id         TEXT NOT NULL,
    confidence       NUMERIC(3, 2) NOT NULL DEFAULT 1.00,
    fallback_setor_id TEXT,
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by       UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_cnae_setor_mapping_setor
    ON public.cnae_setor_mapping (setor_id);

COMMENT ON TABLE public.cnae_setor_mapping IS
    'CNAE 4-digit prefix -> SmartLic sector mapping. DATA-CNAE-001.';
COMMENT ON COLUMN public.cnae_setor_mapping.cnae_code IS
    'CNAE 4-digit prefix (e.g. "4120"). Source of truth: IBGE CNAE 2.3.';
COMMENT ON COLUMN public.cnae_setor_mapping.confidence IS
    'Confidence score 0.00-1.00. 1.00 = exact match curated.';
COMMENT ON COLUMN public.cnae_setor_mapping.notes IS
    'Free-text audit trail. Soft-delete uses notes = ''deleted''.';

ALTER TABLE public.cnae_setor_mapping ENABLE ROW LEVEL SECURITY;

-- Public read: cnae_code -> sector is not sensitive.
DROP POLICY IF EXISTS "cnae_public_read" ON public.cnae_setor_mapping;
CREATE POLICY "cnae_public_read" ON public.cnae_setor_mapping
    FOR SELECT USING (true);

-- Admin-only write (INSERT/UPDATE/DELETE).
DROP POLICY IF EXISTS "cnae_admin_write" ON public.cnae_setor_mapping;
CREATE POLICY "cnae_admin_write" ON public.cnae_setor_mapping
    FOR ALL TO authenticated
    USING (
        (SELECT is_admin FROM public.profiles WHERE id = auth.uid()) = true
    )
    WITH CHECK (
        (SELECT is_admin FROM public.profiles WHERE id = auth.uid()) = true
    );

-- Seed: snapshot from backend/utils/cnae_mapping.py (2026-05-07, 59 entries).
INSERT INTO public.cnae_setor_mapping (cnae_code, setor_id, notes) VALUES
    ('4120', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4211', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4212', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4213', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4221', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4222', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4223', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4291', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4292', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4299', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4311', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4312', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4313', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4319', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4321', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4322', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4329', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4391', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4399', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('7111', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('7112', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('7119', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4781', 'vestuario',          'seed 2026-05-11 DATA-CNAE-001'),
    ('1412', 'vestuario',          'seed 2026-05-11 DATA-CNAE-001'),
    ('1413', 'vestuario',          'seed 2026-05-11 DATA-CNAE-001'),
    ('1421', 'vestuario',          'seed 2026-05-11 DATA-CNAE-001'),
    ('1422', 'vestuario',          'seed 2026-05-11 DATA-CNAE-001'),
    ('8121', 'servicos_prediais',  'seed 2026-05-11 DATA-CNAE-001'),
    ('8122', 'servicos_prediais',  'seed 2026-05-11 DATA-CNAE-001'),
    ('8129', 'servicos_prediais',  'seed 2026-05-11 DATA-CNAE-001'),
    ('8130', 'servicos_prediais',  'seed 2026-05-11 DATA-CNAE-001'),
    ('8011', 'vigilancia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('8012', 'vigilancia',         'seed 2026-05-11 DATA-CNAE-001'),
    ('3250', 'saude',              'seed 2026-05-11 DATA-CNAE-001'),
    ('4644', 'saude',              'seed 2026-05-11 DATA-CNAE-001'),
    ('4645', 'saude',              'seed 2026-05-11 DATA-CNAE-001'),
    ('8610', 'saude',              'seed 2026-05-11 DATA-CNAE-001'),
    ('8621', 'saude',              'seed 2026-05-11 DATA-CNAE-001'),
    ('8630', 'saude',              'seed 2026-05-11 DATA-CNAE-001'),
    ('1011', 'alimentos',          'seed 2026-05-11 DATA-CNAE-001'),
    ('1091', 'alimentos',          'seed 2026-05-11 DATA-CNAE-001'),
    ('4639', 'alimentos',          'seed 2026-05-11 DATA-CNAE-001'),
    ('4711', 'alimentos',          'seed 2026-05-11 DATA-CNAE-001'),
    ('6201', 'informatica',        'seed 2026-05-11 DATA-CNAE-001'),
    ('6202', 'informatica',        'seed 2026-05-11 DATA-CNAE-001'),
    ('6209', 'informatica',        'seed 2026-05-11 DATA-CNAE-001'),
    ('6311', 'informatica',        'seed 2026-05-11 DATA-CNAE-001'),
    ('6319', 'informatica',        'seed 2026-05-11 DATA-CNAE-001'),
    ('2710', 'equipamentos',       'seed 2026-05-11 DATA-CNAE-001'),
    ('2759', 'equipamentos',       'seed 2026-05-11 DATA-CNAE-001'),
    ('2861', 'equipamentos',       'seed 2026-05-11 DATA-CNAE-001'),
    ('4921', 'transporte',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4922', 'transporte',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4924', 'transporte',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4929', 'transporte',         'seed 2026-05-11 DATA-CNAE-001'),
    ('4930', 'transporte',         'seed 2026-05-11 DATA-CNAE-001'),
    ('8411', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001 admin publico'),
    ('8412', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001 admin publico'),
    ('8413', 'engenharia',         'seed 2026-05-11 DATA-CNAE-001 admin publico')
ON CONFLICT (cnae_code) DO NOTHING;

COMMIT;
