-- REPO-004 (#756): Extend leads table with contact, form, and UTM fields
-- All columns are nullable with NULL defaults for backward compatibility.
-- No CHECK constraint on source column (none existed before).

ALTER TABLE public.leads
    ADD COLUMN IF NOT EXISTS nome TEXT,
    ADD COLUMN IF NOT EXISTS empresa TEXT,
    ADD COLUMN IF NOT EXISTS cnpj TEXT,
    ADD COLUMN IF NOT EXISTS telefone TEXT,
    ADD COLUMN IF NOT EXISTS modalidade_interesse TEXT,
    ADD COLUMN IF NOT EXISTS mensagem TEXT,
    ADD COLUMN IF NOT EXISTS utm_source TEXT,
    ADD COLUMN IF NOT EXISTS utm_campaign TEXT,
    ADD COLUMN IF NOT EXISTS referer_path TEXT;

-- Index to speed up UTM attribution queries
CREATE INDEX IF NOT EXISTS idx_leads_utm_source ON public.leads (utm_source)
    WHERE utm_source IS NOT NULL;
