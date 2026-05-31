-- ============================================================================
-- DOWN: predict_incumbent_decay — reverts 20260531175429_predict_incumbent_decay
-- Issue: #1267
-- ============================================================================

DROP FUNCTION IF EXISTS public.predict_incumbent_decay(VARCHAR, TEXT, INT);
