"""DATA-CNAE-001: tests for DB-backed CNAE -> setor mapping.

Covers:

* Snapshot: every CNAE in the original hardcoded dict still resolves to the
  same setor via :func:`utils.cnae_mapping.lookup_cnae_setor` even when the
  DB lookup is unavailable (fallback path).
* Edge: unknown CNAE returns ``None``; ``map_cnae_to_setor`` falls back to
  ``"geral"`` (legacy contract preserved).
* DB path: when the Supabase client returns a row, that value wins over
  the hardcoded dict.
* Cache invalidation: ``invalidate_cnae_cache`` actually clears the LRU.
* Soft delete: rows with ``notes='deleted'`` are ignored.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from utils import cnae_mapping
from utils.cnae_mapping import (
    CNAE_TO_SETOR,
    invalidate_cnae_cache,
    lookup_cnae_setor,
    map_cnae_to_setor,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure each test starts with a cold LRU cache."""
    invalidate_cnae_cache()
    yield
    invalidate_cnae_cache()


@pytest.fixture
def _db_offline(monkeypatch):
    """Force the DB lookup to behave as if Supabase is unavailable."""
    monkeypatch.setattr(cnae_mapping, "_db_lookup", lambda code: None)


class TestSnapshotFallback:
    """When DB is offline every original mapping must keep working."""

    def test_every_original_cnae_resolves(self, _db_offline):
        for cnae, expected in CNAE_TO_SETOR.items():
            assert lookup_cnae_setor(cnae) == expected, (
                f"snapshot regression for cnae={cnae}"
            )

    def test_unknown_cnae_returns_none(self, _db_offline):
        assert lookup_cnae_setor("9999") is None
        assert lookup_cnae_setor("0000") is None

    def test_map_cnae_to_setor_legacy_contract(self, _db_offline):
        assert map_cnae_to_setor("9999") == "geral"
        assert map_cnae_to_setor("") == "geral"
        assert map_cnae_to_setor("4781") == "vestuario"


class TestDbWinsOverHardcoded:
    """Anything returned by the DB beats the hardcoded fallback."""

    def test_db_value_wins(self, monkeypatch):
        monkeypatch.setattr(
            cnae_mapping, "_db_lookup", lambda code: "saude" if code == "4120" else None
        )
        # "4120" is hardcoded as "engenharia"; DB now says "saude".
        assert lookup_cnae_setor("4120") == "saude"

    def test_db_miss_falls_back_to_dict(self, monkeypatch):
        monkeypatch.setattr(cnae_mapping, "_db_lookup", lambda code: None)
        assert lookup_cnae_setor("4120") == "engenharia"

    def test_db_returns_unknown_cnae(self, monkeypatch):
        monkeypatch.setattr(
            cnae_mapping, "_db_lookup", lambda code: "informatica" if code == "9999" else None
        )
        # "9999" is not in the hardcoded dict but DB exposes it now.
        assert lookup_cnae_setor("9999") == "informatica"


class TestCacheInvalidation:
    """Cache must be invalidated after admin writes."""

    def test_cache_holds_first_result(self, monkeypatch):
        calls = {"n": 0}

        def fake(code):
            calls["n"] += 1
            return "engenharia"

        monkeypatch.setattr(cnae_mapping, "_db_lookup", fake)
        assert lookup_cnae_setor("4120") == "engenharia"
        assert lookup_cnae_setor("4120") == "engenharia"
        assert calls["n"] == 1, "second call should have been served from LRU"

    def test_invalidate_forces_refetch(self, monkeypatch):
        calls = {"n": 0}

        def fake(code):
            calls["n"] += 1
            return "engenharia" if calls["n"] == 1 else "saude"

        monkeypatch.setattr(cnae_mapping, "_db_lookup", fake)
        assert lookup_cnae_setor("4120") == "engenharia"
        invalidate_cnae_cache()
        # After invalidation the next call hits _db_lookup again and sees the
        # new value.
        assert lookup_cnae_setor("4120") == "saude"
        assert calls["n"] == 2


class TestSoftDelete:
    """Rows with notes='deleted' must be treated as if absent."""

    def test_soft_deleted_row_ignored(self, monkeypatch):
        # Build a fake supabase client whose .execute() returns a deleted row.
        sb = MagicMock()
        chain = sb.table.return_value.select.return_value.eq.return_value.limit.return_value
        chain.execute.return_value = MagicMock(
            data=[{"setor_id": "engenharia", "notes": "deleted"}]
        )
        monkeypatch.setattr(
            "supabase_client.get_supabase", lambda: sb, raising=False
        )
        # _db_lookup should return None because the row is soft-deleted, so
        # the hardcoded dict ("vestuario" for 4781) takes over.
        assert cnae_mapping._db_lookup("4781") is None

    def test_active_row_returned(self, monkeypatch):
        sb = MagicMock()
        chain = sb.table.return_value.select.return_value.eq.return_value.limit.return_value
        chain.execute.return_value = MagicMock(
            data=[{"setor_id": "engenharia", "notes": None}]
        )
        monkeypatch.setattr(
            "supabase_client.get_supabase", lambda: sb, raising=False
        )
        assert cnae_mapping._db_lookup("4781") == "engenharia"

    def test_db_error_returns_none(self, monkeypatch):
        def boom():
            raise RuntimeError("supabase down")

        monkeypatch.setattr(
            "supabase_client.get_supabase", boom, raising=False
        )
        assert cnae_mapping._db_lookup("4781") is None
