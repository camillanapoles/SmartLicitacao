"""Tests for utils/revalidate_client.py — fire-and-forget ISR revalidation client.

Covers:
- Happy path: sends correct POST with secret header.
- Silent skip when env vars are missing.
- HTTP error → logs warning, does not propagate exception.
- Empty paths → no HTTP call.
"""

from __future__ import annotations

import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx


@pytest.mark.asyncio
async def test_happy_path_sends_correct_post(monkeypatch):
    """revalidate_paths sends POST with json body and x-revalidate-secret header."""
    monkeypatch.setenv("FRONTEND_REVALIDATE_URL", "https://smartlic.tech/api/revalidate")
    monkeypatch.setenv("REVALIDATE_SECRET", "test-secret-xyz")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from utils.revalidate_client import revalidate_paths

        await revalidate_paths(["/licitacoes/saude", "/observatorio/raio-x-maio-2026"])

    mock_client.post.assert_called_once_with(
        "https://smartlic.tech/api/revalidate",
        json={"paths": ["/licitacoes/saude", "/observatorio/raio-x-maio-2026"]},
        headers={"x-revalidate-secret": "test-secret-xyz"},
    )
    mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_missing_url_env_var_skips_silently(monkeypatch):
    """When FRONTEND_REVALIDATE_URL is unset, no HTTP call is made and no exception raised."""
    monkeypatch.delenv("FRONTEND_REVALIDATE_URL", raising=False)
    monkeypatch.setenv("REVALIDATE_SECRET", "test-secret-xyz")

    with patch("httpx.AsyncClient") as mock_cls:
        from utils.revalidate_client import revalidate_paths

        # Should not raise
        await revalidate_paths(["/licitacoes/saude"])

    mock_cls.assert_not_called()


@pytest.mark.asyncio
async def test_missing_secret_env_var_skips_silently(monkeypatch):
    """When REVALIDATE_SECRET is unset, no HTTP call is made and no exception raised."""
    monkeypatch.setenv("FRONTEND_REVALIDATE_URL", "https://smartlic.tech/api/revalidate")
    monkeypatch.delenv("REVALIDATE_SECRET", raising=False)

    with patch("httpx.AsyncClient") as mock_cls:
        from utils.revalidate_client import revalidate_paths

        # Should not raise
        await revalidate_paths(["/licitacoes/saude"])

    mock_cls.assert_not_called()


@pytest.mark.asyncio
async def test_http_error_logs_warning_does_not_raise(monkeypatch, caplog):
    """When the HTTP call raises an exception, a warning is logged and no exception propagates."""
    monkeypatch.setenv("FRONTEND_REVALIDATE_URL", "https://smartlic.tech/api/revalidate")
    monkeypatch.setenv("REVALIDATE_SECRET", "test-secret-xyz")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        with caplog.at_level(logging.WARNING, logger="utils.revalidate_client"):
            from utils.revalidate_client import revalidate_paths

            # Must not raise
            await revalidate_paths(["/licitacoes/saude"])

    assert any("seo_revalidate failed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_http_4xx_error_logs_warning_does_not_raise(monkeypatch, caplog):
    """When the HTTP response is a 4xx/5xx, raise_for_status raises but does not propagate."""
    monkeypatch.setenv("FRONTEND_REVALIDATE_URL", "https://smartlic.tech/api/revalidate")
    monkeypatch.setenv("REVALIDATE_SECRET", "test-secret-xyz")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=MagicMock(status_code=401),
        )
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with caplog.at_level(logging.WARNING, logger="utils.revalidate_client"):
            from utils.revalidate_client import revalidate_paths

            # Must not raise
            await revalidate_paths(["/licitacoes/saude"])

    assert any("seo_revalidate failed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_empty_paths_skips_http_call(monkeypatch):
    """When paths is an empty list, no HTTP call is made."""
    monkeypatch.setenv("FRONTEND_REVALIDATE_URL", "https://smartlic.tech/api/revalidate")
    monkeypatch.setenv("REVALIDATE_SECRET", "test-secret-xyz")

    with patch("httpx.AsyncClient") as mock_cls:
        from utils.revalidate_client import revalidate_paths

        await revalidate_paths([])

    mock_cls.assert_not_called()
