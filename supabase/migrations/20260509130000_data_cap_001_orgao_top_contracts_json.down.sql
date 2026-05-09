-- DATA-CAP-001 rollback: drop get_orgao_top_contracts_json.
-- Routes fall back to the previous .limit(2000) PostgREST query path (which
-- is still the implementation in orgao_publico._fetch_contracts_data when
-- the RPC raises — see the try/except wrap there).

DROP FUNCTION IF EXISTS public.get_orgao_top_contracts_json(text, int);
