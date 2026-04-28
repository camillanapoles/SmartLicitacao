"""DATA-CNAE-001 (AC16): Integration test for the onboarding CNAE path.

The story risk R1 (HIGH) is "regression silenciosa em onboarding
first-analysis" — a wrong setor_id at this stage means every new
trial signup gets routed to the wrong sector and the first analysis
shows zero results.  This test pins the contract:

    1. The DB-backed lookup is the primary source.
    2. When the DB is unreachable, the legacy snapshot keeps the
       behaviour identical to the pre-refactor code path.
    3. The setor names returned to the user are unchanged.

We don't run the full pipeline (that would require a live Supabase +
Redis); we exercise the call site directly to prove the outputs are
byte-equivalent for the 6 most common CNAEs onboarding sees in
production traffic (engenharia, vestuario, servicos_prediais, saude,
informatica, alimentos).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _disable_listener(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CNAE_LISTENER_DISABLED", "true")
    yield


# CNAEs we deliberately exercise — they are the high-traffic ones in
# production telemetry and they map to four distinct sectors.
ONBOARDING_CNAES: list[tuple[str, str, str]] = [
    ("4781-4/00", "vestuario", "Vestuário e Uniformes"),
    ("4120-4/00", "engenharia", "Engenharia, Projetos e Obras"),
    ("8121-4/00", "servicos_prediais", "Serviços Prediais e Facilities"),
    ("8610-1/01", "saude", "Saúde e Hospitalar"),
    ("6201-5/01", "informatica", "TI e Sistemas"),
    ("4711-3/02", "alimentos", "Alimentos e Merenda"),
]


def _make_db_mock(legacy_dict: dict[str, str]):
    """Build a Supabase mock that mirrors the seeded mapping table."""
    captured: dict = {}

    class _Q:
        def select(self, *a, **k):
            return self

        def eq(self, col, val):
            captured[col] = val
            return self

        def limit(self, _n):
            return self

        def execute(self):
            cnae = captured.get("cnae_code")
            setor = legacy_dict.get(cnae)
            res = MagicMock()
            res.data = [{"setor_id": setor}] if setor else []
            return res

    sb = MagicMock()
    sb.table.return_value = _Q()
    return sb


@pytest.mark.parametrize("cnae_input,expected_id,expected_name", ONBOARDING_CNAES)
def test_db_path_returns_expected_setor_and_name(
    cnae_input: str,
    expected_id: str,
    expected_name: str,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CNAE_DB_LOOKUP_ENABLED", "true")
    from utils import cnae_mapping

    cnae_mapping.invalidate_cnae_cache(None)
    sb = _make_db_mock(cnae_mapping._LEGACY_CNAE_TO_SETOR)
    with patch("supabase_client.get_supabase", return_value=sb):
        setor_id = cnae_mapping.map_cnae_to_setor(cnae_input)
    assert setor_id == expected_id
    assert cnae_mapping.get_setor_name(setor_id) == expected_name


@pytest.mark.parametrize("cnae_input,expected_id,expected_name", ONBOARDING_CNAES)
def test_db_unreachable_falls_back_to_legacy(
    cnae_input: str,
    expected_id: str,
    expected_name: str,
    monkeypatch: pytest.MonkeyPatch,
):
    """Critical contract — onboarding must NEVER break when DB is down."""
    monkeypatch.setenv("CNAE_DB_LOOKUP_ENABLED", "true")
    from utils import cnae_mapping

    cnae_mapping.invalidate_cnae_cache(None)
    sb = MagicMock()
    sb.table.side_effect = RuntimeError("Supabase unavailable")
    with patch("supabase_client.get_supabase", return_value=sb):
        setor_id = cnae_mapping.map_cnae_to_setor(cnae_input)
    assert setor_id == expected_id
    assert cnae_mapping.get_setor_name(setor_id) == expected_name


def test_unknown_cnae_returns_default_fallback(monkeypatch: pytest.MonkeyPatch):
    """An unknown CNAE must answer ``geral`` (legacy default)."""
    monkeypatch.setenv("CNAE_DB_LOOKUP_ENABLED", "true")
    from utils import cnae_mapping

    cnae_mapping.invalidate_cnae_cache(None)
    sb = _make_db_mock({})
    with patch("supabase_client.get_supabase", return_value=sb):
        setor_id = cnae_mapping.map_cnae_to_setor("9999-9/99")
    assert setor_id == "geral"
