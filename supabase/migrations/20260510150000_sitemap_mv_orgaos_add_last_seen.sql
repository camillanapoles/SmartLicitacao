-- SEO-SITEMAP-MV-001 follow-up: Add last_seen column to mv_sitemap_orgaos
--
-- Motivation: sitemap_orgaos.py references mv_sitemap_orgaos.last_seen for
-- the stale-data Sentry alert (Alert 3). The initial migration
-- (20260510140000_sitemap_materialized_views.sql) only included cnpj and
-- total_licitacoes columns. This migration recreates the MV with last_seen
-- (MAX(data_publicacao)) so the staleness probe does not fail with a
-- column-not-found error.
--
-- Since MATERIALIZED VIEWs cannot be altered with ADD COLUMN, we must
-- DROP and recreate. CONCURRENTLY cannot be used for the first refresh
-- after recreate (no unique index yet), so we refresh normally then
-- re-create the index.

-- Revoke before drop to avoid permission errors
REVOKE SELECT ON mv_sitemap_orgaos FROM anon, authenticated, service_role;

DROP MATERIALIZED VIEW mv_sitemap_orgaos;

CREATE MATERIALIZED VIEW mv_sitemap_orgaos AS
SELECT DISTINCT
    orgao_cnpj AS cnpj,
    COUNT(*) AS total_licitacoes,
    MAX(data_publicacao) AS last_seen
FROM pncp_raw_bids
WHERE orgao_cnpj ~ '^[A-Z0-9]{12}[0-9]{2}$'
  AND data_publicacao > NOW() - INTERVAL '12 months'
GROUP BY orgao_cnpj
HAVING COUNT(*) >= 5;

CREATE UNIQUE INDEX ON mv_sitemap_orgaos(cnpj);

GRANT SELECT ON mv_sitemap_orgaos TO anon, authenticated, service_role;

COMMENT ON MATERIALIZED VIEW mv_sitemap_orgaos IS 'Órgãos compradores indexáveis no sitemap /orgaos/{cnpj} — ≥5 licitações em 12 meses, inclui last_seen para probe de staleness, atualizado 4h BRT via pg_cron';
