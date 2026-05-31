-- B2GOPS-003 (Wave 0): Schema workspace_timeline + RPCs
--
-- Operational timeline for bids: track events with dates, responsible parties,
-- and status. Complements the pipeline kanban with temporal granularity.
--
-- Events: publicacao, impugnacao, esclarecimento, abertura, habilitacao,
--         recurso, homologacao, adjudicacao, contrato
-- Status: pendente, concluido, atrasado (auto-set by trigger when overdue)

-- ============================================================================
-- Tables
-- ============================================================================

CREATE TABLE public.workspace_timeline (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  licitacao_id TEXT NOT NULL,
  licitacao_fonte TEXT NOT NULL,
  evento TEXT NOT NULL CHECK (evento IN (
    'publicacao', 'impugnacao', 'esclarecimento', 'abertura',
    'habilitacao', 'recurso', 'homologacao', 'adjudicacao', 'contrato'
  )),
  data_evento DATE NOT NULL,
  data_prevista DATE,
  responsavel TEXT,
  notas TEXT,
  status TEXT NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente', 'concluido', 'atrasado')),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================================
-- Indexes
-- ============================================================================

CREATE INDEX idx_timeline_user ON public.workspace_timeline(user_id);
CREATE INDEX idx_timeline_licitacao ON public.workspace_timeline(licitacao_id);
CREATE INDEX idx_timeline_upcoming ON public.workspace_timeline(user_id, data_evento, status);
CREATE INDEX idx_timeline_status_due ON public.workspace_timeline(status, data_evento);

-- ============================================================================
-- RLS
-- ============================================================================

ALTER TABLE public.workspace_timeline ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can CRUD own timeline" ON public.workspace_timeline
  FOR ALL TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Service role full access
GRANT ALL ON public.workspace_timeline TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.workspace_timeline TO authenticated;

-- ============================================================================
-- Trigger: auto-update updated_at on row modification
-- ============================================================================

CREATE OR REPLACE FUNCTION public.set_workspace_timeline_updated_at()
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

CREATE TRIGGER trg_workspace_timeline_updated_at
  BEFORE UPDATE ON public.workspace_timeline
  FOR EACH ROW
  EXECUTE FUNCTION public.set_workspace_timeline_updated_at();

-- ============================================================================
-- Trigger: auto-set status to 'atrasado' when event is overdue
-- ============================================================================

CREATE OR REPLACE FUNCTION public.set_overdue_timeline_status()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  IF NEW.data_evento < CURRENT_DATE AND NEW.status = 'pendente' THEN
    NEW.status := 'atrasado';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_workspace_timeline_overdue
  BEFORE INSERT OR UPDATE ON public.workspace_timeline
  FOR EACH ROW
  EXECUTE FUNCTION public.set_overdue_timeline_status();

-- ============================================================================
-- RPC: ops_add_timeline_event
-- ============================================================================

CREATE OR REPLACE FUNCTION public.ops_add_timeline_event(
    p_licitacao_id TEXT,
    p_licitacao_fonte TEXT,
    p_evento TEXT,
    p_data_evento DATE,
    p_data_prevista DATE DEFAULT NULL,
    p_responsavel TEXT DEFAULT NULL,
    p_notas TEXT DEFAULT NULL,
    p_status TEXT DEFAULT 'pendente'
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
    INSERT INTO public.workspace_timeline (
        user_id, licitacao_id, licitacao_fonte, evento,
        data_evento, data_prevista, responsavel, notas, status
    ) VALUES (
        v_user_id, p_licitacao_id, p_licitacao_fonte, p_evento,
        p_data_evento, p_data_prevista, p_responsavel, p_notas, p_status
    )
    RETURNING row_to_json(public.workspace_timeline.*) INTO v_result;
    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.ops_add_timeline_event(TEXT, TEXT, TEXT, DATE, DATE, TEXT, TEXT, TEXT)
    IS 'B2GOPS-003: Adds a timeline event for the calling user. '
       'Returns the full timeline row as JSON.';

GRANT EXECUTE ON FUNCTION public.ops_add_timeline_event(TEXT, TEXT, TEXT, DATE, DATE, TEXT, TEXT, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.ops_add_timeline_event(TEXT, TEXT, TEXT, DATE, DATE, TEXT, TEXT, TEXT) TO service_role;

-- ============================================================================
-- RPC: ops_get_timeline
-- ============================================================================

CREATE OR REPLACE FUNCTION public.ops_get_timeline(
    p_licitacao_id TEXT
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
    SELECT json_agg(row_to_json(t.*) ORDER BY t.data_evento ASC, t.created_at ASC)
    INTO v_result
    FROM public.workspace_timeline t
    WHERE t.user_id = v_user_id AND t.licitacao_id = p_licitacao_id;
    RETURN COALESCE(v_result, '[]'::json);
END;
$$;

COMMENT ON FUNCTION public.ops_get_timeline(TEXT)
    IS 'B2GOPS-003: Returns the full timeline for a given licitacao_id. '
       'Ordered by data_evento ASC. Returns empty array if no events.';

GRANT EXECUTE ON FUNCTION public.ops_get_timeline(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.ops_get_timeline(TEXT) TO service_role;

-- ============================================================================
-- RPC: ops_upcoming_events
-- ============================================================================

CREATE OR REPLACE FUNCTION public.ops_upcoming_events(
    p_dias INT DEFAULT 7
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
    SELECT json_agg(row_to_json(t.*) ORDER BY t.data_evento ASC, t.data_prevista ASC NULLS LAST)
    INTO v_result
    FROM public.workspace_timeline t
    WHERE t.user_id = v_user_id
      AND t.status != 'concluido'
      AND (
        (t.data_evento >= CURRENT_DATE AND t.data_evento <= CURRENT_DATE + p_dias)
        OR
        (t.data_prevista IS NOT NULL AND t.data_prevista >= CURRENT_DATE AND t.data_prevista <= CURRENT_DATE + p_dias)
      );
    RETURN COALESCE(v_result, '[]'::json);
END;
$$;

COMMENT ON FUNCTION public.ops_upcoming_events(INT)
    IS 'B2GOPS-003: Returns upcoming timeline events for the calling user '
       'within the next p_dias days. Ordered by data_evento ASC. '
       'Returns empty array if none.';

GRANT EXECUTE ON FUNCTION public.ops_upcoming_events(INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.ops_upcoming_events(INT) TO service_role;
