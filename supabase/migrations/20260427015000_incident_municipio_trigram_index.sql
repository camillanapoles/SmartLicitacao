-- Backfill migration: drift recorded in prod schema_migrations on 2026-04-27 01:50 UTC
-- Source of truth: supabase_migrations.schema_migrations.statements (recovered 2026-04-28).
-- Applied originally as part of the backend outage Stage 1 hotfix (memory:
--   project_backend_outage_2026_04_27 + feedback_planner_no_pick_gin_trgm_with_limit_order)
-- to accelerate ILIKE/trigram lookups on pncp_supplier_contracts.municipio.
--
-- IMPORTANT: prod already has this index (verified via pg_indexes 2026-04-28).
-- File is committed solely to clear `supabase migration list` drift so future
-- `supabase db push` cycles stop failing with "remote migration not found locally".
--
-- After this file lands, operator runs (manual, with approval):
--   supabase migration repair --status applied 20260427015000
-- (NOTE: chief-trusty-pasteur transcript suggested `--status reverted`; that is
--  WRONG for our case — the migration is real and applied in prod, so the
--  correct repair status is `applied`.)

CREATE INDEX IF NOT EXISTS idx_psc_municipio_trgm
    ON public.pncp_supplier_contracts
    USING GIN (municipio gin_trgm_ops)
    WHERE is_active = TRUE;
