-- PREDINT-002: Rollback RPC + index + columns
-- Issue: #1265

DROP FUNCTION IF EXISTS public.predict_recurrence_index(VARCHAR(2), TEXT, TEXT);

DROP INDEX IF EXISTS idx_psc_orgao_setor_data;

ALTER TABLE pncp_supplier_contracts DROP COLUMN IF EXISTS setor_classificado;
ALTER TABLE pncp_supplier_contracts DROP COLUMN IF EXISTS data_fim_vigencia;
