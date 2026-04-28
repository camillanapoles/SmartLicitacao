-- ============================================================================
-- DOWN: founding_canonical_policy — reverses 20260428100000_founding_canonical_policy.sql
-- Date: 2026-04-28
-- Author: BIZ-FOUND-002
-- ============================================================================
-- Context:
--   The up migration created the public.founding_policy single-row table,
--   the founding_policy_set_updated_at() trigger function, an updated_at
--   trigger, RLS policies, and a partial index on founding_leads. This
--   reverses everything in opposite order.
--
--   Note: the partial index idx_founding_leads_completed is dropped here
--   because it was created by this migration. Down for the RPC (in
--   20260428100100_check_founding_availability_rpc.down.sql) MUST run BEFORE
--   this down so the FUNCTION is dropped before its referencing table.
-- ============================================================================

BEGIN;

-- Revert checkout_status CHECK to the original 4-value set. Any existing
-- rows with checkout_status='cap_violated' must be remapped first or the
-- ADD will fail. We map them to 'failed' (semantically closest pre-rollback).
UPDATE public.founding_leads
    SET checkout_status = 'failed'
    WHERE checkout_status = 'cap_violated';

ALTER TABLE public.founding_leads
    DROP CONSTRAINT IF EXISTS founding_leads_checkout_status_check;

ALTER TABLE public.founding_leads
    ADD CONSTRAINT founding_leads_checkout_status_check
    CHECK (checkout_status IN ('pending', 'completed', 'abandoned', 'failed'));

DROP INDEX IF EXISTS public.idx_founding_leads_completed;

DROP POLICY IF EXISTS "founding_policy_service_write" ON public.founding_policy;
DROP POLICY IF EXISTS "founding_policy_public_read" ON public.founding_policy;

DROP TRIGGER IF EXISTS founding_policy_updated_at ON public.founding_policy;
DROP FUNCTION IF EXISTS public.founding_policy_set_updated_at();

DROP TABLE IF EXISTS public.founding_policy;

NOTIFY pgrst, 'reload schema';

COMMIT;
