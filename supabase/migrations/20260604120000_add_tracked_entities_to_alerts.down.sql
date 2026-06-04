-- ============================================================================
-- DOWN: ENTITY-001 -- Remove tracked_orgaos and tracked_fornecedores columns
-- Reverses: 20260604120000_add_tracked_entities_to_alerts.sql
-- Date: 2026-06-04
-- ============================================================================
-- Context:
--   The up migration added tracked_orgaos TEXT[] and tracked_fornecedores TEXT[]
--   columns to the alerts table, along with CHECK constraints enforcing CNPJ
--   format (14 digits) for each array element.
--
--   This down migration reverses the operation: drops CHECK constraints first,
--   then drops the columns. All operations are idempotent (IF EXISTS guards).
-- ============================================================================

-- Reverse operations in the OPPOSITE ORDER of the up migration.

-- 1. Drop CHECK constraints
ALTER TABLE alerts DROP CONSTRAINT IF EXISTS alerts_tracked_orgaos_cnpj_check;
ALTER TABLE alerts DROP CONSTRAINT IF EXISTS alerts_tracked_fornecedores_cnpj_check;

-- 2. Drop columns
ALTER TABLE alerts DROP COLUMN IF EXISTS tracked_orgaos;
ALTER TABLE alerts DROP COLUMN IF EXISTS tracked_fornecedores;
