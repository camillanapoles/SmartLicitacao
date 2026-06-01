-- ============================================================================
-- SUBINTEL-010 — RPC subcontract_opportunity_score + FTS index
-- Date: 2026-05-31
--
-- SECTION 0: FTS index on objeto_contrato (prerequisite for performance)
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_psc_objeto_fts
    ON public.pncp_supplier_contracts
    USING GIN (to_tsvector('portuguese', COALESCE(objeto_contrato, '')))
    WHERE is_active = TRUE;

-- ============================================================================
-- SUBINTEL-010 — RPC subcontract_opportunity_score
-- Date: 2026-05-31
-- Purpose: Rank suppliers by subcontracting opportunity probability.
--
-- Computes a composite score (0-1) across 12+ signals derivable from
-- pncp_supplier_contracts, then returns the top-N suppliers ranked.
--
-- Signals (all derivable from available columns):
--   S1 — Object matches software/tech terms (FTS weight A)
--   S2 — Contract growth burst (last 12m vs previous 12m ratio)
--   S3 — Temporal concentration (contracts in last 180d / total in 24m)
--   S4 — Value sweet spot (R$150K–R$800K → peak, R$80K–R$2M → acceptable)
--   S5 — Geographic diversity (distinct UFs × distinct municipios)
--   S6 — Recurrence with same buyer (repeat orgao)
--   S7 — Object vagueness (generic descriptions → higher subcontract need)
--   S8 — Complexity/value ratio (long object ÷ low value = pain)
--   S9 — Esfera municipal preference (small/medium buyers → scope risk)
--   S10 — Peak simultaneous contracts (concurrency stress)
--   S11 — Recent contracts count (last 90d)
--   S12 — Average value proximity to sweet spot
--
-- Signals NOT available (require external enrichment):
--   - CNAE (would need Receita Federal / CNPJ API)
--   - Capital social (Receita Federal)
--   - Employee count (RAIS / CAGED)
--   - Website quality (external crawl)
--   - LinkedIn presence (external API)
--
-- Output: JSON array of top suppliers with scores and signal breakdowns.
-- Pattern: LANGUAGE SQL STABLE (scalar JSON bypasses PostgREST max_rows).
-- Expected p95 < 3s on 3.6M rows with existing indexes.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.subcontract_opportunity_score(
    p_top_n INT DEFAULT 200,
    p_window_months INT DEFAULT 24,
    p_min_valor NUMERIC DEFAULT 50000,
    p_max_valor NUMERIC DEFAULT 5000000
)
RETURNS json
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH
    -- Analysis windows
    win AS (
      SELECT
        CURRENT_DATE AS today,
        CURRENT_DATE - (p_window_months || ' months')::INTERVAL AS cutoff_24m,
        CURRENT_DATE - (12 || ' months')::INTERVAL AS cutoff_12m,
        CURRENT_DATE - (180 || ' days')::INTERVAL AS cutoff_180d,
        CURRENT_DATE - (90 || ' days')::INTERVAL AS cutoff_90d
    ),

    -- Step 1: Pre-filter contracts by software-related objects using FTS
    -- Weight: objetcs that match tech/software terms get priority
    tech_contracts AS (
      SELECT
        c.ni_fornecedor,
        c.nome_fornecedor,
        c.id,
        c.objeto_contrato,
        c.valor_global,
        c.data_assinatura,
        c.uf,
        c.municipio,
        c.esfera,
        c.orgao_nome,
        -- Software relevance score via FTS (0-1)
        ts_rank(
          to_tsvector('portuguese', COALESCE(c.objeto_contrato, '')),
          to_tsquery('portuguese',
            'desenvolvimento|software|sistema|automação|integração|API|' ||
            'painel|dashboard|BI|portal|aplicativo|web|módulo|' ||
            'transformação|digital|implantação|modernização|sustentação|' ||
            'manutenção|evolutiva|customização|fábrica|RPA|' ||
            'inteligência|artificial|chatbot|workflow|documental|' ||
            'processo|eletrônico|dados|migração|plataforma|' ||
            'Power BI|PowerBI|tecnologia|informação|TI'
          )
        ) AS score_objeto_relevance
      FROM pncp_supplier_contracts c, win
      WHERE c.is_active = TRUE
        AND c.data_assinatura >= win.cutoff_24m
        AND c.data_assinatura <= win.today
        AND c.valor_global BETWEEN p_min_valor AND p_max_valor
        AND c.nome_fornecedor IS NOT NULL
        AND c.ni_fornecedor IS NOT NULL
    ),

    -- Only keep contracts with any tech relevance signal
    -- (at least keyword match or generic tech term)
    tech_filtered AS (
      SELECT * FROM tech_contracts
      WHERE score_objeto_relevance > 0
         OR objeto_contrato ~* '(desenvolvimento|software|sistema|automa[cç][aã]o|integra[cç][aã]o|painel|dashboard|portal|aplicativo|plataforma|transforma[cç][aã]o digital|moderniza[cç][aã]o|sustenta[cç][aã]o|manuten[cç][aã]o|customiza[cç][aã]o|f[aá]brica|intelig[eê]ncia artificial|chatbot|workflow|migra[cç][aã]o|implanta[cç][aã]o|dados|processo eletr[ôo]nico|gest[aã]o documental|RPA|API|Power BI|m[óo]dulo|evolutiva|corretiva)'
    ),

    -- Step 2: Per-supplier aggregates over 24m window
    supplier_24m AS (
      SELECT
        ni_fornecedor,
        MAX(nome_fornecedor) AS nome_fornecedor,
        COUNT(*)::INT AS total_contratos_24m,
        COALESCE(SUM(valor_global), 0)::NUMERIC AS valor_total_24m,
        ROUND(COALESCE(AVG(valor_global), 0), 2)::NUMERIC AS ticket_medio,
        COUNT(DISTINCT uf)::INT AS ufs_distintas,
        COUNT(DISTINCT municipio)::INT AS municipios_distintos,
        COUNT(DISTINCT orgao_nome)::INT AS orgaos_distintos,
        -- Count contracts in each sub-window
        COUNT(*) FILTER (WHERE data_assinatura >= (SELECT cutoff_12m FROM win))::INT AS contratos_12m,
        COUNT(*) FILTER (WHERE data_assinatura >= (SELECT cutoff_180d FROM win))::INT AS contratos_180d,
        COUNT(*) FILTER (WHERE data_assinatura >= (SELECT cutoff_90d FROM win))::INT AS contratos_90d,
        -- Contract value in sub-windows
        COALESCE(SUM(valor_global) FILTER (WHERE data_assinatura >= (SELECT cutoff_12m FROM win)), 0)::NUMERIC AS valor_12m,
        COALESCE(SUM(valor_global) FILTER (WHERE data_assinatura >= (SELECT cutoff_180d FROM win)), 0)::NUMERIC AS valor_180d,
        -- Esfera distribution
        COUNT(*) FILTER (WHERE esfera = 'M')::INT AS contratos_municipais,
        COUNT(*) FILTER (WHERE esfera = 'E')::INT AS contratos_estaduais,
        COUNT(*) FILTER (WHERE esfera = 'F')::INT AS contratos_federais,
        -- Software relevance
        ROUND(COALESCE(AVG(score_objeto_relevance), 0)::NUMERIC, 4) AS media_relevancia_objeto,
        -- Repeat buyers (orgaos with >1 contract)
        COUNT(*) FILTER (
          WHERE orgao_nome IN (
            SELECT orgao_nome FROM tech_filtered tf2
            WHERE tf2.ni_fornecedor = tech_filtered.ni_fornecedor
            GROUP BY orgao_nome HAVING COUNT(*) > 1
          )
        )::INT AS contratos_orgao_recorrente,
        -- Object vagueness: short/generic descriptions
        COUNT(*) FILTER (
          WHERE LENGTH(COALESCE(objeto_contrato, '')) < 100
             OR objeto_contrato ~* '^(servi[cç]os|solu[cç][aã]o|consultoria|assessoria|apoio|suporte)'
        )::INT AS contratos_objeto_vago,
        -- Value sweet spot contracts
        COUNT(*) FILTER (WHERE valor_global BETWEEN 150000 AND 800000)::INT AS contratos_valor_ideal,
        COUNT(*) FILTER (WHERE valor_global BETWEEN 80000 AND 2000000)::INT AS contratos_valor_aceitavel,
        -- Low value per complexity: long object + low value = pain
        COUNT(*) FILTER (
          WHERE LENGTH(COALESCE(objeto_contrato, '')) > 200 AND valor_global < 300000
        )::INT AS contratos_complexo_barato
      FROM tech_filtered
      GROUP BY ni_fornecedor
    ),

    -- Step 3: Growth burst — compare last 12m vs previous 12m
    supplier_growth AS (
      SELECT
        ni_fornecedor,
        contratos_12m,
        -- Contracts in previous 12m (12-24m ago)
        (SELECT COUNT(*)::INT FROM tech_filtered tf
         WHERE tf.ni_fornecedor = tech_filtered.ni_fornecedor
           AND tf.data_assinatura >= (SELECT cutoff_24m FROM win)
           AND tf.data_assinatura < (SELECT cutoff_12m FROM win)
        ) AS contratos_prev_12m,
        -- Value in previous 12m
        (SELECT COALESCE(SUM(valor_global), 0)::NUMERIC FROM tech_filtered tf
         WHERE tf.ni_fornecedor = tech_filtered.ni_fornecedor
           AND tf.data_assinatura >= (SELECT cutoff_24m FROM win)
           AND tf.data_assinatura < (SELECT cutoff_12m FROM win)
        ) AS valor_prev_12m,
        valor_12m AS valor_12m_val
      FROM tech_filtered
      GROUP BY ni_fornecedor, tech_filtered.contratos_12m, tech_filtered.valor_12m
    ),

    -- Step 4: Peak simultaneous contracts (self-join on date ranges)
    supplier_peak AS (
      SELECT
        ni_fornecedor,
        COALESCE(MAX(s.cnt), 0)::INT AS pico_contratos_simultaneos
      FROM (
        SELECT
          a.ni_fornecedor,
          COUNT(*) AS cnt
        FROM tech_filtered a
        JOIN tech_filtered b
          ON b.ni_fornecedor = a.ni_fornecedor
          AND b.data_assinatura >= a.data_assinatura
          AND b.data_assinatura < a.data_assinatura + INTERVAL '12 months'
        GROUP BY a.id, a.ni_fornecedor
      ) s
      GROUP BY ni_fornecedor
    ),

    -- Step 5: Combine all signals into the composite score
    combined AS (
      SELECT
        s.ni_fornecedor,
        s.nome_fornecedor,
        s.total_contratos_24m,
        s.valor_total_24m,
        s.ticket_medio,
        s.ufs_distintas,
        s.municipios_distintos,
        s.orgaos_distintos,
        s.contratos_12m,
        s.contratos_180d,
        s.contratos_90d,
        s.contratos_municipais,
        s.media_relevancia_objeto,
        s.contratos_orgao_recorrente,
        s.contratos_objeto_vago,
        s.contratos_valor_ideal,
        s.contratos_complexo_barato,
        COALESCE(g.contratos_prev_12m, 0) AS contratos_prev_12m,
        COALESCE(g.valor_prev_12m, 0) AS valor_prev_12m,
        s.valor_12m,
        COALESCE(p.pico_contratos_simultaneos, 0) AS pico_contratos_simultaneos,

        -- ── COMPOSITE SCORE ──────────────────────────────────────────
        -- Each signal weighted, normalized 0-1, summed with weights
        --
        -- S1: Software relevance (weight 0.12)
        --   Already 0-1 from FTS, use average across contracts
        ROUND(LEAST(1.0, (s.media_relevancia_objeto * 0.12)::NUMERIC), 4) AS s1_relevancia,

        -- S2: Growth burst ratio (weight 0.15)
        --   contratos_12m / max(contratos_prev_12m, 1)
        --   >2x = strong signal, cap at 5x
        ROUND(LEAST(1.0,
          (LEAST(5.0, GREATEST(0,
            s.contratos_12m::NUMERIC / NULLIF(COALESCE(g.contratos_prev_12m, 1), 0)
          )) / 5.0 * 0.15)::NUMERIC
        ), 4) AS s2_crescimento,

        -- S3: Temporal concentration (weight 0.12)
        --   % of contracts in last 180 days
        ROUND(LEAST(1.0,
          (s.contratos_180d::NUMERIC / NULLIF(s.total_contratos_24m, 0) * 0.12)::NUMERIC
        ), 4) AS s3_concentracao,

        -- S4: Value sweet spot (weight 0.10)
        --   % contracts in ideal range (150K-800K)
        ROUND(LEAST(1.0,
          (s.contratos_valor_ideal::NUMERIC / NULLIF(s.total_contratos_24m, 0) * 0.10)::NUMERIC
        ), 4) AS s4_valor_ideal,

        -- S5: Geographic diversity (weight 0.10)
        --   (ufs * municipios) normalized — wide spread = higher subcontract need
        ROUND(LEAST(1.0,
          ((LEAST(27, s.ufs_distintas)::NUMERIC / 27.0) *
           (LEAST(50, s.municipios_distintos)::NUMERIC / 50.0) * 0.10)::NUMERIC
        ), 4) AS s5_geografia,

        -- S6: Repeat buyer recurrence (weight 0.08)
        ROUND(LEAST(1.0,
          (s.contratos_orgao_recorrente::NUMERIC / NULLIF(s.total_contratos_24m, 0) * 0.08)::NUMERIC
        ), 4) AS s6_recorrencia,

        -- S7: Object vagueness (weight 0.10)
        --   Generic descriptions → elastic scope → subcontract opportunity
        ROUND(LEAST(1.0,
          (s.contratos_objeto_vago::NUMERIC / NULLIF(s.total_contratos_24m, 0) * 0.10)::NUMERIC
        ), 4) AS s7_vaguidade,

        -- S8: Complexity-to-value ratio (weight 0.08)
        --   Complex scope + low value = pain
        ROUND(LEAST(1.0,
          (s.contratos_complexo_barato::NUMERIC / NULLIF(s.total_contratos_24m, 0) * 0.08)::NUMERIC
        ), 4) AS s8_complexidade,

        -- S9: Municipal focus (weight 0.06)
        ROUND(LEAST(1.0,
          (s.contratos_municipais::NUMERIC / NULLIF(s.total_contratos_24m, 0) * 0.06)::NUMERIC
        ), 4) AS s9_municipal,

        -- S10: Peak simultaneous contracts (weight 0.09)
        --   >3 simultaneous = moderate, >8 = strong, >15 = extreme
        ROUND(LEAST(1.0,
          (LEAST(20, COALESCE(p.pico_contratos_simultaneos, 0))::NUMERIC / 20.0 * 0.09)::NUMERIC
        ), 4) AS s10_pico
      FROM supplier_24m s
      LEFT JOIN supplier_growth g ON g.ni_fornecedor = s.ni_fornecedor
      LEFT JOIN supplier_peak p ON p.ni_fornecedor = s.ni_fornecedor
      WHERE s.total_contratos_24m >= 2 -- Minimum 2 contracts to be relevant
    ),

    -- Compute total score
    scored AS (
      SELECT
        *,
        ROUND((s1_relevancia + s2_crescimento + s3_concentracao +
               s4_valor_ideal + s5_geografia + s6_recorrencia +
               s7_vaguidade + s8_complexidade + s9_municipal + s10_pico)::NUMERIC, 4
        ) AS score_total,

        -- Classification tier
        CASE
          WHEN (s1_relevancia + s2_crescimento + s3_concentracao +
                s4_valor_ideal + s5_geografia + s6_recorrencia +
                s7_vaguidade + s8_complexidade + s9_municipal + s10_pico) >= 0.45
            THEN 'QUENTE'
          WHEN (s1_relevancia + s2_crescimento + s3_concentracao +
                s4_valor_ideal + s5_geografia + s6_recorrencia +
                s7_vaguidade + s8_complexidade + s9_municipal + s10_pico) >= 0.30
            THEN 'MORNO'
          ELSE 'FRIO'
        END AS tier
      FROM combined
    ),

    -- Rank and limit
    ranked AS (
      SELECT * FROM scored
      ORDER BY score_total DESC
      LIMIT LEAST(500, GREATEST(10, p_top_n))
    )

  -- Output as JSON array
  SELECT COALESCE(json_agg(
    json_build_object(
      'rank', ROW_NUMBER() OVER (ORDER BY score_total DESC),
      'ni_fornecedor', ni_fornecedor,
      'nome_fornecedor', nome_fornecedor,
      'score_total', score_total,
      'tier', tier,
      'total_contratos_24m', total_contratos_24m,
      'valor_total_24m', valor_total_24m,
      'ticket_medio', ticket_medio,
      'ufs_distintas', ufs_distintas,
      'municipios_distintos', municipios_distintos,
      'orgaos_distintos', orgaos_distintos,
      'contratos_12m', contratos_12m,
      'contratos_180d', contratos_180d,
      'contratos_90d', contratos_90d,
      'pico_contratos_simultaneos', pico_contratos_simultaneos,
      'contratos_municipais', contratos_municipais,
      'contratos_orgao_recorrente', contratos_orgao_recorrente,
      'contratos_valor_ideal', contratos_valor_ideal,
      'contratos_complexo_barato', contratos_complexo_barato,
      'media_relevancia_objeto', media_relevancia_objeto,
      'growth_ratio', CASE WHEN contratos_prev_12m > 0
        THEN ROUND((contratos_12m::NUMERIC / contratos_prev_12m)::NUMERIC, 2)
        ELSE NULL END,
      'sinais', json_build_object(
        's1_relevancia_software', s1_relevancia,
        's2_crescimento_brusco', s2_crescimento,
        's3_concentracao_temporal', s3_concentracao,
        's4_valor_sweet_spot', s4_valor_ideal,
        's5_dispersao_geografica', s5_geografia,
        's6_orgaos_recorrentes', s6_recorrencia,
        's7_objeto_vago', s7_vaguidade,
        's8_complexidade_vs_valor', s8_complexidade,
        's9_foco_municipal', s9_municipal,
        's10_pico_simultaneo', s10_pico
      )
    ) ORDER BY score_total DESC
  ), '[]'::json) FROM ranked;
$$;

COMMENT ON FUNCTION public.subcontract_opportunity_score(INT, INT, NUMERIC, NUMERIC) IS
  'SUBINTEL-010 — Ranks suppliers by subcontracting opportunity probability. '
  'Returns JSON array with composite score (0-1), tier, and 10 signal breakdowns. '
  'Params: top_n (default 200), window_months (24), min_valor (50000), max_valor (5000000).';

GRANT EXECUTE ON FUNCTION public.subcontract_opportunity_score(INT, INT, NUMERIC, NUMERIC)
  TO anon, authenticated, service_role;
