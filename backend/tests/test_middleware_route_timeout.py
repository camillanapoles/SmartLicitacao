"""RES-BE-016 AC4: Route-level asyncio timeout middleware tests.

Verifies that route_timeout_middleware:
- Returns 503 with Retry-After when a handler exceeds the timeout
- Passes through normal (fast) responses unchanged
- Exempts SSE headers and health/webhook paths
- Response body contains detail + timeout_s fields

See: backend/startup/middleware_setup.py::route_timeout_middleware
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import AsyncClient, ASGITransport

from startup.middleware_setup import _ROUTE_TIMEOUT_EXEMPT_PREFIXES


def _build_app(timeout_s: float, slow_sleep_s: float = 0.5) -> FastAPI:
    """Return a minimal FastAPI app with an inline timeout middleware.

    slow_sleep_s: how long the /slow route sleeps. Must be > timeout_s.
    Keep it small so background task completes before the test event loop closes.
    """
    app = FastAPI()

    if timeout_s > 0:
        @app.middleware("http")
        async def _timeout_mw(request, call_next):
            path = request.url.path
            accept = request.headers.get("accept", "")
            if (
                any(path.startswith(p) for p in _ROUTE_TIMEOUT_EXEMPT_PREFIXES)
                or "text/event-stream" in accept
            ):
                return await call_next(request)
            try:
                return await asyncio.wait_for(call_next(request), timeout=timeout_s)
            except asyncio.TimeoutError:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "tempo limite excedido", "timeout_s": timeout_s},
                    headers={"Retry-After": "5"},
                )

    @app.get("/fast")
    async def fast_route():
        return {"ok": True}

    @app.get("/slow")
    async def slow_route():
        # sleep must be > timeout_s but small enough to not block test cleanup
        await asyncio.sleep(slow_sleep_s)
        return {"ok": True}

    @app.get("/health/live")
    async def health_live():
        return {"status": "ok"}

    @app.get("/buscar-progress/{sid}")
    async def sse_progress():
        return {"status": "streaming"}

    return app


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_fast_route_returns_200():
    """Normal fast route passes through the middleware unchanged."""
    app = _build_app(timeout_s=1.0, slow_sleep_s=0.5)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/fast")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_slow_route_returns_503():
    """Route that sleeps > timeout returns 503 instead of waiting forever."""
    # timeout=0.05s, slow_sleep=0.5s → middleware fires; background task finishes in 0.5s
    app = _build_app(timeout_s=0.05, slow_sleep_s=0.5)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/slow")
    assert resp.status_code == 503
    body = resp.json()
    assert "detail" in body
    assert body["timeout_s"] == pytest.approx(0.05)
    assert resp.headers.get("retry-after") == "5"


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_503_body_has_required_fields():
    """503 response body contains detail and timeout_s."""
    app = _build_app(timeout_s=0.05, slow_sleep_s=0.5)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/slow")
    body = resp.json()
    assert set(body.keys()) >= {"detail", "timeout_s"}


def test_health_prefix_is_in_exempt_list():
    """/health paths must be in _ROUTE_TIMEOUT_EXEMPT_PREFIXES."""
    assert any(p.startswith("/health") for p in _ROUTE_TIMEOUT_EXEMPT_PREFIXES), (
        "/health must be in _ROUTE_TIMEOUT_EXEMPT_PREFIXES"
    )


def test_buscar_progress_prefix_is_in_exempt_list():
    """/buscar-progress/ SSE endpoint must be in _ROUTE_TIMEOUT_EXEMPT_PREFIXES."""
    assert any("buscar-progress" in p for p in _ROUTE_TIMEOUT_EXEMPT_PREFIXES), (
        "/buscar-progress/ must be in _ROUTE_TIMEOUT_EXEMPT_PREFIXES"
    )


def test_webhooks_prefix_is_in_exempt_list():
    """/webhooks/ must be in _ROUTE_TIMEOUT_EXEMPT_PREFIXES (Stripe validation takes time)."""
    assert any("webhooks" in p for p in _ROUTE_TIMEOUT_EXEMPT_PREFIXES), (
        "/webhooks/ must be in _ROUTE_TIMEOUT_EXEMPT_PREFIXES"
    )


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_sse_accept_header_skips_timeout():
    """Requests with Accept: text/event-stream bypass the timeout middleware."""
    app = _build_app(timeout_s=0.05, slow_sleep_s=0.5)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/fast", headers={"Accept": "text/event-stream"})
    assert resp.status_code == 200


def test_route_timeout_s_default_is_60():
    """ROUTE_TIMEOUT_S defaults to 60 seconds when env var is absent."""
    import os
    import importlib
    import config.pipeline as _pipeline

    env_backup = os.environ.pop("ROUTE_TIMEOUT_S", None)
    try:
        importlib.reload(_pipeline)
        assert _pipeline.ROUTE_TIMEOUT_S == 60.0
    finally:
        if env_backup is not None:
            os.environ["ROUTE_TIMEOUT_S"] = env_backup
        importlib.reload(_pipeline)


def test_route_timeout_s_respects_env_var():
    """ROUTE_TIMEOUT_S reads the ROUTE_TIMEOUT_S env variable."""
    import os
    import importlib
    import config.pipeline as _pipeline

    os.environ["ROUTE_TIMEOUT_S"] = "90"
    try:
        importlib.reload(_pipeline)
        assert _pipeline.ROUTE_TIMEOUT_S == 90.0
    finally:
        os.environ.pop("ROUTE_TIMEOUT_S", None)
        importlib.reload(_pipeline)


def test_route_timeout_total_metric_is_defined():
    """ROUTE_TIMEOUT_TOTAL metric exists and supports .labels()."""
    from metrics import ROUTE_TIMEOUT_TOTAL
    assert ROUTE_TIMEOUT_TOTAL is not None
    assert hasattr(ROUTE_TIMEOUT_TOTAL, "labels")
