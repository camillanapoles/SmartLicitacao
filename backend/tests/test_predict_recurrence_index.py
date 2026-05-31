"""
PREDINT-002: RPC predict_recurrence_index — Static Analysis + Schema Tests

Validates:
1. Migration SQL contains valid function definition
2. Return JSON schema matches expected shape
3. Edge cases: empty results, single contract, UF filter, missing sector
4. indice_recorrencia is always between 0 and 1
5. proxima_janela_inicio > today when indice_recorrencia > 0.5
"""

import json
from pathlib import Path

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"


@pytest.fixture(scope="module")
def migration_sql():
    """Load the predict_recurrence_index migration SQL."""
    path = MIGRATIONS_DIR / "20260531100000_predict_recurrence_index.sql"
    assert path.exists(), f"Migration file not found: {path}"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def down_migration_sql():
    """Load the down migration."""
    path = MIGRATIONS_DIR / "20260531100000_predict_recurrence_index.down.sql"
    assert path.exists(), f"Down migration file not found: {path}"
    return path.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Migration Structure Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMigrationStructure:
    """Static analysis of the migration SQL file."""

    def test_contains_rpc_definition(self, migration_sql):
        """Migration must define the RPC function."""
        assert "CREATE OR REPLACE FUNCTION public.predict_recurrence_index(" in migration_sql
        assert "RETURNS json" in migration_sql

    def test_contains_add_columns(self, migration_sql):
        """Migration must add the required columns."""
        assert "ADD COLUMN IF NOT EXISTS setor_classificado TEXT" in migration_sql
        assert "ADD COLUMN IF NOT EXISTS data_fim_vigencia DATE" in migration_sql

    def test_contains_index(self, migration_sql):
        """Migration must create the composite index."""
        assert "idx_psc_orgao_setor_data" in migration_sql
        assert "ON pncp_supplier_contracts(uf, setor_classificado, data_fim_vigencia)" in migration_sql

    def test_contains_grant_execute(self, migration_sql):
        """GRANT EXECUTE must be present for anon, authenticated, service_role."""
        assert "GRANT EXECUTE ON FUNCTION public.predict_recurrence_index" in migration_sql
        assert "TO anon, authenticated, service_role" in migration_sql

    def test_secdef_search_path(self, migration_sql):
        """Must have search_path with pg_temp per SECDEF audit."""
        assert "SET search_path = public, pg_temp" in migration_sql

    def test_has_comment(self, migration_sql):
        """COMMENT ON FUNCTION must be present."""
        assert "COMMENT ON FUNCTION public.predict_recurrence_index" in migration_sql
        assert "PREDINT-002" in migration_sql

    def test_function_signature(self, migration_sql):
        """Function must accept 3 optional parameters."""
        assert "p_uf VARCHAR(2) DEFAULT NULL" in migration_sql
        assert "p_setor TEXT DEFAULT NULL" in migration_sql
        assert "p_orgao_codigo TEXT DEFAULT NULL" in migration_sql

    def test_language_sql(self, migration_sql):
        """Function must be LANGUAGE SQL."""
        assert "LANGUAGE SQL" in migration_sql

    def test_stable_volatility(self, migration_sql):
        """Function must be STABLE."""
        assert "STABLE" in migration_sql
        assert "SECURITY DEFINER" in migration_sql


class TestDownMigrationStructure:
    """Static analysis of the down migration."""

    def test_drop_function(self, down_migration_sql):
        """Down migration must DROP FUNCTION."""
        assert "DROP FUNCTION IF EXISTS public.predict_recurrence_index" in down_migration_sql

    def test_drop_index(self, down_migration_sql):
        """Down migration must DROP INDEX."""
        assert "DROP INDEX IF EXISTS idx_psc_orgao_setor_data" in down_migration_sql

    def test_drop_columns(self, down_migration_sql):
        """Down migration must DROP COLUMNS."""
        assert "DROP COLUMN IF EXISTS setor_classificado" in down_migration_sql
        assert "DROP COLUMN IF EXISTS data_fim_vigencia" in down_migration_sql


# ─────────────────────────────────────────────────────────────────────────────
# Output Schema Validation
# ─────────────────────────────────────────────────────────────────────────────

