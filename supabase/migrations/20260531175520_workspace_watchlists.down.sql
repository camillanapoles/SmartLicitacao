-- B2GOPS-001 (Wave 0): Rollback workspace_watchlists schema + RPCs
--
-- Order: DROP FUNCTION before DROP TABLE (functions depend on tables at runtime,
-- but DROP TABLE CASCADE handles function dependency at the Postgres level).
-- We drop functions explicitly first for clarity and safety.

DROP FUNCTION IF EXISTS public.ops_match_watchlist(UUID);
DROP FUNCTION IF EXISTS public.ops_create_watchlist(TEXT, TEXT, JSONB, TEXT);

DROP TABLE IF EXISTS public.workspace_watchlist_matches CASCADE;
DROP TABLE IF EXISTS public.workspace_watchlists CASCADE;
