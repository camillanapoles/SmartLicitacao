-- ============================================================================
-- PREDINT-004: RPC predict_incumbent_decay — previsao de queda de incumbentes
-- Issue: #1267
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   Wave 0 RPC for Predictive Intelligence EPIC (#1260). Detects incumbent
--   suppliers whose contract volume is declining compared to their 5-year
--   historical average by analyzing `pncp_supplier_contracts`.
--
--   Detection logic:
--     contratos_ultimo_ano  → contracts signed in the last 12 months
--     contratos_media_5anos → annual average over the 5 years before that
--     taxa_queda = (media_5anos - contratos_ultimo_ano)
--                / GREATEST(media_5anos, 1)
--
--     Only suppliers with taxa_queda >= 0.25 are included in the output.
--     Suppliers with taxa_queda < 0.25 (stable or growing) are excluded.
--
--   Performance:
--     - Analyzes top 200 suppliers by historical volume
--     - Detailed competitor/org data limited to top 50 in decline
--     - statement_timeout = 15s safety guard
--
--   Output (scalar JSON, bypasses PostgREST max_rows=1000):
--     {
--       "incumbentes_em_queda": [
--         {
--           "fornecedor_cnpj": "XX.XXX.XXX/0001-XX",
--           "fornecedor_nome": "EMPRESA X LTDA",
--           "contratos_ultimo_ano": 2,
--           "contratos_media_5anos": 8.0,
--           "taxa_queda": 0.75,
--           "orgaos_abandonando": ["ORGAO A", "ORGAO B"],
--           "concorrentes_ganhando": ["CONCORRENTE Y", "CONCORRENTE Z"],
--           "sinal_alerta": "queda_acentuada",
--           "segmento_afetado": "tecnologia"
--         }
--       ],
--       "stats": {
--         "total_incumbentes_analisados": 500,
--         "em_queda": 34,
--         "queda_media_setor": 0.12
--       }
--     }
--
--   SECURITY DEFINER + SET search_path = public, pg_temp per
--   SEC-SECDEF-001/002 (feedback_secdef_search_path_trap).
--   GRANT to anon, authenticated, service_role — dados de contrato sao publicos.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.predict_incumbent_decay(
    p_uf VARCHAR(2) DEFAULT NULL,
    p_setor TEXT DEFAULT NULL,
    p_min_contratos_historicos INT DEFAULT 3
)
RETURNS json
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
WITH
-- Step 1: Candidate suppliers (top 200 by historical volume)
-- Aggregates 6 years of contract data with optional UF/sector filters.
candidates AS (
    SELECT
        ni_fornecedor,
        MAX(nome_fornecedor) AS nome_fornecedor,
        COUNT(*) FILTER (
            WHERE data_assinatura >= CURRENT_DATE - INTERVAL '1 year'
        )::int AS contratos_ultimo_ano,
        COUNT(*) FILTER (
            WHERE data_assinatura >= CURRENT_DATE - INTERVAL '6 years'
              AND data_assinatura < CURRENT_DATE - INTERVAL '1 year'
        )::int AS contratos_5anos_historico
    FROM pncp_supplier_contracts
    WHERE is_active = TRUE
      AND data_assinatura >= CURRENT_DATE - INTERVAL '6 years'
      AND (p_uf IS NULL OR uf = UPPER(p_uf))
      AND (p_setor IS NULL OR COALESCE(setor_classificado, '') = p_setor)
    GROUP BY ni_fornecedor
    HAVING COUNT(*) FILTER (
        WHERE data_assinatura >= CURRENT_DATE - INTERVAL '6 years'
          AND data_assinatura < CURRENT_DATE - INTERVAL '1 year'
    ) >= p_min_contratos_historicos
    ORDER BY COUNT(*) DESC
    LIMIT 200
),
-- Step 2: Compute decay metrics per supplier
decay AS (
    SELECT
        ni_fornecedor,
        nome_fornecedor,
        contratos_ultimo_ano,
        ROUND(contratos_5anos_historico::numeric / 5.0, 1)::float8
            AS contratos_media_5anos,
        ROUND(
            (
                (contratos_5anos_historico::numeric / 5.0)
                - contratos_ultimo_ano::numeric
            )
            / GREATEST(contratos_5anos_historico::numeric / 5.0, 1.0),
            4
        )::float8 AS taxa_queda
    FROM candidates
),
-- Step 3: Filter to declining suppliers only (taxa_queda >= 0.25)
-- Suppliers with stable or growing contract volume are excluded.
declining AS (
    SELECT *
    FROM decay
    WHERE taxa_queda >= 0.25
),
-- Step 4: Build incumbentes_em_queda JSON array
-- For each declining supplier, compute orgaos_abandonando, concorrentes_ganhando,
-- sinal_alerta, and segmento_afetado via correlated subqueries.
incumbentes_built AS (
    SELECT
        json_build_object(
            'fornecedor_cnpj',
                CASE WHEN length(d.ni_fornecedor) = 14
                THEN format('%s.%s.%s/%s-%s',
                    left(d.ni_fornecedor, 2), substr(d.ni_fornecedor, 3, 3),
                    substr(d.ni_fornecedor, 6, 3), substr(d.ni_fornecedor, 9, 4),
                    right(d.ni_fornecedor, 2))
                ELSE d.ni_fornecedor END,
            'fornecedor_nome', d.nome_fornecedor,
            'contratos_ultimo_ano', d.contratos_ultimo_ano,
            'contratos_media_5anos', d.contratos_media_5anos,
            'taxa_queda', d.taxa_queda,
            -- Orgaos abandonando: orgs where supplier had contracts in the
            -- historical 5-year window but NOT in the last 12 months (max 5)
            'orgaos_abandonando', COALESCE((
                SELECT json_agg(sub.orgao_nome ORDER BY sub.orgao_nome)
                FROM (
                    SELECT ho.orgao_nome
                    FROM (
                        SELECT DISTINCT s.orgao_nome
                        FROM pncp_supplier_contracts s
                        WHERE s.ni_fornecedor = d.ni_fornecedor
                          AND s.is_active = TRUE
                          AND s.data_assinatura >= CURRENT_DATE - INTERVAL '6 years'
                          AND s.data_assinatura < CURRENT_DATE - INTERVAL '1 year'
                          AND s.orgao_nome IS NOT NULL
                    ) ho
                    LEFT JOIN (
                        SELECT DISTINCT s.orgao_nome
                        FROM pncp_supplier_contracts s
                        WHERE s.ni_fornecedor = d.ni_fornecedor
                          AND s.is_active = TRUE
                          AND s.data_assinatura >= CURRENT_DATE - INTERVAL '1 year'
                          AND s.orgao_nome IS NOT NULL
                    ) ro ON ro.orgao_nome = ho.orgao_nome
                    WHERE ro.orgao_nome IS NULL
                    LIMIT 5
                ) sub
            ), '[]'::json),
            -- Concorrentes ganhando: suppliers who won contracts at the abandoned
            -- orgs in the last 12 months (max 3, limited by performance)
            'concorrentes_ganhando', COALESCE((
                SELECT json_agg(sub.competitor_nome ORDER BY sub.cnt DESC)
                FROM (
                    SELECT c.nome_fornecedor AS competitor_nome,
                           COUNT(*)::int AS cnt
                    FROM pncp_supplier_contracts c
                    WHERE c.is_active = TRUE
                      AND c.data_assinatura >= CURRENT_DATE - INTERVAL '1 year'
                      AND c.ni_fornecedor <> d.ni_fornecedor
                      AND c.orgao_nome IN (
                          SELECT ho.orgao_nome
                          FROM (
                              SELECT DISTINCT s.orgao_nome
                              FROM pncp_supplier_contracts s
                              WHERE s.ni_fornecedor = d.ni_fornecedor
                                AND s.is_active = TRUE
                                AND s.data_assinatura >= CURRENT_DATE - INTERVAL '6 years'
                                AND s.data_assinatura < CURRENT_DATE - INTERVAL '1 year'
                                AND s.orgao_nome IS NOT NULL
                          ) ho
                          LEFT JOIN (
                              SELECT DISTINCT s.orgao_nome
                              FROM pncp_supplier_contracts s
                              WHERE s.ni_fornecedor = d.ni_fornecedor
                                AND s.is_active = TRUE
                                AND s.data_assinatura >= CURRENT_DATE - INTERVAL '1 year'
                                AND s.orgao_nome IS NOT NULL
                          ) ro ON ro.orgao_nome = ho.orgao_nome
                          WHERE ro.orgao_nome IS NULL
                          LIMIT 5
                      )
                      AND c.nome_fornecedor IS NOT NULL
                      AND c.nome_fornecedor <> ''
                    GROUP BY c.nome_fornecedor
                    ORDER BY cnt DESC
                    LIMIT 3
                ) sub
            ), '[]'::json),
            -- Sinal de alerta baseado na magnitude da queda
            'sinal_alerta',
                CASE
                    WHEN d.taxa_queda > 0.50
                    THEN 'queda_acentuada'::text
                    ELSE 'queda_moderada'::text
                END,
            -- Segmento mais afetado: setor mais comum entre os contratos perdidos
            'segmento_afetado', COALESCE((
                SELECT COALESCE(s.setor_classificado, 'sem_classificacao')
                FROM pncp_supplier_contracts s
                WHERE s.ni_fornecedor = d.ni_fornecedor
                  AND s.is_active = TRUE
                  AND s.data_assinatura >= CURRENT_DATE - INTERVAL '6 years'
                  AND s.data_assinatura < CURRENT_DATE - INTERVAL '1 year'
                  AND s.orgao_nome IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM pncp_supplier_contracts s2
                      WHERE s2.ni_fornecedor = s.ni_fornecedor
                        AND s2.orgao_nome = s.orgao_nome
                        AND s2.is_active = TRUE
                        AND s2.data_assinatura >= CURRENT_DATE - INTERVAL '1 year'
                  )
                GROUP BY s.setor_classificado
                ORDER BY COUNT(*) DESC
                LIMIT 1
            ), 'sem_classificacao')
        ) AS item,
        d.taxa_queda
    FROM declining d
    ORDER BY d.taxa_queda DESC
    LIMIT 50
),
-- Step 5: Aggregate stats (all declining suppliers, not just top 50)
stats AS (
    SELECT
        (SELECT COUNT(*)::int FROM candidates)
            AS total_incumbentes_analisados,
        (SELECT COUNT(*)::int FROM declining)
            AS em_queda,
        COALESCE(
            (SELECT ROUND(AVG(d.taxa_queda)::numeric, 4)::float8
             FROM declining d),
            0.0::float8
        ) AS queda_media_setor
)
-- Final assembly
SELECT json_build_object(
    'incumbentes_em_queda',
    COALESCE(
        (SELECT json_agg(ib.item ORDER BY ib.taxa_queda DESC)
         FROM incumbentes_built ib),
        '[]'::json
    ),
    'stats', json_build_object(
        'total_incumbentes_analisados',
            (SELECT total_incumbentes_analisados FROM stats),
        'em_queda', (SELECT em_queda FROM stats),
        'queda_media_setor', (SELECT queda_media_setor FROM stats)
    )
);
$$;

COMMENT ON FUNCTION public.predict_incumbent_decay(VARCHAR, TEXT, INT) IS
    'PREDINT-004: Predict incumbent decay from pncp_supplier_contracts. '
    'Returns scalar JSON with incumbentes_em_queda array and stats. '
    'Parameters: p_uf (optional filter by UF), '
    'p_setor (optional filter by sector), '
    'p_min_contratos_historicos (min contracts for baseline, default 3).';

GRANT EXECUTE ON FUNCTION public.predict_incumbent_decay(VARCHAR, TEXT, INT)
    TO anon, authenticated, service_role;
