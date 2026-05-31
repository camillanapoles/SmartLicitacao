-- ============================================================================
-- COMPINT-002: RPC competitor_win_metrics
-- Purpose:   Competitive performance metrics for a supplier CNPJ
--            Estimated win rate, growth/retraction trend, growth speed,
--            expanding segments, market concentration, ticket percentiles.
--
-- Data sources: pncp_supplier_contracts (wins) only.
--   pncp_raw_bids does not store supplier participant CNPJ, so loss
--   inference from raw participations is not possible with current schema.
--   Instead, taxa_vitoria_estimada is computed as the supplier's share of
--   total contract awards in their operating UFs (proxy for win rate).
--
-- Output: scalar JSON (bypasses PostgREST max-rows=1000)
--   {
--     "cnpj": "...",
--     "nome": "...",
--     "win_metrics": { ... },
--     "serie_temporal": [ ... ],
--     "percentis": { ... }
--   }
--
-- Expected: < 500ms p95 (join between supplier_contracts + contracts in
--   same UFs via idx_psc_ni_fornecedor + idx_psc_uf_date).
-- ============================================================================

CREATE OR REPLACE FUNCTION public.competitor_win_metrics(
    p_cnpj TEXT,
    p_anos INT DEFAULT 5
)
RETURNS JSON
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_clean                TEXT;
    v_start_date           DATE;
    v_nome                 TEXT;

    -- Headline
    v_vitorias             BIGINT;
    v_total_vitorias_all   BIGINT;

    -- Market context in same UFs
    v_total_contratos_uf   BIGINT;

    -- Derived metrics
    v_taxa_vitoria         NUMERIC(6,4);
    v_participacoes        BIGINT;
    v_velocidade           NUMERIC(10,4);
    v_tendencia            TEXT;

    -- Concentration / diversification
    v_concentracao_uf      NUMERIC(10,4);
    v_indice_div            NUMERIC(10,4);
    v_dependencia_publica  NUMERIC(6,4);

    -- Percentiles
    v_p25                  NUMERIC(18,2);
    v_p50                  NUMERIC(18,2);
    v_p75                  NUMERIC(18,2);
    v_p90                  NUMERIC(18,2);

    -- Time series
    v_serie_temporal       JSON;

    -- Segments (reserved for future setor_classificado integration)
    v_segmentos_atuais     JSON;
    v_segmentos_emergentes JSON;
    v_segmentos_abandonados JSON;

    -- Supplier active UFs
    v_ufs                  TEXT[];
