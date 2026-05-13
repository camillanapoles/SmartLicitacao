-- SEN-BE-005: RPC for /sitemap/contratos-orgao-indexable
-- Single query GROUP BY + ORDER BY + LIMIT via idx_psc_orgao_cnpj_active_partial
-- Returns JSON scalar (bypasses PostgREST max-rows=1000)
-- Expected < 1s for 2000 results

CREATE OR REPLACE FUNCTION public.get_sitemap_contratos_orgao_json(max_results integer DEFAULT 2000)
RETURNS json
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT COALESCE(json_agg(t.orgao_cnpj ORDER BY t.contract_count DESC), '[]'::json)
  FROM (
    SELECT orgao_cnpj, COUNT(*) AS contract_count
    FROM pncp_supplier_contracts
    WHERE is_active = true
      AND orgao_cnpj IS NOT NULL
      AND orgao_cnpj <> ''
      AND length(orgao_cnpj) >= 14
    GROUP BY orgao_cnpj
    ORDER BY contract_count DESC
    LIMIT max_results
  ) t;
$$;

GRANT EXECUTE ON FUNCTION public.get_sitemap_contratos_orgao_json(integer) TO anon, authenticated, service_role;
