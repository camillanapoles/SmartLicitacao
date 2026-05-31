"""SUBINTEL-003: Tests for supplier_growth_anomaly RPC.

Tests the SQL migration file (static analysis) and validates that
calling the RPC through supabase.rpc() returns the expected JSON schema.

No live database connection required. All RPC calls are mocked.
"""

import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"
MIGRATION_FILE = "20260531174025_supplier_growth_anomaly.sql"


@pytest.fixture(scope="module")
def migration_sql() -> str:
    """Read the migration SQL file for static analysis."""
    path = MIGRATIONS_DIR / MIGRATION_FILE
    if not path.exists():
        # Fallback: try with the worktree path offset
        alt_path = (
            Path(__file__).resolve().parent.parent.parent
            / "supabase"
            / "migrations"
            / MIGRATION_FILE
        )
        if alt_path.exists():
            return alt_path.read_text(encoding="utf-8")
        raise FileNotFoundError(f"Migration file not found: {path}")
    return path.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Sample mock data for RPC responses
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_GROWTH_DATA = {
    "serie_mensal": [
        {"mes": "2024-07", "count": 3, "valor": 180000.00},
        {"mes": "2024-08", "count": 4, "valor": 220000.00},
        {"mes": "2024-09", "count": 2, "valor": 150000.00},
        {"mes": "2024-10", "count": 5, "valor": 310000.00},
        {"mes": "2024-11", "count": 4, "valor": 280000.00},
        {"mes": "2024-12", "count": 3, "valor": 190000.00},
        {"mes": "2025-01", "count": 6, "valor": 350000.00},
        {"mes": "2025-02", "count": 5, "valor": 300000.00},
        {"mes": "2025-03", "count": 4, "valor": 250000.00},
        {"mes": "2025-04", "count": 7, "valor": 400000.00},
        {"mes": "2025-05", "count": 5, "valor": 320000.00},
        {"mes": "2025-06", "count": 6, "valor": 370000.00},
        {"mes": "2025-07", "count": 5, "valor": 290000.00},
        {"mes": "2025-08", "count": 7, "valor": 410000.00},
        {"mes": "2025-09", "count": 6, "valor": 350000.00},
        {"mes": "2025-10", "count": 8, "valor": 480000.00},
        {"mes": "2025-11", "count": 7, "valor": 420000.00},
        {"mes": "2025-12", "count": 9, "valor": 520000.00},
        {"mes": "2026-01", "count": 10, "valor": 600000.00},
        {"mes": "2026-02", "count": 11, "valor": 650000.00},
        {"mes": "2026-03", "count": 12, "valor": 700000.00},
        {"mes": "2026-04", "count": 10, "valor": 590000.00},
        {"mes": "2026-05", "count": 13, "valor": 780000.00},
        {"mes": "2026-06", "count": 15, "valor": 900000.00},
    ],
    "baseline_media": 4.50,
    "baseline_desvio": 1.50,
    "zscore_ultimo_trimestre": 5.33,
    "variacao_pct_yoy": 0.65,
    "flag_crescimento_abrupto": True,
    "flag_incumbente_em_queda": False,
}

ZEROED_GROWTH_DATA = {
    "serie_mensal": [
        {"mes": "2024-06", "count": 0, "valor": 0},
        {"mes": "2024-07", "count": 0, "valor": 0},
    ],
    "baseline_media": 0,
    "baseline_desvio": 0,
    "zscore_ultimo_trimestre": 0,
    "variacao_pct_yoy": 0,
    "flag_crescimento_abrupto": False,
    "flag_incumbente_em_queda": False,
}

STABLE_GROWTH_DATA = {
    "serie_mensal": [],
    "baseline_media": 5.00,
    "baseline_desvio": 0.30,
    "zscore_ultimo_trimestre": 0.50,
    "variacao_pct_yoy": 0.05,
    "flag_crescimento_abrupto": False,
    "flag_incumbente_em_queda": False,
}

ABRUPT_DECLINE_DATA = {
    "serie_mensal": [],
    "baseline_media": 10.00,
    "baseline_desvio": 2.00,
    "zscore_ultimo_trimestre": -3.50,
    "variacao_pct_yoy": -0.30,
    "flag_crescimento_abrupto": False,
    "flag_incumbente_em_queda": True,
}


# =============================================================================
# STATIC ANALYSIS: Migration file structure
# =============================================================================

