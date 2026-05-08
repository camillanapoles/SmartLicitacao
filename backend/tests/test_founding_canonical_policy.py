"""BIZ-FOUND-002: tests for the canonical policy gate on POST /v1/founding/checkout
plus the public GET /v1/founding/availability endpoint.

Covers:
- Cap reached (RPC returns founding_cap_reached) -> 410 + error_code='founding_cap_reached'.
- Deadline passed (RPC returns founding_deadline_passed) -> 410 + error_code='founding_deadline_passed'.
- Paused (RPC returns founding_paused) -> 410 + error_code='founding_paused'.
- Available -> route proceeds past gate (still 409 because email check fires next, but
  importantly NOT 410).
- GET /availability shape contract.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("FOUNDING_ONE_TIME_PRICE_ID", "price_test_founding_lifetime")

from routes.founding import router as founding_router  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


VALID_PAYLOAD = {
    "email": "founder@empresa.com.br",
    "nome": "Maria Silva",
    "cnpj": "00.394.460/0001-41",
    "razao_social": "Tesouro Nacional Brasil",
    "motivo": (
        "Nossa empresa atua em licitacoes B2G e queremos as 50 vagas founding do "
        "SmartLic para moldar o roadmap do produto e ganhar escala em monitoramento."
    ),
}


@pytest.fixture
def app_with_founding():
    app = FastAPI()
    app.include_router(founding_router, prefix="/v1")
    return app


def _make_supabase_mock(rpc_data: list[dict]) -> MagicMock:
    """Build a fake supabase client whose rpc() returns ``rpc_data``."""
    fake_sb = MagicMock()
    rpc_result = MagicMock(data=rpc_data)
    fake_sb.rpc.return_value = MagicMock(execute=MagicMock(return_value=rpc_result))
    # Default: chained table().select().eq().limit().execute() returns no profile.
    fake_sb.table.return_value = fake_sb
    fake_sb.select.return_value = fake_sb
    fake_sb.eq.return_value = fake_sb
    fake_sb.limit.return_value = fake_sb
    fake_sb.execute.return_value = MagicMock(data=[])
    return fake_sb


# ---------------------------------------------------------------------------
# /checkout — gate enforcement
# ---------------------------------------------------------------------------


@patch("routes.founding.get_supabase")
def test_checkout_returns_410_when_cap_reached(mock_get_sb, app_with_founding):
    mock_get_sb.return_value = _make_supabase_mock([
        {
            "available": False,
            "seats_remaining": 0,
            "seats_total": 50,
            "deadline_at": "2026-05-30T23:59:59-03:00",
            "paused": False,
            "reason": "founding_cap_reached",
        }
    ])

    client = TestClient(app_with_founding)
    r = client.post("/v1/founding/checkout", json=VALID_PAYLOAD)
    assert r.status_code == 410
    detail = r.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["error_code"] == "founding_cap_reached"
    assert detail["seats_total"] == 50
    assert detail["seats_remaining"] == 0


@patch("routes.founding.get_supabase")
def test_checkout_returns_410_when_deadline_passed(mock_get_sb, app_with_founding):
    mock_get_sb.return_value = _make_supabase_mock([
        {
            "available": False,
            "seats_remaining": 17,
            "seats_total": 50,
            "deadline_at": "2026-05-30T23:59:59-03:00",
            "paused": False,
            "reason": "founding_deadline_passed",
        }
    ])

    client = TestClient(app_with_founding)
    r = client.post("/v1/founding/checkout", json=VALID_PAYLOAD)
    assert r.status_code == 410
    detail = r.json()["detail"]
    assert detail["error_code"] == "founding_deadline_passed"


@patch("routes.founding.get_supabase")
def test_checkout_returns_410_when_paused(mock_get_sb, app_with_founding):
    mock_get_sb.return_value = _make_supabase_mock([
        {
            "available": False,
            "seats_remaining": 25,
            "seats_total": 50,
            "deadline_at": "2026-05-30T23:59:59-03:00",
            "paused": True,
            "reason": "founding_paused",
        }
    ])

    client = TestClient(app_with_founding)
    r = client.post("/v1/founding/checkout", json=VALID_PAYLOAD)
    assert r.status_code == 410
    assert r.json()["detail"]["error_code"] == "founding_paused"


@patch("routes.founding.get_supabase")
def test_checkout_returns_410_when_disabled(mock_get_sb, app_with_founding):
    mock_get_sb.return_value = _make_supabase_mock([
        {
            "available": False,
            "seats_remaining": 0,
            "seats_total": 50,
            "deadline_at": "2026-05-30T23:59:59-03:00",
            "paused": False,
            "reason": "founding_disabled",
        }
    ])

    client = TestClient(app_with_founding)
    r = client.post("/v1/founding/checkout", json=VALID_PAYLOAD)
    assert r.status_code == 410
    assert r.json()["detail"]["error_code"] == "founding_disabled"


@patch("routes.founding.get_supabase")
def test_checkout_returns_410_when_policy_missing(mock_get_sb, app_with_founding):
    mock_get_sb.return_value = _make_supabase_mock([
        {
            "available": False,
            "seats_remaining": 0,
            "seats_total": 0,
            "deadline_at": None,
            "paused": False,
            "reason": "founding_policy_missing",
        }
    ])

    client = TestClient(app_with_founding)
    r = client.post("/v1/founding/checkout", json=VALID_PAYLOAD)
    assert r.status_code == 410
    assert r.json()["detail"]["error_code"] == "founding_policy_missing"


@patch("routes.founding.get_supabase")
def test_checkout_fail_closed_when_rpc_raises(mock_get_sb, app_with_founding):
    """If the RPC raises (DB flaky), the route MUST fail closed (410)."""
    fake_sb = MagicMock()
    fake_sb.rpc.return_value = MagicMock(execute=MagicMock(side_effect=Exception("db down")))
    mock_get_sb.return_value = fake_sb

    client = TestClient(app_with_founding)
    r = client.post("/v1/founding/checkout", json=VALID_PAYLOAD)
    assert r.status_code == 410
    assert r.json()["detail"]["error_code"] == "unavailable"


@patch("routes.founding.get_supabase")
def test_checkout_passes_gate_when_available(mock_get_sb, app_with_founding):
    """available=True -> gate passes, route proceeds (still 409 from email check, NOT 410)."""
    fake_sb = _make_supabase_mock([
        {
            "available": True,
            "seats_remaining": 42,
            "seats_total": 50,
            "deadline_at": "2026-05-30T23:59:59-03:00",
            "paused": False,
            "reason": "available",
        }
    ])
    # Pretend the email already exists -> 409 (proves the gate passed; we got past it).
    fake_sb.execute.return_value = MagicMock(data=[{"id": "existing-user"}])
    mock_get_sb.return_value = fake_sb

    client = TestClient(app_with_founding)
    r = client.post("/v1/founding/checkout", json=VALID_PAYLOAD)
    assert r.status_code == 409  # email-already-registered path
    # Important: NOT 410 — the gate let us through.


# ---------------------------------------------------------------------------
# GET /availability — public seat counter contract
# ---------------------------------------------------------------------------


@patch("routes.founding.get_supabase")
def test_availability_returns_expected_shape(mock_get_sb, app_with_founding):
    mock_get_sb.return_value = _make_supabase_mock([
        {
            "available": True,
            "seats_remaining": 47,
            "seats_total": 50,
            "deadline_at": "2026-05-30T23:59:59-03:00",
            "paused": False,
            "reason": "available",
        }
    ])

    client = TestClient(app_with_founding)
    r = client.get("/v1/founding/availability")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["seats_total"] == 50
    assert body["seats_remaining"] == 47
    assert body["seats_taken"] == 3
    assert body["paused"] is False
    assert body["reason"] == "available"
    assert body["coupon_code"] == ""
    assert body["discount_pct"] == 0
    assert body["deadline_at"] == "2026-05-30T23:59:59-03:00"


@patch("routes.founding.get_supabase")
def test_availability_when_cap_reached(mock_get_sb, app_with_founding):
    mock_get_sb.return_value = _make_supabase_mock([
        {
            "available": False,
            "seats_remaining": 0,
            "seats_total": 50,
            "deadline_at": "2026-05-30T23:59:59-03:00",
            "paused": False,
            "reason": "founding_cap_reached",
        }
    ])

    client = TestClient(app_with_founding)
    r = client.get("/v1/founding/availability")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert body["seats_taken"] == 50
    assert body["seats_remaining"] == 0
    assert body["reason"] == "founding_cap_reached"


@patch("routes.founding.get_supabase")
def test_availability_fail_closed_on_db_error(mock_get_sb, app_with_founding):
    fake_sb = MagicMock()
    fake_sb.rpc.return_value = MagicMock(execute=MagicMock(side_effect=Exception("boom")))
    mock_get_sb.return_value = fake_sb

    client = TestClient(app_with_founding)
    r = client.get("/v1/founding/availability")
    # Endpoint MUST stay 200 with available=false rather than 5xx — landing
    # page should never error out, just disable CTA.
    assert r.status_code == 200
    assert r.json()["available"] is False
    assert r.json()["reason"] == "unavailable"
