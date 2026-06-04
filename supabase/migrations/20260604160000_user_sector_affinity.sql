-- ============================================================================
-- UP: user_sector_affinity — stores per-user sector affinity scores (FEEDBACK-001)
-- Date: 2026-06-04
-- Author: @dev
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.user_sector_affinity (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    sector_id   TEXT NOT NULL,
    affinity_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    feedback_count INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_sector UNIQUE (user_id, sector_id)
);

CREATE INDEX IF NOT EXISTS idx_user_sector_affinity_user ON public.user_sector_affinity (user_id);
CREATE INDEX IF NOT EXISTS idx_user_sector_affinity_score ON public.user_sector_affinity (user_id, affinity_score DESC);

ALTER TABLE public.user_sector_affinity ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "user_select_own" ON public.user_sector_affinity;
CREATE POLICY "user_select_own" ON public.user_sector_affinity
    FOR SELECT
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS "service_role_all" ON public.user_sector_affinity;
CREATE POLICY "service_role_all" ON public.user_sector_affinity
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE OR REPLACE FUNCTION public.update_user_sector_affinity_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_sector_affinity_updated_at ON public.user_sector_affinity;
CREATE TRIGGER trg_user_sector_affinity_updated_at
    BEFORE UPDATE ON public.user_sector_affinity
    FOR EACH ROW
    EXECUTE FUNCTION public.update_user_sector_affinity_updated_at();

NOTIFY pgrst, 'reload schema';
