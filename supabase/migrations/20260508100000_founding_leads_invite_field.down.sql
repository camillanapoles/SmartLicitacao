-- ============================================================================
-- Rollback: 20260508100000_founding_leads_invite_field
-- ============================================================================

BEGIN;

DROP INDEX IF EXISTS idx_founding_leads_invite_pending;

ALTER TABLE public.founding_leads
    DROP COLUMN IF EXISTS magic_link_sent_at;

COMMIT;
