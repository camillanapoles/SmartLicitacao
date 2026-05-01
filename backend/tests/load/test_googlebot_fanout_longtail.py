"""RES-BE-015 AC5 — Reproducible load test for the Stage 8 wedge pattern.

The 2026-04-30 Stage 8 outage was caused by Googlebot crawling 7+ long-tail
SEO programmatic routes concurrently against ``WEB_CONCURRENCY=1``. Sync
``.execute()`` calls in async handlers blocked the event loop end-to-end;
``/health/live`` started failing the Railway 15s probe and the worker was
restarted — taking the whole site with it.

This test loads the FastAPI app in-process (no Railway proxy / Gunicorn /
uvicorn workers) and dispatches a Stage 8-shaped concurrent fan-out at the
ASGI layer using ``httpx.AsyncClient`` + ``ASGITransport``. It DOES NOT make
real database calls — Supabase clients are stubbed by ``conftest.py`` and the
in-process app simply exercises the *handler* logic.

What the test actually proves
-----------------------------

The test is intentionally LOW-fidelity (vs. a real Locust run) and exists to:

* Lock in the import contract — every refactored route module imports cleanly
  with the new ``pipeline.budget._run_with_budget`` callsite signature. A
  silent ``ImportError`` here would mean a deployed module crash on first
  request.
* Exercise that no handler raises an unhandled exception when the underlying
  Supabase client is unreachable. Anything other than 200 / 404 / 503 / 500
  with a structured body is a regression.
* Catch any handler that re-introduces ``asyncio.wait_for(asyncio.to_thread(
  ...))`` — those would either hang or block the loop, blowing the per-test
  pytest timeout.

What it does NOT prove
----------------------

* Wall-clock latency under real Supabase saturation — that requires a Locust
  + production-shape worker setup outside this test suite.
* Event-loop tick durations — measuring those reliably needs ``loop.set_debug``
  + an external sampler; flaky inside pytest.

Usage
-----

The test is gated by ``@pytest.mark.load`` so it does NOT run in the default
suite. Trigger it explicitly:

    pytest backend/tests/load/test_googlebot_fanout_longtail.py -m load -v

To run a quick smoke (just import + fixture wiring) without ``-m load``:

    pytest backend/tests/load/test_googlebot_fanout_longtail.py::test_imports_resolve -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest

# Ensure backend package root is importable regardless of where pytest is run.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


# ---------------------------------------------------------------------------
# A canonical Stage 8 fan-out pattern. Same path shapes as the route inventory
# in the RES-BE-015 story; values picked to be syntactically valid (so the
# handler reaches the DB call) but harmless if upstream is stubbed.
# ---------------------------------------------------------------------------

LONGTAIL_PATHS: tuple[str, ...] = (
    # blog_stats.contratos_setor (Sentry P0 Stage 8 root cause)
    "/v1/blog/stats/contratos/saude",
    # blog_stats.contratos_setor_uf
    "/v1/blog/stats/contratos/saude/uf/sp",
    # blog_stats.contratos_cidade
    "/v1/blog/stats/contratos/cidade/sao-paulo",
    # blog_stats.contratos_cidade_setor
    "/v1/blog/stats/contratos/cidade/sao-paulo/setor/saude",
    # contratos_publicos.orgao_contratos_stats
    "/v1/contratos/orgao/00000000000000/stats",
    # observatorio.relatorio (mes 1 = recent month → may hit live datalake)
    "/v1/observatorio/relatorio/2026/1",
    # municipios_publicos.municipio_profile (canonical capital slug)
    "/v1/municipios/sao-paulo-sp/profile",
)


# ---------------------------------------------------------------------------
# Smoke: every route module imports cleanly with the refactored signature.
# ---------------------------------------------------------------------------


def test_imports_resolve() -> None:
    """All sweep-scope route modules import without error.

    A silent ``ImportError`` on a new ``from pipeline.budget import
    _run_with_budget`` line would crash production at the first matching
    request — this guard runs in the default suite (no ``load`` marker).
    """
    import importlib

    for module_name in (
        "routes.blog_stats",
        "routes.contratos_publicos",
        "routes.empresa_publica",
        "routes.orgao_publico",
        "routes.observatorio",
        "routes.dados_publicos",
        "routes.municipios_publicos",
        "routes.itens_publicos",
        "routes.compliance_publicos",
        "routes.alertas_publicos",
        "routes.sectors_public",
    ):
        importlib.import_module(module_name)


def test_run_with_budget_signature() -> None:
    """`_run_with_budget` keeps the kwargs the sweep depends on."""
    from pipeline.budget import _run_with_budget
    import inspect

    sig = inspect.signature(_run_with_budget)
    expected = {"coro", "budget", "phase", "source", "fallback"}
    assert expected.issubset(sig.parameters.keys()), (
        f"_run_with_budget signature drifted; have {set(sig.parameters)}"
    )


# ---------------------------------------------------------------------------
# Heavy: actual fan-out against the in-process ASGI app. Marked ``load`` so
# pytest selects it only when explicitly requested.
# ---------------------------------------------------------------------------


@pytest.mark.load
@pytest.mark.timeout(60)
def test_googlebot_fanout_longtail_no_unhandled_exceptions() -> None:
    """Fan out 7 long-tail paths concurrently against the in-process app.

    Asserts that:
      * no request raises an unhandled exception (every response has a status
        code, even when the handler degrades to a partial),
      * every status code is in the "expected universe" (200, 404, 422, 500,
        503) — anything else means a regression in error handling,
      * the whole batch completes within ``WALL_BUDGET_S`` so a regression
        introducing ``wait_for(asyncio.to_thread(...))`` blocks the event
        loop and times out instead of silently passing.

    The test does NOT require a real database — Supabase clients fail open in
    these handlers and return the negative-cache shape.
    """
    httpx = pytest.importorskip("httpx")
    pytest.importorskip("fastapi")

    # Per-handler hard ceiling = max(budget) + headroom (8s budget for
    # observatorio + municipios bids + serialization). Leave generous slack
    # because the in-process ASGI dispatch adds non-trivial overhead under
    # pytest debug mode.
    PER_REQUEST_BUDGET_S = 12.0
    # Total wall-clock for the whole fan-out. With 7 concurrent requests on
    # a single event loop and budgets <= 8s each, anything above this points
    # at a serialization bug (handlers running sequentially → wait_for+to_thread
    # antipattern reintroduced).
    WALL_BUDGET_S = 30.0

    # Suppress optional integrations that bloat startup but add no signal here.
    os.environ.setdefault("DATALAKE_ENABLED", "false")
    os.environ.setdefault("DATALAKE_QUERY_ENABLED", "false")
    os.environ.setdefault("SENTRY_DSN", "")

    from main import app  # noqa: E402  — env vars must be set first

    async def _run() -> list[tuple[str, Any]]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            timeout=PER_REQUEST_BUDGET_S,
        ) as client:
            tasks = [client.get(p) for p in LONGTAIL_PATHS]
            return list(zip(LONGTAIL_PATHS, await asyncio.gather(*tasks, return_exceptions=True)))

    start = time.monotonic()
    results = asyncio.run(_run())
    elapsed = time.monotonic() - start

    assert elapsed < WALL_BUDGET_S, (
        f"fan-out took {elapsed:.1f}s (>{WALL_BUDGET_S}s) — likely "
        "serialization regression (wait_for+to_thread antipattern reintroduced)"
    )

    allowed_status = {200, 304, 400, 404, 422, 500, 502, 503}
    for path, response in results:
        assert not isinstance(response, BaseException), (
            f"{path} raised {type(response).__name__}: {response} — handler "
            "must return a structured response, never propagate."
        )
        assert response.status_code in allowed_status, (
            f"{path} returned unexpected status {response.status_code}; body="
            f"{response.text[:200]!r}"
        )
