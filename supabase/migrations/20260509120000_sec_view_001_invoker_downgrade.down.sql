-- SEC-VIEW-001 ROLLBACK: revert security_invoker downgrade and GRANT changes.
--
-- WARNING: re-enabling SECURITY DEFINER on these views will re-introduce the
-- Supabase advisor "Security Definer View" lints. Only run this if you need to
-- restore the prior posture for an incident.

-- Revert security_invoker = true → false (DEFINER behavior).
ALTER VIEW public.ingestion_orphan_checkpoints SET (security_invoker = false);
ALTER VIEW public.pncp_raw_bids_bloat_stats   SET (security_invoker = false);
ALTER VIEW public.cron_job_health             SET (security_invoker = false);

-- Restore prior GRANTs.
-- pncp_raw_bids_bloat_stats was granted to authenticated + service_role originally
-- (see 20260331000000_debt203_bloat_monitoring.sql section 3).
GRANT SELECT ON public.pncp_raw_bids_bloat_stats TO authenticated;
GRANT SELECT ON public.pncp_raw_bids_bloat_stats TO service_role;

-- cron_job_health had no explicit GRANTs in the source migration
-- (20260414120000_cron_job_health.sql) — only the get_cron_health() RPC was
-- restricted. Granting authenticated SELECT here is intentional rollback to
-- "broader" pre-SEC-VIEW-001 posture.
GRANT SELECT ON public.cron_job_health TO authenticated;
GRANT SELECT ON public.cron_job_health TO service_role;

-- ingestion_orphan_checkpoints: no change to GRANTs (we did not REVOKE in UP).

NOTIFY pgrst, 'reload schema';
