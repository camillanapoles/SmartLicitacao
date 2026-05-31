-- COMPINT-002 rollback: remove competitor_win_metrics RPC
DROP FUNCTION IF EXISTS public.competitor_win_metrics(TEXT, INT);
