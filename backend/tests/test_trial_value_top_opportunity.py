"""Tests for trial-value endpoint top_opportunity (issue #541 — Option B: columns stripped)."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from auth import require_auth


MOCK_USER = {"id": "user-456", "email": "test2@example.com"}


def override_auth():
    return MOCK_USER


@pytest.fixture(autouse=True)
def setup_auth():
    app.dependency_overrides[require_auth] = override_auth
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


class TestTrialValueTopOpportunity:
    def test_returns_top_opportunity_with_value(self, client):
        mock_db = MagicMock()

        profile_result = MagicMock()
        profile_result.data = {"created_at": "2026-04-01T00:00:00Z", "trial_expires_at": "2026-04-15T00:00:00Z"}

        sessions_result = MagicMock()
        sessions_result.data = [
            {
                "total_filtered": 5,
                "valor_total": "87000.00",
                "created_at": "2026-04-05T00:00:00Z",
                "sectors": ["limpeza"],
            }
        ]

        call_count = 0

        async def mock_sb_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return profile_result
            return sessions_result

        with patch("routes.analytics.sb_execute", side_effect=mock_sb_execute), \
             patch("routes.analytics.get_db", return_value=mock_db):
            resp = client.get("/v1/analytics/trial-value")

        assert resp.status_code == 200
        data = resp.json()
        assert data["top_opportunity"] is not None
        assert data["top_opportunity"]["value"] == 87000.0
        assert data["top_opportunity"]["setor"] == "limpeza"
        assert data["top_opportunity"]["objeto"] == "Oportunidade identificada"

    def test_returns_null_when_no_sessions(self, client):
        mock_db = MagicMock()

        profile_result = MagicMock()
        profile_result.data = {"created_at": "2026-04-01T00:00:00Z", "trial_expires_at": None}

        sessions_result = MagicMock()
        sessions_result.data = []

        call_count = 0

        async def mock_sb_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return profile_result
            return sessions_result

        with patch("routes.analytics.sb_execute", side_effect=mock_sb_execute), \
             patch("routes.analytics.get_db", return_value=mock_db):
            resp = client.get("/v1/analytics/trial-value")

        assert resp.status_code == 200
        data = resp.json()
        assert data["top_opportunity"] is None


class TestFormatters:
    def test_format_brl_large_value(self):
        from utils.formatters import format_brl
        assert format_brl(87000.0) == "R$ 87.000"
        assert format_brl(245000.0) == "R$ 245.000"

    def test_format_brl_small_value(self):
        from utils.formatters import format_brl
        result = format_brl(500.0)
        assert result.startswith("R$")

    def test_dias_ate_data_future(self):
        from utils.formatters import dias_ate_data
        from datetime import date, timedelta
        future = (date.today() + timedelta(days=10)).isoformat()
        assert dias_ate_data(future) == 10

    def test_dias_ate_data_past_returns_none(self):
        from utils.formatters import dias_ate_data
        assert dias_ate_data("2020-01-01") is None

    def test_dias_ate_data_none_returns_none(self):
        from utils.formatters import dias_ate_data
        assert dias_ate_data(None) is None

    def test_truncate_text(self):
        from utils.formatters import truncate_text
        long_text = "x" * 200
        result = truncate_text(long_text, 120)
        assert len(result) <= 120
        assert result.endswith("...")
