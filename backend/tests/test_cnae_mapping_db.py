"""DATA-CNAE-001 (AC15 + AC5) tests for the DB-backed CNAE mapping.

NOTE on patch target: ``utils/cnae_mapping.py`` does a *local* import
``from supabase_client import get_supabase`` inside ``_query_db`` to
keep module import cheap.  That means
``patch("utils.cnae_mapping.get_supabase")`` fails (the symbol is
not in the module namespace) — we must patch
``supabase_client.get_supabase`` directly, which is the function
the local import resolves to.

Coverage:
    1. AC15 snapshot regression — every legacy CNAE keeps the same
       sector when looked up via the DB path AND via the legacy
       fallback path.  This is the safety net that prevents an
       onboarding regression in production.
    2. TTL cache hit/miss/invalidation — the cache is the hot path
       and a bug here would silently double DB load.
    3. DB-down fallback — onboarding must not break when Supabase is
       unreachable; lookups fall back to ``_LEGACY_CNAE_TO_SETOR``.
    4. Kill switch — ``CNAE_DB_LOOKUP_ENABLED=false`` skips the DB.
    5. Local invalidate (``invalidate_cnae_cache``) drops only the
       requested key (or everything when called with ``None``).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _disable_listener_and_reset_cache(monkeypatch: pytest.MonkeyPatch):
    """Keep the Redis listener thread off and start every test with an
    empty cache + the DB lookup path enabled.  Tests that need the
    kill-switch path opt in via ``monkeypatch.setenv``.
    """
    monkeypatch.setenv("CNAE_LISTENER_DISABLED", "true")
    monkeypatch.setenv("CNAE_DB_LOOKUP_ENABLED", "true")
    from utils import cnae_mapping  # local import to honour env

    cnae_mapping._cache.clear()
    yield
    cnae_mapping._cache.clear()


# ---------------------------------------------------------------------------
# AC15 — snapshot regression
# ---------------------------------------------------------------------------
class TestSnapshotRegression:
    """Every legacy CNAE must answer identically pre/post DATA-CNAE-001.

    The legacy answer is captured in ``_LEGACY_CNAE_TO_SETOR``; the
    DB answer is simulated by piping the same dict through the
    Supabase mock.  100% match is the gate.
    """

    def test_db_path_matches_legacy_for_every_known_cnae(self):
        from utils import cnae_mapping

        legacy = cnae_mapping._LEGACY_CNAE_TO_SETOR
        sb = MagicMock()

        # Build a fake table query that returns the legacy value for
        # whatever cnae is asked.  Each .eq() call returns the chain
        # so we can pluck the cnae from the call args.
        def _fake_table(_name):
            captured: dict = {}

            class _Q:
                def select(self, *args, **kwargs):
                    return self

                def eq(self, col, val):
                    captured[col] = val
                    return self

                def limit(self, _n):
                    return self

                def execute(self):
                    cnae = captured.get("cnae_code")
                    setor = legacy.get(cnae)
                    res = MagicMock()
                    res.data = [{"setor_id": setor}] if setor else []
                    return res

            return _Q()

        sb.table.side_effect = _fake_table

        with patch("supabase_client.get_supabase", return_value=sb):
            for cnae, expected in legacy.items():
                cnae_mapping.invalidate_cnae_cache(cnae)
                got = cnae_mapping.map_cnae_to_setor(cnae)
                assert got == expected, (
                    f"AC15 regression: cnae={cnae} legacy={expected} db={got}"
                )

    def test_legacy_fallback_matches_legacy_for_every_known_cnae(self, monkeypatch):
        """Kill-switch path must also be byte-equivalent."""
        monkeypatch.setenv("CNAE_DB_LOOKUP_ENABLED", "false")
        from utils import cnae_mapping

        for cnae, expected in cnae_mapping._LEGACY_CNAE_TO_SETOR.items():
            cnae_mapping.invalidate_cnae_cache(cnae)
            assert cnae_mapping.map_cnae_to_setor(cnae) == expected


# ---------------------------------------------------------------------------
# AC5 — TTL cache behaviour
# ---------------------------------------------------------------------------
class TestTTLCache:
    def test_second_call_does_not_hit_db(self):
        from utils import cnae_mapping

        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"setor_id": "engenharia"}
        ]

        with patch("supabase_client.get_supabase", return_value=sb):
            assert cnae_mapping.map_cnae_to_setor("4120") == "engenharia"
            assert cnae_mapping.map_cnae_to_setor("4120") == "engenharia"

        # One DB hit (.execute) — second call served from cache.
        assert sb.table.call_count == 1

    def test_invalidate_drops_specific_key(self):
        from utils import cnae_mapping

        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"setor_id": "engenharia"}
        ]

        with patch("supabase_client.get_supabase", return_value=sb):
            cnae_mapping.map_cnae_to_setor("4120")
            cnae_mapping.invalidate_cnae_cache("4120")
            cnae_mapping.map_cnae_to_setor("4120")

        # Two DB hits — the invalidation forced a refresh.
        assert sb.table.call_count == 2

    def test_invalidate_all_drops_every_entry(self):
        from utils import cnae_mapping

        cnae_mapping._cache.set("4120", "engenharia")
        cnae_mapping._cache.set("4781", "vestuario")
        cnae_mapping.invalidate_cnae_cache(None)
        assert len(cnae_mapping._cache) == 0


# ---------------------------------------------------------------------------
# AC5 — DB-down fallback to legacy
# ---------------------------------------------------------------------------
class TestDbDownFallback:
    def test_db_exception_falls_back_to_legacy(self):
        from utils import cnae_mapping

        sb = MagicMock()
        sb.table.side_effect = RuntimeError("Supabase down")

        with patch("supabase_client.get_supabase", return_value=sb):
            # 4120 is in legacy; must still resolve to engenharia.
            assert cnae_mapping.map_cnae_to_setor("4120") == "engenharia"

    def test_db_returns_empty_falls_back_to_legacy(self):
        from utils import cnae_mapping

        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

        with patch("supabase_client.get_supabase", return_value=sb):
            # 4120 not in DB but in legacy: must still resolve.
            assert cnae_mapping.map_cnae_to_setor("4120") == "engenharia"

    def test_unknown_cnae_returns_geral_under_fallback(self):
        from utils import cnae_mapping

        sb = MagicMock()
        sb.table.side_effect = RuntimeError("Supabase down")

        with patch("supabase_client.get_supabase", return_value=sb):
            assert cnae_mapping.map_cnae_to_setor("9999") == "geral"


# ---------------------------------------------------------------------------
# AC5 — DB returns a value NOT in legacy (admin added a new mapping)
# ---------------------------------------------------------------------------
class TestDbDrivenAnswers:
    def test_db_value_overrides_legacy(self):
        from utils import cnae_mapping

        sb = MagicMock()
        # Legacy says 4120 -> engenharia.  Pretend admin overrode it.
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"setor_id": "manutencao_predial"}
        ]

        with patch("supabase_client.get_supabase", return_value=sb):
            assert cnae_mapping.map_cnae_to_setor("4120") == "manutencao_predial"


# ---------------------------------------------------------------------------
# AC5 — Kill switch
# ---------------------------------------------------------------------------
class TestKillSwitch:
    def test_disabled_skips_db_entirely(self, monkeypatch):
        monkeypatch.setenv("CNAE_DB_LOOKUP_ENABLED", "false")
        from utils import cnae_mapping

        # If the DB *were* hit, this mock would lie.  But with the
        # switch off, ``get_supabase`` is never imported.
        with patch("supabase_client.get_supabase") as mock_sb:
            assert cnae_mapping.map_cnae_to_setor("4120") == "engenharia"
            mock_sb.assert_not_called()


# ---------------------------------------------------------------------------
# Backward-compat — CNAE_TO_SETOR proxy
# ---------------------------------------------------------------------------
class TestLegacyProxy:
    def test_proxy_get_matches_dict(self):
        from utils import cnae_mapping

        assert cnae_mapping.CNAE_TO_SETOR.get("4120") == "engenharia"
        assert cnae_mapping.CNAE_TO_SETOR.get("9999", "fallback") == "fallback"

    def test_proxy_contains_and_iter(self):
        from utils import cnae_mapping

        assert "4120" in cnae_mapping.CNAE_TO_SETOR
        keys = list(iter(cnae_mapping.CNAE_TO_SETOR))
        assert "4781" in keys
        assert len(keys) == len(cnae_mapping._LEGACY_CNAE_TO_SETOR)
