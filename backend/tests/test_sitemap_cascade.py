"""SEO-SITEMAP-CASCADE-001: Tests for 503 on timeout + no negative cache.

Regression guard for the cascade bug where backend returned 200+[] on DB timeout,
which poisoned the ISR cache for 5min → frontend silently cached an empty sitemap
for 1h → Google received XML with zero URLs → GSC "Não foi possível buscar".

Fix: backend now raises HTTPException(503) on asyncio.TimeoutError in all
sitemap routes, and does NOT write to in-memory cache on timeout.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from startup.app_factory import create_app
    app = create_app()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_all_sitemap_caches():
    """Clear all in-memory sitemap caches before and after each test."""
    from routes.sitemap_cnpjs import _sitemap_cache, _fornecedores_sitemap_cache
    from routes.sitemap_licitacoes_do_dia import _cache as _dates_cache
    from routes.sitemap_orgaos import _sitemap_cache as _orgao_cache, _contratos_orgao_cache
    import routes.sitemap_licitacoes as _licit_mod

    _sitemap_cache.clear()
    _fornecedores_sitemap_cache.clear()
    _dates_cache.clear()
    _orgao_cache.clear()
    _contratos_orgao_cache.clear()
    _licit_mod._cache = None

    yield

    _sitemap_cache.clear()
    _fornecedores_sitemap_cache.clear()
    _dates_cache.clear()
    _orgao_cache.clear()
    _contratos_orgao_cache.clear()
    _licit_mod._cache = None


class TestSitemapCnpjsTimeout:
    """sitemap_cnpjs: timeout → 503, cache stays empty."""

    @patch("routes.sitemap_cnpjs._run_with_budget", side_effect=asyncio.TimeoutError())
    def test_timeout_returns_503(self, _mock_budget, client):
        """asyncio.TimeoutError in sitemap_cnpjs must return HTTP 503."""
        response = client.get("/v1/sitemap/cnpjs")
        assert response.status_code == 503
        assert response.json()["detail"] == "sitemap_source_timeout"

    @patch("routes.sitemap_cnpjs._run_with_budget", side_effect=asyncio.TimeoutError())
    def test_timeout_does_not_populate_cache(self, _mock_budget, client):
        """503 timeout must NOT write an empty entry to the in-memory cache."""
        from routes.sitemap_cnpjs import _sitemap_cache
        client.get("/v1/sitemap/cnpjs")
        # Cache must remain empty — no negative cache entry.
        assert "cnpjs" not in _sitemap_cache

    @patch("routes.sitemap_cnpjs._run_with_budget", side_effect=asyncio.TimeoutError())
    def test_second_request_after_timeout_also_hits_db(self, mock_budget, client):
        """Without cache poisoning, each 503 response re-queries the DB."""
        client.get("/v1/sitemap/cnpjs")
        client.get("/v1/sitemap/cnpjs")
        assert mock_budget.call_count == 2


class TestSitemapFornecedoresTimeout:
    """sitemap_fornecedores_cnpj: timeout → 503, cache stays empty."""

    @patch("routes.sitemap_cnpjs._run_with_budget", side_effect=asyncio.TimeoutError())
    def test_timeout_returns_503(self, _mock_budget, client):
        response = client.get("/v1/sitemap/fornecedores-cnpj")
        assert response.status_code == 503
        assert response.json()["detail"] == "sitemap_source_timeout"

    @patch("routes.sitemap_cnpjs._run_with_budget", side_effect=asyncio.TimeoutError())
    def test_timeout_does_not_populate_cache(self, _mock_budget, client):
        from routes.sitemap_cnpjs import _fornecedores_sitemap_cache
        client.get("/v1/sitemap/fornecedores-cnpj")
        assert "fornecedores_cnpj" not in _fornecedores_sitemap_cache


class TestSitemapOrgaosTimeout:
    """sitemap_orgaos: timeout → 503, cache stays empty."""

    @patch("routes.sitemap_orgaos._run_with_budget", side_effect=asyncio.TimeoutError())
    def test_timeout_returns_503(self, _mock_budget, client):
        response = client.get("/v1/sitemap/orgaos")
        assert response.status_code == 503
        assert response.json()["detail"] == "sitemap_source_timeout"

    @patch("routes.sitemap_orgaos._run_with_budget", side_effect=asyncio.TimeoutError())
    def test_timeout_does_not_populate_cache(self, _mock_budget, client):
        from routes.sitemap_orgaos import _sitemap_cache
        client.get("/v1/sitemap/orgaos")
        assert "orgaos" not in _sitemap_cache


class TestSitemapContratosOrgaoTimeout:
    """sitemap_contratos_orgao_indexable: timeout → 503, cache stays empty."""

    @patch("routes.sitemap_orgaos._run_with_budget", side_effect=asyncio.TimeoutError())
    def test_timeout_returns_503(self, _mock_budget, client):
        response = client.get("/v1/sitemap/contratos-orgao-indexable")
        assert response.status_code == 503
        assert response.json()["detail"] == "sitemap_source_timeout"

    @patch("routes.sitemap_orgaos._run_with_budget", side_effect=asyncio.TimeoutError())
    def test_timeout_does_not_populate_cache(self, _mock_budget, client):
        from routes.sitemap_orgaos import _contratos_orgao_cache
        client.get("/v1/sitemap/contratos-orgao-indexable")
        assert "contratos_orgao_indexable" not in _contratos_orgao_cache


class TestSitemapLicitacoesDoDialTimeout:
    """sitemap_licitacoes_do_dia: timeout → 503, cache stays empty."""

    @patch("routes.sitemap_licitacoes_do_dia._run_with_budget", side_effect=asyncio.TimeoutError())
    def test_timeout_returns_503(self, _mock_budget, client):
        response = client.get("/v1/sitemap/licitacoes-do-dia-indexable")
        assert response.status_code == 503
        assert response.json()["detail"] == "sitemap_source_timeout"

    @patch("routes.sitemap_licitacoes_do_dia._run_with_budget", side_effect=asyncio.TimeoutError())
    def test_timeout_does_not_populate_cache(self, _mock_budget, client):
        from routes.sitemap_licitacoes_do_dia import _cache
        client.get("/v1/sitemap/licitacoes-do-dia-indexable")
        assert "dates" not in _cache


class TestSitemapLicitacoesIndexableTimeout:
    """sitemap_licitacoes_indexable: timeout → 503, cache stays None.

    Note: this route uses asyncio.wait_for directly (not _run_with_budget).
    The route-level timeout middleware (RES-BE-016 AC4, 60s) may intercept
    the TimeoutError before the route handler. Either way the response is 503
    — the key invariant is that the in-memory cache is NOT poisoned.
    """

    @patch("routes.sitemap_licitacoes.asyncio.wait_for", side_effect=asyncio.TimeoutError())
    def test_timeout_returns_503(self, _mock_wait, client):
        response = client.get("/v1/sitemap/licitacoes-indexable")
        # Both the route handler and the middleware produce 503 on timeout.
        assert response.status_code == 503

    @patch("routes.sitemap_licitacoes.asyncio.wait_for", side_effect=asyncio.TimeoutError())
    def test_timeout_does_not_populate_cache(self, _mock_wait, client):
        import routes.sitemap_licitacoes as mod
        client.get("/v1/sitemap/licitacoes-indexable")
        assert mod._cache is None


class TestSitemapSuccessPath:
    """Verify that successful requests still cache and return 200."""

    @patch("routes.sitemap_cnpjs._SEED_SUPPLIER_CNPJS", [])
    @patch("routes.sitemap_cnpjs._run_with_budget")
    def test_success_returns_200_and_caches(self, mock_budget, client):
        """Successful DB response returns 200 and stores in cache."""
        from datetime import datetime, timezone
        mock_budget.return_value = {
            "cnpjs": ["11111111000100"],
            "total": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        # mock_budget is an async-compatible MagicMock via TestClient sync context
        # but _run_with_budget is awaited — wrap return in coroutine
        async def fake_budget(*args, **kwargs):
            return mock_budget.return_value
        mock_budget.side_effect = fake_budget

        response = client.get("/v1/sitemap/cnpjs")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert "11111111000100" in body["cnpjs"]

        from routes.sitemap_cnpjs import _sitemap_cache
        assert "cnpjs" in _sitemap_cache
