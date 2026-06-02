-- CONV-011b-1: Schema post_purchase_sequences
--
-- Fundacao para sequencia de pos-compra (0h/48h/7d). Habilita as camadas
-- de email (parte 2) e tracking (parte 3) do CONV-011b.
--
-- Cada purchase gera uma sequence com steps definidos em sequence_steps JSONB,
-- contendo {step, offset_hours, template_id, sent_at, opened_at}.
-- O ARQ job avanca current_step conforme os offsets.

-- ============================================================================
-- Table: post_purchase_sequences
-- ============================================================================

CREATE TABLE public.post_purchase_sequences (
  id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  purchase_id     UUID         NOT NULL REFERENCES intel_report_purchases(id),
  product_sku     TEXT         NOT NULL,
  user_id         UUID         NOT NULL REFERENCES profiles(id),
  status          TEXT         NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'active', 'completed', 'cancelled')),
  sequence_steps  JSONB        NOT NULL DEFAULT '[]',
  current_step    INTEGER      NOT NULL DEFAULT 0,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE  public.post_purchase_sequences IS
    'CONV-011b-1 — Post-purchase email sequence tracking (0h/48h/7d). One row per one-time purchase.';
COMMENT ON COLUMN public.post_purchase_sequences.purchase_id IS
    'FK para intel_report_purchases — purchase que originou a sequencia.';
COMMENT ON COLUMN public.post_purchase_sequences.product_sku IS
    'SKU do produto digital comprado (ex.: fornecedores-vencedores, relatorio-oportunidade).';
COMMENT ON COLUMN public.post_purchase_sequences.sequence_steps IS
    'Array JSONB com steps: [{"step":"delivery","offset_hours":0,"template_id":"...","sent_at":null,"opened_at":null}, ...]';
COMMENT ON COLUMN public.post_purchase_sequences.current_step IS
    'Indice do step atual (0-based). Avancado pelo ARQ job apos envio.';

-- ============================================================================
-- Indexes
-- ============================================================================

CREATE INDEX idx_post_purchase_user_status
    ON public.post_purchase_sequences (user_id, status);

CREATE INDEX idx_post_purchase_purchase
    ON public.post_purchase_sequences (purchase_id);

-- ============================================================================
-- RLS
-- ============================================================================

ALTER TABLE public.post_purchase_sequences ENABLE ROW LEVEL SECURITY;

-- User can see own sequences
CREATE POLICY "pps_owner_select" ON public.post_purchase_sequences
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- service_role full access for webhook + ARQ worker
CREATE POLICY "pps_service_select" ON public.post_purchase_sequences
    FOR SELECT
    TO service_role
    USING (true);

CREATE POLICY "pps_service_insert" ON public.post_purchase_sequences
    FOR INSERT
    TO service_role
    WITH CHECK (true);

CREATE POLICY "pps_service_update" ON public.post_purchase_sequences
    FOR UPDATE
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Grants
GRANT SELECT ON public.post_purchase_sequences TO authenticated;
GRANT ALL ON public.post_purchase_sequences TO service_role;

-- ============================================================================
-- Trigger: auto-update updated_at on row modification
-- ============================================================================

CREATE OR REPLACE FUNCTION public.set_post_purchase_sequences_updated_at()
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

CREATE TRIGGER trg_post_purchase_sequences_updated_at
  BEFORE UPDATE ON public.post_purchase_sequences
  FOR EACH ROW
  EXECUTE FUNCTION public.set_post_purchase_sequences_updated_at();
