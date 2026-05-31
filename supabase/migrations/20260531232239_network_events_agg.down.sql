-- ============================================================================
-- DOWN: NETINT-001 — desfaz network_events_agg + network_record_event
-- Date: 2026-05-31
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   Reverte a migracao UP 20260531232239_network_events_agg.sql.
--   Remove na ordem inversa da UP para evitar dependencias quebradas.
-- ============================================================================

BEGIN;

-- 1. Drop RPC
DROP FUNCTION IF EXISTS public.network_record_event(TEXT, TEXT, TEXT, JSONB);

-- 2. Drop table (cascade remove indices, constraints, policies)
DROP TABLE IF EXISTS public.network_events_agg;

-- 3. Drop column from profiles
ALTER TABLE public.profiles
    DROP COLUMN IF EXISTS allow_network_analytics;

COMMIT;
