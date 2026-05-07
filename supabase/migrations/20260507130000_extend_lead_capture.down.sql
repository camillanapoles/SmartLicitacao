-- Rollback REPO-004 (#756): Remove added columns from leads table
DROP INDEX IF EXISTS idx_leads_utm_source;

ALTER TABLE public.leads
    DROP COLUMN IF EXISTS nome,
    DROP COLUMN IF EXISTS empresa,
    DROP COLUMN IF EXISTS cnpj,
    DROP COLUMN IF EXISTS telefone,
    DROP COLUMN IF EXISTS modalidade_interesse,
    DROP COLUMN IF EXISTS mensagem,
    DROP COLUMN IF EXISTS utm_source,
    DROP COLUMN IF EXISTS utm_campaign,
    DROP COLUMN IF EXISTS referer_path;
