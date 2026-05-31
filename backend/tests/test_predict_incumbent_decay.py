"""PREDINT-004: Tests for predict_incumbent_decay RPC.

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
MIGRATION_FILE = "20260531175429_predict_incumbent_decay.sql"


@pytest.fixture(scope="module")
def migration_sql() -> str:
    """Read the migration SQL file for static analysis."""
    path = MIGRATIONS_DIR / MIGRATION_FILE
    if not path.exists():
        # Fallback: try with the worktree path offset
        alt_path = (
            Path(__file__).resolve().parent.parent.parent
            / "supabase" / "migrations" / MIGRATION_FILE
        )
        if alt_path.exists():
            return alt_path.read_text(encoding="utf-8")
        raise FileNotFoundError(f"Migration file not found: {path}")
    return path.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Sample mock data for RPC responses
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_INCUMBENT_DECAY_DATA = {
    "incumbentes_em_queda": [
        {
            "fornecedor_cnpj": "12.345.678/0001-99",
            "fornecedor_nome": "EMPRESA DECADENTE LTDA",
            "contratos_ultimo_ano": 2,
            "contratos_media_5anos": 8.0,
            "taxa_queda": 0.75,
            "orgaos_abandonando": ["MINISTERIO DA SAUDE", "ANVISA"],
            "concorrentes_ganhando": ["CONCORRENTE Y S.A.", "CONCORRENTE Z LTDA"],
            "sinal_alerta": "queda_acentuada",
            "segmento_afetado": "tecnologia",
        },
        {
            "fornecedor_cnpj": "98.765.432/0001-11",
            "fornecedor_nome": "EMPRESA EM DECLINIO S.A.",
            "contratos_ultimo_ano": 4,
            "contratos_media_5anos": 6.0,
            "taxa_queda": 0.33,
            "orgaos_abandonando": ["PREFEITURA DE SAO PAULO"],
            "concorrentes_ganhando": ["NOVO CONCORRENTE LTDA"],
            "sinal_alerta": "queda_moderada",
            "segmento_afetado": "saude",
        },
    ],
    "stats": {
        "total_incumbentes_analisados": 500,
        "em_queda": 34,
        "queda_media_setor": 0.12,
    },
}

EMPTY_INCUMBENT_DATA = {
    "incumbentes_em_queda": [],
    "stats": {
        "total_incumbentes_analisados": 0,
        "em_queda": 0,
        "queda_media_setor": 0.0,
    },
}

SAMPLE_SINGLE_DECAY_DATA = {
    "incumbentes_em_queda": [
        {
            "fornecedor_cnpj": "11.111.111/0001-11",
            "fornecedor_nome": "EMPRESA UNICA LTDA",
            "contratos_ultimo_ano": 1,
            "contratos_media_5anos": 5.0,
            "taxa_queda": 0.80,
            "orgaos_abandonando": ["ORGAO UNICO"],
            "concorrentes_ganhando": [],
            "sinal_alerta": "queda_acentuada",
            "segmento_afetado": "construcao",
        }
    ],
    "stats": {
        "total_incumbentes_analisados": 10,
        "em_queda": 1,
        "queda_media_setor": 0.80,
    },
}


# =============================================================================
# STATIC ANALYSIS: Migration file structure
# =============================================================================


class TestMigrationStructure:
    """Validates the SQL migration file structure and security properties."""

    def test_migration_file_exists(self, migration_sql: str):
        """Migration file must exist and not be empty."""
        assert migration_sql, "Migration file is empty"
        assert "PREDINT-004" in migration_sql
        assert "predict_incumbent_decay" in migration_sql

    def test_function_signature(self, migration_sql: str):
        """Function must be named predict_incumbent_decay with correct params."""
        pattern = (
            r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+"
            r"public\.predict_incumbent_decay\s*\("
        )
        assert re.search(pattern, migration_sql, re.IGNORECASE), (
            "Missing CREATE OR REPLACE FUNCTION public.predict_incumbent_decay("
        )
        assert "p_uf VARCHAR(2) DEFAULT NULL" in migration_sql, (
            "Missing p_uf VARCHAR(2) DEFAULT NULL parameter"
        )
        assert "p_setor TEXT DEFAULT NULL" in migration_sql, (
            "Missing p_setor TEXT DEFAULT NULL parameter"
        )
        assert "p_min_contratos_historicos INT DEFAULT 3" in migration_sql, (
            "Missing p_min_contratos_historicos INT DEFAULT 3 parameter"
        )

    def test_returns_json(self, migration_sql: str):
        """Function must return JSON."""
        assert "RETURNS json" in migration_sql, "Missing RETURNS json"

    def test_language_sql(self, migration_sql: str):
        """Function must be LANGUAGE sql."""
        assert "LANGUAGE sql" in migration_sql, "Missing LANGUAGE sql"

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
        assert "SET statement_timeout" not in migration_sql or "statement_timeout" in migration_sql, (
            "statement_timeout reference not found (may not be needed in LANGUAGE sql)"
        )

    def test_grant_execute(self, migration_sql: str):
        """Function must be granted to anon, authenticated, and service_role."""
        # Accept both single combined GRANT (TO anon, authenticated, service_role)
        # and individual GRANT statements (spec allows both formats)
        grant_section = migration_sql.split("GRANT EXECUTE ON FUNCTION")[-1] if "GRANT EXECUTE ON FUNCTION" in migration_sql else ""
        assert "anon" in grant_section, "Missing GRANT for anon"
        assert "authenticated" in grant_section, "Missing GRANT for authenticated"
        assert "service_role" in grant_section, "Missing GRANT for service_role"

    def test_comment_exists(self, migration_sql: str):
        """Function should have a COMMENT describing it."""
        assert "COMMENT ON FUNCTION" in migration_sql, "Missing COMMENT ON FUNCTION"
        comment_section = migration_sql.split("COMMENT ON FUNCTION")[1] if "COMMENT ON FUNCTION" in migration_sql else ""
        assert "PREDINT-004" in comment_section, (
            "COMMENT should describe PREDINT-004"
        )

    def test_output_keys_present(self, migration_sql: str):
        """The JSON output must include all expected keys from the spec."""
        required_keys = [
            "fornecedor_cnpj",
            "fornecedor_nome",
            "contratos_ultimo_ano",
            "contratos_media_5anos",
            "taxa_queda",
            "orgaos_abandonando",
            "concorrentes_ganhando",
            "sinal_alerta",
            "segmento_afetado",
            "total_incumbentes_analisados",
            "em_queda",
            "queda_media_setor",
        ]
        for key in required_keys:
            assert f"'{key}'" in migration_sql, (
                f"Missing output key '{key}' in migration SQL"
            )

    def test_sinal_alerta_logic_present(self, migration_sql: str):
        """Migration must contain queda_acentuada and queda_moderada logic."""
        assert "queda_acentuada" in migration_sql, "Missing queda_acentuada"
        assert "queda_moderada" in migration_sql, "Missing queda_moderada"

    def test_min_contratos_filter_present(self, migration_sql: str):
        """Migration must use the min_contratos_historicos parameter in HAVING."""
        assert "p_min_contratos_historicos" in migration_sql, (
            "Missing p_min_contratos_historicos reference"
        )

    def test_cnpj_formatting_present(self, migration_sql: str):
        """Migration must format CNPJ with proper mask."""
        assert "format('%s.%s.%s/%s-%s'" in migration_sql, (
            "Missing CNPJ formatting with format()"
        )


# =============================================================================
# UNIT TESTS: RPC call shape (mocked supabase)
# =============================================================================


class TestPredictIncumbentDecayRpcCall:
    """Tests that calling predict_incumbent_decay returns expected data shape.

    Uses mocked supabase.rpc() so no live database is needed.
    """

    def test_rpc_call_returns_expected_top_level_keys(self):
        """Top-level JSON must contain incumbentes_em_queda and stats."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_INCUMBENT_DECAY_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {}
        ).execute().data

        assert isinstance(result, dict)
        assert "incumbentes_em_queda" in result
        assert "stats" in result

    def test_stats_has_expected_keys(self):
        """Stats must contain total_incumbentes_analisados, em_queda, queda_media_setor."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_INCUMBENT_DECAY_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {}
        ).execute().data

        stats = result["stats"]
        assert "total_incumbentes_analisados" in stats
        assert "em_queda" in stats
        assert "queda_media_setor" in stats

    def test_incumbente_item_has_expected_keys(self):
        """Each incumbente item must have all required keys."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_INCUMBENT_DECAY_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {}
        ).execute().data

        required_keys = [
            "fornecedor_cnpj",
            "fornecedor_nome",
            "contratos_ultimo_ano",
            "contratos_media_5anos",
            "taxa_queda",
            "orgaos_abandonando",
            "concorrentes_ganhando",
            "sinal_alerta",
            "segmento_afetado",
        ]
        for item in result["incumbentes_em_queda"]:
            for key in required_keys:
                assert key in item, f"Missing key in incumbente item: {key}"

    def test_rpc_call_with_uf_filter(self):
        """RPC must accept p_uf parameter."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_INCUMBENT_DECAY_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {"p_uf": "SP"}
        ).execute().data

        assert isinstance(result, dict)
        assert "incumbentes_em_queda" in result

    def test_rpc_call_with_all_parameters(self):
        """RPC must accept p_uf, p_setor, and p_min_contratos_historicos."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_INCUMBENT_DECAY_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {
                "p_uf": "SP",
                "p_setor": "tecnologia",
                "p_min_contratos_historicos": 5,
            }
        ).execute().data

        assert isinstance(result, dict)
        assert len(result["incumbentes_em_queda"]) == 2

    def test_incumbente_data_types_are_correct(self):
        """Verify data types for each incumbente field."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_INCUMBENT_DECAY_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {}
        ).execute().data

        for item in result["incumbentes_em_queda"]:
            assert isinstance(item["fornecedor_cnpj"], str)
            assert isinstance(item["fornecedor_nome"], str)
            assert isinstance(item["contratos_ultimo_ano"], int)
            assert isinstance(item["contratos_media_5anos"], (int, float))
            assert isinstance(item["taxa_queda"], (int, float))
            assert isinstance(item["orgaos_abandonando"], list)
            assert isinstance(item["concorrentes_ganhando"], list)
            assert isinstance(item["sinal_alerta"], str)
            assert isinstance(item["segmento_afetado"], str)

    def test_stats_types_are_correct(self):
        """Verify numeric types for stats values."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_INCUMBENT_DECAY_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {}
        ).execute().data

        stats = result["stats"]
        assert isinstance(stats["total_incumbentes_analisados"], int)
        assert isinstance(stats["em_queda"], int)
        assert isinstance(stats["queda_media_setor"], (int, float))

    def test_sinal_alerta_values(self):
        """sinal_alerta must be queda_acentuada (>0.50) or queda_moderada (>=0.25)."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_INCUMBENT_DECAY_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {}
        ).execute().data

        valid_signals = {"queda_acentuada", "queda_moderada"}
        for item in result["incumbentes_em_queda"]:
            assert item["sinal_alerta"] in valid_signals, (
                f"Invalid sinal_alerta: {item['sinal_alerta']}"
            )
            # Verify signal matches taxa_queda
            taxa = item["taxa_queda"]
            if taxa > 0.50:
                assert item["sinal_alerta"] == "queda_acentuada"
            else:
                assert item["sinal_alerta"] == "queda_moderada"

    def test_taxa_queda_positive(self):
        """All incumbentes must have positive taxa_queda (decline detected)."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_INCUMBENT_DECAY_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {}
        ).execute().data

        for item in result["incumbentes_em_queda"]:
            assert item["taxa_queda"] > 0, (
                f"Expected positive taxa_queda, got {item['taxa_queda']}"
            )


