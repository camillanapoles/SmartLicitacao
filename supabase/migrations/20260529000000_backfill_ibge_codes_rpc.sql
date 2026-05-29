-- RPC: backfill_ibge_codes(p_mapping jsonb)
-- Receives a JSON array of {nome, uf, codigo} objects and updates
-- pncp_raw_bids.codigo_municipio_ibge for matching rows where the
-- column is currently NULL/empty.
--
-- Used by ingestion/enricher.py::enrich_pncp_ibge_codes_job().
-- Runs after each crawl wave to backfill newly ingested rows.

CREATE OR REPLACE FUNCTION public.backfill_ibge_codes(p_mapping jsonb)
RETURNS TABLE(rows_updated bigint)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    WITH mapping AS (
        SELECT
            (item->>'nome')  AS nome,
            (item->>'uf')    AS uf,
            (item->>'codigo') AS codigo
        FROM jsonb_array_elements(p_mapping) AS item
    ),
    updated AS (
        UPDATE pncp_raw_bids b
        SET codigo_municipio_ibge = m.codigo,
            updated_at = now()
        FROM mapping m
        WHERE b.is_active = true
          AND LOWER(b.municipio) = LOWER(m.nome)
          AND UPPER(b.uf) = UPPER(m.uf)
          AND (b.codigo_municipio_ibge IS NULL OR b.codigo_municipio_ibge = '')
        RETURNING 1
    )
    RETURN QUERY
    SELECT count(*)::bigint AS rows_updated
    FROM updated;
END;
$$;
