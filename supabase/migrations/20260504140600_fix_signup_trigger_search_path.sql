-- Fix signup wedge: handle_new_user + create_default_alert_preferences
-- Root cause: SECURITY DEFINER without SET search_path inherits caller's
-- search_path. supabase_auth_admin (GoTrue role) has search_path=auth, so
-- nested trigger create_default_alert_preferences references unqualified
-- `alert_preferences` and fails with 42P01 (relation does not exist),
-- aborting auth.users INSERT and surfacing as "Database error saving new user".
--
-- Fix (defense-in-depth):
--   1. SET search_path = public, pg_temp on both functions
--   2. SECURITY DEFINER on create_default_alert_preferences
--   3. EXCEPTION handler in handle_new_user so partial failures don't abort signup
--
-- Repro: signup wedge since 2026-04-10 (24 days, 0 new users).
-- Validated post-fix: signup 200 OK, profile+alert_preferences cascade populated.

CREATE OR REPLACE FUNCTION public.create_default_alert_preferences()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $func$
BEGIN
  INSERT INTO public.alert_preferences (user_id)
  VALUES (NEW.id)
  ON CONFLICT (user_id) DO NOTHING;
  RETURN NEW;
END;
$func$;

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $func$
DECLARE
  _phone text;
BEGIN
  _phone := regexp_replace(COALESCE(NEW.raw_user_meta_data->>'phone_whatsapp', ''), '[^0-9]', '', 'g');
  IF length(_phone) > 11 AND left(_phone, 2) = '55' THEN _phone := substring(_phone from 3); END IF;
  IF left(_phone, 1) = '0' THEN _phone := substring(_phone from 2); END IF;
  IF length(_phone) NOT IN (10, 11) THEN _phone := NULL; END IF;

  BEGIN
    INSERT INTO public.profiles (
      id, email, full_name, company, sector,
      phone_whatsapp, whatsapp_consent, plan_type,
      avatar_url, context_data, trial_expires_at
    )
    VALUES (
      NEW.id,
      NEW.email,
      COALESCE(NEW.raw_user_meta_data->>'full_name', ''),
      COALESCE(NEW.raw_user_meta_data->>'company', ''),
      COALESCE(NEW.raw_user_meta_data->>'sector', ''),
      _phone,
      COALESCE((NEW.raw_user_meta_data->>'whatsapp_consent')::boolean, FALSE),
      'free_trial',
      NEW.raw_user_meta_data->>'avatar_url',
      '{}'::jsonb,
      NOW() + INTERVAL '14 days'
    )
    ON CONFLICT (id) DO NOTHING;
  EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'handle_new_user failed user=%: % (%)', NEW.id, SQLERRM, SQLSTATE;
  END;

  RETURN NEW;
END;
$func$;