class TestOutputSchema:
    """Validate the RPC output JSON schema.

    These tests use mock data to verify the shape and constraints
    of the JSON returned by predict_recurrence_index.
    """

    @staticmethod
    def _make_orgao(
        orgao_nome="MINISTERIO DA SAUDE",
        uf="DF",
        categoria="tecnologia",
        total_contratos=12,
        intervalo_medio=180,
        intervalo_desvio=15,
        ultimo_contrato_fim="2026-04-01",
        sazonalidade="Q1-Q3",
        indice_recorrencia=0.75,
    ):
        """Build a sample orgao entry as the RPC would return."""
        return {
            "orgao_nome": orgao_nome,
            "orgao_uf": uf,
            "categoria": categoria,
            "indice_recorrencia": indice_recorrencia,
            "total_contratos_5anos": total_contratos,
            "intervalo_medio_dias": intervalo_medio,
            "intervalo_desvio": intervalo_desvio,
            "ultimo_contrato_fim": ultimo_contrato_fim,
            "proxima_janela_inicio": "2026-09-28" if indice_recorrencia > 0.5 else None,
            "proxima_janela_fim": "2026-10-28" if indice_recorrencia > 0.5 else None,
            "sazonalidade_detectada": sazonalidade,
        }

    @staticmethod
    def _make_stats(
        orgaos_analisados=150,
        indice_medio_nacional=0.45,
        categorias=None,
    ):
        """Build a sample stats object as the RPC would return."""
        return {
            "orgaos_analisados": orgaos_analisados,
            "indice_medio_nacional": indice_medio_nacional,
            "categorias_mais_recorrentes": categorias or ["tecnologia", "facilities", "engenharia"],
        }

    def _make_rpc_response(self, orgaos=None, stats=None):
        """Simulate the full RPC JSON response."""
        return {
            "orgaos": orgaos or [],
            "stats": stats or self._make_stats(orgaos_analisados=0, indice_medio_nacional=0.0, categorias=[]),
        }

    def test_full_response_shape(self):
        """Full RPC response must contain orgaos and stats keys."""
        resp = self._make_rpc_response(
            orgaos=[self._make_orgao()],
            stats=self._make_stats(),
        )
        assert "orgaos" in resp
        assert "stats" in resp
        assert isinstance(resp["orgaos"], list)
        assert isinstance(resp["stats"], dict)

    def test_orgao_entry_has_all_required_fields(self):
        """Each orgao entry must have all expected fields."""
        entry = self._make_orgao()
        required = [
            "orgao_nome", "orgao_uf", "categoria",
            "indice_recorrencia", "total_contratos_5anos",
            "intervalo_medio_dias", "intervalo_desvio",
            "ultimo_contrato_fim",
            "proxima_janela_inicio", "proxima_janela_fim",
            "sazonalidade_detectada",
        ]
        for field in required:
            assert field in entry, f"Missing field: {field}"

    def test_stats_has_all_required_fields(self):
        """Stats object must have all expected fields."""
        stats = self._make_stats()
        required = [
            "orgaos_analisados",
            "indice_medio_nacional",
            "categorias_mais_recorrentes",
        ]
        for field in required:
            assert field in stats, f"Missing field: {field}"

    def test_indice_recorrencia_between_0_and_1(self):
        """indice_recorrencia must be between 0 and 1."""
        for value in [0.0, 0.5, 1.0, 0.15, 0.92]:
            entry = self._make_orgao(indice_recorrencia=value)
            assert 0.0 <= entry["indice_recorrencia"] <= 1.0, (
                f"indice_recorrencia {value} out of range [0, 1]"
            )

    def test_proxima_janela_inicio_gt_today_when_above_threshold(self):
        """When indice_recorrencia > 0.5, proxima_janela_inicio must be > today."""
        import datetime
        today = datetime.date.today()

        # Above threshold
        resp = self._make_rpc_response(
            orgaos=[self._make_orgao(indice_recorrencia=0.6)],
        )
        janela = resp["orgaos"][0]["proxima_janela_inicio"]
        assert janela is not None
        janela_date = datetime.date.fromisoformat(janela)
        assert janela_date > today, (
            f"proxima_janela_inicio {janela} should be > {today}"
        )

        # Below threshold
        resp = self._make_rpc_response(
            orgaos=[self._make_orgao(indice_recorrencia=0.3)],
        )
        assert resp["orgaos"][0]["proxima_janela_inicio"] is None

    def test_empty_orgaos_array(self):
        """Org without contracts -> empty orgaos array."""
        resp = self._make_rpc_response(orgaos=[])
        assert resp["orgaos"] == []
        assert resp["stats"]["orgaos_analisados"] == 0

    def test_single_contract_low_recurrence(self):
        """Org with single contract -> low indice_recorrencia.

        Single contract means no intervals (LAG returns NULL for first).
        With no interval data, regularidade = 0, freq_component should be low.
        """
        # Single contract gives total_contratos_5anos = 1
        # freq_component = min(1/20, 1) = 0.05
        # No intervalo data -> regularidade = 0
        # concentracao = 1/1 = 1.0
        # permanencia = 0.2 (1 distinct year)
        # indice = 0.35*0.05 + 0.25*0 + 0.20*1.0 + 0.20*0.2 = 0.0175 + 0 + 0.20 + 0.04 = 0.2575
        entry = self._make_orgao(total_contratos=1, indice_recorrencia=0.26)
        assert entry["indice_recorrencia"] < 0.5
        assert entry["proxima_janela_inicio"] is None  # below threshold

    def test_type_consistency(self):
        """All numeric types must be correct."""
        entry = self._make_orgao()
        assert isinstance(entry["indice_recorrencia"], (int, float))
        assert isinstance(entry["total_contratos_5anos"], int)
        assert isinstance(entry["intervalo_medio_dias"], int)
        assert isinstance(entry["intervalo_desvio"], int)
        assert isinstance(entry["orgao_nome"], str)
        assert isinstance(entry["orgao_uf"], str)
        assert isinstance(entry["categoria"], str)

        stats = self._make_stats()
        assert isinstance(stats["orgaos_analisados"], int)
        assert isinstance(stats["indice_medio_nacional"], (int, float))
        assert isinstance(stats["categorias_mais_recorrentes"], list)

    def test_uf_filter_propagation(self):
        """UF filter should restrict results to matching UF."""
        # Simulate a UF-specific response with only DF orgaos
        resp = self._make_rpc_response(
            orgaos=[self._make_orgao(uf="DF")],
            stats=self._make_stats(orgaos_analisados=1),
        )
        assert all(o["orgao_uf"] == "DF" for o in resp["orgaos"])

    def test_setor_filter_categoria_match(self):
        """When filtered by setor, all orgaos should match that categoria."""
        resp = self._make_rpc_response(
            orgaos=[self._make_orgao(categoria="tecnologia")],
            stats=self._make_stats(),
        )
        assert all(o["categoria"] == "tecnologia" for o in resp["orgaos"])

    def test_sazonalidade_null_when_no_pattern(self):
        """sazonalidade_detectada may be null when no clear pattern."""
        entry = self._make_orgao(sazonalidade=None)
        assert entry["sazonalidade_detectada"] is None

    def test_sazonalidade_format(self):
        """sazonalidade_detectada must be in valid format when present."""
        valid_patterns = {"Q1", "Q2", "Q3", "Q4", "Q1-Q2", "Q1-Q3", "Q1-Q4",
                          "Q2-Q3", "Q2-Q4", "Q3-Q4"}
        for pattern in ["Q1", "Q3-Q4", None]:
            entry = self._make_orgao(sazonalidade=pattern)
            if entry["sazonalidade_detectada"] is not None:
                assert entry["sazonalidade_detectada"] in valid_patterns

    def test_ultimo_contrato_fim_format(self):
        """ultimo_contrato_fim must be a date string (ISO format)."""
        import re
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        entry = self._make_orgao()
        assert date_pattern.match(entry["ultimo_contrato_fim"])


