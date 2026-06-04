-- LIFECYCLE-002 (#1427): Rollback login tracking migration

drop function if exists public.record_login;
drop table if exists public.login_activity;
alter table public.profiles drop column if exists last_login_at;
alter table public.profiles drop column if exists login_count;
