-- BIZ-METRIC-001 (AC2): app_config
--
-- Generic key/value JSONB config table to replace hardcoded constants in
-- backend (starting with ``hours_saved_per_search`` from
-- backend/routes/analytics.py). Read by the backend through a TTL-cached
-- helper; only admins can mutate via PATCH /v1/admin/config/{key}.
--
-- Story: docs/stories/2026-04/BIZ-METRIC-001-empirical-hours-saved-survey.story.md
-- Reversa Audit: _reversa_sdd/review-report.md (Gap-6)
--
-- Note on initial seed value: the existing route uses ``total_searches * 2``
-- (NOT 2.5 as the original story draft mentioned). To preserve the current
-- behaviour and the existing test_analytics.py assertion
-- (``estimated_hours_saved == 6.0  # 3 * 2``), we seed ``2.0`` here.
-- The story draft will be amended to reflect this (Change Log entry).

CREATE TABLE IF NOT EXISTS public.app_config (
  key          TEXT         NOT NULL PRIMARY KEY,
  value        JSONB        NOT NULL,
  description  TEXT,
  updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_by   UUID         REFERENCES auth.users(id) ON DELETE SET NULL,

  CONSTRAINT app_config_key_format_chk
    CHECK (key ~ '^[a-z][a-z0-9_]*$' AND length(key) BETWEEN 1 AND 128)
);

COMMENT ON TABLE  public.app_config             IS 'BIZ-METRIC-001 AC2: key/value JSONB config replacing hardcoded backend constants';
COMMENT ON COLUMN public.app_config.key         IS 'Snake_case identifier; stable contract for backend reads';
COMMENT ON COLUMN public.app_config.value       IS 'JSONB payload — supports scalars, arrays, objects';
COMMENT ON COLUMN public.app_config.description IS 'Human-readable explanation of what this config controls';
COMMENT ON COLUMN public.app_config.updated_by  IS 'Admin user that last mutated this row (audit trail)';

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.app_config_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS app_config_updated_at_trg ON public.app_config;
CREATE TRIGGER app_config_updated_at_trg
  BEFORE UPDATE ON public.app_config
  FOR EACH ROW
  EXECUTE FUNCTION public.app_config_set_updated_at();

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
-- Backend reads via service_role (bypasses RLS). Authenticated clients
-- have NO direct access — admin mutations go through the
-- /v1/admin/config/{key} endpoint which itself enforces require_admin.

ALTER TABLE public.app_config ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role full access on app_config" ON public.app_config;
CREATE POLICY "Service role full access on app_config"
  ON public.app_config
  FOR ALL
  USING (auth.role() = 'service_role');

REVOKE ALL ON public.app_config FROM authenticated;
REVOKE ALL ON public.app_config FROM anon;
GRANT  ALL ON public.app_config TO service_role;

-- ---------------------------------------------------------------------------
-- Seed
-- ---------------------------------------------------------------------------
INSERT INTO public.app_config (key, value, description)
VALUES (
  'hours_saved_per_search',
  '2.0'::jsonb,
  'BIZ-METRIC-001: per-search hours-saved multiplier surfaced on the personal dashboard. Seed value preserves the previous hardcoded constant (analytics.py used total_searches * 2). To be empirically calibrated via post-export survey + scripts/recalibrate_hours_saved.py once n>=30 valid responses collected.'
)
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Verification
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  RAISE NOTICE 'BIZ-METRIC-001 AC2: app_config table created (seeded hours_saved_per_search=2.0)';
END $$;
