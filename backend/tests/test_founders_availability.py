"""Issue #1002 (API-FOUND-003): tests for GET /api/founders/availability.

Coverage:
- Happy path — DB returns N seats taken, response shape matches spec.
- Cap reached (50/50) — vagasRestantes=0 + sold_out=true.
- DB error — fallback=true + vagasRestantes=null + conservative message.
- Cache hit — returns cached payload, does NOT hit DB.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rate_limiter import require_rate_limit
from routes.founders import (
    FOUNDERS_CAP_TOTAL,
    router as founders_router,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_with_founders():
    app = FastAPI()
    # Bypass rate-limiter (Redis) in unit tests.
    app.dependency_overrides[require_rate_limit(60, 60)] = lambda: None
    app.include_router(founders_router)
    return app


def _make_supabase_mock(seats_taken: int, last_founder_iso: str | None = None,
                        opt_in_rows: list[dict] | None = None,
                        opt_in_raises: bool = False) -> MagicMock:
    """Build a fake supabase client whose chained ``.table()...execute()``
    calls return specific shapes for each query the route makes.

    The route makes 3 chained calls in order:
      1) profiles.select(id, count="exact").eq(is_founder, True).execute()
      2) profiles.select(founder_since).eq(...).order(...).limit(1).execute()
      3) profiles.select(razao_social,uf,founder_since).eq(...).eq(...).order(...).limit(5).execute()

    We use a side-effect on `.execute` to return them in order.
    """
    fake_sb = MagicMock()

    # Build the chain so every chained method returns the same fake_sb.
    fake_sb.table.return_value = fake_sb
    fake_sb.select.return_value = fake_sb
    fake_sb.eq.return_value = fake_sb
    fake_sb.order.return_value = fake_sb
    fake_sb.limit.return_value = fake_sb

    count_result = MagicMock(count=seats_taken, data=[])
    last_result = MagicMock(data=(
        [{"founder_since": last_founder_iso}] if last_founder_iso else []
    ))
    if opt_in_raises:
        # The 3rd execute() call should raise.
        side_effects: list = [count_result, last_result, Exception("opt-in column missing")]
    else:
        opt_result = MagicMock(data=opt_in_rows or [])
        side_effects = [count_result, last_result, opt_result]

    fake_sb.execute.side_effect = side_effects
    return fake_sb


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("routes.founders._set_cached", new_callable=AsyncMock)
@patch("routes.founders._get_cached", new_callable=AsyncMock)
@patch("routes.founders.get_supabase")
def test_founders_availability_happy_path(
    mock_get_sb, mock_get_cached, mock_set_cached, app_with_founders
):
    """Happy path: 23 seats taken → vagasRestantes=27, sold_out=false."""
    mock_get_cached.return_value = None  # cache miss
    mock_get_sb.return_value = _make_supabase_mock(
        seats_taken=23,
        last_founder_iso="2026-05-08T14:23:11-03:00",
        opt_in_rows=[
            {"razao_social": "Construtora X", "uf": "SC",
             "founder_since": "2026-05-08T14:23:11-03:00"},
            {"razao_social": "TI Y", "uf": "SP",
             "founder_since": "2026-05-07T09:11:00-03:00"},
        ],
    )

    client = TestClient(app_with_founders)
    r = client.get("/api/founders/availability")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vagasRestantes"] == 27
    assert body["vagasTotal"] == FOUNDERS_CAP_TOTAL
    assert body["vagasPreenchidas"] == 23
    assert body["sold_out"] is False
    assert body["fallback"] is False
    assert body["deadline"]  # non-empty
    assert body["ultimaVagaEm"] == "2026-05-08T14:23:11-03:00"
    assert len(body["ultimasVagasOptIn"]) == 2
    assert body["ultimasVagasOptIn"][0]["empresa"] == "Construtora X"
    assert body["ultimasVagasOptIn"][0]["uf"] == "SC"
    # Cache-Control header present
    assert "public" in r.headers.get("cache-control", "")


@patch("routes.founders._set_cached", new_callable=AsyncMock)
@patch("routes.founders._get_cached", new_callable=AsyncMock)
@patch("routes.founders.get_supabase")
def test_founders_availability_cap_reached(
    mock_get_sb, mock_get_cached, mock_set_cached, app_with_founders
):
    """Cap reached (50/50): vagasRestantes=0 + sold_out=true."""
    mock_get_cached.return_value = None
    mock_get_sb.return_value = _make_supabase_mock(seats_taken=50)

    client = TestClient(app_with_founders)
    r = client.get("/api/founders/availability")

    assert r.status_code == 200
    body = r.json()
    assert body["vagasRestantes"] == 0
    assert body["vagasPreenchidas"] == 50
    assert body["sold_out"] is True
    assert body["fallback"] is False


@patch("routes.founders._set_cached", new_callable=AsyncMock)
@patch("routes.founders._get_cached", new_callable=AsyncMock)
@patch("routes.founders.get_supabase")
def test_founders_availability_db_error_returns_fallback(
    mock_get_sb, mock_get_cached, mock_set_cached, app_with_founders
):
    """DB error → 200 with fallback=true and vagasRestantes=null."""
    mock_get_cached.return_value = None
    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_sb
    fake_sb.select.return_value = fake_sb
    fake_sb.eq.return_value = fake_sb
    fake_sb.execute.side_effect = Exception("db down")
    mock_get_sb.return_value = fake_sb

    client = TestClient(app_with_founders)
    r = client.get("/api/founders/availability")

    assert r.status_code == 200
    body = r.json()
    assert body["fallback"] is True
    assert body["vagasRestantes"] is None
    assert body["vagasPreenchidas"] is None
    assert body["vagasTotal"] == FOUNDERS_CAP_TOTAL
    assert "Vagas limitadas" in (body.get("message") or "")


@patch("routes.founders._set_cached", new_callable=AsyncMock)
@patch("routes.founders._get_cached", new_callable=AsyncMock)
@patch("routes.founders.get_supabase")
def test_founders_availability_uses_cache(
    mock_get_sb, mock_get_cached, mock_set_cached, app_with_founders
):
    """Cache hit: response served from cache, DB never hit."""
    mock_get_cached.return_value = {
        "vagasRestantes": 12,
        "vagasTotal": FOUNDERS_CAP_TOTAL,
        "vagasPreenchidas": 38,
        "diasRestantes": 50,
        "horasRestantes": 1200,
        "deadline": "2026-06-30T23:59:59-03:00",
        "ultimaVagaEm": "2026-05-09T10:00:00-03:00",
        "ultimasVagasOptIn": [],
        "sold_out": False,
        "fallback": False,
        "message": None,
    }

    client = TestClient(app_with_founders)
    r = client.get("/api/founders/availability")

    assert r.status_code == 200
    body = r.json()
    assert body["vagasRestantes"] == 12
    assert body["vagasPreenchidas"] == 38
    # DB was NOT called because cache returned a payload.
    mock_get_sb.assert_not_called()
    # Set should NOT have been called either (cache hit short-circuits).
    mock_set_cached.assert_not_called()


@patch("routes.founders._set_cached", new_callable=AsyncMock)
@patch("routes.founders._get_cached", new_callable=AsyncMock)
@patch("routes.founders.get_supabase")
def test_founders_availability_opt_in_column_missing_is_non_blocking(
    mock_get_sb, mock_get_cached, mock_set_cached, app_with_founders
):
    """If the LGPD opt-in column doesn't exist yet, route still returns
    a 200 with empty ultimasVagasOptIn — graceful migration support."""
    mock_get_cached.return_value = None
    mock_get_sb.return_value = _make_supabase_mock(
        seats_taken=5,
        last_founder_iso="2026-05-09T10:00:00-03:00",
        opt_in_raises=True,
    )

    client = TestClient(app_with_founders)
    r = client.get("/api/founders/availability")

    assert r.status_code == 200
    body = r.json()
    assert body["vagasRestantes"] == 45
    assert body["vagasPreenchidas"] == 5
    assert body["ultimasVagasOptIn"] == []
    assert body["fallback"] is False
