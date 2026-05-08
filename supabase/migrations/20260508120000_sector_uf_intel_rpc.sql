-- ============================================================================
-- UP: sector_uf_intel_rpc — RPC de agregação para Panorama Setorial × UF
-- Date: 2026-05-08
-- Issue: #826
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   Pipeline INTEL-REPORT-002 (R$147): DataLake → RPC → PDF → Stripe → email.
--   Esta migration entrega o passo 2 (RPC). Agrega `pncp_supplier_contracts`
--   por setor (via keywords no objeto_contrato) + UF, retornando JSONB pronto
--   para gerar PDF via ReportLab (pdf_generator_sector_uf_report.py).
--
--   Como `pncp_supplier_contracts` NÃO possui coluna `setor`, a filtragem
--   setorial é feita via `objeto_contrato ILIKE '%keyword%'` sobre o array
--   `p_keywords` — mesma abordagem de `count_contracts_by_setor_uf` (#SEO-471).
--
--   Assinatura:
--     sector_uf_intel(p_sector TEXT, p_keywords TEXT[], p_uf TEXT,
--                     p_window_months INTEGER DEFAULT 24) RETURNS JSONB
--
--   SECURITY DEFINER + `SET search_path = public, pg_temp` é mandatory por
--   SEC-SECDEF-001/002 (`feedback_secdef_search_path_trap`).
--   GRANT só a service_role — payload liberado pós-pagamento pelo backend.
-- ============================================================================

BEGIN;

-- ────────────────────────────────────────────────────────────────────────────
-- RPC: sector_uf_intel
-- Retorna JSONB com métricas do setor na UF dentro da janela de tempo.
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.sector_uf_intel(
    p_sector         TEXT,
    p_keywords       TEXT[],
    p_uf             TEXT,
    p_window_months  INTEGER DEFAULT 24
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_uf_clean      TEXT;
    v_window_start  DATE;
    v_result        JSONB;

    v_total_count        BIGINT;
    v_total_value        NUMERIC;
    v_avg_ticket         NUMERIC;
    v_median_ticket      NUMERIC;
    v_p90_ticket         NUMERIC;
    v_data_primeiro      DATE;
    v_data_ultimo        DATE;

    v_top_fornecedores   JSONB;
    v_distribuicao_mod   JSONB;
    v_serie_temporal     JSONB;
    v_top_orgaos         JSONB;
    v_top_objetos        JSONB;
BEGIN
    -- ── Defesa em profundidade: timeout local
    SET LOCAL statement_timeout = '15s';

    -- ── Validar inputs
    IF p_keywords IS NULL OR array_length(p_keywords, 1) IS NULL THEN
        RAISE EXCEPTION 'p_keywords must be a non-empty array';
    END IF;

    v_uf_clean := upper(regexp_replace(COALESCE(p_uf, ''), '[^A-Za-z]', '', 'g'));
    IF length(v_uf_clean) <> 2 THEN
        RAISE EXCEPTION 'invalid uf: must be 2-letter state code after normalization';
    END IF;

    IF p_window_months IS NULL OR p_window_months < 1 OR p_window_months > 240 THEN
        RAISE EXCEPTION 'invalid window: p_window_months must be between 1 and 240';
    END IF;

    v_window_start := (CURRENT_DATE - (p_window_months || ' months')::INTERVAL)::DATE;

    -- ── Headline metrics (single pass)
    SELECT
        COUNT(*)::BIGINT,
        COALESCE(SUM(valor_global), 0)::NUMERIC,
        COALESCE(AVG(valor_global), 0)::NUMERIC,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY valor_global),
        PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY valor_global),
        MIN(data_assinatura),
        MAX(data_assinatura)
      INTO
        v_total_count,
        v_total_value,
        v_avg_ticket,
        v_median_ticket,
        v_p90_ticket,
        v_data_primeiro,
        v_data_ultimo
      FROM public.pncp_supplier_contracts
     WHERE is_active = TRUE
       AND upper(uf) = v_uf_clean
       AND data_assinatura >= v_window_start
       AND EXISTS (
           SELECT 1 FROM unnest(p_keywords) AS kw
            WHERE objeto_contrato ILIKE '%' || kw || '%'
       );

    -- ── Top 20 fornecedores por valor total
    SELECT COALESCE(
             jsonb_agg(entry ORDER BY (entry->>'valor_total')::NUMERIC DESC),
             '[]'::JSONB
           )
      INTO v_top_fornecedores
      FROM (
        SELECT jsonb_build_object(
                   'ni_fornecedor',  ni_fornecedor,
                   'nome_fornecedor', MAX(nome_fornecedor),
                   'count',          COUNT(*)::BIGINT,
                   'valor_total',    COALESCE(SUM(valor_global), 0)::NUMERIC,
                   'avg_ticket',     COALESCE(AVG(valor_global), 0)::NUMERIC
               ) AS entry
          FROM public.pncp_supplier_contracts
         WHERE is_active = TRUE
           AND upper(uf) = v_uf_clean
           AND data_assinatura >= v_window_start
           AND EXISTS (
               SELECT 1 FROM unnest(p_keywords) AS kw
                WHERE objeto_contrato ILIKE '%' || kw || '%'
           )
           AND ni_fornecedor IS NOT NULL
         GROUP BY ni_fornecedor
         ORDER BY SUM(valor_global) DESC NULLS LAST
         LIMIT 20
      ) sub;

    -- ── Distribuição por modalidade (esfera usado como proxy — tabela não tem modalidade)
    -- Nota: pncp_supplier_contracts não possui coluna modalidade; usa esfera como
    -- proxy de concentração contratual (F/E/M/D).
    SELECT COALESCE(
             jsonb_agg(entry ORDER BY (entry->>'valor_total')::NUMERIC DESC),
             '[]'::JSONB
           )
      INTO v_distribuicao_mod
      FROM (
        SELECT jsonb_build_object(
                   'esfera',      COALESCE(esfera, '?'),
                   'count',       COUNT(*)::BIGINT,
                   'valor_total', COALESCE(SUM(valor_global), 0)::NUMERIC
               ) AS entry
          FROM public.pncp_supplier_contracts
         WHERE is_active = TRUE
           AND upper(uf) = v_uf_clean
           AND data_assinatura >= v_window_start
           AND EXISTS (
               SELECT 1 FROM unnest(p_keywords) AS kw
                WHERE objeto_contrato ILIKE '%' || kw || '%'
           )
         GROUP BY COALESCE(esfera, '?')
      ) sub;

    -- ── Série temporal mensal com zero-fill via generate_series
    -- generate_series garante todos os meses na janela, mesmo sem contratos.
    SELECT COALESCE(jsonb_agg(entry ORDER BY entry->>'mes'), '[]'::JSONB)
      INTO v_serie_temporal
      FROM (
        SELECT jsonb_build_object(
                   'mes',         to_char(gs.mes, 'YYYY-MM'),
                   'count',       COALESCE(agg.cnt, 0)::BIGINT,
                   'valor_total', COALESCE(agg.valor, 0)::NUMERIC
               ) AS entry
          FROM (
            SELECT generate_series(
                       date_trunc('month', v_window_start::TIMESTAMP),
                       date_trunc('month', CURRENT_DATE::TIMESTAMP),
                       '1 month'::INTERVAL
                   ) AS mes
          ) gs
          LEFT JOIN (
            SELECT date_trunc('month', data_assinatura)  AS mes,
                   COUNT(*)::BIGINT                      AS cnt,
                   COALESCE(SUM(valor_global), 0)::NUMERIC AS valor
              FROM public.pncp_supplier_contracts
             WHERE is_active = TRUE
               AND upper(uf) = v_uf_clean
               AND data_assinatura >= v_window_start
               AND data_assinatura IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM unnest(p_keywords) AS kw
                    WHERE objeto_contrato ILIKE '%' || kw || '%'
               )
             GROUP BY date_trunc('month', data_assinatura)
          ) agg ON agg.mes = gs.mes
      ) t;

    -- ── Top 10 órgãos compradores por valor
    SELECT COALESCE(
             jsonb_agg(entry ORDER BY (entry->>'valor_total')::NUMERIC DESC),
             '[]'::JSONB
           )
      INTO v_top_orgaos
      FROM (
        SELECT jsonb_build_object(
                   'orgao_cnpj',  orgao_cnpj,
                   'orgao_nome',  MAX(orgao_nome),
                   'count',       COUNT(*)::BIGINT,
                   'valor_total', COALESCE(SUM(valor_global), 0)::NUMERIC
               ) AS entry
          FROM public.pncp_supplier_contracts
         WHERE is_active = TRUE
           AND upper(uf) = v_uf_clean
           AND data_assinatura >= v_window_start
           AND EXISTS (
               SELECT 1 FROM unnest(p_keywords) AS kw
                WHERE objeto_contrato ILIKE '%' || kw || '%'
           )
           AND orgao_cnpj IS NOT NULL
         GROUP BY orgao_cnpj
         ORDER BY SUM(valor_global) DESC NULLS LAST
         LIMIT 10
      ) sub;

    -- ── Top 10 objetos por frequência
    SELECT COALESCE(
             jsonb_agg(entry ORDER BY (entry->>'count')::BIGINT DESC),
             '[]'::JSONB
           )
      INTO v_top_objetos
      FROM (
        SELECT jsonb_build_object(
                   'objeto_resumo', objeto_resumo,
                   'count',         COUNT(*)::BIGINT,
                   'valor_total',   COALESCE(SUM(valor_global), 0)::NUMERIC
               ) AS entry
          FROM (
            SELECT LEFT(COALESCE(NULLIF(TRIM(objeto_contrato), ''), '(sem objeto)'), 80) AS objeto_resumo,
                   valor_global
              FROM public.pncp_supplier_contracts
             WHERE is_active = TRUE
               AND upper(uf) = v_uf_clean
               AND data_assinatura >= v_window_start
               AND EXISTS (
                   SELECT 1 FROM unnest(p_keywords) AS kw
                    WHERE objeto_contrato ILIKE '%' || kw || '%'
               )
          ) raw
         GROUP BY objeto_resumo
         ORDER BY COUNT(*) DESC, SUM(valor_global) DESC NULLS LAST
         LIMIT 10
      ) sub;

    -- ── Assemble final payload
    v_result := jsonb_build_object(
        'sector',               COALESCE(p_sector, ''),
        'uf',                   v_uf_clean,
        'window_months',        p_window_months,
        'window_start',         v_window_start,
        'total_contracts',      v_total_count,
        'total_value',          v_total_value,
        'avg_ticket',           v_avg_ticket,
        'median_ticket',        v_median_ticket,
        'p90_ticket',           v_p90_ticket,
        'data_primeiro_contrato', v_data_primeiro,
        'data_ultimo_contrato', v_data_ultimo,
        'top_fornecedores',     v_top_fornecedores,
        'distribuicao_esfera',  v_distribuicao_mod,
        'serie_temporal',       v_serie_temporal,
        'top_orgaos',           v_top_orgaos,
        'top_objetos',          v_top_objetos,
        'generated_at',         NOW()
    );

    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.sector_uf_intel(TEXT, TEXT[], TEXT, INTEGER) IS
    'INTEL-REPORT-002 — Agregações sobre pncp_supplier_contracts por setor×UF para PDF Panorama Setorial. SECURITY DEFINER, service_role only.';

REVOKE ALL ON FUNCTION public.sector_uf_intel(TEXT, TEXT[], TEXT, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.sector_uf_intel(TEXT, TEXT[], TEXT, INTEGER) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.sector_uf_intel(TEXT, TEXT[], TEXT, INTEGER) TO service_role;

COMMIT;
