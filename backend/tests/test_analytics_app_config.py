"""BIZ-METRIC-001 (AC5): tests for app_config integration in analytics.summary.

Covers:
    * estimated_hours_saved uses app_config.hours_saved_per_search when set
    * Falls back to DEFAULT_HOURS_SAVED_PER_SEARCH (2.0) when app_config
      table missing / row absent / value invalid
    * TTL cache: clear_cache() resets the in-process state
    * get_hours_saved_per_search clamps invalid values to default
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from utils.app_config import (
    DEFAULT_HOURS_SAVED_PER_SEARCH,
    clear_cache,
    get_config_value,
    get_hours_saved_per_search,
    invalidate_app_config,
)


@pytest.fixture(autouse=True)
def _reset_app_config_cache():
    clear_cache()
    yield
    clear_cache()


def _mock_user():
    return {"id": "user-app-config-1", "email": "u@test.com", "role": "authenticated"}


@pytest.fixture
def client():
    from main import app
    from auth import require_auth

    app.dependency_overrides[require_auth] = _mock_user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def mock_db_with_3_searches():
    """Returns a Supabase mock where the analytics RPC returns
    total_searches=3 (so estimated_hours_saved = 3 * multiplier).
    """
    from main import app
    from database import get_db

    sb = MagicMock()
    rpc_chain = MagicMock()
    rpc_result = MagicMock()
    rpc_result.data = [{
        "total_searches": 3,
        "total_downloads": 1,
        "total_opportunities": 12,
        "total_value_discovered": 1000.0,
        "member_since": "2026-01-01T00:00:00Z",
    }]
    rpc_chain.execute.return_value = rpc_result
    sb.rpc.return_value = rpc_chain

    app.dependency_overrides[get_db] = lambda: sb
    yield sb
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Pure helpers — TTL cache + fallback semantics
# ---------------------------------------------------------------------------

class TestAppConfigHelper:
    def test_default_returned_when_db_unavailable(self):
        with patch("supabase_client.get_supabase") as mock_sb:
            mock_sb.side_effect = RuntimeError("db down")
            value = get_hours_saved_per_search()
        assert value == DEFAULT_HOURS_SAVED_PER_SEARCH

    def test_default_returned_when_row_missing(self):
        sb = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        result = MagicMock()
        result.data = []
        chain.execute.return_value = result
        sb.table.return_value = chain

        with patch("supabase_client.get_supabase", return_value=sb):
            value = get_hours_saved_per_search()
        assert value == DEFAULT_HOURS_SAVED_PER_SEARCH

    def test_value_read_from_db_when_present(self):
        sb = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        result = MagicMock()
        result.data = [{"value": 3.5}]
        chain.execute.return_value = result
        sb.table.return_value = chain

        with patch("supabase_client.get_supabase", return_value=sb):
            value = get_hours_saved_per_search()
        assert value == 3.5

    def test_invalid_value_falls_back_to_default(self):
        sb = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        result = MagicMock()
        # negative value out of sane range
        result.data = [{"value": -1}]
        chain.execute.return_value = result
        sb.table.return_value = chain

        with patch("supabase_client.get_supabase", return_value=sb):
            value = get_hours_saved_per_search()
        assert value == DEFAULT_HOURS_SAVED_PER_SEARCH

    def test_non_numeric_value_falls_back_to_default(self):
        sb = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        result = MagicMock()
        result.data = [{"value": "not-a-number"}]
        chain.execute.return_value = result
        sb.table.return_value = chain

        with patch("supabase_client.get_supabase", return_value=sb):
            value = get_hours_saved_per_search()
        assert value == DEFAULT_HOURS_SAVED_PER_SEARCH

    def test_cache_serves_subsequent_reads_until_invalidation(self):
        sb = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        result_a = MagicMock(); result_a.data = [{"value": 2.5}]
        result_b = MagicMock(); result_b.data = [{"value": 9.0}]
        # Two different DB states across calls.
        chain.execute.side_effect = [result_a, result_b, result_b, result_b]
        sb.table.return_value = chain

        with patch("supabase_client.get_supabase", return_value=sb):
            v1 = get_hours_saved_per_search()
            v2 = get_hours_saved_per_search()  # should hit cache → 2.5
            assert v1 == 2.5
            assert v2 == 2.5
            # invalidate then read again → should re-fetch and see 9.0
            invalidate_app_config("hours_saved_per_search")
            v3 = get_hours_saved_per_search()
            assert v3 == 9.0


# ---------------------------------------------------------------------------
# Endpoint integration
# ---------------------------------------------------------------------------

class TestAnalyticsSummaryUsesAppConfig:
    def test_summary_uses_default_when_app_config_unreadable(self, client, mock_db_with_3_searches):
        with patch(
            "routes.analytics.get_hours_saved_per_search",
            return_value=DEFAULT_HOURS_SAVED_PER_SEARCH,
        ):
            resp = client.get("/v1/analytics/summary", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        # 3 searches * 2.0 = 6.0 — preserves legacy value (story Change Log)
        assert resp.json()["estimated_hours_saved"] == 6.0

    def test_summary_uses_calibrated_value_when_present(self, client, mock_db_with_3_searches):
        with patch("routes.analytics.get_hours_saved_per_search", return_value=4.5):
            resp = client.get("/v1/analytics/summary", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        # 3 searches * 4.5 = 13.5
        assert resp.json()["estimated_hours_saved"] == pytest.approx(13.5)

    def test_summary_falls_back_when_helper_raises(self, client, mock_db_with_3_searches):
        with patch(
            "routes.analytics.get_hours_saved_per_search",
            side_effect=RuntimeError("totally broken"),
        ):
            resp = client.get("/v1/analytics/summary", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        # Belt-and-suspenders fallback hit → uses DEFAULT_HOURS_SAVED_PER_SEARCH (2.0)
        assert resp.json()["estimated_hours_saved"] == 6.0