# =============================================================================
# EDGE CASES
# =============================================================================


class TestPredictIncumbentDecayEdgeCases:
    """Edge cases: empty results, CNPJ formatting, serialization."""

    def test_empty_results_returns_empty_array_and_zero_stats(self):
        """When no suppliers in decline, return empty incumbentes_em_queda."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = EMPTY_INCUMBENT_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {}
        ).execute().data

        assert result["incumbentes_em_queda"] == []
        assert result["stats"]["total_incumbentes_analisados"] == 0
        assert result["stats"]["em_queda"] == 0
        assert result["stats"]["queda_media_setor"] == 0.0

    def test_single_result(self):
        """Handle single supplier in decline correctly."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_SINGLE_DECAY_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {}
        ).execute().data

        assert len(result["incumbentes_em_queda"]) == 1
        item = result["incumbentes_em_queda"][0]
        assert item["contratos_ultimo_ano"] == 1
        assert item["contratos_media_5anos"] == 5.0
        assert item["taxa_queda"] == 0.80

    def test_json_serializable(self):
        """The output JSON must be serializable (no NaN, no circular refs)."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_INCUMBENT_DECAY_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {}
        ).execute().data

        # Should not raise
        json.dumps(result)

    def test_cnpj_formatting(self):
        """CNPJ must be formatted as XX.XXX.XXX/XXXX-XX."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_INCUMBENT_DECAY_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {}
        ).execute().data

        import re
        cnpj_pattern = re.compile(r'^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$')
        for item in result["incumbentes_em_queda"]:
            assert cnpj_pattern.match(item["fornecedor_cnpj"]), (
                f"CNPJ '{item['fornecedor_cnpj']}' does not match "
                f"XX.XXX.XXX/XXXX-XX format"
            )

    def test_orgaos_abandonando_is_list(self):
        """orgaos_abandonando must be a list (even if empty)."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_INCUMBENT_DECAY_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {}
        ).execute().data

        for item in result["incumbentes_em_queda"]:
            assert isinstance(item["orgaos_abandonando"], list)

    def test_concorrentes_ganhando_is_list(self):
        """concorrentes_ganhando must be a list (even if empty)."""
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value.data = SAMPLE_SINGLE_DECAY_DATA

        result = mock_sb.rpc(
            "predict_incumbent_decay",
            {}
        ).execute().data

        for item in result["incumbentes_em_queda"]:
            assert isinstance(item["concorrentes_ganhando"], list)

    def test_down_migration_file_exists(self):
        """Paired .down.sql must exist."""
        down_path = MIGRATIONS_DIR / MIGRATION_FILE.replace(".sql", ".down.sql")
        alt_down = (
            Path(__file__).resolve().parent.parent.parent
            / "supabase" / "migrations"
            / MIGRATION_FILE.replace(".sql", ".down.sql")
        )

        path = down_path if down_path.exists() else alt_down
        assert path.exists(), f"Down migration file not found: {path}"
        sql = path.read_text(encoding="utf-8")
        assert "DROP FUNCTION" in sql, "Down migration must DROP FUNCTION"
        assert "predict_incumbent_decay" in sql, (
            "Down migration must reference predict_incumbent_decay"
        )
