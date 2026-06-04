-- LIFECYCLE-002 (#1427): Login tracking columns and tables
--
-- Adds:
--   - last_login_at + login_count columns to profiles
--   - login_activity table (1 row per user per day)
--   - record_login RPC for atomic increment

-- ============================================================
-- 1. Add columns to profiles
-- ============================================================
alter table public.profiles
  add column if not exists last_login_at timestamptz,
  add column if not exists login_count int not null default 0;

-- ============================================================
-- 2. Create login_activity table
-- ============================================================
create table if not exists public.login_activity (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  login_date date not null,
  created_at timestamptz not null default now(),
  unique(user_id, login_date)
);

create index if not exists idx_login_activity_user_date
  on public.login_activity(user_id, login_date desc);

-- ============================================================
-- 3. RLS for login_activity
-- ============================================================
alter table public.login_activity enable row level security;

create policy "login_activity_select_own" on public.login_activity
  for select using (auth.uid() = user_id);

-- Note: inserts are done by service_role (write-behind flush), not by the user.
-- No insert/update policy needed since service_role bypasses RLS.

-- ============================================================
-- 4. RPC for atomic login tracking (idempotent per day)
-- ============================================================
-- Only increments login_count when a NEW login_activity row is
-- inserted (first login of the day). Still updates last_login_at
-- on repeated calls within the same day.
create or replace function public.record_login(
  p_user_id uuid,
  p_login_date date default current_date,
  p_last_login_at timestamptz default now()
) returns void as $$
declare
  v_row_count int;
begin
  -- Insert login_activity (idempotent per day)
  insert into public.login_activity (user_id, login_date)
  values (p_user_id, p_login_date)
  on conflict (user_id, login_date) do nothing;

  get diagnostics v_row_count = row_count;

  if v_row_count > 0 then
    -- New login day: increment login_count
    update public.profiles
    set last_login_at = p_last_login_at,
        login_count = login_count + 1
    where id = p_user_id;
  else
    -- Same day update: only refresh last_login_at
    update public.profiles
    set last_login_at = p_last_login_at
    where id = p_user_id;
  end if;
end;
$$ language plpgsql security definer;
