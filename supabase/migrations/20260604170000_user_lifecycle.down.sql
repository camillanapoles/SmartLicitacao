-- LIFECYCLE-003 (#1428): Rollback user lifecycle migration
--
-- Reverses in opposite order:
--   1. Drop functions
--   2. Drop tables
--   3. Drop enum type

drop function if exists public.get_user_lifecycles;
drop function if exists public.compute_all_user_lifecycles;
drop function if exists public.compute_user_lifecycle;

drop table if exists public.user_lifecycle_events;
drop table if exists public.user_lifecycle;

drop type if exists public.user_lifecycle_state;
