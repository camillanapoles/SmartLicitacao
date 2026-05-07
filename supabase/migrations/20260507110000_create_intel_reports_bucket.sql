-- ============================================================================
-- UP: create_intel_reports_bucket — #824 INTEL-BLOCKER
-- Date: 2026-05-07
-- Issue: #824
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   The ARQ job `generate_intel_report` (backend/jobs/queue/jobs.py) uploads
--   generated PDF files to the `intel-reports` Supabase Storage bucket.
--   Without this bucket the upload silently fails, blocking all real purchases
--   of the Intel Reports product.
--
--   Files are stored at path: {user_id}/{purchase_id}.pdf
--
--   Access model:
--     - service_role: full INSERT/SELECT for backend uploads and signed URLs
--     - authenticated: SELECT only for files in their own {user_id}/ prefix
--     - anon: no access
-- ============================================================================

BEGIN;

-- Create the private bucket for Intel Report PDFs
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'intel-reports',
    'intel-reports',
    false,
    52428800, -- 50MB limit per file
    ARRAY['application/pdf']
)
ON CONFLICT (id) DO NOTHING;

-- RLS: service_role full access (backend uploads via ARQ worker)
CREATE POLICY "service_role_full_access_intel_reports"
ON storage.objects
FOR ALL
TO service_role
USING (bucket_id = 'intel-reports')
WITH CHECK (bucket_id = 'intel-reports');

-- RLS: authenticated users can only read their own files.
-- Files are stored at {user_id}/{purchase_id}.pdf so foldername(name)[1]
-- (PG 1-indexed) is the user_id segment of the path.
CREATE POLICY "users_read_own_intel_reports"
ON storage.objects
FOR SELECT
TO authenticated
USING (
    bucket_id = 'intel-reports'
    AND (storage.foldername(name))[1] = auth.uid()::text
);

COMMIT;
