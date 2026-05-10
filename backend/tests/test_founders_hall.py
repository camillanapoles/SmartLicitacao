"""Issue #1008 (COPY-HALL-009): tests for /api/founders/hall.

Coverage
--------
- GET /api/founders/hall — happy path (consent rows transformed to entries).
- GET /api/founders/hall — DB error → fallback=true + founders=[].
- GET /api/founders/hall — cache hit short-circuits the DB query.
- POST /api/founders/hall/consent — opt-in updates DB + audit log.
- POST /api/founders/hall/consent — opt-out updates DB.
- POST /api/founders/hall/consent — invalid logo_url rejected (422).
- POST /api/founders/hall/consent — DB failure surfaces 503.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import require_auth
from rate_limiter import require_rate_limit
from routes.founders_hall import router as hall_router


FAKE_USER = {"id": "00000000-0000-0000-0000-000000000001", "email": "founder@example.com"}


@pytest.fixture
def app_with_hall():
    app = FastAPI()
    # Bypass rate limiter (Redis) and auth in unit tests.
    app.dependency_overrides[require_rate_limit(60, 60)] = lambda: None
    app.dependency_overrides[require_rate_limit(20, 60)] = lambda: None
    app.dependency_overrides[require_auth] = lambda: FAKE_USER
    app.include_router(hall_router)
    return app


def _make_listing_supabase_mock(rows: list[dict] | None = None, raise_on_execute: bool = False) -> MagicMock:
    sb = MagicMock()
    sb.table.return_value = sb
    sb.select.return_value = sb
    sb.eq.return_value = sb
    sb.order.return_value = sb
    sb.limit.return_value = sb
    if raise_on_execute:
        sb.execute.side_effect = Exception("boom")
    else:
        sb.execute.return_value = MagicMock(data=rows or [])
    return sb


def _make_update_supabase_mock(updated_row: dict | None = None, raise_on_execute: bool = False) -> MagicMock:
    sb = MagicMock()
    sb.table.return_value = sb
    sb.update.return_value = sb
    sb.eq.return_value = sb
    if raise_on_execute:
        sb.execute.side_effect = Exception("update failed")
    else:
        sb.execute.return_value = MagicMock(data=[updated_row] if updated_row else [])
    return sb


# ---------------------------------------------------------------------------
# GET /api/founders/hall
# ---------------------------------------------------------------------------


@patch("routes.founders_hall._set_cached_listing", new_callable=AsyncMock)
@patch("routes.founders_hall._get_cached_listing", new_callable=AsyncMock)
@patch("routes.founders_hall.get_supabase")
def test_hall_happy_path(mock_get_sb, mock_cache_get, mock_cache_set, app_with_hall):
    mock_cache_get.return_value = None
    mock_get_sb.return_value = _make_listing_supabase_mock(
        rows=[
            {
                "razao_social": "Construtora Alpha",
                "uf": "SC",
                "founder_since": "2026-05-08T14:23:11-03:00",
                "founder_listing_display_name": None,
                "founder_company_logo_url": "https://cdn.example.com/alpha.png",
                "founder_consent_changed_at": "2026-05-09T12:00:00-03:00",
                "setor_principal": "Construção Civil",
            },
            {
                "razao_social": "Beta TI",
                "uf": "sp",  # exercise upper-case normalization
                "founder_since": "2026-05-07T09:11:00-03:00",
                "founder_listing_display_name": "Beta Tecnologia",
                "founder_company_logo_url": None,
                "founder_consent_changed_at": "2026-05-08T08:00:00-03:00",
                "setor_principal": None,
            },
        ]
    )

    client = TestClient(app_with_hall)
    r = client.get("/api/founders/hall")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 2
    assert body["fallback"] is False
    assert body["founders"][0]["display_name"] == "Construtora Alpha"
    assert body["founders"][0]["uf"] == "SC"
    assert body["founders"][0]["setor"] == "Construção Civil"
    assert body["founders"][0]["logo_url"] == "https://cdn.example.com/alpha.png"
    # display name override wins over razao_social.
    assert body["founders"][1]["display_name"] == "Beta Tecnologia"
    assert body["founders"][1]["uf"] == "SP"
    assert "public" in r.headers.get("cache-control", "")
    # Cache was populated.
    assert mock_cache_set.await_count == 1


@patch("routes.founders_hall._set_cached_listing", new_callable=AsyncMock)
@patch("routes.founders_hall._get_cached_listing", new_callable=AsyncMock)
@patch("routes.founders_hall.get_supabase")
def test_hall_db_error_returns_fallback(mock_get_sb, mock_cache_get, mock_cache_set, app_with_hall):
    mock_cache_get.return_value = None
    mock_get_sb.return_value = _make_listing_supabase_mock(raise_on_execute=True)

    client = TestClient(app_with_hall)
    r = client.get("/api/founders/hall")

    assert r.status_code == 200
    body = r.json()
    assert body["fallback"] is True
    assert body["founders"] == []
    assert body["count"] == 0


@patch("routes.founders_hall._set_cached_listing", new_callable=AsyncMock)
@patch("routes.founders_hall._get_cached_listing", new_callable=AsyncMock)
@patch("routes.founders_hall.get_supabase")
def test_hall_cache_hit_short_circuits(mock_get_sb, mock_cache_get, mock_cache_set, app_with_hall):
    cached_payload = {
        "founders": [
            {
                "display_name": "Cached Co",
                "uf": "RS",
                "setor": None,
                "logo_url": None,
                "founder_since": "2026-05-01T00:00:00-03:00",
            }
        ],
        "count": 1,
        "fallback": False,
    }
    mock_cache_get.return_value = cached_payload

    client = TestClient(app_with_hall)
    r = client.get("/api/founders/hall")

    assert r.status_code == 200
    assert r.json()["founders"][0]["display_name"] == "Cached Co"
    # DB never queried.
    assert mock_get_sb.call_count == 0
    assert mock_cache_set.await_count == 0


# ---------------------------------------------------------------------------
# POST /api/founders/hall/consent
# ---------------------------------------------------------------------------


@patch("routes.founders_hall._invalidate_listing_cache", new_callable=AsyncMock)
@patch("routes.founders_hall.audit_logger.log", new_callable=AsyncMock)
@patch("routes.founders_hall.get_supabase")
def test_consent_opt_in_round_trip(mock_get_sb, mock_audit, mock_invalidate, app_with_hall):
    mock_get_sb.return_value = _make_update_supabase_mock(
        updated_row={
            "founder_listing_display_name": "Empresa X",
            "founder_company_logo_url": "https://cdn.example.com/x.png",
            "is_founder": True,
        }
    )

    client = TestClient(app_with_hall)
    r = client.post(
        "/api/founders/hall/consent",
        json={
            "consent": True,
            "display_name": "Empresa X",
            "logo_url": "https://cdn.example.com/x.png",
        },
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["consent"] is True
    assert body["display_name"] == "Empresa X"
    assert body["logo_url"] == "https://cdn.example.com/x.png"
    assert body["is_founder"] is True
    # Audit + cache invalidation always fired.
    mock_audit.assert_awaited_once()
    audit_kwargs = mock_audit.await_args.kwargs
    assert audit_kwargs["event_type"] == "lgpd.consent_change"
    assert audit_kwargs["details"]["consent"] is True
    mock_invalidate.assert_awaited_once()


@patch("routes.founders_hall._invalidate_listing_cache", new_callable=AsyncMock)
@patch("routes.founders_hall.audit_logger.log", new_callable=AsyncMock)
@patch("routes.founders_hall.get_supabase")
def test_consent_opt_out_round_trip(mock_get_sb, mock_audit, mock_invalidate, app_with_hall):
    mock_get_sb.return_value = _make_update_supabase_mock(
        updated_row={"is_founder": True}
    )

    client = TestClient(app_with_hall)
    r = client.post(
        "/api/founders/hall/consent",
        json={"consent": False},
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["consent"] is False
    mock_audit.assert_awaited_once()
    assert mock_audit.await_args.kwargs["details"]["consent"] is False
    mock_invalidate.assert_awaited_once()


def test_consent_rejects_invalid_logo_url(app_with_hall):
    client = TestClient(app_with_hall)
    r = client.post(
        "/api/founders/hall/consent",
        json={"consent": True, "logo_url": "ftp://nope.example.com/logo"},
    )
    assert r.status_code == 422


@patch("routes.founders_hall._invalidate_listing_cache", new_callable=AsyncMock)
@patch("routes.founders_hall.audit_logger.log", new_callable=AsyncMock)
@patch("routes.founders_hall.get_supabase")
def test_consent_db_failure_returns_503(mock_get_sb, mock_audit, mock_invalidate, app_with_hall):
    mock_get_sb.return_value = _make_update_supabase_mock(raise_on_execute=True)

    client = TestClient(app_with_hall)
    r = client.post("/api/founders/hall/consent", json={"consent": True})

    assert r.status_code == 503
    # Audit not logged when update failed (we don't reach the audit step).
    mock_audit.assert_not_awaited()
    mock_invalidate.assert_not_awaited()
