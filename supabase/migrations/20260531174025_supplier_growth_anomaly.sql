-- ============================================================================
-- SUBINTEL-003: RPC supplier_growth_anomaly
-- Purpose:   Detects growth anomalies by supplier CNPJ from
--            pncp_supplier_contracts. Computes monthly contract series,
--            baseline statistics (mean/stddev), z-score of the last
--            quarter vs baseline, YoY percentage variation, and anomaly
--            flags (abrupt growth, incumbent decline).
--
-- Data source: pncp_supplier_contracts (read-only, is_active = true)
--
-- Output: scalar JSON (bypasses PostgREST max-rows=1000)
--   {
--     "serie_mensal": [
--       {"mes": "2025-01", "count": 5, "valor": 350000.00},
--       ...
--     ],
--     "baseline_media": 4.5,
--     "baseline_desvio": 1.2,
--     "zscore_ultimo_trimestre": 2.8,
--     "variacao_pct_yoy": 0.65,
--     "flag_crescimento_abrupto": true,
--     "flag_incumbente_em_queda": false
--   }
--
-- Logic:
--   - serie_mensal: last 24 complete calendar months
--   - baseline_media / baseline_desvio: computed from the oldest
--     p_baseline_months months within the 24-month window
--   - zscore_ultimo_trimestre: (avg of last 3 months - baseline_media)
--     / baseline_desvio (0 if desvio <= 0)
--   - variacao_pct_yoy: (current year count - previous year count)
--     / previous year count within the 24-month window (0 if prev = 0)
--   - flag_crescimento_abrupto: zscore > 2 AND variacao_pct_yoy > 0.50
--   - flag_incumbente_em_queda: >= 3 consecutive months below
--     baseline_media in the recent period
--
-- Expected p95 < 800ms using existing indexes:
--   idx_psc_ni_fornecedor (ni_fornecedor)
--   idx_psc_fornecedor_data (ni_fornecedor, data_assinatura DESC)
-- ============================================================================

CREATE OR REPLACE FUNCTION public.supplier_growth_anomaly(
    p_ni_fornecedor TEXT,
    p_baseline_months INT DEFAULT 12
)
RETURNS JSON
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_ni_clean          TEXT;
    v_now               DATE;
    v_cutoff            DATE;
    v_baseline_cutoff   DATE;

    v_serie_mensal      JSON;
    v_baseline_media    NUMERIC(18,2);
    v_baseline_desvio   NUMERIC(18,2);
    v_trim_media        NUMERIC(18,2);
    v_zscore            NUMERIC(18,2);
    v_variacao_pct      NUMERIC(10,4);
    v_flag_crescimento  BOOLEAN;
    v_flag_queda        BOOLEAN;

    v_year_curr         INT;
    v_year_prev         INT;
    v_count_curr        INT;
    v_count_prev        INT;
    v_consecutive_below INT;
