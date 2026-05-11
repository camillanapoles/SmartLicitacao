"""Tests for SEO-COVERAGE-MANIFEST-001: /v1/seo/coverage-manifest endpoint.

Adapted for the deployed route format (flat manifest with composite keys).
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _clear_cache():
    from routes.seo_coverage_manifest import _coverage_cache
    _coverage_cache.clear()
    yield
    _coverage_cache.clear()


@pytest.fixture
def client():
    from startup.app_factory import create_app
    app = create_app()
    return TestClient(app)


def _mock_sb_with_rows(rows: list[dict]):
    """Mock supabase client chain for the paginated _fetch_manifest query.

    Chain: table().select().range().execute
    First call returns rows; second call returns empty (exits pagination loop).
    """
    mock_sb = MagicMock()

    execute_fn = MagicMock(name="execute")
    resp_page1 = MagicMock(name="page1")
    resp_page1.data = rows
    resp_page2 = MagicMock(name="page2")
    resp_page2.data = []
    execute_fn.side_effect = [resp_page1, resp_page2]

    mock_sb.table.return_value.select.return_value.range.return_value.execute = execute_fn

    return mock_sb


class TestCoverageManifestEndpoint:
    """Tests for GET /v1/seo/coverage-manifest."""

    @patch("supabase_client.get_supabase")
    def test_returns_200_with_empty_manifest(self, mock_get_sb, client):
        mock_get_sb.return_value = _mock_sb_with_rows([])
        resp = client.get("/v1/seo/coverage-manifest")
        assert resp.status_code == 200
        body = resp.json()
        assert "manifest" in body
        assert "total_entities" in body
        assert body["total_entities"] == 0

    @patch("supabase_client.get_supabase")
    def test_returns_manifest_with_entries(self, mock_get_sb, client):
        rows = [
            {
                "entity_type": "municipio",
                "slug": "sao-paulo-sp",
                "coverage_status": "full",
                "bid_count": 145,
                "last_updated": "2026-05-11T06:00:00+00:00",
            },
            {
                "entity_type": "municipio",
                "slug": "guaranesia-mg",
                "coverage_status": "empty",
                "bid_count": 0,
                "last_updated": "2026-05-11T06:00:00+00:00",
            },
        ]
        mock_get_sb.return_value = _mock_sb_with_rows(rows)
        resp = client.get("/v1/seo/coverage-manifest")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_entities"] == 2
        assert "municipio/sao-paulo-sp" in body["manifest"]
        assert body["manifest"]["municipio/sao-paulo-sp"]["coverage_status"] == "full"
        assert body["manifest"]["municipio/sao-paulo-sp"]["bid_count"] == 145
        assert body["manifest"]["municipio/guaranesia-mg"]["coverage_status"] == "empty"
        assert body["manifest"]["municipio/guaranesia-mg"]["bid_count"] == 0

    @patch("supabase_client.get_supabase")
    def test_returns_cache_control_header(self, mock_get_sb, client):
        mock_get_sb.return_value = _mock_sb_with_rows([])
        resp = client.get("/v1/seo/coverage-manifest")
        assert "Cache-Control" in resp.headers
        assert "max-age=3600" in resp.headers["Cache-Control"]

    @patch("supabase_client.get_supabase")
    def test_in_memory_cache_prevents_second_db_call(self, mock_get_sb, client):
        mock_get_sb.return_value = _mock_sb_with_rows([])
        client.get("/v1/seo/coverage-manifest")
        client.get("/v1/seo/coverage-manifest")
        # supabase called only once (cache hit on second request);
        # get_supabase may be called from middleware/lifespan so check table was called once
        table_calls = mock_get_sb.return_value.table.call_count
        assert table_calls <= 1

    @patch("supabase_client.get_supabase")
    def test_graceful_fallback_on_db_error(self, mock_get_sb, client):
        mock_get_sb.side_effect = Exception("DB unavailable")
        resp = client.get("/v1/seo/coverage-manifest")
        # Should not 500 — returns empty manifest
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_entities"] == 0
        assert body["manifest"] == {}
