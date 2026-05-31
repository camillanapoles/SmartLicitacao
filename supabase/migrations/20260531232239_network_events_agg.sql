-- ============================================================================
-- NETINT-001: Schema network_events_agg + Mecanismo de coleta anonimizada
-- Issue: #1283
-- Wave: NETINT Wave 0 — Fundacao de privacidade e coleta anonimizada
-- ============================================================================
-- Context:
--   Network Intelligence EPIC (#1263). Camada de coleta de eventos agregados
--   e anonimizados para inteligencia coletiva. LGPD-first: nunca armazena PII
--   ou dado individual.
--
--   Tabela network_events_agg:
--     - Agregados diarios por (evento_tipo, dimensao_tipo, dimensao_valor)
--     - UPSERT via network_record_event: se registro do dia ja existe,
--       incrementa contagem em vez de duplicar
--     - Sem RLS restritivo — SELECT publico (apenas agregados anonimos)
--     - Metadados JSONB sanitizados: NUNCA user_id, cnpj, email, ip
--
--   Coluna profiles.allow_network_analytics:
--     - NULL = nao decidiu (tratado como false — opt-out ate consentimento)
--     - true = contribui com dados anonimos agregados
--     - false = nunca coleta
--
--   SECURITY DEFINER + SET search_path = public (SEC-SECDEF-001/002).
--   GRANT para authenticated, service_role — INSERT via RPC com sanitizacao.
--   GRANT SELECT para anon, authenticated, service_role (dados agregados).
-- ============================================================================

BEGIN;

-- ────────────────────────────────────────────────────────────────────────────
-- 1. Create network_events_agg table
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.network_events_agg (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evento_tipo TEXT NOT NULL,
    dimensao_tipo TEXT NOT NULL,
    dimensao_valor TEXT NOT NULL,
    periodo DATE NOT NULL,
    contagem INTEGER DEFAULT 1,
    metadados JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE public.network_events_agg IS
    'NETINT-001: Eventos agregados anonimos de inteligencia coletiva. NUNCA contem PII.';

COMMENT ON COLUMN public.network_events_agg.evento_tipo IS
    'Tipo do evento: search_query, sector_view, org_view, cnpj_lookup, discount_view, migration_view, competitor_view';

COMMENT ON COLUMN public.network_events_agg.dimensao_tipo IS
    'Tipo da dimensao: setor, uf, modalidade, orgao, municipio';

COMMENT ON COLUMN public.network_events_agg.dimensao_valor IS
    'Valor da dimensao (ex: "saude", "SP", "pregao") — nunca PII';

COMMENT ON COLUMN public.network_events_agg.periodo IS
    'Data do evento (agregacao diaria)';

COMMENT ON COLUMN public.network_events_agg.contagem IS
    'Contagem de eventos neste periodo — incremental via UPSERT';

COMMENT ON COLUMN public.network_events_agg.metadados IS
    'Metadados adicionais: {"setores": [], "ufs": [], "modalidades": []}. NUNCA user_id, cnpj, email, ip.';

-- ────────────────────────────────────────────────────────────────────────────
-- 2. Indexes
-- ────────────────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_network_events_periodo
    ON public.network_events_agg (periodo, evento_tipo, dimensao_tipo);

CREATE INDEX IF NOT EXISTS idx_network_events_tipo_valor
    ON public.network_events_agg (evento_tipo, dimensao_valor);

-- ────────────────────────────────────────────────────────────────────────────
-- 3. Unique constraint for daily aggregation (antes do RPC que o referencia)
-- ────────────────────────────────────────────────────────────────────────────

CREATE UNIQUE INDEX IF NOT EXISTS idx_network_events_unique_daily
    ON public.network_events_agg (evento_tipo, dimensao_tipo, dimensao_valor, periodo);

ALTER TABLE public.network_events_agg
    ADD CONSTRAINT network_events_agg_unique_daily
    UNIQUE USING INDEX idx_network_events_unique_daily;

-- ────────────────────────────────────────────────────────────────────────────
-- 4. RLS — SELECT-only policies (INSERT via SECURITY DEFINER RPC)
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.network_events_agg ENABLE ROW LEVEL SECURITY;

CREATE POLICY "network_events_agg_select_anon"
    ON public.network_events_agg
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "network_events_agg_select_authenticated"
    ON public.network_events_agg
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "network_events_agg_select_service_role"
    ON public.network_events_agg
    FOR SELECT
    TO service_role
    USING (true);

-- ────────────────────────────────────────────────────────────────────────────
-- 5. RPC: network_record_event — sanitized UPSERT
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.network_record_event(
    p_evento_tipo TEXT,
    p_dimensao_tipo TEXT,
    p_dimensao_valor TEXT,
    p_metadados JSONB DEFAULT '{}'::jsonb
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_sanitized JSONB;
    v_proibido TEXT[];
    v_key TEXT;
BEGIN
    -- ── Input validation ──────────────────────────────────────────────────
    IF p_evento_tipo IS NULL OR trim(p_evento_tipo) = '' THEN
        RAISE EXCEPTION 'p_evento_tipo is required';
    END IF;

    IF p_dimensao_tipo IS NULL OR trim(p_dimensao_tipo) = '' THEN
        RAISE EXCEPTION 'p_dimensao_tipo is required';
    END IF;

    IF p_dimensao_valor IS NULL OR trim(p_dimensao_valor) = '' THEN
        RAISE EXCEPTION 'p_dimensao_valor is required';
    END IF;

    -- ── Sanitizacao obrigatoria: remove quaisquer chaves proibidas ─────────
    -- (LGPD: garantir que nenhum PII seja armazenado mesmo que enviado)
    v_proibido := ARRAY[
        'user_id', 'profile_id', 'email', 'cnpj', 'cpf',
        'ip', 'user_agent', 'fingerprint', 'telefone',
        'endereco', 'nome', 'token', 'session_id'
    ];

    IF p_metadados IS NULL THEN
        v_sanitized := '{}'::jsonb;
    ELSE
        v_sanitized := p_metadados;

        -- Remove todas as chaves proibidas (case-insensitive)
        FOREACH v_key IN ARRAY v_proibido
        LOOP
            v_sanitized := v_sanitized - v_key;
            -- Tambem remove variacoes camelCase/snake_case
            v_sanitized := v_sanitized - replace(v_key, '_', '');
            v_sanitized := v_sanitized - upper(v_key);
            v_sanitized := v_sanitized - initcap(v_key);
        END LOOP;

        -- Remove qualquer chave que termine com "id" (userId, customerId, ...)
        SELECT v_sanitized - key
        INTO v_sanitized
        FROM jsonb_object_keys(v_sanitized) AS key
        WHERE key ~* '.*(id|Id|ID)$';
    END IF;

    -- ── Rejeitar se patterns de PII persistirem no JSON serializado ────────
    -- CNPJ: 14 digitos consecutivos
    IF v_sanitized::text ~ '"[0-9]{14}"' THEN
        RAISE EXCEPTION 'metadados contem CNPJ — rejeitado por seguranca LGPD';
    END IF;

    -- CNPJ formatado: XX.XXX.XXX/XXXX-XX
    IF v_sanitized::text ~ '[0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2}' THEN
        RAISE EXCEPTION 'metadados contem CNPJ — rejeitado por seguranca LGPD';
    END IF;

    -- Email pattern
    IF v_sanitized::text ~ '[A-Za-z0-9._%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' THEN
        RAISE EXCEPTION 'metadados contem email — rejeitado por seguranca LGPD';
    END IF;

    -- UUID pattern (user_id, profile_id)
    IF v_sanitized::text ~ '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' THEN
        RAISE EXCEPTION 'metadados contem UUID — rejeitado por seguranca LGPD';
    END IF;

    -- IPv4 pattern
    IF v_sanitized::text ~ '\m[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\M' THEN
        RAISE EXCEPTION 'metadados contem IP — rejeitado por seguranca LGPD';
    END IF;

    -- ── SET LOCAL statement_timeout para defesa contra runaway ─────────────
    SET LOCAL statement_timeout = '5s';

    -- ── UPSERT: incrementa contagem se registro do dia ja existe ──────────
    INSERT INTO public.network_events_agg (
        evento_tipo,
        dimensao_tipo,
        dimensao_valor,
        periodo,
        contagem,
        metadados
    ) VALUES (
        trim(p_evento_tipo),
        trim(p_dimensao_tipo),
        trim(p_dimensao_valor),
        CURRENT_DATE,
        1,
        v_sanitized
    )
    ON CONFLICT ON CONSTRAINT network_events_agg_unique_daily
    DO UPDATE SET
        contagem = public.network_events_agg.contagem + 1,
        metadados = (
            SELECT jsonb_object_agg(
                COALESCE(n.key, o.key),
                CASE
                    WHEN jsonb_typeof(n.value) = 'array' AND jsonb_typeof(o.value) = 'array'
                    THEN (
                        SELECT jsonb_agg(DISTINCT elem)
                        FROM (
                            SELECT jsonb_array_elements_text(n.value) AS elem
                            UNION
                            SELECT jsonb_array_elements_text(o.value) AS elem
                        ) sub
                    )
                    ELSE COALESCE(n.value, o.value)
                END
            )
            FROM jsonb_each(public.network_events_agg.metadados) o
            FULL OUTER JOIN jsonb_each(v_sanitized) n ON n.key = o.key
        ),
        created_at = now();
END;
$$;

COMMENT ON FUNCTION public.network_record_event(TEXT, TEXT, TEXT, JSONB) IS
    'NETINT-001 — Registra evento anonimo agregado com sanitizacao LGPD. '
    'UPSERT: incrementa contagem se mesma combinacao ja existe no dia. '
    'Rejeita metadados contendo PII (CNPJ, email, UUID, IP).';

-- ────────────────────────────────────────────────────────────────────────────
-- 6. Add profiles.allow_network_analytics column (aditiva, DEFAULT NULL)
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS allow_network_analytics BOOLEAN DEFAULT NULL;

COMMENT ON COLUMN public.profiles.allow_network_analytics IS
    'NETINT-001: Consentimento LGPD para coleta anonima. '
    'NULL = nao decidiu (tratado como false — opt-out ate consentimento explicito). '
    'true = contribui com dados agregados anonimos. false = nunca coleta.';

-- ────────────────────────────────────────────────────────────────────────────
-- 7. Grants
-- ────────────────────────────────────────────────────────────────────────────

-- SELECT: publico (dados agregados anonimos — sem PII)
GRANT SELECT ON public.network_events_agg TO anon;
GRANT SELECT ON public.network_events_agg TO authenticated;
GRANT SELECT ON public.network_events_agg TO service_role;

-- INSERT/UPDATE/DELETE: apenas via RPC (SECURITY DEFINER)
-- Nenhuma permissao direta de DML para anon ou authenticated.

-- RPC: authenticated + service_role
GRANT EXECUTE ON FUNCTION public.network_record_event(TEXT, TEXT, TEXT, JSONB) TO authenticated;
GRANT EXECUTE ON FUNCTION public.network_record_event(TEXT, TEXT, TEXT, JSONB) TO service_role;

COMMIT;
