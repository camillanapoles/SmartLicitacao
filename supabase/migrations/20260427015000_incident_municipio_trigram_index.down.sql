-- Rollback for 20260427015000_incident_municipio_trigram_index.sql
-- Drops the trigram GIN index added during the 2026-04-27 incident hotfix.
-- Safe in production: pg_indexes lookup before/after will confirm removal.
-- Performance impact: ILIKE queries on pncp_supplier_contracts.municipio
-- (used by /v1/observatorio, /v1/contratos/* programmatic SEO) will fall back
-- to seq scan. Only roll back if the index is causing harm (bloat, write
-- amplification) — otherwise prefer to keep it.

DROP INDEX IF EXISTS public.idx_psc_municipio_trgm;
