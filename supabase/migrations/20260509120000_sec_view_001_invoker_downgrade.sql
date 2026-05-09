-- SEC-VIEW-001: Downgrade 3 SECURITY DEFINER views to SECURITY INVOKER.
--
-- Supabase Database Linter flags any view in `public` that runs with the
-- creator's privileges (default Postgres behavior pre-15) as a "Security
-- Definer View" lint. Postgres 15+ supports `security_invoker = true` on
-- views, which makes the view evaluate row access using the *invoker's*
-- role and policies — the safer default for application schemas.
--
-- Affected views:
--   1. public.ingestion_orphan_checkpoints
--      Source: 20260331300000_debt207_checkpoint_orphan_monitoring.sql
--      Reads:  public.ingestion_checkpoints LEFT JOIN public.ingestion_runs.
--              These are app tables guarded by RLS — INVOKER is the correct
--              behavior so RLS is enforced for the calling role.
--      GRANT:  Keep authenticated SELECT (RLS path).
--
--   2. public.pncp_raw_bids_bloat_stats
--      Source: 20260331000000_debt203_bloat_monitoring.sql
--      Reads:  pg_stat_user_tables / pg_total_relation_size /
--              pg_relation_size / pg_indexes_size — system catalogs that
--              are world-readable. INVOKER is fine; restrict GRANT to
--              service_role only because this is admin diagnostic data
--              and shouldn't bleed to authenticated dashboards.
--
--   3. public.cron_job_health
--      Source: 20260414120000_cron_job_health.sql
--      Reads:  cron.job + cron.job_run_details — cron schema is owned by
--              the supabase_admin/postgres role and not granted to
--              authenticated/anon. INVOKER guarantees access flows through
--              service_role's grants on cron.*; ANON/AUTHENTICATED would
--              receive permission_denied (which is the desired posture).
--      GRANT:  service_role only.
--
-- Rollback: see paired 20260509120000_sec_view_001_invoker_downgrade.down.sql

-- ════════════════════════════════════════════════════════════════════════
-- SECTION 1: Downgrade SECURITY DEFINER → SECURITY INVOKER (Postgres 15+)
-- ════════════════════════════════════════════════════════════════════════

ALTER VIEW public.ingestion_orphan_checkpoints SET (security_invoker = true);
ALTER VIEW public.pncp_raw_bids_bloat_stats   SET (security_invoker = true);
ALTER VIEW public.cron_job_health             SET (security_invoker = true);

-- ════════════════════════════════════════════════════════════════════════
-- SECTION 2: GRANT alignment
-- ════════════════════════════════════════════════════════════════════════
-- ingestion_orphan_checkpoints:
--   Keep authenticated GRANT — RLS on ingestion_checkpoints/ingestion_runs
--   already gates per-role access. INVOKER + RLS is the correct path.

-- pncp_raw_bids_bloat_stats: restrict to service_role only.
REVOKE ALL ON public.pncp_raw_bids_bloat_stats FROM authenticated;
REVOKE ALL ON public.pncp_raw_bids_bloat_stats FROM anon;
GRANT  SELECT ON public.pncp_raw_bids_bloat_stats TO service_role;

-- cron_job_health: restrict to service_role only.
REVOKE ALL ON public.cron_job_health FROM authenticated;
REVOKE ALL ON public.cron_job_health FROM anon;
GRANT  SELECT ON public.cron_job_health TO service_role;

-- ════════════════════════════════════════════════════════════════════════
-- SECTION 3: Verification
-- ════════════════════════════════════════════════════════════════════════

DO $$
DECLARE
    v_view RECORD;
    v_invoker_count INT := 0;
BEGIN
    FOR v_view IN
        SELECT c.relname, c.reloptions
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname IN (
              'ingestion_orphan_checkpoints',
              'pncp_raw_bids_bloat_stats',
              'cron_job_health'
          )
          AND c.relkind = 'v'
    LOOP
        IF v_view.reloptions IS NOT NULL
           AND 'security_invoker=true' = ANY(v_view.reloptions) THEN
            v_invoker_count := v_invoker_count + 1;
        ELSE
            RAISE WARNING 'SEC-VIEW-001: view % NOT downgraded to INVOKER (reloptions=%)',
                v_view.relname, v_view.reloptions;
        END IF;
    END LOOP;

    IF v_invoker_count <> 3 THEN
        RAISE WARNING 'SEC-VIEW-001: expected 3 INVOKER views, found %', v_invoker_count;
    ELSE
        RAISE NOTICE 'SEC-VIEW-001: 3/3 views downgraded to security_invoker=true';
    END IF;
END $$;

NOTIFY pgrst, 'reload schema';
