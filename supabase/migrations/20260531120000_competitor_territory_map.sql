-- ============================================================================
-- COMPINT-001: RPC competitor_territory_map — mapa territorial do concorrente
-- Issue: #1272
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   Wave 0 RPC for Competitive Intelligence EPIC (#1261). Analyzes
--   `pncp_supplier_contracts` to build a competitor's territorial map:
--   where they win, average ticket, favorite agencies, geographic patterns.
--
--   Output (scalar JSON, bypasses PostgREST max_rows=1000):
--     {
--       "concorrente": { cnpj, nome, total_contratos, ticket_medio,
--                        ticket_mediana, valor_total_contratado },
--       "territorio": [{ uf, contratos, valor_total, ticket_medio_uf,
--                        orgaos_principais, market_share_uf, tendencia }],
--       "orgaos_favoritos": [{ orgao_nome, contratos, valor_total,
--                              categorias, ultima_vitoria, frequencia_anual }],
--       "stats": { ufs_atuacao, orgaos_unicos, anos_atuacao, crescimento_anual }
--     }
--
--   SECURITY DEFINER + SET search_path = public, pg_temp per
--   SEC-SECDEF-001/002 (feedback_secdef_search_path_trap).
--   GRANT to anon, authenticated, service_role — dados de contrato são públicos.
-- ============================================================================

-- Auxiliary index: cnpj_vencedor + data_assinatura DESC cobre o padrão de
-- consulta principal: WHERE ni_fornecedor = ? AND data_assinatura >= ?
CREATE INDEX IF NOT EXISTS idx_psc_cnpj_vencedor_data
    ON pncp_supplier_contracts(ni_fornecedor, data_assinatura DESC);

CREATE OR REPLACE FUNCTION public.competitor_territory_map(
    p_cnpj text,
    p_anos int DEFAULT 5
)
RETURNS json
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_cnpj_clean     text;
    v_cutoff_date    date;
    v_result         json;

    -- Section 1: concorrente
    v_cnpj           text;
    v_nome           text;
    v_total_contratos int;
    v_ticket_medio   float8;
    v_ticket_mediana float8;
    v_valor_total    float8;

    -- Section 2: territorio
    v_territorio     json;

    -- Section 3: orgaos_favoritos
    v_orgaos         json;

    -- Section 4: stats
    v_stats          json;
BEGIN
    -- ── Defesa em profundidade: timeout local de 15s
    SET LOCAL statement_timeout = '15s';

    -- ── Normalizar CNPJ: dígitos apenas, 14 caracteres
    v_cnpj_clean := regexp_replace(COALESCE(p_cnpj, ''), '[^0-9]', '', 'g');
    IF length(v_cnpj_clean) <> 14 THEN
        RAISE EXCEPTION 'CNPJ invalido: deve conter 14 digitos apos normalizacao, obtido %', length(v_cnpj_clean)
            USING HINT = 'Forneca um CNPJ de 14 digitos (apenas numeros)';
    END IF;

    IF p_anos IS NULL OR p_anos < 1 OR p_anos > 50 THEN
        RAISE EXCEPTION 'parametro invalido: p_anos deve estar entre 1 e 50';
    END IF;

    v_cutoff_date := (CURRENT_DATE - (p_anos || ' years')::INTERVAL)::DATE;

    -- ── Seção 1: Concorrente (metadados agregados)
    v_cnpj := v_cnpj_clean;

    SELECT
        COALESCE(MAX(nome_fornecedor), '')          AS nome,
        COUNT(*)::int                                AS total_contratos,
        ROUND(COALESCE(AVG(valor_global), 0)::numeric, 2)::float8 AS ticket_medio,
        ROUND(COALESCE(
            (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY valor_global)
             FROM public.pncp_supplier_contracts
             WHERE ni_fornecedor = v_cnpj_clean
               AND is_active = TRUE
               AND data_assinatura >= v_cutoff_date
               AND valor_global IS NOT NULL),
            0
        )::numeric, 2)::float8                      AS ticket_mediana,
        ROUND(COALESCE(SUM(valor_global), 0)::numeric, 2)::float8 AS valor_total_contratado
    INTO
        v_nome, v_total_contratos,
        v_ticket_medio, v_ticket_mediana, v_valor_total
    FROM public.pncp_supplier_contracts
    WHERE ni_fornecedor = v_cnpj_clean
      AND is_active = TRUE
      AND data_assinatura >= v_cutoff_date;

    -- ── Se v_total_contratos = 0, retornar objeto zerado
    IF v_total_contratos IS NULL OR v_total_contratos = 0 THEN
        RETURN json_build_object(
            'concorrente', json_build_object(
                'cnpj',                  v_cnpj_clean,
                'nome',                  '',
                'total_contratos',       0,
                'ticket_medio',          0.0,
                'ticket_mediana',        0.0,
                'valor_total_contratado', 0.0
            ),
            'territorio',       '[]'::json,
            'orgaos_favoritos', '[]'::json,
            'stats', json_build_object(
                'ufs_atuacao',      0,
                'orgaos_unicos',    0,
                'anos_atuacao',     0,
                'crescimento_anual', 0.0
            )
        );
    END IF;

    -- ── Seção 2: Território (agregação por UF)
    WITH territorio AS (
        SELECT
            c.uf,
            COUNT(*)::int                                                      AS contratos,
            ROUND(COALESCE(SUM(c.valor_global), 0)::numeric, 2)::float8        AS valor_total,
            ROUND(COALESCE(AVG(c.valor_global), 0)::numeric, 2)::float8        AS ticket_medio_uf,
            LEAST(
                ROUND(
                    COUNT(*)::numeric
                    / NULLIF(
                        (SELECT COUNT(*) FROM public.pncp_supplier_contracts
                         WHERE uf = c.uf AND is_active = TRUE
                           AND data_assinatura >= v_cutoff_date),
                        0
                    ),
                    4
                )::float8,
                1.0
            )                                                                  AS market_share_uf,
            (
                SELECT COALESCE(json_agg(t.orgao ORDER BY t.cnt DESC), '[]'::json)
                FROM (
                    SELECT c2.orgao_nome AS orgao, COUNT(*)::int AS cnt
                    FROM public.pncp_supplier_contracts c2
                    WHERE c2.ni_fornecedor = v_cnpj_clean
                      AND c2.is_active = TRUE
                      AND c2.data_assinatura >= v_cutoff_date
                      AND c2.uf = c.uf
                      AND c2.orgao_nome IS NOT NULL AND c2.orgao_nome <> ''
                    GROUP BY c2.orgao_nome
                    ORDER BY cnt DESC
                    LIMIT 3
                ) t
            )                                                                  AS orgaos_principais,
            CASE
                WHEN COUNT(*) >= 3 THEN (
                    WITH uf_split AS (
                        SELECT
                            COUNT(*) FILTER (WHERE data_assinatura >= CURRENT_DATE - ((p_anos * 365) / 2) * INTERVAL '1 day') AS recentes,
                            COUNT(*) FILTER (WHERE data_assinatura <  CURRENT_DATE - ((p_anos * 365) / 2) * INTERVAL '1 day') AS antigos
                        FROM public.pncp_supplier_contracts
                        WHERE ni_fornecedor = v_cnpj_clean
                          AND is_active = TRUE
                          AND data_assinatura >= v_cutoff_date
                          AND uf = c.uf
                    )
                    SELECT CASE
                        WHEN recentes > antigos * 1.2 THEN 'crescendo'
                        WHEN recentes < antigos * 0.8 THEN 'declinio'
                        ELSE 'estavel'
                    END
                    FROM uf_split
                )
                ELSE 'estavel'
            END                                                                AS tendencia
        FROM public.pncp_supplier_contracts c
        WHERE c.ni_fornecedor = v_cnpj_clean
          AND c.is_active = TRUE
          AND c.data_assinatura >= v_cutoff_date
          AND c.uf IS NOT NULL AND c.uf <> ''
        GROUP BY c.uf
    )
    SELECT COALESCE(json_agg(territorio.* ORDER BY territorio.contratos DESC), '[]'::json)
    INTO v_territorio
    FROM territorio;

    -- ── Seção 3: Órgãos favoritos
    WITH orgaos_favoritos AS (
        SELECT
            c.orgao_nome,
            COUNT(*)::int                                                      AS contratos,
            ROUND(COALESCE(SUM(c.valor_global), 0)::numeric, 2)::float8        AS valor_total,
            (
                SELECT COALESCE(json_agg(DISTINCT t.cat ORDER BY t.cat), '[]'::json)
                FROM (
                    SELECT
                        CASE
                            WHEN c2.objeto_contrato ~* 'tecnologia|software|informatica|sistema|digital' THEN 'tecnologia'
                            WHEN c2.objeto_contrato ~* 'consultoria|assessoria|auditoria|parecer' THEN 'consultoria'
                            WHEN c2.objeto_contrato ~* 'saude|medico|hospitalar|farmaceutico|medicamento' THEN 'saude'
                            WHEN c2.objeto_contrato ~* 'educacao|ensino|treinamento|curso|capacitacao' THEN 'educacao'
                            WHEN c2.objeto_contrato ~* 'construcao|engenharia|reforma|edificacao|obra' THEN 'construcao'
                            WHEN c2.objeto_contrato ~* 'limpeza|higienizacao|asseio|conservacao' THEN 'limpeza'
                            WHEN c2.objeto_contrato ~* 'alimentacao|refeicao|merenda|nutricao|alimento' THEN 'alimentacao'
                            WHEN c2.objeto_contrato ~* 'transporte|logistica|frota|veiculo' THEN 'transporte'
                            WHEN c2.objeto_contrato ~* 'seguranca|vigilancia|monitoramento|protecao' THEN 'seguranca'
                        END AS cat
                    FROM public.pncp_supplier_contracts c2
                    WHERE c2.ni_fornecedor = v_cnpj_clean
                      AND c2.is_active = TRUE
                      AND c2.data_assinatura >= v_cutoff_date
                      AND c2.orgao_nome = c.orgao_nome
                      AND c2.objeto_contrato IS NOT NULL
                ) t
                WHERE t.cat IS NOT NULL
            )                                                                  AS categorias,
            MAX(c.data_assinatura::text)                                       AS ultima_vitoria,
            ROUND(COUNT(*)::numeric / p_anos, 1)::float8                       AS frequencia_anual
        FROM public.pncp_supplier_contracts c
        WHERE c.ni_fornecedor = v_cnpj_clean
          AND c.is_active = TRUE
          AND c.data_assinatura >= v_cutoff_date
          AND c.orgao_nome IS NOT NULL AND c.orgao_nome <> ''
        GROUP BY c.orgao_nome
        ORDER BY COUNT(*) DESC
        LIMIT 10
    )
    SELECT COALESCE(json_agg(orgaos_favoritos.* ORDER BY orgaos_favoritos.contratos DESC), '[]'::json)
    INTO v_orgaos
    FROM orgaos_favoritos;

    -- ── Seção 4: Stats (métricas globais)
    WITH yearly_counts AS (
        SELECT
            EXTRACT(YEAR FROM data_assinatura)::int AS ano,
            COUNT(*)::int AS cnt
        FROM public.pncp_supplier_contracts
        WHERE ni_fornecedor = v_cnpj_clean
          AND is_active = TRUE
          AND data_assinatura >= v_cutoff_date
        GROUP BY ano
    )
    SELECT json_build_object(
        'ufs_atuacao', (SELECT COUNT(DISTINCT uf)::int
                        FROM public.pncp_supplier_contracts
                        WHERE ni_fornecedor = v_cnpj_clean
                          AND is_active = TRUE
                          AND data_assinatura >= v_cutoff_date
                          AND uf IS NOT NULL AND uf <> ''),
        'orgaos_unicos', (SELECT COUNT(DISTINCT orgao_nome)::int
                          FROM public.pncp_supplier_contracts
                          WHERE ni_fornecedor = v_cnpj_clean
                            AND is_active = TRUE
                            AND data_assinatura >= v_cutoff_date
                            AND orgao_nome IS NOT NULL AND orgao_nome <> ''),
        'anos_atuacao', COALESCE((SELECT COUNT(*)::int FROM yearly_counts), 0),
        'crescimento_anual', COALESCE((
            SELECT CASE
                WHEN COUNT(*) >= 2
                 AND MIN(cnt) > 0
                 AND MAX(ano) > MIN(ano)
                THEN ROUND(
                    (POWER(1.0 * MAX(cnt) / MIN(cnt), 1.0 / (MAX(ano) - MIN(ano))) - 1.0)::numeric,
                    4
                )::float8
                ELSE 0.0
            END
            FROM yearly_counts
        ), 0.0)
    )
    INTO v_stats;

    -- ── Montar resultado final
    v_result := json_build_object(
        'concorrente', json_build_object(
            'cnpj',                  v_cnpj,
            'nome',                  v_nome,
            'total_contratos',       v_total_contratos,
            'ticket_medio',          v_ticket_medio,
            'ticket_mediana',        v_ticket_mediana,
            'valor_total_contratado', v_valor_total
        ),
        'territorio',       v_territorio,
        'orgaos_favoritos', v_orgaos,
        'stats',            v_stats
    );

    RETURN v_result;
END;
$$;

-- Permite chamada pública — dados de contrato do PNCP são públicos
GRANT EXECUTE ON FUNCTION public.competitor_territory_map(text, int)
    TO anon, authenticated, service_role;

COMMENT ON FUNCTION public.competitor_territory_map(text, int) IS
    'COMPINT-001: Build competitor territorial map from pncp_supplier_contracts. '
    'Returns scalar JSON with concorrente, territorio, orgaos_favoritos, and stats sections. '
    'Parameters: p_cnpj (14-digit CNPJ), p_anos (analysis window in years, default 5).';
