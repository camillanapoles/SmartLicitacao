-- COPY-COP-006: Lead captures table for lead magnets, newsletter, exit intent, SEO banners.
--
-- Stores email captures from non-converting visitors. Source identifies the
-- conversion point; origin_url captures the page where the user converted.
-- metadata is a flexible JSONB field for future extension.

BEGIN;

CREATE TABLE IF NOT EXISTS public.lead_captures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    sector TEXT,
    source TEXT NOT NULL,
    origin_url TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE public.lead_captures IS 'Email captures from non-converting visitors (COPY-COP-006)';
COMMENT ON COLUMN public.lead_captures.source IS 'Conversion point identifier: lead_magnet_1, lead_magnet_2, lead_magnet_3, newsletter, exit_intent, seo_banner';
COMMENT ON COLUMN public.lead_captures.origin_url IS 'Page URL where the user converted';

-- RLS: public insert (anon), select admin only
ALTER TABLE public.lead_captures ENABLE ROW LEVEL SECURITY;

CREATE POLICY lead_captures_anon_insert
    ON public.lead_captures
    FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY lead_captures_service_all
    ON public.lead_captures
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY lead_captures_admin_select
    ON public.lead_captures
    FOR SELECT
    TO authenticated
    USING (
        auth.jwt() ->> 'role' IN ('service_role', 'supabase_admin')
        OR EXISTS (
            SELECT 1 FROM public.profiles
            WHERE id = auth.uid()
            AND (is_admin = true OR is_master = true)
        )
    );

-- Index for source + created_at queries (analytics / admin dashboards)
CREATE INDEX IF NOT EXISTS idx_lead_captures_source_created
    ON public.lead_captures (source, created_at DESC);

COMMIT;