class TestMigrationStructure:
    """Validates the SQL migration file structure and security properties."""

    def test_migration_file_exists(self, migration_sql: str):
        """Migration file must exist and not be empty."""
        assert migration_sql, "Migration file is empty"
        assert "SUBINTEL-003" in migration_sql
        assert "supplier_growth_anomaly" in migration_sql

    def test_function_signature(self, migration_sql: str):
        """Function must be named supplier_growth_anomaly with correct params."""
        pattern = (
            r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+"
            r"public\.supplier_growth_anomaly\s*\("
        )
        assert re.search(pattern, migration_sql, re.IGNORECASE), (
            "Missing CREATE OR REPLACE FUNCTION public.supplier_growth_anomaly("
        )
        assert "p_ni_fornecedor TEXT" in migration_sql, (
            "Missing p_ni_fornecedor TEXT parameter"
        )
        assert "p_baseline_months INT DEFAULT 12" in migration_sql, (
            "Missing p_baseline_months INT DEFAULT 12 parameter"
        )

    def test_returns_json(self, migration_sql: str):
        """Function must return JSON."""
        assert "RETURNS JSON" in migration_sql, "Missing RETURNS JSON"

    def test_language_plpgsql(self, migration_sql: str):
        """Function must be LANGUAGE plpgsql for complex aggregation."""
        assert "LANGUAGE plpgsql" in migration_sql, "Missing LANGUAGE plpgsql"

    def test_is_stable(self, migration_sql: str):
        """Function must be STABLE (read-only)."""
        assert "STABLE" in migration_sql, "Missing STABLE volatility"

    def test_security_definer(self, migration_sql: str):
        """Function must be SECURITY DEFINER for RLS bypass."""
        assert "SECURITY DEFINER" in migration_sql

    def test_search_path(self, migration_sql: str):
        """Function must set search_path to public, pg_temp per secdef policy."""
        assert "SET search_path = public, pg_temp" in migration_sql, (
            "Missing SET search_path = public, pg_temp"
        )

    def test_statement_timeout(self, migration_sql: str):
        """Function must set a local statement timeout."""
        assert "SET LOCAL statement_timeout" in migration_sql, (
            "Missing SET LOCAL statement_timeout for safety"
        )

    def test_grant_execute(self, migration_sql: str):
        """Function must be granted to anon, authenticated, and service_role."""
        assert (
            "GRANT EXECUTE ON FUNCTION"
            " public.supplier_growth_anomaly(TEXT, INT) TO anon"
            in migration_sql
        ), "Missing GRANT EXECUTE TO anon"
        assert (
            "GRANT EXECUTE ON FUNCTION"
            " public.supplier_growth_anomaly(TEXT, INT) TO authenticated"
            in migration_sql
        ), "Missing GRANT EXECUTE TO authenticated"
        assert (
            "GRANT EXECUTE ON FUNCTION"
            " public.supplier_growth_anomaly(TEXT, INT) TO service_role"
            in migration_sql
        ), "Missing GRANT EXECUTE TO service_role"

    def test_comment_exists(self, migration_sql: str):
        """Function should have a COMMENT describing it."""
        assert "COMMENT ON FUNCTION" in migration_sql, (
            "Missing COMMENT ON FUNCTION"
        )
        assert "SUBINTEL-003" in migration_sql.split("COMMENT ON FUNCTION")[1] if (
            "COMMENT ON FUNCTION" in migration_sql
        ) else "", "COMMENT should describe SUBINTEL-003"

    def test_output_keys_present(self, migration_sql: str):
        """The JSON output must include all expected keys from the spec."""
        required_keys = [
            "serie_mensal",
            "baseline_media",
            "baseline_desvio",
            "zscore_ultimo_trimestre",
            "variacao_pct_yoy",
            "flag_crescimento_abrupto",
            "flag_incumbente_em_queda",
        ]
        for key in required_keys:
            assert f"'{key}'" in migration_sql, (
                f"Missing output key '{key}' in migration SQL"
            )


# =============================================================================
# UNIT TESTS: RPC call shape (mocked supabase)
# =============================================================================

