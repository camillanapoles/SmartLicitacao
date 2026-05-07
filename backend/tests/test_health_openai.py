"""TD-BE-025: Tests for check_openai_health() — OpenAI connectivity probe.

Covers:
- ok status when API responds successfully (mocked)
- degraded status on timeout (mocked)
- not_configured when OPENAI_API_KEY is absent
- 5-minute in-memory cache behaviour
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import health as health_module
from health import check_openai_health


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_cache():
    """Clear the module-level cache between tests."""
    health_module._openai_health_cache = None


# Mock AsyncOpenAI at the openai module level since the function does a local import
_MOCK_TARGET = "openai.AsyncOpenAI"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCheckOpenaiHealth:
    """Unit tests for check_openai_health()."""

    @pytest.mark.asyncio
    async def test_returns_ok_when_api_accessible(self):
        """When models.list() succeeds, status must be 'ok' with latency_ms."""
        _reset_cache()

        mock_client = MagicMock()
        mock_client.models.list = AsyncMock(return_value=MagicMock())

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            with patch(_MOCK_TARGET, return_value=mock_client):
                result = await check_openai_health()

        assert result["status"] == "ok"
        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], float)
        assert result.get("cached") is False

    @pytest.mark.asyncio
    async def test_returns_degraded_on_timeout(self):
        """When models.list() raises a timeout-like exception, status is 'degraded'."""
        _reset_cache()

        import openai

        mock_client = MagicMock()
        mock_client.models.list = AsyncMock(
            side_effect=openai.APITimeoutError(request=MagicMock())
        )

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            with patch(_MOCK_TARGET, return_value=mock_client):
                result = await check_openai_health()

        assert result["status"] == "degraded"
        assert "latency_ms" in result
        assert "error" in result
        assert result.get("cached") is False

    @pytest.mark.asyncio
    async def test_returns_not_configured_when_no_api_key(self):
        """When OPENAI_API_KEY is absent, must return not_configured without calling API."""
        _reset_cache()

        import os as _os
        original = _os.environ.pop("OPENAI_API_KEY", None)
        try:
            with patch(_MOCK_TARGET) as mock_cls:
                result = await check_openai_health()
            mock_cls.assert_not_called()
        finally:
            if original is not None:
                _os.environ["OPENAI_API_KEY"] = original

        assert result["status"] == "not_configured"
        assert "latency_ms" not in result

    @pytest.mark.asyncio
    async def test_cache_prevents_repeated_calls_within_ttl(self):
        """Second call within TTL must return cached=True without calling AsyncOpenAI again."""
        _reset_cache()

        mock_client = MagicMock()
        mock_client.models.list = AsyncMock(return_value=MagicMock())

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            with patch(_MOCK_TARGET, return_value=mock_client) as mock_cls:
                first = await check_openai_health()
                second = await check_openai_health()

        # AsyncOpenAI constructor should only have been called once
        assert mock_cls.call_count == 1
        assert first.get("cached") is False
        assert second.get("cached") is True
        assert second["status"] == "ok"

    @pytest.mark.asyncio
    async def test_cache_refreshes_after_ttl_expiry(self):
        """After TTL expires the probe must run again (cached=False)."""
        _reset_cache()

        mock_client = MagicMock()
        mock_client.models.list = AsyncMock(return_value=MagicMock())

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            with patch(_MOCK_TARGET, return_value=mock_client) as mock_cls:
                # Populate cache
                await check_openai_health()

                # Manually expire the cache
                cached_result, _ = health_module._openai_health_cache
                health_module._openai_health_cache = (cached_result, time.monotonic() - 1)

                # Second call should bypass cache
                second = await check_openai_health()

        assert mock_cls.call_count == 2
        assert second.get("cached") is False

    @pytest.mark.asyncio
    async def test_returns_degraded_on_connection_error(self):
        """Any non-timeout exception also results in 'degraded'."""
        _reset_cache()

        mock_client = MagicMock()
        mock_client.models.list = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            with patch(_MOCK_TARGET, return_value=mock_client):
                result = await check_openai_health()

        assert result["status"] == "degraded"
        assert result.get("error") == "Exception"
