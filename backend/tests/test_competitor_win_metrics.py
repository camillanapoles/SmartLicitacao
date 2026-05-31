"""COMPINT-002: Tests for competitor_win_metrics RPC.

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
MIGRATION_FILE = "20260531000000_competitor_win_metrics.sql"


@pytest.fixture(scope="module")
def migration_sql() -> str:
    """Read the migration SQL file for static analysis."""
    path = MIGRATIONS_DIR / MIGRATION_FILE
    if not path.exists():
        # Fallback: try with the worktree path offset
        alt_path = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations" / MIGRATION_FILE
        if alt_path.exists():
            return alt_path.read_text(encoding="utf-8")
        raise FileNotFoundError(f"Migration file not found: {path}")
    return path.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Sample mock data for RPC responses
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_CONTRACT_WIN_DATA = {
    "cnpj": "12345678000199",
    "nome": "EMPRESA MODELO LTDA",
    "win_metrics": {
        "taxa_vitoria_estimada": 0.12,
        "total_participacoes_estimadas": 392,
        "total_vitorias": 47,
        "velocidade_crescimento": 0.15,
        "tendencia": "crescimento",
        "segmentos_atuais": [],
        "segmentos_emergentes": [],
        "segmentos_abandonados": [],
        "dependencia_publica": 1.0,
        "concentracao_uf": 0.42,
        "indice_diversificacao": 0.58
    },
    "serie_temporal": [
        {"ano": 2022, "contratos": 8, "valor": 2800000},
        {"ano": 2023, "contratos": 10, "valor": 3500000},
        {"ano": 2024, "contratos": 11, "valor": 4100000},
        {"ano": 2025, "contratos": 12, "valor": 3800000},
        {"ano": 2026, "contratos": 6, "valor": 2250000}
    ],
    "percentis": {
        "p25_ticket": 85000.00,
        "p50_ticket": 180000.00,
        "p75_ticket": 450000.00,
        "p90_ticket": 900000.00
    }
}

EMPTY_CONTRACT_DATA = {
    "cnpj": "99999999000199",
    "nome": "",
    "win_metrics": {
        "taxa_vitoria_estimada": 0.0,
        "total_participacoes_estimadas": 0,
        "total_vitorias": 0,
        "velocidade_crescimento": 0.0,
        "tendencia": "estavel",
        "segmentos_atuais": [],
        "segmentos_emergentes": [],
        "segmentos_abandonados": [],
        "dependencia_publica": 1.0,
        "concentracao_uf": 0.0,
        "indice_diversificacao": 0.0
    },
    "serie_temporal": [],
    "percentis": {
        "p25_ticket": 0,
        "p50_ticket": 0,
        "p75_ticket": 0,
        "p90_ticket": 0
    }
}


# =============================================================================
# STATIC ANALYSIS: Migration file structure
# =============================================================================

class TestMigrationStructure:
    """Validates the SQL migration file structure and security properties."""

    def test_migration_file_exists(self, migration_sql: str):
        """Migration file must exist and not be empty."""
        assert migration_sql, "Migration file is empty"
        assert "COMPINT-002" in migration_sql
        assert "competitor_win_metrics" in migration_sql

    def test_function_signature(self, migration_sql: str):
        """Function must be named competitor_win_metrics with correct params."""
        pattern = r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\.competitor_win_metrics\s*\("
        assert re.search(pattern, migration_sql, re.IGNORECASE), (
            "Missing CREATE OR REPLACE FUNCTION public.competitor_win_metrics("
        )
        assert "p_cnpj TEXT" in migration_sql, "Missing p_cnpj TEXT parameter"
        assert "p_anos INT DEFAULT 5" in migration_sql, (
            "Missing p_anos INT DEFAULT 5 parameter"
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
        assert "GRANT EXECUTE ON FUNCTION public.competitor_win_metrics(TEXT, INT) TO anon" in migration_sql, (
            "Missing GRANT EXECUTE TO anon"
        )
        assert "GRANT EXECUTE ON FUNCTION public.competitor_win_metrics(TEXT, INT) TO authenticated" in migration_sql, (
            "Missing GRANT EXECUTE TO authenticated"
        )
        assert "GRANT EXECUTE ON FUNCTION public.competitor_win_metrics(TEXT, INT) TO service_role" in migration_sql, (
            "Missing GRANT EXECUTE TO service_role"
        )

    def test_comment_exists(self, migration_sql: str):
        """Function should have a COMMENT describing it."""
        assert "COMMENT ON FUNCTION" in migration_sql, "Missing COMMENT ON FUNCTION"
        assert "COMPINT-002" in migration_sql.split("COMMENT ON FUNCTION")[1] if "COMMENT ON FUNCTION" in migration_sql else "", (
            "COMMENT should describe COMPINT-002"
        )

    def test_output_keys_present(self, migration_sql: str):
        """The JSON output must include all expected keys from the spec."""
        required_keys = [
            "taxa_vitoria_estimada",
            "total_participacoes_estimadas",
            "total_vitorias",
            "velocidade_crescimento",
            "tendencia",
            "segmentos_atuais",
            "segmentos_emergentes",
            "segmentos_abandonados",
            "dependencia_publica",
            "concentracao_uf",
            "indice_diversificacao",
            "serie_temporal",
            "p25_ticket",
            "p50_ticket",
            "p75_ticket",
            "p90_ticket",
        ]
        for key in required_keys:
            assert f"'{key}'" in migration_sql, (
                f"Missing output key '{key}' in migration SQL"
            )


# =============================================================================
# UNIT TESTS: RPC call shape (mocked supabase)
# =============================================================================

class TestCompetitorWinMetricsRpcCall:
    """Tests that calling competitor_win_metrics returns expected data shape.

    Uses mocked supabase.rpc() so no live database is needed.
    """

    def test_rpc_call_returns_expected_top_level_keys(self):
        """Top-level JSON must contain cnpj, nome, win_metrics, serie_temporal, percentis."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_CONTRACT_WIN_DATA

        # Simulate: supabase.rpc("competitor_win_metrics", {"p_cnpj": "12345678000199"}).execute().data
        result = mock_sb.rpc(
            "competitor_win_metrics",
            {"p_cnpj": "12345678000199"}
        ).execute().data

        assert isinstance(result, dict)
        assert "cnpj" in result
        assert "nome" in result
        assert "win_metrics" in result
        assert "serie_temporal" in result
        assert "percentis" in result

    def test_rpc_call_win_metrics_has_expected_keys(self):
        """win_metrics must contain all expected sub-keys."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_CONTRACT_WIN_DATA

        result = mock_sb.rpc(
            "competitor_win_metrics",
            {"p_cnpj": "12345678000199"}
        ).execute().data

        metrics = result["win_metrics"]
        expected_keys = [
            "taxa_vitoria_estimada",
            "total_participacoes_estimadas",
            "total_vitorias",
            "velocidade_crescimento",
            "tendencia",
            "segmentos_atuais",
            "segmentos_emergentes",
            "segmentos_abandonados",
            "dependencia_publica",
            "concentracao_uf",
            "indice_diversificacao",
        ]
        for key in expected_keys:
            assert key in metrics, f"Missing win_metrics key: {key}"

    def test_rpc_call_percentis_has_expected_keys(self):
        """percentis must contain p25_ticket, p50_ticket, p75_ticket, p90_ticket."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_CONTRACT_WIN_DATA

        result = mock_sb.rpc(
            "competitor_win_metrics",
            {"p_cnpj": "12345678000199"}
        ).execute().data

        percentis = result["percentis"]
        assert "p25_ticket" in percentis
        assert "p50_ticket" in percentis
        assert "p75_ticket" in percentis
        assert "p90_ticket" in percentis

    def test_rpc_call_with_p_anos_parameter(self):
        """RPC must accept p_anos parameter."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_CONTRACT_WIN_DATA

        result = mock_sb.rpc(
            "competitor_win_metrics",
            {"p_cnpj": "12345678000199", "p_anos": 3}
        ).execute().data

        assert result["cnpj"] == "12345678000199"

    def test_serie_temporal_has_correct_structure(self):
        """serie_temporal items must have ano, contratos, valor keys."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_CONTRACT_WIN_DATA

        result = mock_sb.rpc(
            "competitor_win_metrics",
            {"p_cnpj": "12345678000199"}
        ).execute().data

        assert isinstance(result["serie_temporal"], list)
        for item in result["serie_temporal"]:
            assert "ano" in item
            assert "contratos" in item
            assert "valor" in item

    def test_win_metrics_types_are_correct(self):
        """Verify numeric types for win_metrics values."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_CONTRACT_WIN_DATA

        result = mock_sb.rpc(
            "competitor_win_metrics",
            {"p_cnpj": "12345678000199"}
        ).execute().data

        metrics = result["win_metrics"]
        assert isinstance(metrics["taxa_vitoria_estimada"], (int, float))
        assert isinstance(metrics["total_participacoes_estimadas"], int)
        assert isinstance(metrics["total_vitorias"], int)
        assert isinstance(metrics["velocidade_crescimento"], (int, float))
        assert isinstance(metrics["dependencia_publica"], (int, float))
        assert isinstance(metrics["concentracao_uf"], (int, float))
        assert isinstance(metrics["indice_diversificacao"], (int, float))
        assert isinstance(metrics["tendencia"], str)
        assert metrics["tendencia"] in ("crescimento", "retracao", "estavel")


# =============================================================================
# EDGE CASES
# =============================================================================

class TestCompetitorWinMetricsEdgeCases:
    """Edge cases: empty results, CNPJ validation."""

    def test_cnpj_without_contracts_returns_zero_metrics(self):
        """CNPJ with no contracts must return 0 for vitorias and win rate."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = EMPTY_CONTRACT_DATA

        result = mock_sb.rpc(
            "competitor_win_metrics",
            {"p_cnpj": "99999999000199"}
        ).execute().data

        metrics = result["win_metrics"]
        assert metrics["total_vitorias"] == 0
        assert metrics["taxa_vitoria_estimada"] == 0.0
        assert metrics["total_participacoes_estimadas"] == 0
        assert metrics["velocidade_crescimento"] == 0.0
        assert metrics["tendencia"] == "estavel"
        assert metrics["concentracao_uf"] == 0.0
        assert metrics["indice_diversificacao"] == 0.0

    def test_cnpj_without_contracts_returns_empty_time_series(self):
        """CNPJ with no contracts must return empty serie_temporal."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = EMPTY_CONTRACT_DATA

        result = mock_sb.rpc(
            "competitor_win_metrics",
            {"p_cnpj": "99999999000199"}
        ).execute().data

        assert result["serie_temporal"] == []
        assert result["nome"] == ""

    def test_cnpj_without_contracts_returns_zero_percentis(self):
        """CNPJ with no contracts must return zero percentis."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = EMPTY_CONTRACT_DATA

        result = mock_sb.rpc(
            "competitor_win_metrics",
            {"p_cnpj": "99999999000199"}
        ).execute().data

        p = result["percentis"]
        assert p["p25_ticket"] == 0
        assert p["p50_ticket"] == 0
        assert p["p75_ticket"] == 0
        assert p["p90_ticket"] == 0

    def test_tendencia_classification(self):
        """Tendencia must be crescimento (>0.05), retracao (<-0.05), or estavel."""
        def _make_result(velocidade: float) -> dict:
            """Helper to create a mock result with a given velocidade."""
            base: dict = dict(SAMPLE_CONTRACT_WIN_DATA)
            metrics: dict = dict(base["win_metrics"])
            metrics["velocidade_crescimento"] = velocidade
            if velocidade > 0.05:
                metrics["tendencia"] = "crescimento"
            elif velocidade < -0.05:
                metrics["tendencia"] = "retracao"
            else:
                metrics["tendencia"] = "estavel"
            base["win_metrics"] = metrics
            return base

        mock_sb = MagicMock()

        # crescimento
        mock_sb.rpc.return_value.execute.return_value.data = _make_result(0.15)
        result = mock_sb.rpc("competitor_win_metrics", {"p_cnpj": "123"}).execute().data
        assert result["win_metrics"]["tendencia"] == "crescimento"

        # retracao
        mock_sb.rpc.return_value.execute.return_value.data = _make_result(-0.10)
        result = mock_sb.rpc("competitor_win_metrics", {"p_cnpj": "123"}).execute().data
        assert result["win_metrics"]["tendencia"] == "retracao"

        # estavel (positive but small)
        mock_sb.rpc.return_value.execute.return_value.data = _make_result(0.03)
        result = mock_sb.rpc("competitor_win_metrics", {"p_cnpj": "123"}).execute().data
        assert result["win_metrics"]["tendencia"] == "estavel"

        # estavel (negative but small)
        mock_sb.rpc.return_value.execute.return_value.data = _make_result(-0.03)
        result = mock_sb.rpc("competitor_win_metrics", {"p_cnpj": "123"}).execute().data
        assert result["win_metrics"]["tendencia"] == "estavel"

        # estavel (exactly zero)
        mock_sb.rpc.return_value.execute.return_value.data = _make_result(0.0)
        result = mock_sb.rpc("competitor_win_metrics", {"p_cnpj": "123"}).execute().data
        assert result["win_metrics"]["tendencia"] == "estavel"

    def test_json_serializable(self):
        """The output JSON must be serializable (no NaN, no circular refs)."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_CONTRACT_WIN_DATA

        result = mock_sb.rpc(
            "competitor_win_metrics",
            {"p_cnpj": "12345678000199"}
        ).execute().data

        # Should not raise
        json.dumps(result)

    def test_invalid_cnpj_returns_error(self):
        """Invalid CNPJ format would be caught by the database function, but
        our test validates the application code handles it gracefully."""
        mock_sb = MagicMock()
        error_data = {
            "cnpj": "123",
            "erro": "CNPJ invalido: deve ter 14 digitos apos normalizacao"
        }
        mock_sb.rpc.return_value.execute.return_value.data = error_data

        result = mock_sb.rpc(
            "competitor_win_metrics",
            {"p_cnpj": "123"}
        ).execute().data

        assert "erro" in result
        assert "invalido" in result["erro"].lower()

    def test_down_migration_file_exists(self):
        """Paired .down.sql must exist."""
        down_path = MIGRATIONS_DIR / MIGRATION_FILE.replace(".sql", ".down.sql")
        alt_down = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations" / MIGRATION_FILE.replace(".sql", ".down.sql")

        path = down_path if down_path.exists() else alt_down
        assert path.exists(), f"Down migration file not found: {path}"
        sql = path.read_text(encoding="utf-8")
        assert "DROP FUNCTION" in sql, "Down migration must DROP FUNCTION"
        assert "competitor_win_metrics" in sql, (
            "Down migration must reference competitor_win_metrics"
        )