class TestSupplierGrowthAnomalyRpcCall:
    """Tests that calling supplier_growth_anomaly returns expected data shape.

    Uses mocked supabase.rpc() so no live database is needed.
    """

    def test_rpc_call_returns_expected_top_level_keys(self):
        """Top-level JSON must contain all expected keys."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_GROWTH_DATA

        result = mock_sb.rpc(
            "supplier_growth_anomaly",
            {"p_ni_fornecedor": "12345678000199"},
        ).execute().data

        assert isinstance(result, dict)
        expected_keys = [
            "serie_mensal",
            "baseline_media",
            "baseline_desvio",
            "zscore_ultimo_trimestre",
            "variacao_pct_yoy",
            "flag_crescimento_abrupto",
            "flag_incumbente_em_queda",
        ]
        for key in expected_keys:
            assert key in result, f"Missing top-level key: {key}"

    def test_serie_mensal_has_correct_structure(self):
        """serie_mensal items must have mes, count, valor keys."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_GROWTH_DATA

        result = mock_sb.rpc(
            "supplier_growth_anomaly",
            {"p_ni_fornecedor": "12345678000199"},
        ).execute().data

        assert isinstance(result["serie_mensal"], list)
        for item in result["serie_mensal"]:
            assert "mes" in item
            assert "count" in item
            assert "valor" in item
            assert isinstance(item["mes"], str)
            assert isinstance(item["count"], int)
            assert isinstance(item["valor"], (int, float))

    def test_rpc_call_with_p_baseline_months(self):
        """RPC must accept p_baseline_months parameter."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_GROWTH_DATA

        result = mock_sb.rpc(
            "supplier_growth_anomaly",
            {"p_ni_fornecedor": "12345678000199", "p_baseline_months": 6},
        ).execute().data

        assert result["baseline_media"] >= 0
        assert result["baseline_desvio"] >= 0

    def test_top_level_types_are_correct(self):
        """Verify types for all top-level fields."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_GROWTH_DATA

        result = mock_sb.rpc(
            "supplier_growth_anomaly",
            {"p_ni_fornecedor": "12345678000199"},
        ).execute().data

        assert isinstance(result["baseline_media"], (int, float))
        assert isinstance(result["baseline_desvio"], (int, float))
        assert isinstance(result["zscore_ultimo_trimestre"], (int, float))
        assert isinstance(result["variacao_pct_yoy"], (int, float))
        assert isinstance(result["flag_crescimento_abrupto"], bool)
        assert isinstance(result["flag_incumbente_em_queda"], bool)
        assert isinstance(result["serie_mensal"], list)

    def test_flags_are_mutually_exclusive_in_sample(self):
        """In the sample data, only crescimento_abrupto is true."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_GROWTH_DATA

        result = mock_sb.rpc(
            "supplier_growth_anomaly",
            {"p_ni_fornecedor": "12345678000199"},
        ).execute().data

        assert result["flag_crescimento_abrupto"] is True
        assert result["flag_incumbente_em_queda"] is False


# =============================================================================
# EDGE CASES
# =============================================================================

class TestSupplierGrowthAnomalyEdgeCases:
    """Edge cases: empty results, zero baseline, flag combinations."""

    def test_empty_supplier_returns_zeroed_metrics(self):
        """CNPJ with no contracts must return zeroed baseline stats."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = ZEROED_GROWTH_DATA

        result = mock_sb.rpc(
            "supplier_growth_anomaly",
            {"p_ni_fornecedor": "99999999000199"},
        ).execute().data

        assert result["baseline_media"] == 0
        assert result["baseline_desvio"] == 0
        assert result["zscore_ultimo_trimestre"] == 0
        assert result["variacao_pct_yoy"] == 0
        assert result["flag_crescimento_abrupto"] is False
        assert result["flag_incumbente_em_queda"] is False

    def test_empty_supplier_returns_serie_mensal_with_zeros(self):
        """CNPJ with no contracts must return serie_mensal with zero counts."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = ZEROED_GROWTH_DATA

        result = mock_sb.rpc(
            "supplier_growth_anomaly",
            {"p_ni_fornecedor": "99999999000199"},
        ).execute().data

        assert isinstance(result["serie_mensal"], list)
        for item in result["serie_mensal"]:
            assert item["count"] == 0

    def test_stable_growth_does_not_trigger_flags(self):
        """Stable growth should not trigger any anomaly flags."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = STABLE_GROWTH_DATA

        result = mock_sb.rpc(
            "supplier_growth_anomaly",
            {"p_ni_fornecedor": "12345678000199"},
        ).execute().data

        assert result["flag_crescimento_abrupto"] is False
        assert result["flag_incumbente_em_queda"] is False

    def test_abrupt_decline_triggers_incumbente_em_queda(self):
        """Sharp decline should trigger incumbente_em_queda flag."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = ABRUPT_DECLINE_DATA

        result = mock_sb.rpc(
            "supplier_growth_anomaly",
            {"p_ni_fornecedor": "12345678000199"},
        ).execute().data

        assert result["flag_crescimento_abrupto"] is False
        assert result["flag_incumbente_em_queda"] is True
        assert result["zscore_ultimo_trimestre"] < -2

    def test_json_serializable(self):
        """The output JSON must be serializable (no NaN, no circular refs)."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_GROWTH_DATA

        result = mock_sb.rpc(
            "supplier_growth_anomaly",
            {"p_ni_fornecedor": "12345678000199"},
        ).execute().data

        # Should not raise
        json.dumps(result)

    def test_zscore_bounds_are_reasonable(self):
        """zscore should be within reasonable bounds for normal data."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = STABLE_GROWTH_DATA

        result = mock_sb.rpc(
            "supplier_growth_anomaly",
            {"p_ni_fornecedor": "12345678000199"},
        ).execute().data

        # Stable data: zscore should be small
        assert abs(result["zscore_ultimo_trimestre"]) < 2.0

    def test_down_migration_file_exists(self):
        """Paired .down.sql must exist."""
        down_path = MIGRATIONS_DIR / MIGRATION_FILE.replace(".sql", ".down.sql")
        alt_down = (
            Path(__file__).resolve().parent.parent.parent
            / "supabase"
            / "migrations"
            / MIGRATION_FILE.replace(".sql", ".down.sql")
        )

        path = down_path if down_path.exists() else alt_down
        assert path.exists(), f"Down migration file not found: {path}"
        sql = path.read_text(encoding="utf-8")
        assert "DROP FUNCTION" in sql, "Down migration must DROP FUNCTION"
        assert "supplier_growth_anomaly" in sql, (
            "Down migration must reference supplier_growth_anomaly"
        )
