-- ENTITY-001: Add tracked_orgaos and tracked_fornecedores columns to alerts table
-- These columns store CNPJ lists for entity-level tracking within an alert.
-- Tracked orgaos: public agencies the user wants to follow
-- Tracked fornecedores: suppliers the user wants to follow
--
-- Both are TEXT[] with DEFAULT '{}' to ensure retrocompatibility:
-- existing alerts without any tracked entities continue to function normally.

-- ============================================================================
-- 1. Add columns
-- ============================================================================

ALTER TABLE alerts
  ADD COLUMN IF NOT EXISTS tracked_orgaos TEXT[] NOT NULL DEFAULT '{}'::text[];

ALTER TABLE alerts
  ADD COLUMN IF NOT EXISTS tracked_fornecedores TEXT[] NOT NULL DEFAULT '{}'::text[];

-- ============================================================================
-- 2. CHECK constraints for CNPJ format (14 digits)
-- ============================================================================

-- Each element in tracked_orgaos must be a 14-digit string or the array must be empty
ALTER TABLE alerts
  ADD CONSTRAINT alerts_tracked_orgaos_cnpj_check
  CHECK (
    tracked_orgaos IS NULL
    OR array_length(tracked_orgaos, 1) IS NULL
    OR (SELECT bool_and(elem ~ '^\d{14}$'::text) FROM unnest(tracked_orgaos) AS elem)
  );

ALTER TABLE alerts
  ADD CONSTRAINT alerts_tracked_fornecedores_cnpj_check
  CHECK (
    tracked_fornecedores IS NULL
    OR array_length(tracked_fornecedores, 1) IS NULL
    OR (SELECT bool_and(elem ~ '^\d{14}$'::text) FROM unnest(tracked_fornecedores) AS elem)
  );

-- ============================================================================
-- 3. Update column comments
-- ============================================================================

COMMENT ON COLUMN alerts.tracked_orgaos
  IS 'ENTITY-001: CNPJ list of public agencies (orgaos) to track within this alert. Each entry must be 14 digits.';

COMMENT ON COLUMN alerts.tracked_fornecedores
  IS 'ENTITY-001: CNPJ list of suppliers (fornecedores) to track within this alert. Each entry must be 14 digits.';
