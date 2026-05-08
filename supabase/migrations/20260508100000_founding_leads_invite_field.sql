-- ============================================================================
-- Migration: 20260508100000_founding_leads_invite_field
-- Story: FOUND-CRIT-003 / FOUND-CRIT-006 — Founding webhook mode=payment +
--        magic-link invite for buyers without accounts
-- Date: 2026-05-08
--
-- Purpose:
--   Adds magic_link_sent_at to founding_leads to gate idempotency for the
--   Supabase invite_user_by_email call dispatched by the webhook handler when
--   a founding checkout completes but the buyer has not yet created an account.
--
--   The column is already referenced in routes/founding.py (GET /session-status)
--   and test fixtures — this migration materialises it in the DB.
--
-- Down migration: 20260508100000_founding_leads_invite_field.down.sql
-- ============================================================================

BEGIN;

ALTER TABLE public.founding_leads
    ADD COLUMN IF NOT EXISTS magic_link_sent_at TIMESTAMPTZ NULL;

COMMENT ON COLUMN public.founding_leads.magic_link_sent_at IS
    'FOUND-CRIT-003: timestamp when the Supabase magic-link invite was sent to a '
    'founding buyer who has not yet created an account. NULL = invite not sent. '
    'Used as idempotency gate — webhook skips re-invite if NOT NULL.';

-- Partial index for efficient invite-pending queries.
CREATE INDEX IF NOT EXISTS idx_founding_leads_invite_pending
    ON public.founding_leads (email)
    WHERE checkout_status = 'completed' AND magic_link_sent_at IS NULL;

NOTIFY pgrst, 'reload schema';

COMMIT;
