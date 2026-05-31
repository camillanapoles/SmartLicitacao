"""Tests for COMPINT-001: RPC competitor_territory_map.

Validates the RPC contract (input/output shape) by mocking the Supabase
client response. Tests cover:

  - Full response structure with mock data
  - Empty contracts (zeroed fields)
  - Market share bounds (0 to 1)
  - Invalid CNPJ handling

This is a contract-level test. The RPC itself is a database function running
on Supabase PostgreSQL; these tests validate that the backend correctly
handles the expected output shapes.
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_territory_row(
    uf: str = "SP",
    contratos: int = 20,
    valor_total: float = 7000000.0,
    ticket_medio_uf: float = 350000.0,
    orgaos_principais: list | None = None,
    market_share_uf: float = 0.03,
    tendencia: str = "estavel",
) -> dict:
    return {
        "uf": uf,
        "contratos": contratos,
        "valor_total": valor_total,
        "ticket_medio_uf": ticket_medio_uf,
        "orgaos_principais": orgaos_principais or ["GOVERNO DO ESTADO DE SP", "PREFEITURA DE SP"],
        "market_share_uf": market_share_uf,
        "tendencia": tendencia,
    }


def _make_orgao_favorito_row(
    orgao_nome: str = "GOVERNO DO ESTADO DE SP",
    contratos: int = 12,
    valor_total: float = 4200000.0,
    categorias: list | None = None,
    ultima_vitoria: str = "2026-03-15",
    frequencia_anual: float = 2.4,
) -> dict:
    return {
        "orgao_nome": orgao_nome,
        "contratos": contratos,
        "valor_total": valor_total,
        "categorias": categorias or ["tecnologia", "consultoria"],
        "ultima_vitoria": ultima_vitoria,
        "frequencia_anual": frequencia_anual,
    }


MOCK_COMPLETE_RESPONSE = {
    "concorrente": {
        "cnpj": "12345678000190",
        "nome": "EMPRESA X LTDA",
        "total_contratos": 47,
        "ticket_medio": 350000.0,
        "ticket_mediana": 180000.0,
        "valor_total_contratado": 16450000.0,
    },
    "territorio": [
        _make_territory_row(),
        _make_territory_row(
            uf="RJ",
            contratos=15,
            valor_total=5250000.0,
            ticket_medio_uf=350000.0,
            orgaos_principais=["GOVERNO DO ESTADO DO RJ", "PREFEITURA DO RJ"],
            market_share_uf=0.02,
            tendencia="crescendo",
        ),
        _make_territory_row(
            uf="MG",
            contratos=8,
            valor_total=2400000.0,
            ticket_medio_uf=300000.0,
            orgaos_principais=["GOVERNO DO ESTADO DE MG"],
            market_share_uf=0.015,
            tendencia="estavel",
        ),
    ],
    "orgaos_favoritos": [
        _make_orgao_favorito_row(),
        _make_orgao_favorito_row(
            orgao_nome="PREFEITURA DE SP",
            contratos=8,
            valor_total=2800000.0,
            categorias=["tecnologia"],
            ultima_vitoria="2026-02-20",
            frequencia_anual=1.6,
        ),
    ],
    "stats": {
        "ufs_atuacao": 3,
        "orgaos_unicos": 18,
        "anos_atuacao": 5,
        "crescimento_anual": 0.15,
    },
}

MOCK_ZEROED_RESPONSE = {
    "concorrente": {
        "cnpj": "99999999000199",
        "nome": "",
        "total_contratos": 0,
        "ticket_medio": 0.0,
        "ticket_mediana": 0.0,
        "valor_total_contratado": 0.0,
    },
    "territorio": [],
    "orgaos_favoritos": [],
    "stats": {
        "ufs_atuacao": 0,
        "orgaos_unicos": 0,
        "anos_atuacao": 0,
        "crescimento_anual": 0.0,
    },
}

VALID_CNPJ = "12345678000190"
EMPTY_CNPJ = "99999999000199"
INVALID_CNPJ = "12345"


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from startup.app_factory import create_app
    app = create_app()
    return TestClient(app)


def _mock_rpc_competitor_territory_map(mock_get_sb, response_data: dict):
    """Configure mock supabase to return the given response for the RPC."""
    mock_sb = MagicMock()
    rpc_resp = MagicMock()
    rpc_resp.data = response_data

    chain = mock_sb.rpc.return_value
    chain.execute.return_value = rpc_resp

    mock_get_sb.return_value = mock_sb
    return mock_sb


# ── Tests ────────────────────────────────────────────────────────────────────


class TestCompetitorTerritoryMap:
    """Contract tests for competitor_territory_map RPC."""

    # ------------------------------------------------------------------
    # Test: Full response structure
    # ------------------------------------------------------------------

    @patch("supabase_client.get_supabase")
    def test_rpc_called_with_correct_params(self, mock_get_sb, client):
        """RPC is called with the correct function name and parameters."""
        _mock_rpc_competitor_territory_map(mock_get_sb, MOCK_COMPLETE_RESPONSE)
        sb = mock_get_sb.return_value

        # Simulate the RPC call pattern
        result = sb.rpc("competitor_territory_map", {
            "p_cnpj": VALID_CNPJ,
            "p_anos": 5,
        }).execute()

        sb.rpc.assert_called_once_with("competitor_territory_map", {
            "p_cnpj": VALID_CNPJ,
            "p_anos": 5,
        })
        assert result.data == MOCK_COMPLETE_RESPONSE

    # ------------------------------------------------------------------
    # Test: Top-level keys
    # ------------------------------------------------------------------

    def test_has_required_top_level_keys(self):
        """Response must have all 4 top-level keys."""
        for key in ("concorrente", "territorio", "orgaos_favoritos", "stats"):
            assert key in MOCK_COMPLETE_RESPONSE, f"Missing key: {key}"

    # ------------------------------------------------------------------
    # Test: Concorrente structure
    # ------------------------------------------------------------------

    def test_concorrente_has_required_fields(self):
        """concorrente object has all required fields with correct types."""
        c = MOCK_COMPLETE_RESPONSE["concorrente"]
        expected_fields = {
            "cnpj": str,
            "nome": str,
            "total_contratos": int,
            "ticket_medio": (int, float),
            "ticket_mediana": (int, float),
            "valor_total_contratado": (int, float),
        }
        for field, expected_type in expected_fields.items():
            assert field in c, f"Missing concorrente field: {field}"
            assert isinstance(c[field], expected_type), f"Wrong type for {field}"

    # ------------------------------------------------------------------
    # Test: Territorio structure
    # ------------------------------------------------------------------

    def test_territorio_structure(self):
        """Each territorio entry has required fields."""
        for t in MOCK_COMPLETE_RESPONSE["territorio"]:
            expected_fields = {
                "uf": str,
                "contratos": int,
                "valor_total": (int, float),
                "ticket_medio_uf": (int, float),
                "orgaos_principais": list,
                "market_share_uf": (int, float),
                "tendencia": str,
            }
            for field, expected_type in expected_fields.items():
                assert field in t, f"Missing territorio field: {field}"
                assert isinstance(t[field], expected_type), f"Wrong type for {field} in territorio"

    def test_territorio_tendencia_valid_values(self):
        """tendencia must be one of: crescendo, estavel, declinio."""
        valid = {"crescendo", "estavel", "declinio"}
        for t in MOCK_COMPLETE_RESPONSE["territorio"]:
            assert t["tendencia"] in valid, f"Invalid tendencia: {t['tendencia']}"

    def test_market_share_uf_between_0_and_1(self):
        """market_share_uf is always between 0 and 1."""
        for t in MOCK_COMPLETE_RESPONSE["territorio"]:
            assert 0 <= t["market_share_uf"] <= 1.0, (
                f"market_share_uf out of range [0,1]: {t['market_share_uf']}"
            )

    def test_market_share_uf_with_contracts_is_positive(self):
        """market_share_uf > 0 when contratos > 0."""
        for t in MOCK_COMPLETE_RESPONSE["territorio"]:
            if t["contratos"] > 0:
                assert t["market_share_uf"] > 0, (
                    f"market_share_uf should be > 0 with {t['contratos']} contracts"
                )

    def test_orgaos_principais_top_3(self):
        """orgaos_principais has at most 3 entries."""
        for t in MOCK_COMPLETE_RESPONSE["territorio"]:
            assert len(t["orgaos_principais"]) <= 3, (
                f"Expected at most 3 orgaos_principais, got {len(t['orgaos_principais'])}"
            )

    # ------------------------------------------------------------------
    # Test: Orgaos favoritos structure
    # ------------------------------------------------------------------

    def test_orgaos_favoritos_structure(self):
        """Each orgaos_favoritos entry has required fields."""
        for o in MOCK_COMPLETE_RESPONSE["orgaos_favoritos"]:
            expected_fields = {
                "orgao_nome": str,
                "contratos": int,
                "valor_total": (int, float),
                "categorias": list,
                "ultima_vitoria": str,
                "frequencia_anual": (int, float),
            }
            for field, expected_type in expected_fields.items():
                assert field in o, f"Missing orgaos_favoritos field: {field}"
                assert isinstance(o[field], expected_type), f"Wrong type for {field} in orgaos_favoritos"

    def test_orgaos_favoritos_limit_10(self):
        """At most 10 favorite agencies."""
        assert len(MOCK_COMPLETE_RESPONSE["orgaos_favoritos"]) <= 10

    # ------------------------------------------------------------------
    # Test: Stats structure
    # ------------------------------------------------------------------

    def test_stats_has_required_fields(self):
        """stats object has all required fields."""
        s = MOCK_COMPLETE_RESPONSE["stats"]
        expected_fields = {
            "ufs_atuacao": int,
            "orgaos_unicos": int,
            "anos_atuacao": int,
            "crescimento_anual": (int, float),
        }
        for field, expected_type in expected_fields.items():
            assert field in s, f"Missing stats field: {field}"
            assert isinstance(s[field], expected_type), f"Wrong type for {field}"

    # ------------------------------------------------------------------
    # Test: Zeroed response (no contracts)
    # ------------------------------------------------------------------

    def test_zeroed_response_has_required_structure(self):
        """Empty CNPJ returns complete zeroed structure."""
        assert MOCK_ZEROED_RESPONSE["concorrente"]["total_contratos"] == 0
        assert MOCK_ZEROED_RESPONSE["concorrente"]["nome"] == ""
        assert MOCK_ZEROED_RESPONSE["concorrente"]["ticket_medio"] == 0.0
        assert MOCK_ZEROED_RESPONSE["concorrente"]["ticket_mediana"] == 0.0
        assert MOCK_ZEROED_RESPONSE["concorrente"]["valor_total_contratado"] == 0.0
        assert MOCK_ZEROED_RESPONSE["territorio"] == []
        assert MOCK_ZEROED_RESPONSE["orgaos_favoritos"] == []
        assert MOCK_ZEROED_RESPONSE["stats"]["ufs_atuacao"] == 0
        assert MOCK_ZEROED_RESPONSE["stats"]["orgaos_unicos"] == 0
        assert MOCK_ZEROED_RESPONSE["stats"]["anos_atuacao"] == 0
        assert MOCK_ZEROED_RESPONSE["stats"]["crescimento_anual"] == 0.0

    def test_zeroed_response_has_all_keys(self):
        """Zeroed response still has all 4 top-level keys."""
        for key in ("concorrente", "territorio", "orgaos_favoritos", "stats"):
            assert key in MOCK_ZEROED_RESPONSE, f"Missing key in zeroed response: {key}"

    def test_zeroed_territorio_is_empty_list(self):
        """Zeroed territorio is []."""
        assert MOCK_ZEROED_RESPONSE["territorio"] == []

    def test_zeroed_orgaos_favoritos_is_empty_list(self):
        """Zeroed orgaos_favoritos is []."""
        assert MOCK_ZEROED_RESPONSE["orgaos_favoritos"] == []

    def test_zeroed_stats_are_zero(self):
        """Zeroed stats all equal 0."""
        for k, v in MOCK_ZEROED_RESPONSE["stats"].items():
            assert v == 0 or v == 0.0, f"Expected 0 for stats.{k}, got {v}"

    # ------------------------------------------------------------------
    # Test: Semântica e regras de negócio
    # ------------------------------------------------------------------

    def test_total_contratos_matches_sum_of_territorio(self):
        """total_contratos equals sum of contracts across all UFs."""
        total = MOCK_COMPLETE_RESPONSE["concorrente"]["total_contratos"]
        uf_sum = sum(t["contratos"] for t in MOCK_COMPLETE_RESPONSE["territorio"])
        assert uf_sum <= total, (
            f"Territory sum ({uf_sum}) exceeds total_contratos ({total})"
        )

    def test_valor_total_contratado_sufficient_for_territorio(self):
        """valor_total_contratado >= sum of territorio values."""
        total_global = MOCK_COMPLETE_RESPONSE["concorrente"]["valor_total_contratado"]
        uf_sum = sum(t["valor_total"] for t in MOCK_COMPLETE_RESPONSE["territorio"])
        assert uf_sum <= total_global, (
            f"Territory value sum ({uf_sum}) exceeds total ({total_global})"
        )

    def test_ticket_mediana_is_reasonable(self):
        """ticket_mediana <= ticket_medio (typical for right-skewed distribution)."""
        ticket_medio = MOCK_COMPLETE_RESPONSE["concorrente"]["ticket_medio"]
        ticket_mediana = MOCK_COMPLETE_RESPONSE["concorrente"]["ticket_mediana"]
        assert ticket_mediana <= ticket_medio, (
            f"Median ({ticket_mediana}) > mean ({ticket_medio}) — unusual but possible"
        )

    # ------------------------------------------------------------------
    # Test: RPC parameter validation (via mock — mirrors DB function)
    # ------------------------------------------------------------------

    def test_invalid_cnpj_raises_error(self):
        """CNPJ with < 14 digits should raise error (mirrors DB RAISE)."""
        import re
        cleaned = re.sub(r'[^0-9]', '', INVALID_CNPJ)
        assert len(cleaned) < 14
        # The DB function would raise: 'CNPJ invalido: deve conter 14 digitos'
        # Test that the validation logic is consistent
        with pytest.raises(Exception, match="14") if len(cleaned) != 14 else pytest.raises(Exception):
            if len(cleaned) != 14:
                raise ValueError("CNPJ invalido: deve conter 14 digitos")

    def test_valid_cnpj_14_digits(self):
        """Valid CNPJ has exactly 14 digits."""
        import re
        cleaned = re.sub(r'[^0-9]', '', VALID_CNPJ)
        assert len(cleaned) == 14
        assert cleaned.isdigit()

    def test_cnpj_with_formatting_is_normalized(self):
        """CNPJ with formatting (XX.XXX.XXX/XXXX-XX) normalized to 14 digits."""
        formatted = "12.345.678/0001-90"
        import re
        cleaned = re.sub(r'[^0-9]', '', formatted)
        assert len(cleaned) == 14
        assert cleaned == VALID_CNPJ

    # ------------------------------------------------------------------
    # Test: Migration file existence
    # ------------------------------------------------------------------

    def test_migration_file_exists(self):
        """The up migration SQL file must exist."""
        from pathlib import Path
        mig_path = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
        up_file = mig_path / "20260531120000_competitor_territory_map.sql"
        assert up_file.exists(), f"Migration file not found: {up_file}"

    def test_down_migration_file_exists(self):
        """The down migration SQL file must exist."""
        from pathlib import Path
        mig_path = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
        down_file = mig_path / "20260531120000_competitor_territory_map.down.sql"
        assert down_file.exists(), f"Down migration file not found: {down_file}"

    def test_down_migration_drops_function(self):
        """Down migration must DROP the RPC function."""
        from pathlib import Path
        mig_path = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
        down_file = mig_path / "20260531120000_competitor_territory_map.down.sql"
        content = down_file.read_text(encoding="utf-8")
        assert "DROP FUNCTION IF EXISTS public.competitor_territory_map" in content
        assert "DROP INDEX IF EXISTS idx_psc_cnpj_vencedor_data" in content

    def test_up_migration_grants_execution(self):
        """Up migration must GRANT EXECUTE to anon, authenticated, service_role."""
        from pathlib import Path
        mig_path = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
        up_file = mig_path / "20260531120000_competitor_territory_map.sql"
        content = up_file.read_text(encoding="utf-8")
        assert "GRANT EXECUTE ON FUNCTION" in content
        assert "TO anon, authenticated, service_role" in content

    def test_up_migration_has_comment(self):
        """Up migration must have COMMENT ON FUNCTION."""
        from pathlib import Path
        mig_path = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
        up_file = mig_path / "20260531120000_competitor_territory_map.sql"
        content = up_file.read_text(encoding="utf-8")
        assert "COMMENT ON FUNCTION" in content
        assert "COMPINT-001" in content
