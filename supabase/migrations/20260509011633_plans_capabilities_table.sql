-- ============================================================================
-- UP: plans capabilities table — TD-GTM-003 (#192)
-- Date: 2026-05-09
-- Author: @dev / @data-engineer
-- ============================================================================
-- Context:
--   Migrates hardcoded PLAN_CAPABILITIES dict (backend/quota/quota_core.py) to
--   the existing public.plans table by adding capability columns + audit table.
--
-- Changes:
--   1. ADD columns to public.plans:
--      - display_name text         (UI-facing label)
--      - monthly_quota int         (mirrors max_searches per spec)
--      - capabilities jsonb        (structured plan limits — source of truth)
--      - version int default 1
--      - updated_at timestamptz default now()
--      - updated_by uuid references auth.users(id)
--   2. CREATE TABLE public.plans_audit (full history INSERT/UPDATE/DELETE)
--   3. CREATE TRIGGER on public.plans → public.plans_audit
--   4. RLS:
--      - plans: existing public SELECT preserved (anon hits /v1/plans landing)
--               writes restricted to service_role
--      - plans_audit: service_role only (read + write)
--   5. SEED missing plan rows (free_trial, founding_member, consultoria) so
--      _load_plan_capabilities_from_db() returns complete coverage.
--   6. BACKFILL capabilities jsonb for every plan_id from hardcoded dict.
-- ============================================================================

BEGIN;

-- 1. Add columns to existing public.plans table
ALTER TABLE public.plans
  ADD COLUMN IF NOT EXISTS display_name text,
  ADD COLUMN IF NOT EXISTS monthly_quota int,
  ADD COLUMN IF NOT EXISTS capabilities jsonb,
  ADD COLUMN IF NOT EXISTS version int NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_by uuid REFERENCES auth.users(id) ON DELETE SET NULL;

COMMENT ON COLUMN public.plans.capabilities IS
  'JSONB plan limits: max_history_days, allow_excel, allow_pipeline, max_requests_per_month, max_requests_per_min, max_summary_tokens, priority. Source of truth for runtime quota enforcement (TD-GTM-003 #192).';
COMMENT ON COLUMN public.plans.monthly_quota IS
  'Monthly request quota; mirrors max_searches. Kept distinct so #192 spec is auditable.';
COMMENT ON COLUMN public.plans.version IS
  'Monotonically incremented on capability change. Used by clients to detect changes without polling.';

-- 2. Seed missing plan rows that exist in hardcoded PLAN_CAPABILITIES
--    Existing rows: free, pack_5, pack_10, pack_20, monthly, annual, master, smartlic_pro
--    Hardcoded dict additionally has: free_trial, consultor_agil, maquina, sala_guerra, founding_member, consultoria
INSERT INTO public.plans (id, name, description, max_searches, price_brl, duration_days, is_active)
VALUES
  ('free_trial',      'FREE Trial',                'GTM-003: 14-day full-access trial',         1000, 0,       14,  true),
  ('consultor_agil',  'Consultor Ágil (legacy)',   'Legacy plan — kept for historical subs',    50,   297.00,  30,  false),
  ('maquina',         'Máquina (legacy)',          'Legacy plan — kept for historical subs',    300,  597.00,  30,  false),
  ('sala_guerra',     'Sala de Guerra (legacy)',   'Legacy plan — kept for historical subs',    1000, 1497.00, 30,  false),
  ('founding_member', 'SmartLic Founding Member',  'MAYDAY-A2: same caps as Pro, 50% off',     1000, 197.00,  30,  true),
  ('consultoria',     'SmartLic Consultoria',      'STORY-322: multi-user org plan',           5000, 997.00,  30,  true)
ON CONFLICT (id) DO NOTHING;

-- 3. Backfill capabilities jsonb + display_name + monthly_quota for ALL plan_ids
--    Single statement using CASE so the migration is hermetic — does not depend
--    on Python code for source of truth at apply-time.
UPDATE public.plans SET
  display_name = CASE id
    WHEN 'free_trial'      THEN 'FREE Trial'
    WHEN 'consultor_agil'  THEN 'Consultor Ágil (legacy)'
    WHEN 'maquina'         THEN 'Máquina (legacy)'
    WHEN 'sala_guerra'     THEN 'Sala de Guerra (legacy)'
    WHEN 'smartlic_pro'    THEN 'SmartLic Pro'
    WHEN 'founding_member' THEN 'SmartLic Founding Member'
    WHEN 'consultoria'     THEN 'SmartLic Consultoria'
    WHEN 'free'            THEN 'Free'
    WHEN 'master'          THEN 'Master'
    ELSE name
  END,
  monthly_quota = CASE id
    WHEN 'free_trial'      THEN 1000
    WHEN 'consultor_agil'  THEN 50
    WHEN 'maquina'         THEN 300
    WHEN 'sala_guerra'     THEN 1000
    WHEN 'smartlic_pro'    THEN 1000
    WHEN 'founding_member' THEN 1000
    WHEN 'consultoria'     THEN 5000
    WHEN 'free'            THEN 10
    WHEN 'master'          THEN 99999
    ELSE COALESCE(max_searches, 0)
  END,
  capabilities = CASE id
    WHEN 'free_trial' THEN jsonb_build_object(
      'max_history_days', 365,
      'allow_excel', true,
      'allow_pipeline', true,
      'max_requests_per_month', 1000,
      'max_requests_per_min', 2,
      'max_summary_tokens', 10000,
      'priority', 'normal'
    )
    WHEN 'consultor_agil' THEN jsonb_build_object(
      'max_history_days', 30,
      'allow_excel', false,
      'allow_pipeline', false,
      'max_requests_per_month', 50,
      'max_requests_per_min', 10,
      'max_summary_tokens', 200,
      'priority', 'normal'
    )
    WHEN 'maquina' THEN jsonb_build_object(
      'max_history_days', 365,
      'allow_excel', true,
      'allow_pipeline', true,
      'max_requests_per_month', 300,
      'max_requests_per_min', 30,
      'max_summary_tokens', 500,
      'priority', 'high'
    )
    WHEN 'sala_guerra' THEN jsonb_build_object(
      'max_history_days', 1825,
      'allow_excel', true,
      'allow_pipeline', true,
      'max_requests_per_month', 1000,
      'max_requests_per_min', 60,
      'max_summary_tokens', 10000,
      'priority', 'critical'
    )
    WHEN 'smartlic_pro' THEN jsonb_build_object(
      'max_history_days', 1825,
      'allow_excel', true,
      'allow_pipeline', true,
      'max_requests_per_month', 1000,
      'max_requests_per_min', 60,
      'max_summary_tokens', 10000,
      'priority', 'normal'
    )
    WHEN 'founding_member' THEN jsonb_build_object(
      'max_history_days', 1825,
      'allow_excel', true,
      'allow_pipeline', true,
      'max_requests_per_month', 1000,
      'max_requests_per_min', 60,
      'max_summary_tokens', 10000,
      'priority', 'normal'
    )
    WHEN 'consultoria' THEN jsonb_build_object(
      'max_history_days', 1825,
      'allow_excel', true,
      'allow_pipeline', true,
      'max_requests_per_month', 5000,
      'max_requests_per_min', 10,
      'max_summary_tokens', 10000,
      'priority', 'high'
    )
    WHEN 'free' THEN jsonb_build_object(
      'max_history_days', 7,
      'allow_excel', false,
      'allow_pipeline', false,
      'max_requests_per_month', 10,
      'max_requests_per_min', 2,
      'max_summary_tokens', 200,
      'priority', 'low'
    )
    WHEN 'master' THEN jsonb_build_object(
      'max_history_days', 99999,
      'allow_excel', true,
      'allow_pipeline', true,
      'max_requests_per_month', 99999,
      'max_requests_per_min', 120,
      'max_summary_tokens', 10000,
      'priority', 'high'
    )
    ELSE capabilities
  END;

-- 4. Create plans_audit table
CREATE TABLE IF NOT EXISTS public.plans_audit (
  id bigserial PRIMARY KEY,
  plan_id text,
  operation text NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
  old_value jsonb,
  new_value jsonb,
  changed_by uuid,
  changed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_plans_audit_plan_id_changed_at
  ON public.plans_audit (plan_id, changed_at DESC);

COMMENT ON TABLE public.plans_audit IS
  'Immutable audit log of every change to public.plans (TD-GTM-003 #192).';

-- 5. Audit trigger function — SECURITY INVOKER (default).
--    Writers of public.plans are constrained to service_role by RLS, so the
--    trigger inherits service_role privileges and does not need DEFINER.
CREATE OR REPLACE FUNCTION public.plans_audit_trigger_fn()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO public.plans_audit (plan_id, operation, old_value, new_value, changed_by)
    VALUES (NEW.id, 'INSERT', NULL, to_jsonb(NEW), NEW.updated_by);
    RETURN NEW;
  ELSIF TG_OP = 'UPDATE' THEN
    INSERT INTO public.plans_audit (plan_id, operation, old_value, new_value, changed_by)
    VALUES (NEW.id, 'UPDATE', to_jsonb(OLD), to_jsonb(NEW), NEW.updated_by);
    RETURN NEW;
  ELSIF TG_OP = 'DELETE' THEN
    INSERT INTO public.plans_audit (plan_id, operation, old_value, new_value, changed_by)
    VALUES (OLD.id, 'DELETE', to_jsonb(OLD), NULL, OLD.updated_by);
    RETURN OLD;
  END IF;
  RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS plans_audit_trigger ON public.plans;
CREATE TRIGGER plans_audit_trigger
  AFTER INSERT OR UPDATE OR DELETE ON public.plans
  FOR EACH ROW EXECUTE FUNCTION public.plans_audit_trigger_fn();

-- 6. RLS — keep existing public SELECT on plans (anon hits /v1/plans on landing
--    page). Tighten WRITES to service_role only. plans_audit is service_role-only.
--
--    Existing policy "plans_select_all FOR SELECT USING (true)" stays in place.
--    Add explicit deny-by-default for non-service writes.

-- Drop and re-create write policies idempotently
DROP POLICY IF EXISTS "plans_service_write" ON public.plans;
CREATE POLICY "plans_service_write" ON public.plans
  FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE public.plans_audit ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "plans_audit_service_all" ON public.plans_audit;
CREATE POLICY "plans_audit_service_all" ON public.plans_audit
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- 7. Self-test invariant: every active plan must now have a non-null capabilities
DO $$
DECLARE
  missing_count int;
BEGIN
  SELECT count(*) INTO missing_count
  FROM public.plans
  WHERE is_active = true AND capabilities IS NULL;

  IF missing_count > 0 THEN
    RAISE EXCEPTION 'TD-GTM-003 #192 invariant failed: % active plans have NULL capabilities', missing_count;
  END IF;
END $$;

COMMIT;
