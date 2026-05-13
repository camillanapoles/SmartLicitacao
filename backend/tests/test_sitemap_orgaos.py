"""Tests for SEO SITEMAP-MV-001: /v1/sitemap/orgaos via mv_sitemap_orgaos."""

import asyncio
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear sitemap_orgaos caches between tests."""
    from routes.sitemap_orgaos import _sitemap_cache, _contratos_orgao_cache
    _sitemap_cache.clear()
    _contratos_orgao_cache.clear()
    yield
    _sitemap_cache.clear()
    _contratos_orgao_cache.clear()


@pytest.fixture
def client():
    from startup.app_factory import create_app
    app = create_app()
    return TestClient(app)


def _mock_mv_data(rows: list[dict]):
    """Build a mock for MV queries:
    sb.table("mv_sitemap_<X>").select("cnpj").order("cnpj").range(offset, end).execute()
    Simula paginação de 1000 por página.
    """
    mock_sb = MagicMock()
    page_size = 1000
    next_offset = {"value": 0}

    def execute_paginated(*_args, **_kwargs):
        resp = MagicMock()
        start = next_offset["value"]
        resp.data = rows[start: start + page_size]
        next_offset["value"] += page_size
        return resp

    (
        mock_sb.table.return_value
        .select.return_value
        .order.return_value
        .range.return_value
        .execute
    ).side_effect = execute_paginated
    return mock_sb


class TestSitemapOrgaos:
    """Tests for GET /v1/sitemap/orgaos via mv_sitemap_orgaos."""

    @patch("supabase_client.get_supabase")
    def test_returns_orgaos_from_mv(self, mock_get_sb, client):
        """MV returns CNPJs de órgãos com ≥5 licitações."""
        mock_get_sb.return_value = _mock_mv_data([
            {"cnpj": "33333333000300"},
            {"cnpj": "11111111000100"},
        ])

        resp = client.get("/v1/sitemap/orgaos")
        assert resp.status_code == 200
        data = resp.json()
        assert "33333333000300" in data["orgaos"]
        assert "11111111000100" in data["orgaos"]
        assert data["total"] == 2

    @patch("supabase_client.get_supabase")
    def test_empty_mv(self, mock_get_sb, client):
        """Empty MV returns empty list, not error."""
        mock_get_sb.return_value = _mock_mv_data([])

        resp = client.get("/v1/sitemap/orgaos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["orgaos"] == []
        assert data["total"] == 0

    @patch("supabase_client.get_supabase")
    def test_filters_invalid_cnpjs(self, mock_get_sb, client):
        """Null, empty, and short CNPJs filtered out."""
        mock_get_sb.return_value = _mock_mv_data([
            {"cnpj": None},
            {"cnpj": ""},
            {"cnpj": "123"},
            {"cnpj": "44444444000400"},
        ])

        resp = client.get("/v1/sitemap/orgaos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["orgaos"] == ["44444444000400"]
        assert data["total"] == 1

    @patch("supabase_client.get_supabase")
    def test_cache_serves_second_request(self, mock_get_sb, client):
        """Second request should be served from cache (no DB call)."""
        rows = [{"cnpj": "55555555000500"}]
        mock_get_sb.return_value = _mock_mv_data(rows)

        resp1 = client.get("/v1/sitemap/orgaos")
        assert resp1.status_code == 200

        # Reset mock — second call should NOT hit DB
        mock_get_sb.reset_mock()
        resp2 = client.get("/v1/sitemap/orgaos")
        assert resp2.status_code == 200
        assert resp2.json() == resp1.json()
        mock_get_sb.assert_not_called()

    @patch("supabase_client.get_supabase")
    def test_graceful_failure(self, mock_get_sb, client):
        """Supabase error returns empty list, not 500."""
        mock_get_sb.side_effect = Exception("Connection refused")

        resp = client.get("/v1/sitemap/orgaos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["orgaos"] == []
        assert data["total"] == 0

    @patch("supabase_client.get_supabase")
    def test_response_schema(self, mock_get_sb, client):
        """Response must have orgaos, total, updated_at fields."""
        rows = [{"cnpj": "66666666000600"}]
        mock_get_sb.return_value = _mock_mv_data(rows)

        resp = client.get("/v1/sitemap/orgaos")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["orgaos"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["updated_at"], str)

    @patch("supabase_client.get_supabase")
    def test_max_2000_orgaos(self, mock_get_sb, client):
        """Should return at most 2000 órgãos."""
        rows = [{"cnpj": f"{i:014d}"} for i in range(2500)]
        mock_get_sb.return_value = _mock_mv_data(rows)

        resp = client.get("/v1/sitemap/orgaos")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["orgaos"]) <= 2000
        assert data["total"] <= 2000


# ---------------------------------------------------------------------------
# Tests for /v1/sitemap/contratos-orgao-indexable (SEN-BE-005)
# Usa RPC get_sitemap_contratos_orgao_json para agregar no servidor.
# ---------------------------------------------------------------------------


def _mock_contratos_orgao_rpc(cnpjs: list[str]):
    """Mock for contratos_orgao RPC call.

    Simulates:
      sb.rpc("get_sitemap_contratos_orgao_json", {"max_results": 2000}).execute()
    where resp.data = cnpjs (list of CNPJ strings)
    """
    mock_sb = MagicMock()
    resp = MagicMock()
    resp.data = cnpjs
    mock_sb.rpc.return_value.execute.return_value = resp
    return mock_sb


class TestSitemapContratosOrgaoIndexable:
    """Tests for GET /v1/sitemap/contratos-orgao-indexable via RPC (SEN-BE-005)."""

    @patch("supabase_client.get_supabase")
    def test_dedup_by_rpc(self, mock_get_sb, client):
        """RPC returns deduped list (SQL GROUP BY handles dedup)."""
        mock_get_sb.return_value = _mock_contratos_orgao_rpc([
            "11111111000101",
            "22222222000202",
        ])

        resp = client.get("/v1/sitemap/contratos-orgao-indexable")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["orgaos"]) == 2
        assert len(set(data["orgaos"])) == 2, "Response contains duplicate CNPJs"

    @patch("supabase_client.get_supabase")
    def test_sorted_by_contract_count(self, mock_get_sb, client):
        """RPC already returns sorted by contract count (SQL ORDER BY)."""
        mock_get_sb.return_value = _mock_contratos_orgao_rpc([
            "22222222000202",  # most contracts first
            "33333333000303",
            "11111111000101",
        ])

        resp = client.get("/v1/sitemap/contratos-orgao-indexable")
        assert resp.status_code == 200
        data = resp.json()
        assert data["orgaos"][0] == "22222222000202"
        assert data["orgaos"][1] == "33333333000303"
        assert data["orgaos"][2] == "11111111000101"

    @patch("supabase_client.get_supabase")
    def test_filters_invalid_orgao_cnpjs(self, mock_get_sb, client):
        """Non-14-digit values excluded (Python-side validation after RPC)."""
        mock_get_sb.return_value = _mock_contratos_orgao_rpc([
            "",
            "123",
            "ABCDEFGHIJKLMN",
            "44444444000404",
        ])

        resp = client.get("/v1/sitemap/contratos-orgao-indexable")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["orgaos"] == ["44444444000404"]

    @patch("supabase_client.get_supabase")
    def test_max_2000_orgaos(self, mock_get_sb, client):
        """RPC limit 2000 — response respects _MAX_CONTRATOS_ORGAOS."""
        cnps = [f"{i:014d}" for i in range(3000)]
        mock_get_sb.return_value = _mock_contratos_orgao_rpc(cnps)

        resp = client.get("/v1/sitemap/contratos-orgao-indexable")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] <= 2000
        assert len(data["orgaos"]) <= 2000

    @patch("supabase_client.get_supabase")
    def test_graceful_failure(self, mock_get_sb, client):
        """RPC error returns empty list (not 500)."""
        mock_get_sb.side_effect = Exception("DB unavailable")

        resp = client.get("/v1/sitemap/contratos-orgao-indexable")
        assert resp.status_code == 200
        data = resp.json()
        assert data["orgaos"] == []
        assert data["total"] == 0

    @patch("supabase_client.get_supabase")
    def test_response_schema(self, mock_get_sb, client):
        """Response has orgaos, total, updated_at fields."""
        mock_get_sb.return_value = _mock_contratos_orgao_rpc(["66666666000606"])

        resp = client.get("/v1/sitemap/contratos-orgao-indexable")
        data = resp.json()
        assert isinstance(data["orgaos"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["updated_at"], str)

    @patch("supabase_client.get_supabase")
    def test_empty_datalake(self, mock_get_sb, client):
        """Empty RPC result returns empty orgaos list."""
        mock_get_sb.return_value = _mock_contratos_orgao_rpc([])

        resp = client.get("/v1/sitemap/contratos-orgao-indexable")
        assert resp.status_code == 200
        data = resp.json()
        assert data["orgaos"] == []
        assert data["total"] == 0

    @patch("supabase_client.get_supabase")
    def test_rpc_failure_fallback_empty(self, mock_get_sb, client):
        """RPC failure returns empty list (graceful degradation)."""
        from routes.sitemap_orgaos import _contratos_orgao_cache
        import time

        stale_data = {
            "orgaos": ["11111111000101"],
            "total": 1,
            "updated_at": "2026-05-01T00:00:00Z",
        }
        _contratos_orgao_cache["contratos_orgao_indexable"] = (stale_data, time.time() - 1, 0)

        # _fetch_contratos_orgao_indexable catches its own DB errors
        mock_get_sb.side_effect = Exception("RPC timeout")

        resp = client.get("/v1/sitemap/contratos-orgao-indexable")
        assert resp.status_code == 200
        data = resp.json()
        # Function catches internal errors and returns empty gracefully
        assert data["orgaos"] == []

    @patch("routes.sitemap_orgaos._run_with_budget")
    def test_stale_cache_on_budget_timeout(self, mock_run_budget, client):
        """When _run_with_budget raises TimeoutError and stale cache exists, serve stale."""
        from routes.sitemap_orgaos import _contratos_orgao_cache
        import time

        stale_data = {
            "orgaos": ["33333333000303"],
            "total": 1,
            "updated_at": "2026-05-01T00:00:00Z",
        }
        _contratos_orgao_cache["contratos_orgao_indexable"] = (stale_data, time.time() - 1, 0)

        mock_run_budget.side_effect = asyncio.TimeoutError()

        resp = client.get("/v1/sitemap/contratos-orgao-indexable")
        assert resp.status_code == 200
        data = resp.json()
        assert data["orgaos"] == ["33333333000303"]
        assert data["total"] == 1

    @patch("routes.sitemap_orgaos._run_with_budget")
    def test_503_when_no_stale_cache_on_timeout(self, mock_run_budget, client):
        """When budget times out and no stale cache, return 503."""
        mock_run_budget.side_effect = asyncio.TimeoutError()

        resp = client.get("/v1/sitemap/contratos-orgao-indexable")
        assert resp.status_code == 503
        data = resp.json()
        assert data["detail"] == "sitemap_source_timeout"
