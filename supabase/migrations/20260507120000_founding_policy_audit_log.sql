BEGIN;

CREATE TABLE IF NOT EXISTS public.founding_policy_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changed_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    field_name TEXT NOT NULL,
    old_value JSONB,
    new_value JSONB,
    reason TEXT
);

-- Trigger function: record any UPDATE to founding_policy
CREATE OR REPLACE FUNCTION public.founding_policy_audit_trigger()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    -- Track changes to key fields
    IF OLD.deadline_at IS DISTINCT FROM NEW.deadline_at THEN
        INSERT INTO public.founding_policy_audit_log (field_name, old_value, new_value)
        VALUES ('deadline_at', to_jsonb(OLD.deadline_at), to_jsonb(NEW.deadline_at));
    END IF;
    IF OLD.seat_limit IS DISTINCT FROM NEW.seat_limit THEN
        INSERT INTO public.founding_policy_audit_log (field_name, old_value, new_value)
        VALUES ('seat_limit', to_jsonb(OLD.seat_limit), to_jsonb(NEW.seat_limit));
    END IF;
    IF OLD.active IS DISTINCT FROM NEW.active THEN
        INSERT INTO public.founding_policy_audit_log (field_name, old_value, new_value)
        VALUES ('active', to_jsonb(OLD.active), to_jsonb(NEW.active));
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS founding_policy_audit ON public.founding_policy;
CREATE TRIGGER founding_policy_audit
    AFTER UPDATE ON public.founding_policy
    FOR EACH ROW
    EXECUTE FUNCTION public.founding_policy_audit_trigger();

-- RLS: service_role can write, admin can read
ALTER TABLE public.founding_policy_audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "founding_policy_audit_service_write" ON public.founding_policy_audit_log
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

NOTIFY pgrst, 'reload schema';

COMMIT;
