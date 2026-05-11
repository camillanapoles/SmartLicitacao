-- Rollback: restore mv_sitemap_orgaos without last_seen column
-- (reverts 20260510150000_sitemap_mv_orgaos_add_last_seen.sql)

REVOKE SELECT ON mv_sitemap_orgaos FROM anon, authenticated, service_role;

DROP MATERIALIZED VIEW mv_sitemap_orgaos;

CREATE MATERIALIZED VIEW mv_sitemap_orgaos AS
SELECT DISTINCT
    orgao_cnpj AS cnpj,
    COUNT(*) AS total_licitacoes
FROM pncp_raw_bids
WHERE orgao_cnpj ~ '^[A-Z0-9]{12}[0-9]{2}$'
  AND data_publicacao > NOW() - INTERVAL '12 months'
GROUP BY orgao_cnpj
HAVING COUNT(*) >= 5;

CREATE UNIQUE INDEX ON mv_sitemap_orgaos(cnpj);

GRANT SELECT ON mv_sitemap_orgaos TO anon, authenticated, service_role;

COMMENT ON MATERIALIZED VIEW mv_sitemap_orgaos IS 'Órgãos compradores indexáveis no sitemap /orgaos/{cnpj} — ≥5 licitações em 12 meses, atualizado 4h BRT via pg_cron';
