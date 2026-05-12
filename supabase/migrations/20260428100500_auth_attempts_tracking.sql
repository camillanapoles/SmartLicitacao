-- MFA-EXT-001 AC4: auth_attempts table for brute-force MFA trigger.
--
-- Tracks consecutive password failures per user. Reset on:
--   - Successful login
--   - 24h idle window (via cron + per-attempt runtime check)
--
-- When `consecutive_failures >= 3` and user has no verified MFA, the
-- backend endpoint POST /auth/login-attempt sets
-- `profiles.force_mfa_enrollment_until = NOW() + 7d` and emits a Sentry
-- warning `auth.bruteforce.mfa_forced`.
--
-- RLS: service-role only (matches mfa_recovery_attempts pattern from STORY-317).
-- Fix migration: supabase/migrations/20260512173300_auth_attempts_rls_policy.sql adds
-- explicit service_role ALL policy to close the audit gap.
-- rls-exempt: auth_attempts — service-role only table, no anon/authenticated access needed.

BEGIN;

CREATE TABLE IF NOT EXISTS public.auth_attempts (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  consecutive_failures INTEGER NOT NULL DEFAULT 0,
  last_failure_at TIMESTAMPTZ,
  last_success_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.auth_attempts IS
  'MFA-EXT-001: per-user password attempt counter. 3 consecutive failures + no MFA -> force_mfa_enrollment_until set to NOW()+7d. Reset on success or 24h idle.';

COMMENT ON COLUMN public.auth_attempts.consecutive_failures IS
  'Count of consecutive password failures. Reset to 0 on successful login or after 24h idle (last_failure_at).';

-- Partial index used by cron to find stale rows needing reset
CREATE INDEX IF NOT EXISTS idx_auth_attempts_last_failure_at
  ON public.auth_attempts (last_failure_at)
  WHERE consecutive_failures > 0;

-- updated_at trigger (matches existing convention)
CREATE OR REPLACE FUNCTION public.update_auth_attempts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS auth_attempts_updated_at ON public.auth_attempts;
CREATE TRIGGER auth_attempts_updated_at
  BEFORE UPDATE ON public.auth_attempts
  FOR EACH ROW
  EXECUTE FUNCTION public.update_auth_attempts_updated_at();

-- RLS: lock down. Only service-role (backend) reads/writes.
ALTER TABLE public.auth_attempts ENABLE ROW LEVEL SECURITY;

-- No policies for authenticated/anon = no access.
-- Service-role bypasses RLS by design (Supabase default).

COMMIT;
