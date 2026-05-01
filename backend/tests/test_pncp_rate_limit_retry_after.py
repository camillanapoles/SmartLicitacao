"""Tests for issue #209 — PNCPRateLimitError carries retry_after on 429 exhaustion."""
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from exceptions import PNCPAPIError, PNCPRateLimitError


class TestPNCPRateLimitErrorAttribute:
    def test_has_retry_after_default(self):
        err = PNCPRateLimitError("rate limited")
        assert err.retry_after == 60

    def test_has_retry_after_custom(self):
        err = PNCPRateLimitError("rate limited", retry_after=120)
        assert err.retry_after == 120

    def test_is_subclass_of_pncp_api_error(self):
        err = PNCPRateLimitError("x")
        assert isinstance(err, PNCPAPIError)


class TestSyncClientRateLimitExhaustion:
    def _make_response(self, status_code, retry_after=None):
        resp = MagicMock()
        resp.status_code = status_code
        headers = {}
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        resp.headers = headers
        return resp

    def test_all_429_raises_rate_limit_error(self):
        from clients.pncp.sync_client import PNCPClient
        from config import RetryConfig

        config = RetryConfig(max_retries=1)
        client = PNCPClient(config=config)

        resp_429 = self._make_response(429, retry_after=30)
        with patch.object(client.session, "get", return_value=resp_429), \
             patch("time.sleep"):
            with pytest.raises(PNCPRateLimitError) as exc_info:
                client.fetch_page("2026-01-01", "2026-01-10", 6, uf="SP")

        assert exc_info.value.retry_after == 30

    def test_429_then_500_raises_api_error(self):
        from clients.pncp.sync_client import PNCPClient
        from config import RetryConfig

        config = RetryConfig(max_retries=1)
        client = PNCPClient(config=config)

        resp_429 = self._make_response(429, retry_after=15)
        resp_500 = self._make_response(500)
        responses = iter([resp_429, resp_500])

        with patch.object(client.session, "get", side_effect=lambda *a, **kw: next(responses)), \
             patch("time.sleep"):
            with pytest.raises(PNCPAPIError) as exc_info:
                client.fetch_page("2026-01-01", "2026-01-10", 6, uf="SP")

        assert not isinstance(exc_info.value, PNCPRateLimitError)

    def test_429_then_200_returns_result(self):
        from clients.pncp.sync_client import PNCPClient
        from config import RetryConfig

        config = RetryConfig(max_retries=1)
        client = PNCPClient(config=config)

        resp_429 = self._make_response(429, retry_after=5)

        resp_200 = self._make_response(200)
        resp_200.headers = {"content-type": "application/json"}
        resp_200.json.return_value = {"data": [], "totalRegistros": 0, "totalPaginas": 1}

        responses = iter([resp_429, resp_200])

        with patch.object(client.session, "get", side_effect=lambda *a, **kw: next(responses)), \
             patch("time.sleep"):
            result = client.fetch_page("2026-01-01", "2026-01-10", 6, uf="SP")

        assert result["totalRegistros"] == 0


class TestAsyncClientRateLimitExhaustion:
    def _make_response(self, status_code, retry_after=None):
        resp = MagicMock()
        resp.status_code = status_code
        headers = {}
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        resp.headers = headers
        return resp

    @pytest.mark.asyncio
    async def test_all_429_raises_rate_limit_error(self):
        from clients.pncp.async_client import AsyncPNCPClient
        from config import RetryConfig
        import httpx

        config = RetryConfig(max_retries=1)

        resp_429 = self._make_response(429, retry_after=45)
        mock_get = AsyncMock(return_value=resp_429)

        async with AsyncPNCPClient(config=config) as client:
            with patch.object(client._client, "get", mock_get), \
                 patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(PNCPRateLimitError) as exc_info:
                    await client._fetch_page_async("2026-01-01", "2026-01-10", 6, uf="SP")

        assert exc_info.value.retry_after == 45

    @pytest.mark.asyncio
    async def test_429_then_200_returns_result(self):
        from clients.pncp.async_client import AsyncPNCPClient
        from config import RetryConfig

        config = RetryConfig(max_retries=1)

        resp_429 = self._make_response(429, retry_after=5)
        resp_200 = self._make_response(200)
        resp_200.headers = {"content-type": "application/json"}
        resp_200.json.return_value = {"data": [], "totalRegistros": 0, "totalPaginas": 1}

        responses = iter([resp_429, resp_200])

        async def side_effect(*a, **kw):
            return next(responses)

        async with AsyncPNCPClient(config=config) as client:
            with patch.object(client._client, "get", side_effect=side_effect), \
                 patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client._fetch_page_async("2026-01-01", "2026-01-10", 6, uf="SP")

        assert result["totalRegistros"] == 0
