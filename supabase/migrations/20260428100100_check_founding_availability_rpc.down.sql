-- ============================================================================
-- DOWN: check_founding_availability RPC — reverses 20260428100100_check_founding_availability_rpc.sql
-- Date: 2026-04-28
-- Author: BIZ-FOUND-002
-- ============================================================================
-- Context:
--   Drops the public.check_founding_availability() RPC. Must be applied
--   BEFORE 20260428100000_founding_canonical_policy.down.sql since the
--   function references the founding_policy table.
-- ============================================================================

BEGIN;

REVOKE EXECUTE ON FUNCTION public.check_founding_availability()
    FROM service_role, authenticated, anon;

DROP FUNCTION IF EXISTS public.check_founding_availability();

NOTIFY pgrst, 'reload schema';

COMMIT;