BEGIN
    -- ---------------------------------------------------------------
    -- 1. Input normalization & validation
    -- ---------------------------------------------------------------
    v_ni_clean := regexp_replace(COALESCE(p_ni_fornecedor, ''), '[^0-9]', '', 'g');

    IF p_baseline_months IS NULL OR p_baseline_months < 1 OR p_baseline_months > 23 THEN
        p_baseline_months := 12;
    END IF;

    v_now := CURRENT_DATE;
    -- 24 complete months from the start of (current month - 23 months)
    -- to the start of the current month
    v_cutoff := date_trunc('month', v_now) - INTERVAL '23 months';
    -- Boundary: contracts on/after this date are "recent";
    -- contracts before are "baseline"
    v_baseline_cutoff := v_now - (p_baseline_months || ' months')::INTERVAL;

    SET LOCAL statement_timeout = '15s';

    -- ---------------------------------------------------------------
    -- 2. Monthly series — 24 months with zero-fill
    -- ---------------------------------------------------------------
    WITH grid AS (
        SELECT
            to_char(d, 'YYYY-MM')       AS mes,
            d                            AS mes_date
        FROM generate_series(
            v_cutoff,
            date_trunc('month', v_now),
            '1 month'::interval
        ) AS d
    ),
    agg AS (
        SELECT
            date_trunc('month', data_assinatura)  AS mes_date,
            COUNT(*)::INT                          AS cnt,
            COALESCE(SUM(valor_global), 0)::NUMERIC(18,2) AS vlr
        FROM pncp_supplier_contracts
        WHERE ni_fornecedor = v_ni_clean
          AND is_active = true
          AND data_assinatura >= v_cutoff
          AND data_assinatura IS NOT NULL
        GROUP BY date_trunc('month', data_assinatura)
    ),
    filled AS (
        SELECT
            g.mes,
            g.mes_date,
            COALESCE(a.cnt, 0)::INT              AS count,
            COALESCE(a.vlr, 0)::NUMERIC(18,2)    AS valor
        FROM grid g
        LEFT JOIN agg a ON g.mes_date = a.mes_date
    )
    SELECT COALESCE(json_agg(
        json_build_object('mes', f.mes, 'count', f.count, 'valor', f.valor)
        ORDER BY f.mes_date
    ), '[]'::json)
    INTO v_serie_mensal
    FROM filled f;

    -- ---------------------------------------------------------------
    -- 3. Baseline statistics (oldest p_baseline_months months)
    -- ---------------------------------------------------------------
    WITH baseline_data AS (
        SELECT COALESCE(a.cnt, 0)::INT AS count
        FROM generate_series(
            v_cutoff,
            date_trunc('month', v_baseline_cutoff),
            '1 month'::interval
        ) AS d
        LEFT JOIN (
            SELECT date_trunc('month', data_assinatura) AS mes_date,
                   COUNT(*)::INT AS cnt
            FROM pncp_supplier_contracts
            WHERE ni_fornecedor = v_ni_clean
              AND is_active = true
              AND data_assinatura >= v_cutoff
            GROUP BY date_trunc('month', data_assinatura)
        ) a ON d = a.mes_date
    )
    SELECT INTO v_baseline_media, v_baseline_desvio
        ROUND(COALESCE(AVG(count), 0)::NUMERIC, 2),
        CASE
            WHEN COUNT(*) >= 2 THEN ROUND(COALESCE(stddev_samp(count), 0)::NUMERIC, 2)
            ELSE 0
        END
    FROM baseline_data;

    -- ---------------------------------------------------------------
    -- 4. Last 3 months average (most recent complete months)
    -- ---------------------------------------------------------------
    WITH last_3 AS (
        SELECT COALESCE(a.cnt, 0)::INT AS count
        FROM generate_series(
            date_trunc('month', v_now) - INTERVAL '2 months',
            date_trunc('month', v_now),
            '1 month'::interval
        ) AS d
        LEFT JOIN (
            SELECT date_trunc('month', data_assinatura) AS mes_date,
                   COUNT(*)::INT AS cnt
            FROM pncp_supplier_contracts
            WHERE ni_fornecedor = v_ni_clean
              AND is_active = true
              AND data_assinatura >= v_cutoff
            GROUP BY date_trunc('month', data_assinatura)
        ) a ON d = a.mes_date
    )
    SELECT COALESCE(AVG(count), 0)::NUMERIC(18,2)
    INTO v_trim_media
    FROM last_3;

    -- ---------------------------------------------------------------
    -- 5. Z-score of last quarter vs baseline
    -- ---------------------------------------------------------------
    IF v_baseline_desvio > 0 THEN
        v_zscore := ROUND((v_trim_media - v_baseline_media) / v_baseline_desvio, 2);
    ELSE
        v_zscore := 0;
    END IF;

    -- ---------------------------------------------------------------
    -- 6. YoY variation (current year vs previous year, 24mo window)
    -- ---------------------------------------------------------------
    v_year_curr := EXTRACT(YEAR FROM v_now);
    v_year_prev := v_year_curr - 1;

    SELECT COUNT(*)::INT INTO v_count_curr
    FROM pncp_supplier_contracts
    WHERE ni_fornecedor = v_ni_clean
      AND is_active = true
      AND EXTRACT(YEAR FROM data_assinatura) = v_year_curr
      AND data_assinatura >= v_cutoff;

    SELECT COUNT(*)::INT INTO v_count_prev
    FROM pncp_supplier_contracts
    WHERE ni_fornecedor = v_ni_clean
      AND is_active = true
      AND EXTRACT(YEAR FROM data_assinatura) = v_year_prev
      AND data_assinatura >= v_cutoff;

    IF v_count_prev > 0 THEN
        v_variacao_pct := ROUND(
            (v_count_curr::NUMERIC - v_count_prev) / v_count_prev,
            4
        );
    ELSE
        v_variacao_pct := 0;
    END IF;

    -- ---------------------------------------------------------------
    -- 7. Sustained decline check (flag_incumbente_em_queda)
    --    Uses gaps-and-islands: months in recent period where count
    --    < baseline_media are grouped; max group length >= 3 → flag
    -- ---------------------------------------------------------------
    WITH recent_data AS (
        SELECT
            d AS mes_date,
            COALESCE(a.cnt, 0)::INT AS count
        FROM generate_series(
            date_trunc('month', v_baseline_cutoff),
            date_trunc('month', v_now),
            '1 month'::interval
        ) AS d
        LEFT JOIN (
            SELECT date_trunc('month', data_assinatura) AS mes_date,
                   COUNT(*)::INT AS cnt
            FROM pncp_supplier_contracts
            WHERE ni_fornecedor = v_ni_clean
              AND is_active = true
              AND data_assinatura >= v_cutoff
            GROUP BY date_trunc('month', data_assinatura)
        ) a ON d = a.mes_date
    ),
    flagged AS (
        SELECT
            count,
            CASE WHEN count < v_baseline_media THEN 1 ELSE 0 END AS is_below,
            ROW_NUMBER() OVER (ORDER BY mes_date)
            - ROW_NUMBER() OVER (
                PARTITION BY CASE WHEN count < v_baseline_media THEN 1 ELSE 0 END
                ORDER BY mes_date
              ) AS grp
        FROM recent_data
    )
    SELECT COALESCE(MAX(seq_len), 0) INTO v_consecutive_below
    FROM (
        SELECT COUNT(*) AS seq_len
        FROM flagged
        WHERE is_below = 1
        GROUP BY grp
    ) seq;

    -- ---------------------------------------------------------------
    -- 8. Flags
    -- ---------------------------------------------------------------
    v_flag_crescimento := v_zscore > 2 AND v_variacao_pct > 0.50;
    v_flag_queda       := v_consecutive_below >= 3;

    -- ---------------------------------------------------------------
    -- 9. Assemble final JSON
    -- ---------------------------------------------------------------
    RETURN json_build_object(
        'serie_mensal',              v_serie_mensal,
        'baseline_media',           v_baseline_media,
        'baseline_desvio',          v_baseline_desvio,
        'zscore_ultimo_trimestre',  v_zscore,
        'variacao_pct_yoy',        v_variacao_pct,
        'flag_crescimento_abrupto', v_flag_crescimento,
        'flag_incumbente_em_queda', v_flag_queda
    );
END;
$$;

COMMENT ON FUNCTION public.supplier_growth_anomaly(TEXT, INT) IS
    'SUBINTEL-003 — Detects growth anomalies by supplier CNPJ. '
    'Returns monthly contract series, baseline statistics (mean/stddev), '
    'z-score of last quarter vs baseline, YoY variation, and anomaly flags. '
    'STABLE + SECURITY DEFINER for RLS bypass.';

GRANT EXECUTE ON FUNCTION public.supplier_growth_anomaly(TEXT, INT) TO anon;
GRANT EXECUTE ON FUNCTION public.supplier_growth_anomaly(TEXT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.supplier_growth_anomaly(TEXT, INT) TO service_role;
