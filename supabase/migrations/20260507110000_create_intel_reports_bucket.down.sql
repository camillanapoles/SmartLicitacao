-- ============================================================================
-- DOWN: create_intel_reports_bucket — #824 INTEL-BLOCKER
-- Rollback: drop intel-reports Storage bucket and its RLS policies
-- ============================================================================

BEGIN;

DROP POLICY IF EXISTS "users_read_own_intel_reports" ON storage.objects;
DROP POLICY IF EXISTS "service_role_full_access_intel_reports" ON storage.objects;

DELETE FROM storage.buckets WHERE id = 'intel-reports';

COMMIT;
