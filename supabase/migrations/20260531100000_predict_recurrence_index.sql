-- ============================================================================
-- PREDINT-002 — RPC predict_recurrence_index (indice de recorrencia por orgao)
-- Issue: #1265
-- Date: 2026-05-31
-- ============================================================================
-- Context:
--   Wave 0 RPC for Predictive Intelligence EPIC (#1260). Calculates recurrence
--   index by orgao + sector category, ranking orgaos by repurchase predictability.
--
--   Index logic (4 components, weighted):
--     indice_recorrencia = 0.35 * frequencia_5anos
--                        + 0.25 * regularidade_intervalo
--                        + 0.20 * concentracao_categoria
--                        + 0.20 * permanencia_orgao
--
--     frequencia_5anos:        min(cnt / 20, 1) -- normalized by 20 contracts
--     regularidade_intervalo:  1 - (stddev/avg_interval) -- clamped [0, 1]
--     concentracao_categoria:  category_contracts / org_total_contracts
--     permanencia_orgao:       1 if >=3 consecutive years, 0.5 if >=2, 0.2 otherwise
--
--   Returns scalar JSON to bypass PostgREST max_rows=1000.
--
-- Reference: supabase/migrations/20260512080000_sitemap_contratos_orgao_rpc.sql
--            supabase/migrations/20260509172143_data_cap_001_orgao_top_contracts_rpc.sql
-- ============================================================================

-- ────────────────────────────────────────────────────────────────────────────
-- SECTION 1: Add columns (idempotent) + index
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE pncp_supplier_contracts
  ADD COLUMN IF NOT EXISTS setor_classificado TEXT;

ALTER TABLE pncp_supplier_contracts
  ADD COLUMN IF NOT EXISTS data_fim_vigencia DATE;

COMMENT ON COLUMN pncp_supplier_contracts.setor_classificado IS
  'PREDINT-002: SmartLic sector classification from ingestion enrichment';

COMMENT ON COLUMN pncp_supplier_contracts.data_fim_vigencia IS
  'PREDINT-002: Contract end date for recurrence interval calculation';

CREATE INDEX IF NOT EXISTS idx_psc_orgao_setor_data
  ON pncp_supplier_contracts(uf, setor_classificado, data_fim_vigencia);

-- ────────────────────────────────────────────────────────────────────────────
-- SECTION 2: RPC — predict_recurrence_index
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.predict_recurrence_index(
  p_uf VARCHAR(2) DEFAULT NULL,
  p_setor TEXT DEFAULT NULL,
  p_orgao_codigo TEXT DEFAULT NULL
)
RETURNS json
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  WITH
  -- Step 1: Base contracts in 5-year window with optional filters
  base AS (
    SELECT
      orgao_nome,
      uf,
      COALESCE(setor_classificado, 'sem_classificacao') AS categoria,
      data_fim_vigencia,
      data_assinatura
    FROM pncp_supplier_contracts
    WHERE is_active = TRUE
      AND data_assinatura >= (CURRENT_DATE - INTERVAL '5 years')
      AND data_assinatura IS NOT NULL
      AND (p_uf IS NULL OR uf = UPPER(p_uf))
      AND (p_setor IS NULL OR COALESCE(setor_classificado, '') = p_setor)
      AND (p_orgao_codigo IS NULL OR orgao_cnpj = p_orgao_codigo)
  ),
  -- Step 2: Lagged dates for interval computation (per orgao + categoria)
  with_lag AS (
    SELECT *,
      LAG(data_assinatura) OVER (
        PARTITION BY orgao_nome, COALESCE(setor_classificado, 'sem_classificacao')
        ORDER BY data_assinatura
      ) AS lag_data
    FROM base
  ),
  -- Step 3: Per (orgao, categoria) statistics
  per_pair AS (
    SELECT
      orgao_nome,
      uf,
      COALESCE(setor_classificado, 'sem_classificacao') AS categoria,
      COUNT(*)::bigint AS total_contratos_5anos,
      COUNT(DISTINCT EXTRACT(YEAR FROM data_assinatura))::integer AS anos_distintos,
      MAX(data_fim_vigencia) AS ultimo_contrato_fim,
      MAX(data_assinatura) AS ultima_assinatura,
      ROUND(
        COALESCE(AVG(EXTRACT(DAY FROM data_assinatura - lag_data)), 0)
      )::integer AS intervalo_medio_dias,
      ROUND(
        COALESCE(STDDEV_POP(EXTRACT(DAY FROM data_assinatura - lag_data)), 0)
      )::integer AS intervalo_desvio
    FROM with_lag
    WHERE lag_data IS NOT NULL  -- first contract has no predecessor
    GROUP BY orgao_nome, uf, COALESCE(setor_classificado, 'sem_classificacao')
  ),
  -- Step 4: Total contracts per orgao (for concentration ratio)
  org_total AS (
    SELECT
      orgao_nome,
      COUNT(*)::bigint AS total_org
    FROM base
    GROUP BY orgao_nome
  ),
  -- Step 5: Quarterly distribution for seasonality detection
  sazonalidade AS (
    SELECT
      orgao_nome,
      COALESCE(setor_classificado, 'sem_classificacao') AS categoria,
      CASE
        WHEN q1 > avg_q AND q2 > avg_q THEN 'Q1-Q2'
        WHEN q1 > avg_q AND q3 > avg_q THEN 'Q1-Q3'
        WHEN q1 > avg_q AND q4 > avg_q THEN 'Q1-Q4'
        WHEN q2 > avg_q AND q3 > avg_q THEN 'Q2-Q3'
        WHEN q2 > avg_q AND q4 > avg_q THEN 'Q2-Q4'
        WHEN q3 > avg_q AND q4 > avg_q THEN 'Q3-Q4'
        WHEN q1 > avg_q THEN 'Q1'
        WHEN q2 > avg_q THEN 'Q2'
        WHEN q3 > avg_q THEN 'Q3'
        WHEN q4 > avg_q THEN 'Q4'
        ELSE NULL
      END AS sazonalidade_detectada
    FROM (
      SELECT
        orgao_nome,
        COALESCE(setor_classificado, 'sem_classificacao') AS categoria,
        COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM data_assinatura) IN (1,2,3))::numeric AS q1,
        COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM data_assinatura) IN (4,5,6))::numeric AS q2,
        COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM data_assinatura) IN (7,8,9))::numeric AS q3,
        COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM data_assinatura) IN (10,11,12))::numeric AS q4,
        COUNT(*)::numeric / 4.0 AS avg_q
      FROM base
      GROUP BY orgao_nome, COALESCE(setor_classificado, 'sem_classificacao')
    ) sub
  ),
  -- Step 6: Calculate recurrence components
  calc AS (
    SELECT
      p.orgao_nome,
      p.uf,
      p.categoria,
      p.total_contratos_5anos,
      p.intervalo_medio_dias,
      p.intervalo_desvio,
      p.ultimo_contrato_fim,
      p.ultima_assinatura,
      ot.total_org,
      s.sazonalidade_detectada,
      -- Component 1: Frequency (normalized, capped at 20 contracts)
      LEAST(p.total_contratos_5anos::numeric / 20.0, 1.0) AS freq_component,
      -- Component 2: Regularity = 1 - (deviation / avg_interval)
      CASE
        WHEN p.intervalo_medio_dias > 0
        THEN GREATEST(1.0 - (p.intervalo_desvio::numeric / p.intervalo_medio_dias), 0.0)
        ELSE 0.0
      END AS regularidade,
      -- Component 3: Category concentration
      CASE
        WHEN ot.total_org > 0
        THEN (p.total_contratos_5anos::numeric / ot.total_org)
        ELSE 0.0
      END AS concentracao,
      -- Component 4: Permanence (3+ consecutive years indicates stability)
      CASE
        WHEN p.anos_distintos >= 3 THEN 1.0
        WHEN p.anos_distintos >= 2 THEN 0.5
        ELSE 0.2
      END AS permanencia
    FROM per_pair p
    LEFT JOIN org_total ot ON ot.orgao_nome = p.orgao_nome
    LEFT JOIN sazonalidade s ON s.orgao_nome = p.orgao_nome AND s.categoria = p.categoria
  ),
  -- Step 7: Build individual orgao JSON objects
  orgaos_built AS (
    SELECT
      json_build_object(
        'orgao_nome', c.orgao_nome,
        'orgao_uf', c.uf,
        'categoria', c.categoria,
        'indice_recorrencia', ROUND(ci.indice_numeric, 2)::float8,
        'total_contratos_5anos', c.total_contratos_5anos,
        'intervalo_medio_dias', c.intervalo_medio_dias,
        'intervalo_desvio', c.intervalo_desvio,
        'ultimo_contrato_fim',
          COALESCE(c.ultimo_contrato_fim::text, c.ultima_assinatura::text),
        'proxima_janela_inicio',
          CASE
            WHEN ci.indice_numeric > 0.5
            THEN GREATEST(
              (COALESCE(c.ultimo_contrato_fim, c.ultima_assinatura)
               + (c.intervalo_medio_dias - GREATEST(c.intervalo_desvio, 1)) * INTERVAL '1 day'),
              CURRENT_DATE + INTERVAL '1 day'
            )::text
            ELSE NULL
          END,
        'proxima_janela_fim',
          CASE
            WHEN ci.indice_numeric > 0.5
            THEN (COALESCE(c.ultimo_contrato_fim, c.ultima_assinatura)
                  + (c.intervalo_medio_dias + GREATEST(c.intervalo_desvio, 1)) * INTERVAL '1 day')::text
            ELSE NULL
          END,
        'sazonalidade_detectada', c.sazonalidade_detectada
      ) AS item,
      ci.indice_numeric
    FROM calc c
    CROSS JOIN LATERAL (
      SELECT (0.35 * c.freq_component
            + 0.25 * c.regularidade
            + 0.20 * c.concentracao
            + 0.20 * c.permanencia)::numeric AS indice_numeric
    ) ci
  ),
  -- Step 8: National stats
  stats AS (
    SELECT
      (SELECT COUNT(DISTINCT orgao_nome) FROM base) AS orgaos_analisados,
      COALESCE(
        (SELECT ROUND(AVG(ci.indice_numeric), 2)
         FROM calc c
         CROSS JOIN LATERAL (
           SELECT (0.35 * c.freq_component
                 + 0.25 * c.regularidade
                 + 0.20 * c.concentracao
                 + 0.20 * c.permanencia)::numeric AS indice_numeric
         ) ci),
        0.0
      )::float8 AS indice_medio_nacional,
      COALESCE(
        (SELECT json_agg(t.categoria ORDER BY t.avg_indice DESC)
         FROM (
           SELECT c.categoria,
                  AVG(0.35 * c.freq_component + 0.25 * c.regularidade
                     + 0.20 * c.concentracao + 0.20 * c.permanencia)::numeric AS avg_indice
           FROM calc c
           GROUP BY c.categoria
           ORDER BY avg_indice DESC
           LIMIT 3
         ) t),
        '[]'::json
      ) AS categorias_mais_recorrentes
  )
  -- Final assembly
  SELECT json_build_object(
    'orgaos', COALESCE(
      (SELECT json_agg(ob.item ORDER BY ob.indice_numeric DESC) FROM orgaos_built ob),
      '[]'::json
    ),
    'stats', json_build_object(
      'orgaos_analisados', (SELECT orgaos_analisados FROM stats),
      'indice_medio_nacional', (SELECT indice_medio_nacional FROM stats),
      'categorias_mais_recorrentes', (SELECT categorias_mais_recorrentes FROM stats)
    )
  );
$$;

COMMENT ON FUNCTION public.predict_recurrence_index(VARCHAR(2), TEXT, TEXT) IS
  'PREDINT-002: Recurrence index by orgao + sector category. Returns scalar JSON.';

GRANT EXECUTE ON FUNCTION public.predict_recurrence_index(VARCHAR(2), TEXT, TEXT)
  TO anon, authenticated, service_role;
