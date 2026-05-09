"""Tests for DB-backed plan capabilities loader (TD-GTM-003 #192).

Covers:
  - Cache TTL is 30s (per task spec)
  - Cache hit/miss behavior
  - jsonb capabilities column is preferred source of truth
  - Per-row fallback to hardcoded dict on missing/malformed jsonb
  - Whole-dict fallback on Supabase exception
  - PLAN_CAPABILITIES symbol still importable / unchanged for legacy callers
  - _FALLBACK_PLAN_CAPABILITIES is a complete superset (all hardcoded plans)
"""

from unittest.mock import MagicMock, patch

import pytest

from quota import (
    PLAN_CAPABILITIES,
    PLAN_CAPABILITIES_CACHE_TTL,
    _FALLBACK_PLAN_CAPABILITIES,
    _coerce_capabilities_row,
    _load_plan_capabilities_from_db,
    clear_plan_capabilities_cache,
    get_plan_capabilities,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    """Clear the cache before and after every test for isolation."""
    clear_plan_capabilities_cache()
    yield
    clear_plan_capabilities_cache()


def _make_supabase_mock(rows):
    """Build a Supabase client mock that returns the given rows for plans.select(...).execute()."""
    sb = MagicMock()
    table = MagicMock()
    select = MagicMock()
    eq = MagicMock()
    result = MagicMock()
    result.data = rows
    eq.execute.return_value = result
    select.eq.return_value = eq
    table.select.return_value = select
    sb.table.return_value = table
    return sb


# ---------------------------------------------------------------------------
# Constants & exports
# ---------------------------------------------------------------------------

class TestExports:
    def test_cache_ttl_is_30_seconds(self):
        """TD-GTM-003 #192: TTL reduced to 30s."""
        assert PLAN_CAPABILITIES_CACHE_TTL == 30

    def test_fallback_dict_is_alias_of_legacy_symbol(self):
        """Backwards compat: _FALLBACK_PLAN_CAPABILITIES IS PLAN_CAPABILITIES (same object)."""
        assert _FALLBACK_PLAN_CAPABILITIES is PLAN_CAPABILITIES

    def test_fallback_covers_all_known_plans(self):
        """Every plan_id used elsewhere in the codebase must be present in fallback."""
        required_plans = {
            "free_trial", "consultor_agil", "maquina", "sala_guerra",
            "smartlic_pro", "founding_member", "consultoria", "free", "master",
        }
        assert required_plans <= set(_FALLBACK_PLAN_CAPABILITIES.keys())


# ---------------------------------------------------------------------------
# _coerce_capabilities_row
# ---------------------------------------------------------------------------

class TestCoerceCapabilitiesRow:
    VALID_RAW = {
        "max_history_days": 1825,
        "allow_excel": True,
        "allow_pipeline": True,
        "max_requests_per_month": 1000,
        "max_requests_per_min": 60,
        "max_summary_tokens": 10000,
        "priority": "normal",
    }

    def test_valid_jsonb_returns_capabilities(self):
        caps = _coerce_capabilities_row("smartlic_pro", self.VALID_RAW, max_searches=None)
        assert caps is not None
        assert caps["max_history_days"] == 1825
        assert caps["allow_excel"] is True
        assert caps["max_requests_per_month"] == 1000

    def test_max_searches_overrides_jsonb_quota(self):
        """When the legacy max_searches column is set, it wins over jsonb."""
        caps = _coerce_capabilities_row("smartlic_pro", self.VALID_RAW, max_searches=42)
        assert caps is not None
        assert caps["max_requests_per_month"] == 42

    def test_missing_required_key_returns_none(self):
        partial = dict(self.VALID_RAW)
        del partial["priority"]
        assert _coerce_capabilities_row("x", partial, None) is None

    def test_non_dict_returns_none(self):
        assert _coerce_capabilities_row("x", None, None) is None
        assert _coerce_capabilities_row("x", "not-a-dict", None) is None  # type: ignore[arg-type]

    def test_malformed_value_returns_none(self):
        broken = dict(self.VALID_RAW, max_history_days="not-an-int")
        # int("not-an-int") raises ValueError → coercion returns None
        assert _coerce_capabilities_row("x", broken, None) is None


# ---------------------------------------------------------------------------
# _load_plan_capabilities_from_db
# ---------------------------------------------------------------------------

class TestLoadFromDB:
    JSONB_PRO = {
        "max_history_days": 1825,
        "allow_excel": True,
        "allow_pipeline": True,
        "max_requests_per_month": 1000,
        "max_requests_per_min": 60,
        "max_summary_tokens": 10000,
        "priority": "normal",
    }

    def test_jsonb_capabilities_preferred(self):
        rows = [{"id": "smartlic_pro", "max_searches": None, "capabilities": self.JSONB_PRO}]
        sb = _make_supabase_mock(rows)
        with patch("supabase_client.get_supabase", return_value=sb):
            result = _load_plan_capabilities_from_db()
        assert result["smartlic_pro"]["max_history_days"] == 1825
        assert result["smartlic_pro"]["priority"] == "normal"

    def test_per_row_fallback_when_jsonb_missing(self):
        """Row with NULL capabilities falls back to hardcoded for that plan_id."""
        rows = [{"id": "smartlic_pro", "max_searches": None, "capabilities": None}]
        sb = _make_supabase_mock(rows)
        with patch("supabase_client.get_supabase", return_value=sb):
            result = _load_plan_capabilities_from_db()
        assert result["smartlic_pro"] == _FALLBACK_PLAN_CAPABILITIES["smartlic_pro"]

    def test_unknown_plan_with_no_jsonb_uses_conservative_defaults(self):
        rows = [{"id": "weird_unknown_plan", "max_searches": 7, "capabilities": None}]
        sb = _make_supabase_mock(rows)
        with patch("supabase_client.get_supabase", return_value=sb):
            result = _load_plan_capabilities_from_db()
        # max_searches=7 should override conservative default
        assert result["weird_unknown_plan"]["max_requests_per_month"] == 7
        assert result["weird_unknown_plan"]["allow_excel"] is False

    def test_full_fallback_on_exception(self):
        """Whole-dict fallback when Supabase raises."""
        sb = MagicMock()
        sb.table.side_effect = RuntimeError("connection lost")
        with patch("supabase_client.get_supabase", return_value=sb):
            result = _load_plan_capabilities_from_db()
        assert result is _FALLBACK_PLAN_CAPABILITIES

    def test_full_fallback_on_empty_table(self):
        sb = _make_supabase_mock([])
        with patch("supabase_client.get_supabase", return_value=sb):
            result = _load_plan_capabilities_from_db()
        assert result is _FALLBACK_PLAN_CAPABILITIES

    def test_db_result_is_superset_of_fallback(self):
        """DB result must contain every hardcoded plan_id even if DB row is missing."""
        # DB only returns one row — the loader should still expose the rest via fallback.
        rows = [{"id": "smartlic_pro", "max_searches": None, "capabilities": self.JSONB_PRO}]
        sb = _make_supabase_mock(rows)
        with patch("supabase_client.get_supabase", return_value=sb):
            result = _load_plan_capabilities_from_db()
        for plan_id in _FALLBACK_PLAN_CAPABILITIES:
            assert plan_id in result, f"plan_id '{plan_id}' missing from DB-loaded dict"


# ---------------------------------------------------------------------------
# get_plan_capabilities — caching
# ---------------------------------------------------------------------------

class TestCacheBehavior:
    JSONB_PRO = {
        "max_history_days": 1825,
        "allow_excel": True,
        "allow_pipeline": True,
        "max_requests_per_month": 1000,
        "max_requests_per_min": 60,
        "max_summary_tokens": 10000,
        "priority": "normal",
    }

    def test_cache_hit_avoids_second_db_call(self):
        rows = [{"id": "smartlic_pro", "max_searches": None, "capabilities": self.JSONB_PRO}]
        sb = _make_supabase_mock(rows)
        with patch("supabase_client.get_supabase", return_value=sb) as mock_get:
            get_plan_capabilities()  # miss
            get_plan_capabilities()  # hit
            get_plan_capabilities()  # hit
        assert mock_get.call_count == 1

    def test_clear_cache_forces_reload(self):
        rows = [{"id": "smartlic_pro", "max_searches": None, "capabilities": self.JSONB_PRO}]
        sb = _make_supabase_mock(rows)
        with patch("supabase_client.get_supabase", return_value=sb) as mock_get:
            get_plan_capabilities()  # miss
            clear_plan_capabilities_cache()
            get_plan_capabilities()  # miss again
        assert mock_get.call_count == 2

    def test_cache_expires_after_ttl(self):
        """Simulate clock advancing past TTL by patching the clock used by quota_core."""
        rows = [{"id": "smartlic_pro", "max_searches": None, "capabilities": self.JSONB_PRO}]
        sb = _make_supabase_mock(rows)
        # Clock state — return whatever the test currently assigns. Each call to
        # time.time() inside the loader reads this single source.
        clock = [0.0]

        def _now():
            return clock[0]

        with patch("supabase_client.get_supabase", return_value=sb) as mock_get, \
             patch("quota.quota_core.time.time", side_effect=_now):
            clock[0] = 0.0
            get_plan_capabilities()  # MISS at t=0 → loads from DB
            clock[0] = float(PLAN_CAPABILITIES_CACHE_TTL) + 5.0
            get_plan_capabilities()  # MISS again — cache expired
        assert mock_get.call_count == 2

    def test_fallback_response_does_not_break_cache(self):
        """Even when DB raises, get_plan_capabilities() returns a usable dict and caches it."""
        sb = MagicMock()
        sb.table.side_effect = RuntimeError("boom")
        with patch("supabase_client.get_supabase", return_value=sb):
            result = get_plan_capabilities()
        assert "smartlic_pro" in result
        assert result["smartlic_pro"]["max_requests_per_month"] > 0
