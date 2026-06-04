-- FEEDBACK-001: user_sector_affinity table — user affinity scores per sector
-- Issue: #1435
--
-- Stores the user's affinity score (0.0–1.0) for each sector. Used by
-- the feedback/ML pipeline to personalize opportunity relevance ranking.
-- Each user gets a neutral score of 0.5 by default for every sector they
-- interact with.

-- ============================================================================
-- Table: user_sector_affinity
-- ============================================================================

CREATE TABLE public.user_sector_affinity (
  user_id        UUID         NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  sector_id      VARCHAR      NOT NULL,
  affinity_score NUMERIC(3,2) NOT NULL DEFAULT 0.5,
  updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, sector_id),
  CONSTRAINT chk_affinity_score_range CHECK (affinity_score >= 0.0 AND affinity_score <= 1.0)
);

COMMENT ON TABLE  public.user_sector_affinity IS
    'FEEDBACK-001 — User affinity score per sector (0.0–1.0). Used for personalized opportunity ranking.';
COMMENT ON COLUMN public.user_sector_affinity.user_id IS
    'FK para profiles — user that owns this affinity score.';
COMMENT ON COLUMN public.user_sector_affinity.sector_id IS
    'Identificador do setor (ex.: tecnologia, saude, educacao).';
COMMENT ON COLUMN public.user_sector_affinity.affinity_score IS
    'Pontuacao de afinidade entre 0.0 (nenhuma) e 1.0 (maxima). Default 0.5 (neutro).';

-- ============================================================================
-- RLS
-- ============================================================================

ALTER TABLE public.user_sector_affinity ENABLE ROW LEVEL SECURITY;

-- User can CRUD own affinity rows
CREATE POLICY "usa_owner_all" ON public.user_sector_affinity
    FOR ALL
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Grants
GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_sector_affinity TO authenticated;
GRANT ALL ON public.user_sector_affinity TO service_role;

-- ============================================================================
-- Trigger: auto-update updated_at on row modification
-- ============================================================================

CREATE OR REPLACE FUNCTION public.set_user_sector_affinity_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_user_sector_affinity_updated_at
  BEFORE UPDATE ON public.user_sector_affinity
  FOR EACH ROW
  EXECUTE FUNCTION public.set_user_sector_affinity_updated_at();
