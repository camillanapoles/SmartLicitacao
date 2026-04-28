"""BIZ-FOUND-002: tests for admin endpoints under /v1/admin/founding/*.

Covers:
- GET /policy returns snapshot + live seat usage.
- GET /leads filters by status; respects limit cap.
- POST /pause sets paused_at, paused_by, paused_reason.
- POST /resume clears pause fields.
- All endpoints reject anonymous (no admin override -> 403).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")

from main import app  # noqa: E402
from auth import require_auth  # noqa: E402
from admin import require_admin  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_client():
    fake_admin = {"id": "00000000-0000-0000-0000-00000000a001", "email": "admin@test"}
    app.dependency_overrides[require_auth] = lambda: fake_admin
    app.dependency_overrides[require_admin] = lambda: fake_admin
    yield TestClient(app)
    app.dependency_overrides.pop(require_auth, None)
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def regular_client():
    """Logged-in non-admin user — should get 403 from require_admin."""
    fake_user = {"id": "regular-user", "email": "user@test"}
    app.dependency_overrides[require_auth] = lambda: fake_user
    yield TestClient(app)
    app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# GET /policy
# ---------------------------------------------------------------------------


@patch("routes.admin_founding.get_supabase")
def test_get_policy_returns_snapshot(mock_get_sb, admin_client):
    fake_sb = MagicMock()

    # founding_policy fetch
    policy_query = MagicMock()
    policy_query.execute.return_value = MagicMock(data=[{
        "seat_limit": 50,
        "deadline_at": "2026-05-30T23:59:59-03:00",
        "discount_pct": 50,
        "coupon_code": "FOUNDING_LIFETIME",
        "active": True,
        "paused_at": None,
        "paused_by": None,
        "paused_reason": None,
    }])

    # founding_leads count
    count_query = MagicMock()
    count_query.execute.return_value = MagicMock(data=[], count=12)

    table_chain = MagicMock()
    table_chain.select.return_value = table_chain
    table_chain.eq.return_value = table_chain
    table_chain.limit.return_value = policy_query
    # second call: count exact path
    count_chain = MagicMock()
    count_chain.select.return_value = count_chain
    count_chain.eq.return_value = count_query

    fake_sb.table.side_effect = [table_chain, count_chain]
    mock_get_sb.return_value = fake_sb

    r = admin_client.get("/v1/admin/founding/policy")
    assert r.status_code == 200
    body = r.json()
    assert body["seat_limit"] == 50
    assert body["seats_taken"] == 12
    assert body["seats_remaining"] == 38
    assert body["completion_pct"] == 24.0
    assert body["coupon_code"] == "FOUNDING_LIFETIME"
    assert body["paused"] is False


@patch("routes.admin_founding.get_supabase")
def test_get_policy_503_when_row_missing(mock_get_sb, admin_client):
    fake_sb = MagicMock()
    table_chain = MagicMock()
    table_chain.select.return_value = table_chain
    table_chain.eq.return_value = table_chain
    table_chain.limit.return_value = table_chain
    table_chain.execute.return_value = MagicMock(data=[])
    fake_sb.table.return_value = table_chain
    mock_get_sb.return_value = fake_sb

    r = admin_client.get("/v1/admin/founding/policy")
    assert r.status_code == 503


def test_get_policy_rejects_non_admin(regular_client):
    r = regular_client.get("/v1/admin/founding/policy")
    # require_admin raises 403 for non-admin
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /leads
# ---------------------------------------------------------------------------


@patch("routes.admin_founding.get_supabase")
def test_list_leads_returns_paginated(mock_get_sb, admin_client):
    fake_sb = MagicMock()
    leads_chain = MagicMock()
    leads_chain.select.return_value = leads_chain
    leads_chain.order.return_value = leads_chain
    leads_chain.limit.return_value = leads_chain
    leads_chain.eq.return_value = leads_chain
    leads_chain.execute.return_value = MagicMock(data=[
        {
            "id": "lead-1",
            "email": "founder1@x.com",
            "nome": "F1",
            "cnpj": "00394460000141",
            "razao_social": "Empresa 1",
            "checkout_status": "completed",
            "created_at": "2026-04-25T10:00:00Z",
            "completed_at": "2026-04-25T10:05:00Z",
            "stripe_customer_id": "cus_1",
        },
        {
            "id": "lead-2",
            "email": "founder2@x.com",
            "nome": "F2",
            "cnpj": "00394460000141",
            "razao_social": None,
            "checkout_status": "pending",
            "created_at": "2026-04-26T10:00:00Z",
            "completed_at": None,
            "stripe_customer_id": None,
        },
    ])
    fake_sb.table.return_value = leads_chain
    mock_get_sb.return_value = fake_sb

    r = admin_client.get("/v1/admin/founding/leads?limit=50")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert body["completed_count"] == 1
    assert body["pending_count"] == 1
    assert len(body["leads"]) == 2


@patch("routes.admin_founding.get_supabase")
def test_list_leads_filter_by_status(mock_get_sb, admin_client):
    fake_sb = MagicMock()
    leads_chain = MagicMock()
    leads_chain.select.return_value = leads_chain
    leads_chain.order.return_value = leads_chain
    leads_chain.limit.return_value = leads_chain
    leads_chain.eq.return_value = leads_chain
    leads_chain.execute.return_value = MagicMock(data=[])
    fake_sb.table.return_value = leads_chain
    mock_get_sb.return_value = fake_sb

    r = admin_client.get("/v1/admin/founding/leads?status=completed")
    assert r.status_code == 200
    # confirm .eq was called for the status filter
    eq_calls = [c.args for c in leads_chain.eq.call_args_list]
    assert ("checkout_status", "completed") in eq_calls


# ---------------------------------------------------------------------------
# POST /pause + /resume
# ---------------------------------------------------------------------------


@patch("routes.admin_founding.get_supabase")
def test_pause_sets_paused_fields(mock_get_sb, admin_client):
    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_sb
    fake_sb.update.return_value = fake_sb
    fake_sb.eq.return_value = fake_sb
    fake_sb.execute.return_value = MagicMock(data=[])
    mock_get_sb.return_value = fake_sb

    r = admin_client.post(
        "/v1/admin/founding/pause",
        json={"reason": "manual review backlog"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["paused"] is True
    assert body["paused_at"] is not None
    assert body["paused_reason"] == "manual review backlog"

    # Confirm update payload included paused_at, paused_by, paused_reason.
    update_payload = fake_sb.update.call_args.args[0]
    assert "paused_at" in update_payload
    assert "paused_by" in update_payload
    assert update_payload["paused_reason"] == "manual review backlog"


@patch("routes.admin_founding.get_supabase")
def test_resume_clears_paused_fields(mock_get_sb, admin_client):
    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_sb
    fake_sb.update.return_value = fake_sb
    fake_sb.eq.return_value = fake_sb
    fake_sb.execute.return_value = MagicMock(data=[])
    mock_get_sb.return_value = fake_sb

    r = admin_client.post("/v1/admin/founding/resume")
    assert r.status_code == 200
    body = r.json()
    assert body["paused"] is False
    assert body["paused_at"] is None

    update_payload = fake_sb.update.call_args.args[0]
    assert update_payload["paused_at"] is None
    assert update_payload["paused_by"] is None
    assert update_payload["paused_reason"] is None


def test_pause_rejects_non_admin(regular_client):
    r = regular_client.post("/v1/admin/founding/pause", json={})
    assert r.status_code == 403


def test_resume_rejects_non_admin(regular_client):
    r = regular_client.post("/v1/admin/founding/resume")
    assert r.status_code == 403
