-- LIFECYCLE-003 (#1428): User lifecycle classification
--
-- Creates:
--   1. user_lifecycle_state enum type (10 states)
--   2. compute_user_lifecycle(user_id UUID) function
--   3. user_lifecycle_cache + user_lifecycle_events tables
--   4. compute_all_user_lifecycles() batch function
--
-- Performance: CTE-based, <200ms for all users with proper indexes

-- ============================================================
-- 1. Create enum type for lifecycle states
-- ============================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_lifecycle_state') THEN
    CREATE TYPE public.user_lifecycle_state AS ENUM (
      'anonymous', 'lead', 'trial_active', 'trial_limited', 'trial_expired',
      'paid_active', 'paid_past_due', 'canceled', 'churned', 'power_user'
    );
  END IF;
END
$$;

-- ============================================================
-- 2. Create user_lifecycle cache table
-- ============================================================
CREATE TABLE IF NOT EXISTS public.user_lifecycle (
  user_id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
  lifecycle public.user_lifecycle_state NOT NULL,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_lifecycle_state
  ON public.user_lifecycle(lifecycle);

-- ============================================================
-- 3. Create user_lifecycle_events table (transition tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.user_lifecycle_events (
  id UUID PRIMARY KEY DEFAULT GEN_RANDOM_UUID(),
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  previous_lifecycle public.user_lifecycle_state,
  new_lifecycle public.user_lifecycle_state NOT NULL,
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lifecycle_events_user_time
  ON public.user_lifecycle_events(user_id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_lifecycle_events_changed_at
  ON public.user_lifecycle_events(changed_at DESC);

-- ============================================================
-- 4. RLS (service_role only -- admin endpoint uses service_role client)
-- ============================================================
ALTER TABLE public.user_lifecycle ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_lifecycle_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_all_lifecycle" ON public.user_lifecycle;
CREATE POLICY "service_all_lifecycle" ON public.user_lifecycle
  FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service_all_lifecycle_events" ON public.user_lifecycle_events;
CREATE POLICY "service_all_lifecycle_events" ON public.user_lifecycle_events
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================
-- 5. compute_user_lifecycle(p_user_id UUID) -- single user
--    Returns the classified lifecycle state for the given user.
--    Idempotent: stores result in user_lifecycle and logs
--    transitions to user_lifecycle_events when state changes.
-- ============================================================
CREATE OR REPLACE FUNCTION public.compute_user_lifecycle(p_user_id UUID)
RETURNS public.user_lifecycle_state
LANGUAGE plpgsql STABLE
AS $$
DECLARE
  v_state public.user_lifecycle_state;
  v_prev_state public.user_lifecycle_state;
  v_plan_type TEXT;
  v_sub_status TEXT;
  v_trial_expires_at TIMESTAMPTZ;
  v_last_login_at TIMESTAMPTZ;
  v_logins_14d INT;
  v_pipeline_count INT;
  v_alert_count INT;
  v_search_count INT;
  v_paid_subs INT;
BEGIN
  -- Fetch user profile data
  SELECT
    p.plan_type,
    p.subscription_status,
    p.trial_expires_at,
    p.last_login_at
  INTO v_plan_type, v_sub_status, v_trial_expires_at, v_last_login_at
  FROM public.profiles p
  WHERE p.id = p_user_id;

  -- No profile found -> anonymous
  IF NOT FOUND THEN
    RETURN 'anonymous'::public.user_lifecycle_state;
  END IF;

  -- Aggregate counts in parallel subqueries (efficient with indexes)
  SELECT
    COALESCE((SELECT COUNT(*) FROM public.login_activity la
              WHERE la.user_id = p_user_id AND la.login_date >= CURRENT_DATE - 14), 0),
    COALESCE((SELECT COUNT(*) FROM public.pipeline_items pi
              WHERE pi.user_id = p_user_id), 0),
    COALESCE((SELECT COUNT(*) FROM public.alerts a
              WHERE a.user_id = p_user_id AND a.active = true), 0),
    COALESCE((SELECT COUNT(*) FROM public.search_sessions ss
              WHERE ss.user_id = p_user_id), 0),
    COALESCE((SELECT COUNT(*) FROM public.user_subscriptions us
              WHERE us.user_id = p_user_id
                AND us.is_active = true
                AND us.plan_id NOT IN ('free_trial', 'free')
                AND us.subscription_status = 'active'), 0)
  INTO v_logins_14d, v_pipeline_count, v_alert_count, v_search_count, v_paid_subs;

  -- Get previously cached state (if any)
  SELECT lifecycle INTO v_prev_state
  FROM public.user_lifecycle
  WHERE user_id = p_user_id;

  -- === Classification (highest specificity first) ===

  -- Power user: overrides all other states
  IF v_logins_14d >= 5 AND v_pipeline_count >= 3 AND v_alert_count >= 1 THEN
    v_state := 'power_user';

  -- Churned: canceled + no login for 30 days
  ELSIF v_sub_status IN ('canceling', 'expired')
    AND (v_last_login_at IS NULL OR v_last_login_at < NOW() - INTERVAL '30 days') THEN
    v_state := 'churned';

  -- Canceled
  ELSIF v_sub_status IN ('canceling', 'expired') THEN
    v_state := 'canceled';

  -- Paid past due
  ELSIF v_sub_status = 'past_due' AND v_paid_subs > 0 THEN
    v_state := 'paid_past_due';

  -- Paid active
  ELSIF v_paid_subs > 0 THEN
    v_state := 'paid_active';

  -- Trial expired
  ELSIF v_plan_type = 'free_trial'
    AND v_trial_expires_at IS NOT NULL
    AND v_trial_expires_at < NOW() THEN
    v_state := 'trial_expired';

  -- Trial limited (quota exhaustion -- >= 3 searches used on free_trial)
  ELSIF v_plan_type = 'free_trial'
    AND (v_trial_expires_at IS NULL OR v_trial_expires_at > NOW())
    AND v_search_count >= 3 THEN
    v_state := 'trial_limited';

  -- Trial active
  ELSIF v_plan_type = 'free_trial'
    AND (v_trial_expires_at IS NULL OR v_trial_expires_at > NOW()) THEN
    v_state := 'trial_active';

  -- Lead: has profile but never started trial or paid
  ELSIF (v_plan_type IS NULL OR v_plan_type IN ('free', 'free_trial'))
    AND v_trial_expires_at IS NULL THEN
    v_state := 'lead';

  ELSE
    v_state := 'anonymous';
  END IF;

  -- === Track transition ===
  IF v_prev_state IS DISTINCT FROM v_state THEN
    INSERT INTO public.user_lifecycle_events (user_id, previous_lifecycle, new_lifecycle)
    VALUES (p_user_id, v_prev_state, v_state);
  END IF;

  -- === Upsert cache ===
  INSERT INTO public.user_lifecycle (user_id, lifecycle, computed_at)
  VALUES (p_user_id, v_state, NOW())
  ON CONFLICT (user_id) DO UPDATE SET
    lifecycle = v_state,
    computed_at = NOW();

  RETURN v_state;
END;
$$;

-- ============================================================
-- 6. compute_all_user_lifecycles() -- batch compute for all users
--    Returns table of (user_id, lifecycle) for every profile.
--    Uses a single CTE pass for performance (<200ms target).
-- ============================================================
CREATE OR REPLACE FUNCTION public.compute_all_user_lifecycles()
RETURNS TABLE(user_id UUID, lifecycle public.user_lifecycle_state)
LANGUAGE plpgsql STABLE
AS $$
BEGIN
  RETURN QUERY
  WITH stats AS (
    SELECT
      p.id,
      p.plan_type,
      p.subscription_status,
      p.trial_expires_at,
      p.last_login_at,
      COALESCE(la.logins_14d, 0) AS logins_14d,
      COALESCE(pi.pipeline_count, 0) AS pipeline_count,
      COALESCE(al.alert_count, 0) AS alert_count,
      COALESCE(ss.search_count, 0) AS search_count,
      COALESCE(ps.paid_subs, 0) AS paid_subs
    FROM public.profiles p
    LEFT JOIN LATERAL (
      SELECT COUNT(*) AS logins_14d
      FROM public.login_activity
      WHERE user_id = p.id AND login_date >= CURRENT_DATE - 14
    ) la ON true
    LEFT JOIN LATERAL (
      SELECT COUNT(*) AS pipeline_count
      FROM public.pipeline_items
      WHERE user_id = p.id
    ) pi ON true
    LEFT JOIN LATERAL (
      SELECT COUNT(*) AS alert_count
      FROM public.alerts
      WHERE user_id = p.id AND active = true
    ) al ON true
    LEFT JOIN LATERAL (
      SELECT COUNT(*) AS search_count
      FROM public.search_sessions
      WHERE user_id = p.id
    ) ss ON true
    LEFT JOIN LATERAL (
      SELECT COUNT(*) AS paid_subs
      FROM public.user_subscriptions
      WHERE user_id = p.id
        AND is_active = true
        AND plan_id NOT IN ('free_trial', 'free')
        AND subscription_status = 'active'
    ) ps ON true
  ),
  classified AS (
    SELECT
      s.id,
      CASE
        -- Power user
        WHEN s.logins_14d >= 5 AND s.pipeline_count >= 3 AND s.alert_count >= 1
          THEN 'power_user'::public.user_lifecycle_state
        -- Churned
        WHEN s.subscription_status IN ('canceling', 'expired')
          AND (s.last_login_at IS NULL OR s.last_login_at < NOW() - INTERVAL '30 days')
          THEN 'churned'::public.user_lifecycle_state
        -- Canceled
        WHEN s.subscription_status IN ('canceling', 'expired')
          THEN 'canceled'::public.user_lifecycle_state
        -- Paid past due
        WHEN s.subscription_status = 'past_due' AND s.paid_subs > 0
          THEN 'paid_past_due'::public.user_lifecycle_state
        -- Paid active
        WHEN s.paid_subs > 0
          THEN 'paid_active'::public.user_lifecycle_state
        -- Trial expired
        WHEN s.plan_type = 'free_trial'
          AND s.trial_expires_at IS NOT NULL
          AND s.trial_expires_at < NOW()
          THEN 'trial_expired'::public.user_lifecycle_state
        -- Trial limited
        WHEN s.plan_type = 'free_trial'
          AND (s.trial_expires_at IS NULL OR s.trial_expires_at > NOW())
          AND s.search_count >= 3
          THEN 'trial_limited'::public.user_lifecycle_state
        -- Trial active
        WHEN s.plan_type = 'free_trial'
          AND (s.trial_expires_at IS NULL OR s.trial_expires_at > NOW())
          THEN 'trial_active'::public.user_lifecycle_state
        -- Lead
        WHEN (s.plan_type IS NULL OR s.plan_type IN ('free', 'free_trial'))
          AND s.trial_expires_at IS NULL
          THEN 'lead'::public.user_lifecycle_state
        ELSE 'anonymous'::public.user_lifecycle_state
      END AS lifecycle
    FROM stats s
  )
  SELECT c.id, c.lifecycle
  FROM classified c;
END;
$$;

-- ============================================================
-- 7. Helper: get_user_lifecycles() -- read current cached states
-- ============================================================
CREATE OR REPLACE FUNCTION public.get_user_lifecycles()
RETURNS TABLE(
  user_id UUID,
  lifecycle public.user_lifecycle_state,
  computed_at TIMESTAMPTZ
)
LANGUAGE plpgsql STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT ul.user_id, ul.lifecycle, ul.computed_at
  FROM public.user_lifecycle ul
  ORDER BY ul.lifecycle, ul.user_id;
END;
$$;
