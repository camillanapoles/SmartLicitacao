"""Tests for GET /v1/health/sitemap endpoint.

SEO-SITEMAP-TELEMETRY-001 #1059: Validates that the sitemap healthcheck
returns the correct structure and status for MV states.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from startup.app_factory import create_app
    app = create_app()
    return TestClient(app)


def _mock_sb_with_mv_counts(mv_counts: dict[str, int | None]) -> MagicMock:
    """Build a Supabase mock where each MV returns the given count.

    *mv_counts* maps MV name to expected COUNT(*) result.
    A value of None simulates a table-not-found error.
    """
    mock_sb = MagicMock()

    def apply_mock(table_name: str):
        """Configure .table(name) on mock_sb to return per-MV behavior."""
        mock_table = MagicMock()

        if table_name in mv_counts:
            count = mv_counts[table_name]
            if count is None:
                # Simulate MV not found (error)
                mock_table.select = MagicMock(
                    side_effect=Exception(f'relation "{table_name}" does not exist')
                )
            else:
                mock_resp = MagicMock()
                mock_resp.count = count
                mock_resp.data = []
                mock_table.select.return_value.limit.return_value.execute = MagicMock(
                    return_value=mock_resp
                )
                mock_table.select.return_value.count = mock_resp.count
        else:
            # Unknown MV
            mock_table.select = MagicMock(
                side_effect=Exception(f'relation "{table_name}" does not exist')
            )

        return mock_table

    mock_sb.table.side_effect = apply_mock
    return mock_sb


class TestSitemapHealth:
    """Tests for GET /v1/health/sitemap."""

    @patch("routes.health.get_supabase")
    @patch("routes.health._SITEMAP_MVS", ["mv_sitemap_cnpjs", "mv_sitemap_orgaos"])
    def test_ok_when_all_mvs_have_data(self, mock_get_sb, client):
        """Returns 200 with status=ok when all MVs have data."""
        mock_get_sb.return_value = _mock_sb_with_mv_counts({
            "mv_sitemap_cnpjs": 150,
            "mv_sitemap_orgaos": 85,
        })

        resp = client.get("/v1/health/sitemap")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "checks" in data
        assert data["checks"]["mv_sitemap_cnpjs"]["status"] == "ok"
        assert data["checks"]["mv_sitemap_cnpjs"]["count"] == 150
        assert data["checks"]["mv_sitemap_orgaos"]["status"] == "ok"

    @patch("routes.health.get_supabase")
    @patch("routes.health._SITEMAP_MVS", ["mv_sitemap_cnpjs", "mv_sitemap_orgaos"])
    def test_degraded_when_empty_mv(self, mock_get_sb, client):
        """Returns 503 with status=degraded when MV has 0 rows."""
        mock_get_sb.return_value = _mock_sb_with_mv_counts({
            "mv_sitemap_cnpjs": 0,
            "mv_sitemap_orgaos": 85,
        })

        resp = client.get("/v1/health/sitemap")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["checks"]["mv_sitemap_cnpjs"]["status"] == "empty"

    @patch("routes.health.get_supabase")
    @patch("routes.health._SITEMAP_MVS", ["mv_sitemap_cnpjs"])
    def test_degraded_when_mv_errors(self, mock_get_sb, client):
        """Returns 503 with status=error when MV query fails (table not found)."""
        mock_get_sb.return_value = _mock_sb_with_mv_counts({
            "mv_sitemap_cnpjs": None,
        })

        resp = client.get("/v1/health/sitemap")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["checks"]["mv_sitemap_cnpjs"]["status"] == "error"
        assert "error" in data["checks"]["mv_sitemap_cnpjs"]

    @patch("routes.health.get_supabase")
    @patch("routes.health._SITEMAP_MVS", ["mv_sitemap_cnpjs", "mv_sitemap_orgaos", "mv_sitemap_fornecedores", "mv_sitemap_municipios"])
    def test_all_mvs_checked(self, mock_get_sb, client):
        """All 4 MVs are present in the checks response."""
        mock_get_sb.return_value = _mock_sb_with_mv_counts({
            "mv_sitemap_cnpjs": 100,
            "mv_sitemap_orgaos": 100,
            "mv_sitemap_fornecedores": 100,
            "mv_sitemap_municipios": 100,
        })

        resp = client.get("/v1/health/sitemap")
        assert resp.status_code == 200
        data = resp.json()
        for mv in ["mv_sitemap_cnpjs", "mv_sitemap_orgaos", "mv_sitemap_fornecedores", "mv_sitemap_municipios"]:
            assert mv in data["checks"], f"Missing MV: {mv}"

    @patch("routes.health.get_supabase")
    @patch("routes.health._SITEMAP_MVS", ["mv_sitemap_cnpjs"])
    def test_response_has_timestamp(self, mock_get_sb, client):
        """Response includes ISO timestamp."""
        mock_get_sb.return_value = _mock_sb_with_mv_counts({"mv_sitemap_cnpjs": 5})

        resp = client.get("/v1/health/sitemap")
        data = resp.json()
        assert "timestamp" in data
        assert "T" in data["timestamp"]  # ISO format contains 'T'
