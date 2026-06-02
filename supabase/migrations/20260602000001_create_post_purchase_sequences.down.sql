-- CONV-011b-1: Rollback post_purchase_sequences schema
-- Drop table, indexes, policies, trigger, function.

DROP TRIGGER IF EXISTS trg_post_purchase_sequences_updated_at ON public.post_purchase_sequences;
DROP FUNCTION IF EXISTS public.set_post_purchase_sequences_updated_at();

DROP POLICY IF EXISTS "pps_owner_select"   ON public.post_purchase_sequences;
DROP POLICY IF EXISTS "pps_service_select"  ON public.post_purchase_sequences;
DROP POLICY IF EXISTS "pps_service_insert"  ON public.post_purchase_sequences;
DROP POLICY IF EXISTS "pps_service_update"  ON public.post_purchase_sequences;

DROP INDEX IF EXISTS idx_post_purchase_user_status;
DROP INDEX IF EXISTS idx_post_purchase_purchase;

DROP TABLE IF EXISTS public.post_purchase_sequences;
