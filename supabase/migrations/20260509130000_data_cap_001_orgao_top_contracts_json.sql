-- DATA-CAP-001: get_orgao_top_contracts_json — RETURNS json scalar
-- Bypasses PostgREST max_rows=1000 cap by returning a single json scalar
-- instead of a TABLE/SETOF (the cap only applies to row-shaped results).
--
-- Used by backend/routes/orgao_publico.py::_fetch_contracts_data, which
-- previously did ``.limit(2000).execute()`` against pncp_supplier_contracts
-- and was silently capped at 1000 rows (so órgãos with >1000 contracts had
-- a degraded top-fornecedores aggregation). Default p_limit preserves the
-- previous 2000-row aggregation source set; the route still aggregates
-- top-N suppliers in Python from this raw set so we keep behavior identical.
--
-- Pattern reference: 20260408200000_sitemap_rpc_json.sql (sitemap RPCs).

CREATE OR REPLACE FUNCTION public.get_orgao_top_contracts_json(
    p_orgao_cnpj text,
    p_limit int DEFAULT 2000
)
RETURNS json
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  -- Returns the raw rows the route aggregates over — same projection as the
  -- previous .select("ni_fornecedor,nome_fornecedor,valor_global"). Python
  -- aggregator (top-fornecedores + total + valor_total) stays unchanged.
  SELECT COALESCE(
    json_agg(
      json_build_object(
        'ni_fornecedor', t.ni_fornecedor,
        'nome_fornecedor', t.nome_fornecedor,
        'valor_global', t.valor_global
      )
    ),
    '[]'::json
  )
  FROM (
    SELECT ni_fornecedor, nome_fornecedor, valor_global
    FROM pncp_supplier_contracts
    WHERE orgao_cnpj = p_orgao_cnpj
      AND is_active = true
    LIMIT p_limit
  ) t;
$$;

GRANT EXECUTE ON FUNCTION public.get_orgao_top_contracts_json(text, int)
    TO anon, authenticated, service_role;

COMMENT ON FUNCTION public.get_orgao_top_contracts_json(text, int) IS
    'DATA-CAP-001: Returns up to p_limit raw contract rows for an órgão CNPJ '
    'as a json scalar (bypasses PostgREST max_rows=1000 cap). Caller '
    'aggregates top suppliers in Python.';
