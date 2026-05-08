-- ============================================================================
-- Migration: 20260508100000_founding_leads_invite_fields
-- Story: STORY-863 — Auto-create credentials after Founders purchase
-- Date: 2026-05-08
--
-- Purpose:
--   Adds invite tracking fields to founding_leads to support:
--     * invite_sent_at     — idempotency gate: skip re-invite if NOT NULL
--     * invite_token_hash  — optional hash of the Supabase invite token for
--                            audit / dedup (populated if token is available)
--
-- Down migration: 20260508100000_founding_leads_invite_fields.down.sql
-- ============================================================================

BEGIN;

ALTER TABLE public.founding_leads
    ADD COLUMN IF NOT EXISTS invite_sent_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS invite_token_hash TEXT NULL;

COMMENT ON COLUMN public.founding_leads.invite_sent_at IS
    'STORY-863: Timestamp when a Supabase auth invite email was dispatched to '
    'a founding buyer who had no pre-existing account. NULL = not yet sent. '
    'Used as idempotency gate — webhook skips invite if NOT NULL.';

COMMENT ON COLUMN public.founding_leads.invite_token_hash IS
    'STORY-863: SHA-256 hash of the Supabase invite token returned by '
    'auth.admin.invite_user_by_email, stored for audit purposes. '
    'NULL if the token was unavailable or hashing was skipped.';

-- Partial index for efficient idempotency queries on pending invites.
CREATE INDEX IF NOT EXISTS idx_founding_leads_invite_pending
    ON public.founding_leads (email)
    WHERE checkout_status = 'completed' AND invite_sent_at IS NULL;

NOTIFY pgrst, 'reload schema';

COMMIT;
