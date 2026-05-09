-- ============================================================================
-- DOWN: plans capabilities table — reverses 20260509011633_plans_capabilities_table.sql
-- Date: 2026-05-09
-- Author: @dev / @data-engineer
-- ============================================================================
-- Context:
--   Removes audit table, trigger, and the columns added to public.plans by
--   the up migration. Seeded plan rows (free_trial, founding_member, etc.) are
--   intentionally NOT deleted — other code/data may now reference them. If a
--   full rollback is required, that DELETE must be done manually after
--   verifying no FK refs exist in user_subscriptions / profiles.
-- ============================================================================

BEGIN;

-- Reverse trigger before columns it depends on
DROP TRIGGER IF EXISTS plans_audit_trigger ON public.plans;
DROP FUNCTION IF EXISTS public.plans_audit_trigger_fn();

-- Reverse policies
DROP POLICY IF EXISTS "plans_audit_service_all" ON public.plans_audit;
DROP POLICY IF EXISTS "plans_service_write" ON public.plans;

-- Drop audit table
DROP INDEX IF EXISTS public.idx_plans_audit_plan_id_changed_at;
DROP TABLE IF EXISTS public.plans_audit;

-- Drop columns added to plans (idempotent)
ALTER TABLE public.plans
  DROP COLUMN IF EXISTS updated_by,
  DROP COLUMN IF EXISTS updated_at,
  DROP COLUMN IF EXISTS version,
  DROP COLUMN IF EXISTS capabilities,
  DROP COLUMN IF EXISTS monthly_quota,
  DROP COLUMN IF EXISTS display_name;

COMMIT;
