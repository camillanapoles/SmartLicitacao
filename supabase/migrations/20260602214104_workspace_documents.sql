-- B2GOPS-002: Workspace documents table + RPCs for document management
-- Issue: #1278
--
-- Manages documents linked to licitacoes: editais, propostas, certidoes,
-- contratos, and outros. Each document belongs to a user and optionally
-- links to a licitacao (by id + fonte).
--
-- Key features:
--   - ops_insert_document: insert document metadata after Storage upload
--   - ops_list_documents: list documents linked to a licitacao
--   - ops_check_expiring_certidoes: find certidoes expiring within N days
--   - Certidao validity tracking with expiration alerts

-- ============================================================================
-- Tables
-- ============================================================================

CREATE TABLE public.workspace_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  licitacao_id TEXT,
  licitacao_fonte TEXT,
  nome TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('edital', 'proposta', 'certidao', 'contrato', 'outro')),
  tamanho_bytes BIGINT,
  mime_type TEXT,
  storage_path TEXT,
  status TEXT DEFAULT 'ativo' CHECK (status IN ('ativo', 'vencido', 'arquivado')),
  data_validade DATE,
  tags TEXT[],
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- List documents by licitacao
CREATE INDEX idx_workspace_documents_licitacao ON public.workspace_documents(licitacao_id, licitacao_fonte);
-- User documents lookup
CREATE INDEX idx_workspace_documents_user ON public.workspace_documents(user_id);
-- Expiring certidoes (partial index for common query)
CREATE INDEX idx_workspace_documents_validade ON public.workspace_documents(data_validade)
  WHERE tipo = 'certidao' AND status = 'ativo';

-- ============================================================================
-- RLS
-- ============================================================================

ALTER TABLE public.workspace_documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can CRUD own documents" ON public.workspace_documents
  FOR ALL TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Service role full access (bypasses RLS for backend operations)
GRANT ALL ON public.workspace_documents TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.workspace_documents TO authenticated;

-- ============================================================================
-- RPC: ops_list_documents
-- ============================================================================

CREATE OR REPLACE FUNCTION public.ops_list_documents(
    p_licitacao_id TEXT,
    p_licitacao_fonte TEXT DEFAULT NULL
)
RETURNS SETOF public.workspace_documents
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  SELECT * FROM public.workspace_documents
  WHERE user_id = auth.uid()
    AND licitacao_id = p_licitacao_id
    AND (p_licitacao_fonte IS NULL OR licitacao_fonte = p_licitacao_fonte)
  ORDER BY created_at DESC;
$$;

COMMENT ON FUNCTION public.ops_list_documents(TEXT, TEXT)
    IS 'B2GOPS-002: Lists documents linked to a licitacao for the calling user. '
       'Filters by licitacao_fonte when provided. Ordered by created_at DESC.';

GRANT EXECUTE ON FUNCTION public.ops_list_documents(TEXT, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.ops_list_documents(TEXT, TEXT) TO service_role;

-- ============================================================================
-- RPC: ops_check_expiring_certidoes
-- ============================================================================

CREATE OR REPLACE FUNCTION public.ops_check_expiring_certidoes(
    p_dias INTEGER DEFAULT 30
)
RETURNS SETOF public.workspace_documents
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  SELECT * FROM public.workspace_documents
  WHERE user_id = auth.uid()
    AND tipo = 'certidao'
    AND status = 'ativo'
    AND data_validade IS NOT NULL
    AND data_validade <= (CURRENT_DATE + p_dias)
    AND data_validade >= CURRENT_DATE
  ORDER BY data_validade ASC;
$$;

COMMENT ON FUNCTION public.ops_check_expiring_certidoes(INTEGER)
    IS 'B2GOPS-002: Returns active certidoes expiring within p_dias days '
       'for the calling user. Ordered by data_validade ASC.';

GRANT EXECUTE ON FUNCTION public.ops_check_expiring_certidoes(INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION public.ops_check_expiring_certidoes(INTEGER) TO service_role;

-- ============================================================================
-- RPC: ops_insert_document
-- ============================================================================

CREATE OR REPLACE FUNCTION public.ops_insert_document(
    p_licitacao_id TEXT,
    p_licitacao_fonte TEXT,
    p_nome TEXT,
    p_tipo TEXT,
    p_tamanho_bytes BIGINT,
    p_mime_type TEXT,
    p_storage_path TEXT,
    p_data_validade DATE DEFAULT NULL,
    p_tags TEXT[] DEFAULT NULL
)
RETURNS public.workspace_documents
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_doc public.workspace_documents;
BEGIN
    INSERT INTO public.workspace_documents (
        user_id, licitacao_id, licitacao_fonte, nome, tipo,
        tamanho_bytes, mime_type, storage_path, data_validade, tags
    ) VALUES (
        auth.uid(), p_licitacao_id, p_licitacao_fonte, p_nome, p_tipo,
        p_tamanho_bytes, p_mime_type, p_storage_path, p_data_validade, p_tags
    )
    RETURNING * INTO v_doc;

    RETURN v_doc;
END;
$$;

COMMENT ON FUNCTION public.ops_insert_document(TEXT, TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, DATE, TEXT[])
    IS 'B2GOPS-002: Inserts a workspace document for the calling user. '
       'Returns the full document row. Designed to be called after Storage upload.';

GRANT EXECUTE ON FUNCTION public.ops_insert_document(TEXT, TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, DATE, TEXT[]) TO authenticated;
GRANT EXECUTE ON FUNCTION public.ops_insert_document(TEXT, TEXT, TEXT, TEXT, BIGINT, TEXT, TEXT, DATE, TEXT[]) TO service_role;
