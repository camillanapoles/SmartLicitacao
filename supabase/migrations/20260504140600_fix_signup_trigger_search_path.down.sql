-- Rollback: restore pre-fix versions (search_path inherited, no exception handler).
-- WARNING: rollback re-introduces signup wedge bug. Only use if fix causes regression.

CREATE OR REPLACE FUNCTION public.create_default_alert_preferences()
RETURNS trigger
LANGUAGE plpgsql
AS $func$
BEGIN
  INSERT INTO alert_preferences (user_id)
  VALUES (NEW.id)
  ON CONFLICT (user_id) DO NOTHING;
  RETURN NEW;
END;
$func$;

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $func$
DECLARE
  _phone text;
BEGIN
  _phone := regexp_replace(COALESCE(NEW.raw_user_meta_data->>'phone_whatsapp', ''), '[^0-9]', '', 'g');
  IF length(_phone) > 11 AND left(_phone, 2) = '55' THEN _phone := substring(_phone from 3); END IF;
  IF left(_phone, 1) = '0' THEN _phone := substring(_phone from 2); END IF;
  IF length(_phone) NOT IN (10, 11) THEN _phone := NULL; END IF;

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
  RETURN NEW;
END;
$func$;
