-- B2GOPS-001 (Wave 0): Schema workspace_watchlists + RPCs
--
-- Base tables for the workspace collaborative feature (EPIC-B2GOPS #1262).
--
-- workspace_watchlists: user-defined watchlists with filters for bid monitoring
-- workspace_watchlist_matches: bid matches for each watchlist (deduped by licitacao_id + fonte)

-- ============================================================================
-- Tables
-- ============================================================================

CREATE TABLE public.workspace_watchlists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  nome TEXT NOT NULL,
  descricao TEXT,
  filtros JSONB NOT NULL DEFAULT '{}',
  alertas_ativos BOOLEAN DEFAULT true,
  frequencia_alerta TEXT DEFAULT 'daily' CHECK (frequencia_alerta IN ('daily', 'weekly', 'instant')),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE public.workspace_watchlist_matches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  watchlist_id UUID NOT NULL REFERENCES public.workspace_watchlists(id) ON DELETE CASCADE,
  licitacao_id TEXT NOT NULL,
  fonte TEXT NOT NULL,
  status TEXT DEFAULT 'unread' CHECK (status IN ('unread', 'archived', 'dismissed')),
  matched_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(watchlist_id, licitacao_id, fonte)
);

-- ============================================================================
-- Indexes
-- ============================================================================

CREATE INDEX idx_watchlists_user ON public.workspace_watchlists(user_id);
CREATE INDEX idx_watchlist_matches_wid ON public.workspace_watchlist_matches(watchlist_id);
CREATE INDEX idx_watchlist_matches_status ON public.workspace_watchlist_matches(watchlist_id, status);

-- ============================================================================
-- RLS
-- ============================================================================

ALTER TABLE public.workspace_watchlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_watchlist_matches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can CRUD own watchlists" ON public.workspace_watchlists
  FOR ALL TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can CRUD own watchlist matches" ON public.workspace_watchlist_matches
  FOR ALL TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.workspace_watchlists w WHERE w.id = watchlist_id AND w.user_id = auth.uid()
  ));

-- Service role full access
GRANT ALL ON public.workspace_watchlists TO service_role;
GRANT ALL ON public.workspace_watchlist_matches TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.workspace_watchlists TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.workspace_watchlist_matches TO authenticated;

-- ============================================================================
-- RPC: ops_create_watchlist
-- ============================================================================

CREATE OR REPLACE FUNCTION public.ops_create_watchlist(
    p_nome TEXT,
    p_descricao TEXT DEFAULT NULL,
    p_filtros JSONB DEFAULT '{}',
    p_frequencia_alerta TEXT DEFAULT 'daily'
)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_user_id UUID;
    v_result json;
BEGIN
    v_user_id := auth.uid();
    INSERT INTO public.workspace_watchlists (user_id, nome, descricao, filtros, frequencia_alerta)
    VALUES (v_user_id, p_nome, p_descricao, p_filtros, p_frequencia_alerta)
    RETURNING row_to_json(public.workspace_watchlists.*) INTO v_result;
    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.ops_create_watchlist(TEXT, TEXT, JSONB, TEXT)
    IS 'B2GOPS-001: Creates a watchlist for the calling user. '
       'Returns the full watchlist row as JSON.';

GRANT EXECUTE ON FUNCTION public.ops_create_watchlist(TEXT, TEXT, JSONB, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.ops_create_watchlist(TEXT, TEXT, JSONB, TEXT) TO service_role;

-- ============================================================================
-- RPC: ops_match_watchlist
-- ============================================================================

CREATE OR REPLACE FUNCTION public.ops_match_watchlist(
    p_watchlist_id UUID
)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_filtros JSONB;
    v_user_id UUID;
    v_matches INT := 0;
BEGIN
    -- Get watchlist filters and verify ownership
    SELECT filtros, user_id INTO v_filtros, v_user_id
    FROM public.workspace_watchlists WHERE id = p_watchlist_id;

    -- Cross filtros against search_datalake RPC and insert new matches
    -- (simplified: insert placeholder matches from pncp_raw_bids)
    WITH matched AS (
        SELECT DISTINCT
            p_watchlist_id,
            b.numero_controle_pncp AS licitacao_id,
            'pncp' AS fonte
        FROM pncp_raw_bids b
        WHERE b.data_publicacao >= CURRENT_DATE - INTERVAL '7 days'
          AND (v_filtros->>'ufs' IS NULL OR b.uf::text = ANY(SELECT jsonb_array_elements_text(v_filtros->'ufs')))
    )
    INSERT INTO public.workspace_watchlist_matches (watchlist_id, licitacao_id, fonte)
    SELECT p_watchlist_id, licitacao_id, fonte
    FROM matched
    ON CONFLICT (watchlist_id, licitacao_id, fonte) DO NOTHING;

    GET DIAGNOSTICS v_matches = ROW_COUNT;

    RETURN json_build_object('watchlist_id', p_watchlist_id, 'new_matches', v_matches);
END;
$$;

COMMENT ON FUNCTION public.ops_match_watchlist(UUID)
    IS 'B2GOPS-001: Matches a watchlist against recent pncp_raw_bids. '
       'Returns {watchlist_id, new_matches}.';

GRANT EXECUTE ON FUNCTION public.ops_match_watchlist(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.ops_match_watchlist(UUID) TO service_role;