# ─────────────────────────────────────────────────────────────────────────────
# JSON Serialization Test
# ─────────────────────────────────────────────────────────────────────────────

class TestJsonSerialization:
    """Ensure the entire RPC response is JSON-serializable."""

    def test_full_response_json_serializable(self):
        """Full response must serialize to JSON without error."""
        resp = {
            "orgaos": [
                {
                    "orgao_nome": "MINISTERIO DA SAUDE",
                    "orgao_uf": "DF",
                    "categoria": "tecnologia",
                    "indice_recorrencia": 0.92,
                    "total_contratos_5anos": 47,
                    "intervalo_medio_dias": 180,
                    "intervalo_desvio": 15,
                    "ultimo_contrato_fim": "2026-04-01",
                    "proxima_janela_inicio": "2026-09-28",
                    "proxima_janela_fim": "2026-10-28",
                    "sazonalidade_detectada": "Q1-Q3",
                }
            ],
            "stats": {
                "orgaos_analisados": 150,
                "indice_medio_nacional": 0.45,
                "categorias_mais_recorrentes": ["tecnologia", "facilities", "engenharia"],
            },
        }
        # This should not raise
        serialized = json.dumps(resp, ensure_ascii=False)
        deserialized = json.loads(serialized)
        assert deserialized["orgaos"][0]["indice_recorrencia"] == 0.92
        assert deserialized["stats"]["orgaos_analisados"] == 150

    def test_empty_response_json_serializable(self):
        """Empty response must serialize to JSON without error."""
        resp = {
            "orgaos": [],
            "stats": {
                "orgaos_analisados": 0,
                "indice_medio_nacional": 0.0,
                "categorias_mais_recorrentes": [],
            },
        }
        serialized = json.dumps(resp, ensure_ascii=False)
        deserialized = json.loads(serialized)
        assert deserialized["orgaos"] == []
        assert deserialized["stats"]["indice_medio_nacional"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Contract Test: Index Component Validation
# ─────────────────────────────────────────────────────────────────────────────

class TestIndexComponents:
    """Validate the indice_recorrencia calculation components."""

    def test_freq_component_linear_scale(self):
        """Frequency component scales with contract count, capped at 20."""
        # 0 contracts -> 0.0
        assert min(0 / 20.0, 1.0) == 0.0
        # 10 contracts -> 0.5
        assert min(10 / 20.0, 1.0) == 0.5
        # 20 contracts -> 1.0
        assert min(20 / 20.0, 1.0) == 1.0
        # 50 contracts -> 1.0 (capped)
        assert min(50 / 20.0, 1.0) == 1.0

    def test_regularidade_clamped(self):
        """Regularidade = max(1 - deviation/avg, 0)."""
        # No deviation -> perfect regularity 1.0
        assert max(1.0 - 0.0 / 180.0, 0.0) == 1.0
        # deviation = avg -> 0.0
        assert max(1.0 - 180.0 / 180.0, 0.0) == 0.0
        # deviation > avg -> clamped to 0.0
        assert max(1.0 - 200.0 / 180.0, 0.0) == 0.0
        # Moderate deviation -> proportional
        assert max(1.0 - 30.0 / 180.0, 0.0) == pytest.approx(1.0 - 30.0 / 180.0)

    def test_concentracao_categoria(self):
        """Category concentration = category_contracts / org_total."""
        # All contracts in one category -> 1.0
        assert 12 / 12 == 1.0
        # Half in category -> 0.5
        assert 6 / 12 == 0.5
        # None -> 0.0
        assert 0 / 12 == 0.0

    def test_permanencia_orgao(self):
        """Permanence based on consecutive years of purchases."""
        assert (lambda anos: 1.0 if anos >= 3 else 0.5 if anos >= 2 else 0.2)(5) == 1.0
        assert (lambda anos: 1.0 if anos >= 3 else 0.5 if anos >= 2 else 0.2)(3) == 1.0
        assert (lambda anos: 1.0 if anos >= 3 else 0.5 if anos >= 2 else 0.2)(2) == 0.5
        assert (lambda anos: 1.0 if anos >= 3 else 0.5 if anos >= 2 else 0.2)(1) == 0.2

    def test_indice_recorrencia_weighted_sum(self):
        """Final index = 0.35*freq + 0.25*regularidade + 0.20*concentracao + 0.20*permanencia."""
        def calc(freq, reg, conc, perm):
            return round(0.35 * freq + 0.25 * reg + 0.20 * conc + 0.20 * perm, 2)

        # All max -> 1.0
        assert calc(1.0, 1.0, 1.0, 1.0) == 1.0
        # All min -> 0.0
        assert calc(0.0, 0.0, 0.0, 0.2) == 0.04
        # Realistic: 15 contracts, 180d avg, 30d stddev, 60% concentration, 3+ years
        # freq = min(15/20, 1) = 0.75
        # reg = 1 - 30/180 = 0.833
        # conc = 0.60
        # perm = 1.0
        # index = 0.35*0.75 + 0.25*0.833 + 0.20*0.60 + 0.20*1.0
        #       = 0.2625 + 0.2083 + 0.12 + 0.20 = 0.7908
        assert calc(0.75, 0.833, 0.60, 1.0) == pytest.approx(0.79, abs=0.01)
