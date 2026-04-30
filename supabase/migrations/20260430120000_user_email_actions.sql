-- 20260430120000_user_email_actions.sql
-- CONV-INST-003: Persist email resend cooldown + confirm events in DB
-- so they survive Railway redeploys (previously in-memory _resend_timestamps reset 2-3x/week).
CREATE TABLE IF NOT EXISTS public.user_email_actions (
  id BIGSERIAL PRIMARY KEY,
  email TEXT NOT NULL,
  action_type TEXT NOT NULL CHECK (action_type IN ('resend','confirm')),
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_email_actions_email_created
  ON public.user_email_actions (email, created_at DESC);

ALTER TABLE public.user_email_actions ENABLE ROW LEVEL SECURITY;

-- service_role only (backend writes); deny anon/authenticated direct access
CREATE POLICY "service_role_insert" ON public.user_email_actions
  FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "service_role_select" ON public.user_email_actions
  FOR SELECT TO service_role USING (true);