BEGIN
    -- ------------------------------------------------------------------
    -- 1. Input validation & normalization
    -- ------------------------------------------------------------------
    v_clean := regexp_replace(COALESCE(p_cnpj, ''), '[^0-9]', '', 'g');
    IF length(v_clean) <> 14 THEN
        RETURN json_build_object(
            'cnpj',          COALESCE(p_cnpj, ''),
            'erro',          'CNPJ invalido: deve ter 14 digitos apos normalizacao'
        );
    END IF;

    IF p_anos IS NULL OR p_anos < 1 OR p_anos > 20 THEN
        p_anos := 5;
    END IF;

    v_start_date := (CURRENT_DATE - (p_anos || ' years')::INTERVAL)::DATE;

    SET LOCAL statement_timeout = '15s';

    -- ------------------------------------------------------------------
    -- 2. Get supplier name (from most recent contract)
    -- ------------------------------------------------------------------
    SELECT nome_fornecedor
      INTO v_nome
      FROM public.pncp_supplier_contracts
     WHERE ni_fornecedor = v_clean
       AND is_active = TRUE
       AND nome_fornecedor IS NOT NULL
     ORDER BY data_assinatura DESC NULLS LAST
     LIMIT 1;

    -- ------------------------------------------------------------------
    -- 3. Count total wins in window
    -- ------------------------------------------------------------------
    SELECT COUNT(*)::BIGINT
      INTO v_vitorias
      FROM public.pncp_supplier_contracts
     WHERE ni_fornecedor = v_clean
       AND is_active = TRUE
       AND data_assinatura >= v_start_date;

    -- ------------------------------------------------------------------
    -- 4. Get supplier's UFs (where they have active contracts)
    -- ------------------------------------------------------------------
    SELECT ARRAY_AGG(DISTINCT uf)
      INTO v_ufs
      FROM public.pncp_supplier_contracts
     WHERE ni_fornecedor = v_clean
       AND is_active = TRUE
       AND data_assinatura >= v_start_date
       AND uf IS NOT NULL
       AND uf <> '';

    -- ------------------------------------------------------------------
    -- 5. Count total contract awards in same UFs (market size proxy)
    -- ------------------------------------------------------------------
    -- If supplier has no contracts yet (v_ufs IS NULL), fall back to
    -- v_vitorias only (single row counts).
    IF v_ufs IS NOT NULL AND cardinality(v_ufs) > 0 THEN
        SELECT COUNT(*)::BIGINT
          INTO v_total_contratos_uf
          FROM public.pncp_supplier_contracts
         WHERE uf = ANY(v_ufs)
           AND is_active = TRUE
           AND data_assinatura >= v_start_date
           AND ni_fornecedor <> v_clean;  -- exclude self to avoid double-count
    ELSE
        v_total_contratos_uf := 0;
    END IF;

    -- Total all-time wins (for full-period metrics)
    SELECT COUNT(*)::BIGINT
      INTO v_total_vitorias_all
      FROM public.pncp_supplier_contracts
     WHERE ni_fornecedor = v_clean
       AND is_active = TRUE;

    -- ------------------------------------------------------------------
    -- 6. Derived win metrics
    -- ------------------------------------------------------------------
    IF v_vitorias = 0 OR (v_total_contratos_uf + v_vitorias) = 0 THEN
        v_taxa_vitoria   := 0.0;
        v_participacoes  := 0;
    ELSE
        -- taxa_vitoria = vitorias / (vitorias + derrotas_estimadas)
        -- derrotas_estimadas = total_contracts_awarded_in_same_UFs
        -- This represents the supplier's share of total awards in their
        -- operating area, a proxy for win rate against market competition.
        v_taxa_vitoria   := LEAST(
                                ROUND(
                                    v_vitorias::NUMERIC
                                    / GREATEST(v_vitorias + v_total_contratos_uf, 1)::NUMERIC,
                                    4
                                ),
                                1.0
                            );
        v_participacoes  := v_vitorias + v_total_contratos_uf;
    END IF;

    -- ------------------------------------------------------------------
    -- 7. Velocidade de crescimento (year-over-year CAGR approximation)
    -- ------------------------------------------------------------------
    WITH yearly AS (
        SELECT
            EXTRACT(YEAR FROM data_assinatura)::INT AS ano,
            COUNT(*)::BIGINT                         AS contratos,
            COALESCE(SUM(valor_global), 0)::NUMERIC  AS valor
        FROM public.pncp_supplier_contracts
        WHERE ni_fornecedor = v_clean
          AND is_active = TRUE
          AND data_assinatura >= v_start_date
          AND data_assinatura IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM data_assinatura)
    ),
    first_last AS (
        SELECT
            MIN(ano) AS primeiro_ano,
            MAX(ano) AS ultimo_ano,
            MAX(valor) FILTER (WHERE ano = (SELECT MIN(ano) FROM yearly)) AS valor_inicial,
            MAX(valor) FILTER (WHERE ano = (SELECT MAX(ano) FROM yearly)) AS valor_final,
            COUNT(*) AS anos_com_dados
        FROM yearly
    )
    SELECT
        CASE
            WHEN fl.valor_inicial IS NOT NULL
             AND fl.valor_inicial > 0
             AND fl.ultimo_ano > fl.primeiro_ano
            THEN ROUND(
                    (POWER(
                        fl.valor_final::NUMERIC / fl.valor_inicial::NUMERIC,
                        1.0 / GREATEST(fl.ultimo_ano - fl.primeiro_ano, 1)::NUMERIC
                    ) - 1)::NUMERIC,
                    4
                 )
            ELSE 0.0
        END
    INTO v_velocidade
    FROM first_last fl;

    -- ------------------------------------------------------------------
    -- 8. Trend classification
    -- ------------------------------------------------------------------
    v_tendencia := CASE
        WHEN v_velocidade > 0.05 THEN 'crescimento'
        WHEN v_velocidade < -0.05 THEN 'retracao'
        ELSE 'estavel'
    END;

    -- ------------------------------------------------------------------
    -- 9. Dependencia publica (all contracts are government → 1.0)
    -- ------------------------------------------------------------------
    v_dependencia_publica := 1.0;

    -- ------------------------------------------------------------------
    -- 10. Concentracao UF (Herfindahl index)
    -- ------------------------------------------------------------------
    WITH uf_dist AS (
        SELECT
            uf,
            COUNT(*)::NUMERIC AS total_uf
        FROM public.pncp_supplier_contracts
        WHERE ni_fornecedor = v_clean
          AND is_active = TRUE
          AND data_assinatura >= v_start_date
          AND uf IS NOT NULL
        GROUP BY uf
    )
    SELECT ROUND(
               COALESCE(
                   SUM(POWER(total_uf / NULLIF(v_vitorias::NUMERIC, 0), 2)),
                   0
               )::NUMERIC,
               4
           )
      INTO v_concentracao_uf
      FROM uf_dist;

    -- ------------------------------------------------------------------
    -- 11. Indice de diversificacao = 1 - Herfindahl (normalized)
    -- ------------------------------------------------------------------
    IF v_vitorias > 0 THEN
        v_indice_div := ROUND((1.0 - v_concentracao_uf)::NUMERIC, 4);
    ELSE
        v_indice_div := 0.0;
    END IF;

    -- ------------------------------------------------------------------
    -- 12. Time series (yearly)
    -- ------------------------------------------------------------------
    SELECT COALESCE(
               json_agg(
                   json_build_object(
                       'ano',       t.ano,
                       'contratos', t.contratos,
                       'valor',     t.valor
                   ) ORDER BY t.ano
               ),
               '[]'::JSON
           )
      INTO v_serie_temporal
      FROM (
        SELECT
            EXTRACT(YEAR FROM data_assinatura)::INT AS ano,
            COUNT(*)::BIGINT                         AS contratos,
            COALESCE(SUM(valor_global), 0)::NUMERIC  AS valor
        FROM public.pncp_supplier_contracts
        WHERE ni_fornecedor = v_clean
          AND is_active = TRUE
          AND data_assinatura IS NOT NULL
          AND data_assinatura >= v_start_date
        GROUP BY EXTRACT(YEAR FROM data_assinatura)
        ORDER BY ano
    ) t;

    -- ------------------------------------------------------------------
    -- 13. Percentiles (ticket values)
    -- ------------------------------------------------------------------
    WITH tickets AS (
        SELECT valor_global
        FROM public.pncp_supplier_contracts
        WHERE ni_fornecedor = v_clean
          AND is_active = TRUE
          AND data_assinatura >= v_start_date
          AND valor_global IS NOT NULL
          AND valor_global > 0
    )
    SELECT
        ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY valor_global)::NUMERIC, 2),
        ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY valor_global)::NUMERIC, 2),
        ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY valor_global)::NUMERIC, 2),
        ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY valor_global)::NUMERIC, 2)
      INTO v_p25, v_p50, v_p75, v_p90
      FROM tickets;

    -- ------------------------------------------------------------------
    -- 14. Segmentos (empty until setor_classificado is available)
    -- ------------------------------------------------------------------
    v_segmentos_atuais      := '[]'::JSON;
    v_segmentos_emergentes  := '[]'::JSON;
    v_segmentos_abandonados := '[]'::JSON;

    -- ------------------------------------------------------------------
    -- 15. Assemble final payload
    -- ------------------------------------------------------------------
    RETURN json_build_object(
        'cnpj',              v_clean,
        'nome',              COALESCE(v_nome, ''),
        'win_metrics',       json_build_object(
            'taxa_vitoria_estimada',       ROUND(v_taxa_vitoria::NUMERIC, 4),
            'total_participacoes_estimadas', v_participacoes,
            'total_vitorias',               v_vitorias,
            'velocidade_crescimento',        ROUND(COALESCE(v_velocidade, 0)::NUMERIC, 4),
            'tendencia',                     v_tendencia,
            'segmentos_atuais',              v_segmentos_atuais,
            'segmentos_emergentes',          v_segmentos_emergentes,
            'segmentos_abandonados',         v_segmentos_abandonados,
            'dependencia_publica',           ROUND(v_dependencia_publica::NUMERIC, 4),
            'concentracao_uf',               ROUND(COALESCE(v_concentracao_uf, 0)::NUMERIC, 4),
            'indice_diversificacao',         ROUND(COALESCE(v_indice_div, 0)::NUMERIC, 4)
        ),
        'serie_temporal',    COALESCE(v_serie_temporal, '[]'::JSON),
        'percentis',         json_build_object(
            'p25_ticket', COALESCE(v_p25, 0),
            'p50_ticket', COALESCE(v_p50, 0),
            'p75_ticket', COALESCE(v_p75, 0),
            'p90_ticket', COALESCE(v_p90, 0)
        )
    );
END;
$$;

COMMENT ON FUNCTION public.competitor_win_metrics(TEXT, INT) IS
    'COMPINT-002 — Competitive performance metrics for a supplier CNPJ. '
    'Computes estimated win rate (market-share proxy via total awards in same UFs), '
    'year-over-year CAGR growth trend, UF Herfindahl concentration, '
    'ticket percentiles, and yearly time series. '
    'STABLE + SECURITY DEFINER for RLS bypass and consistent index usage.';

-- Grant access to all authenticated roles (public competition data)
GRANT EXECUTE ON FUNCTION public.competitor_win_metrics(TEXT, INT) TO anon;
GRANT EXECUTE ON FUNCTION public.competitor_win_metrics(TEXT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.competitor_win_metrics(TEXT, INT) TO service_role;
