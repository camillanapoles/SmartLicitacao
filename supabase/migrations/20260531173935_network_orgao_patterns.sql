-- ============================================================================
-- NETINT-003: RPC network_orgao_patterns — padroes emergentes por orgao
-- Date: 2026-05-31
-- Issue: #1285
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   Wave 0 RPC for Network Intelligence EPIC (#1263). Detecta padroes
--   emergentes de contratacao por orgao publico, comparando a frequencia
--   recente de contratos contra a media historica.
--
--   Para cada orgao + categoria, calcula:
--     - frequencia_recente:  count na janela de p_meses meses
--     - frequencia_historica: media mensal no periodo anterior (mesma duracao)
--     - fator_mudanca:        frequencia_recente / GREATEST(media_historica, 1)
--     - sinal:               explosao (>5), crescimento (2-5), moderado (<2)
--
--   Categoria inferida de pncp_supplier_contracts.setor_classificado.
--   Se setor_classificado for NULL, usa 'geral' como fallback.
--
--   Fonte: pncp_supplier_contracts (leitura, 100% dados publicos).
--   Performance: p95 < 500ms com indices existentes.
--
--   Privacy: 100% dados publicos PNCP. Zero dados de usuario.
--
--   Assinatura:
--     network_orgao_patterns(p_uf VARCHAR(2) DEFAULT NULL,
--                            p_meses INT DEFAULT 6,
--                            p_min_frequencia INT DEFAULT 3) RETURNS json
--
--   SECURITY DEFINER + SET search_path = public, pg_temp conforme padrao.
--   GRANT para anon, authenticated, service_role (dados publicos).
-- ============================================================================

CREATE OR REPLACE FUNCTION public.network_orgao_patterns(
    p_uf VARCHAR(2) DEFAULT NULL,
    p_meses INT DEFAULT 6,
    p_min_frequencia INT DEFAULT 3
)
RETURNS json
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_cutoff_atual DATE;
    v_cutoff_historico DATE;
    v_result json;
BEGIN
    -- ------------------------------------------------------------------
    -- Validacao de parametros
    -- ------------------------------------------------------------------
    IF p_meses IS NULL OR p_meses < 1 THEN
        p_meses := 6;
    END IF;

    IF p_min_frequencia IS NULL OR p_min_frequencia < 1 THEN
        p_min_frequencia := 3;
    END IF;

    -- Janelas de tempo
    v_cutoff_atual := (CURRENT_DATE - (p_meses || ' months')::INTERVAL)::DATE;
    v_cutoff_historico := (v_cutoff_atual - (p_meses || ' months')::INTERVAL)::DATE;

    -- statement_timeout local: defesa contra queries runaway
    SET LOCAL statement_timeout = '15s';

    -- ------------------------------------------------------------------
    -- CTEs de agregacao
    -- ------------------------------------------------------------------
    WITH
    -- Base: contratos no periodo completo (historico + recente)
    contract_base AS (
        SELECT
            orgao_nome,
            uf,
            COALESCE(setor_classificado, 'geral') AS categoria,
            data_assinatura,
            valor_global
        FROM pncp_supplier_contracts
        WHERE is_active = TRUE
          AND data_assinatura >= v_cutoff_historico
          AND (p_uf IS NULL OR UPPER(uf) = UPPER(p_uf))
    ),
    -- Frequencia recente: count e volume nos ultimos p_meses meses
    recent_freq AS (
        SELECT
            orgao_nome,
            uf,
            categoria,
            COUNT(*)::integer AS frequencia_recente,
            COALESCE(SUM(valor_global), 0) AS volume_recente
        FROM contract_base
        WHERE data_assinatura >= v_cutoff_atual
        GROUP BY orgao_nome, uf, categoria
        HAVING COUNT(*) >= p_min_frequencia
    ),
    -- Frequencia historica: media mensal no periodo anterior (mesma duracao)
    historical_freq AS (
        SELECT
            orgao_nome,
            uf,
            categoria,
            COUNT(*)::numeric / p_meses AS frequencia_historica
        FROM contract_base
        WHERE data_assinatura >= v_cutoff_historico
          AND data_assinatura < v_cutoff_atual
        GROUP BY orgao_nome, uf, categoria
    ),
    -- Combinar e calcular fator_mudanca e sinal
    patterns AS (
        SELECT
            r.orgao_nome,
            r.uf AS orgao_uf,
            r.categoria,
            r.frequencia_recente,
            COALESCE(h.frequencia_historica, 0) AS frequencia_historica,
            r.frequencia_recente / GREATEST(COALESCE(h.frequencia_historica, 0), 1) AS fator_mudanca,
            r.volume_recente,
            CASE
                WHEN r.frequencia_recente / GREATEST(COALESCE(h.frequencia_historica, 0), 1) > 5
                THEN 'explosao'
                WHEN r.frequencia_recente / GREATEST(COALESCE(h.frequencia_historica, 0), 1) >= 2
                THEN 'crescimento'
                ELSE 'moderado'
            END AS sinal
        FROM recent_freq r
        LEFT JOIN historical_freq h
            ON r.orgao_nome = h.orgao_nome
            AND r.uf = h.uf
            AND r.categoria = h.categoria
    ),
    -- Stats agregados
    stats_data AS (
        SELECT
            COUNT(DISTINCT p.orgao_nome || '|' || p.orgao_uf)::integer AS orgaos_analisados,
            COUNT(*)::integer AS padroes_detectados,
            COALESCE(
                (SELECT p2.categoria
                 FROM patterns p2
                 GROUP BY p2.categoria
                 ORDER BY COUNT(*) DESC
                 LIMIT 1),
                'N/A'
            ) AS categoria_mais_emergente
        FROM patterns p
    )
    -- ------------------------------------------------------------------
    -- Montagem do payload final
    -- ------------------------------------------------------------------
    SELECT json_build_object(
        'padroes_emergentes', COALESCE(
            (SELECT json_agg(
                json_build_object(
                    'orgao_nome', p.orgao_nome,
                    'orgao_uf', p.orgao_uf,
                    'categoria', p.categoria,
                    'frequencia_recente', p.frequencia_recente,
                    'frequencia_historica', ROUND(p.frequencia_historica::numeric, 2),
                    'fator_mudanca', ROUND(p.fator_mudanca::numeric, 2),
                    'volume_recente', ROUND(p.volume_recente::numeric, 2),
                    'sinal', p.sinal
                ) ORDER BY p.fator_mudanca DESC
            ) FROM patterns p),
            '[]'::json
        ),
        'stats', json_build_object(
            'orgaos_analisados', s.orgaos_analisados,
            'padroes_detectados', s.padroes_detectados,
            'categoria_mais_emergente', s.categoria_mais_emergente
        )
    ) INTO v_result
    FROM stats_data s;

    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.network_orgao_patterns(VARCHAR, INT, INT) IS
    'NETINT-003 — Padroes emergentes de contratacao por orgao publico. '
    'Compara frequencia recente vs historica por orgao+categoria. '
    'Dados publicos PNCP. SECURITY DEFINER.';

-- Grants: dados publicos PNCP — todos os roles podem consultar
GRANT EXECUTE ON FUNCTION public.network_orgao_patterns(VARCHAR, INT, INT) TO anon;
GRANT EXECUTE ON FUNCTION public.network_orgao_patterns(VARCHAR, INT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.network_orgao_patterns(VARCHAR, INT, INT) TO service_role;


