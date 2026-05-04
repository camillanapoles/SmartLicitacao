-- BIZ-METRIC-001 (AC1): export_time_saved_survey
--
-- Stores user responses to the post-export survey ("how long would
-- this have taken manually?"). Used by scripts/recalibrate_hours_saved.py
-- to empirically calibrate the analytics constant
-- ``app_config.hours_saved_per_search`` (replaces the previous hardcoded
-- value in backend/routes/analytics.py).
--
-- Story: docs/stories/2026-04/BIZ-METRIC-001-empirical-hours-saved-survey.story.md
-- Reversa Audit: _reversa_sdd/review-report.md (Gap-6)
--
-- Supabase CLI runs each migration file in its own transaction; no explicit
-- BEGIN/COMMIT needed (matches majority repo convention).

-- ---------------------------------------------------------------------------
-- Table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.export_time_saved_survey (
  id                       UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id                  UUID         NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  search_id                TEXT,
  export_id                TEXT,
  export_type              TEXT         NOT NULL,
  bid_count                INTEGER,
  estimated_manual_hours   NUMERIC(5,2) NOT NULL,
  free_text                TEXT,
  submitted_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

  CONSTRAINT export_time_saved_survey_export_type_chk
    CHECK (export_type IN ('excel', 'pdf', 'sheets')),

  CONSTRAINT export_time_saved_survey_hours_range_chk
    CHECK (estimated_manual_hours >= 0.1 AND estimated_manual_hours <= 50),

  CONSTRAINT export_time_saved_survey_bid_count_nonneg_chk
    CHECK (bid_count IS NULL OR bid_count >= 0),

  CONSTRAINT export_time_saved_survey_free_text_len_chk
    CHECK (free_text IS NULL OR length(free_text) <= 2000)
);

COMMENT ON TABLE  public.export_time_saved_survey                       IS 'BIZ-METRIC-001: user-reported time-saved estimates from post-export modal';
COMMENT ON COLUMN public.export_time_saved_survey.search_id             IS 'Search session correlation id (matches search_sessions.id when available)';
COMMENT ON COLUMN public.export_time_saved_survey.export_id             IS 'Export job/download identifier — correlate with download events';
COMMENT ON COLUMN public.export_time_saved_survey.export_type           IS 'excel | pdf | sheets';
COMMENT ON COLUMN public.export_time_saved_survey.bid_count             IS 'Number of bids included in the export (denominator for per-bid calibration)';
COMMENT ON COLUMN public.export_time_saved_survey.estimated_manual_hours IS 'User-reported manual-equivalent hours (range [0.1, 50])';
COMMENT ON COLUMN public.export_time_saved_survey.free_text             IS '"How would you have done this before?" — optional, capped 2000 chars';

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_export_time_saved_submitted_at
  ON public.export_time_saved_survey(submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_export_time_saved_user_submitted
  ON public.export_time_saved_survey(user_id, submitted_at DESC);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
-- Pattern (mirrors organization_audit_log RLS):
--   * authenticated users can SELECT their own rows
--   * authenticated users can INSERT rows where user_id = auth.uid()
--   * UPDATE / DELETE blocked for authenticated/anon (immutable from client)
--   * service_role has full access (admin endpoints + recalibration job)

ALTER TABLE public.export_time_saved_survey ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "User can read own surveys" ON public.export_time_saved_survey;
CREATE POLICY "User can read own surveys"
  ON public.export_time_saved_survey
  FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "User can insert own surveys" ON public.export_time_saved_survey;
CREATE POLICY "User can insert own surveys"
  ON public.export_time_saved_survey
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Service role full access on export surveys" ON public.export_time_saved_survey;
CREATE POLICY "Service role full access on export surveys"
  ON public.export_time_saved_survey
  FOR ALL
  USING (auth.role() = 'service_role');

REVOKE UPDATE, DELETE ON public.export_time_saved_survey FROM authenticated;
REVOKE UPDATE, DELETE ON public.export_time_saved_survey FROM anon;

GRANT SELECT, INSERT ON public.export_time_saved_survey TO authenticated;
GRANT ALL            ON public.export_time_saved_survey TO service_role;

-- ---------------------------------------------------------------------------
-- Verification
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  RAISE NOTICE 'BIZ-METRIC-001 AC1: export_time_saved_survey table created';
END $$;
