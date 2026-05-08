-- ============================================================================
-- Down Migration: 20260508100000_founding_leads_invite_fields
-- Reverts: STORY-863 founding_leads invite tracking fields
-- ============================================================================

BEGIN;

DROP INDEX IF EXISTS public.idx_founding_leads_invite_pending;

ALTER TABLE public.founding_leads
    DROP COLUMN IF EXISTS invite_sent_at,
    DROP COLUMN IF EXISTS invite_token_hash;

COMMIT;
