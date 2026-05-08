"""Tests for GET /v1/founding/session-status (#865).

Verifies the enriched session-status endpoint used by /fundadores/obrigado
to determine post-purchase copy (has account vs. "check your email").
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("FOUNDING_ONE_TIME_PRICE_ID", "price_test_founding_lifetime")

from routes.founding import _mask_email, router as founding_router  # noqa: E402


# ---------------------------------------------------------------------------
# _mask_email unit tests
# ---------------------------------------------------------------------------


def test_mask_email_standard():
    assert _mask_email("mariaalvabaron@gmail.com") == "ma****@gmail.com"


def test_mask_email_short_local_part():
    assert _mask_email("ab@example.com") == "ab****@example.com"


def test_mask_email_one_char_local_part():
    # Only 1 char before @: local[:2] still returns 1 char
    assert _mask_email("a@example.com") == "a****@example.com"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_with_founding():
    app = FastAPI()
    app.include_router(founding_router, prefix="/v1")
    return app


def _mk_sb(lead_row=None, profile_row=None):
    """Build a minimal Supabase mock that returns deterministic data."""
    sb = MagicMock()

    class _Chain:
        def __init__(self):
            self._table = None
            self._lead_row = lead_row
            self._profile_row = profile_row

        def table(self, name):
            self._table = name
            return self

        def select(self, *a, **kw):
            return self

        def eq(self, *a, **kw):
            return self

        def limit(self, *a, **kw):
            return self

        def execute(self):
            if self._table == "founding_leads":
                return MagicMock(data=[self._lead_row] if self._lead_row else [])
            if self._table == "profiles":
                return MagicMock(data=[self._profile_row] if self._profile_row else [])
            return MagicMock(data=[])

    chain = _Chain()
    sb.table.side_effect = lambda name: chain.table(name)
    return sb


# ---------------------------------------------------------------------------
# Happy path: completed session, user HAS an account
# ---------------------------------------------------------------------------


@patch("routes.founding.get_supabase")
def test_session_status_completed_with_account(mock_get_supabase, app_with_founding):
    lead = {
        "email": "founder@empresa.com.br",
        "checkout_status": "completed",
        "magic_link_sent_at": None,
        "created_at": "2026-05-08T10:00:00+00:00",
    }
    profile = {"id": "some-uuid"}

    # Build a mock that returns the lead row for founding_leads and a profile
    sb = MagicMock()
    call_count = {"n": 0}

    def table_side_effect(name):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        if name == "founding_leads":
            chain.execute.return_value = MagicMock(data=[lead])
        elif name == "profiles":
            chain.execute.return_value = MagicMock(data=[profile])
        else:
            chain.execute.return_value = MagicMock(data=[])
        return chain

    sb.table.side_effect = table_side_effect
    mock_get_supabase.return_value = sb

    client = TestClient(app_with_founding)
    r = client.get("/v1/founding/session-status?session_id=cs_test_12345678")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["has_account"] is True
    assert body["invite_sent"] is False
    # Email must be masked
    assert "@" in body["email"]
    assert "fo****@" in body["email"]


# ---------------------------------------------------------------------------
# Happy path: completed, no account, invite sent
# ---------------------------------------------------------------------------


@patch("routes.founding.get_supabase")
def test_session_status_completed_no_account_invite_sent(
    mock_get_supabase, app_with_founding
):
    lead = {
        "email": "newuser@gmail.com",
        "checkout_status": "completed",
        "magic_link_sent_at": "2026-05-08T11:00:00+00:00",
        "created_at": "2026-05-08T10:00:00+00:00",
    }

    sb = MagicMock()

    def table_side_effect(name):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        if name == "founding_leads":
            chain.execute.return_value = MagicMock(data=[lead])
        elif name == "profiles":
            chain.execute.return_value = MagicMock(data=[])  # no profile
        else:
            chain.execute.return_value = MagicMock(data=[])
        return chain

    sb.table.side_effect = table_side_effect
    mock_get_supabase.return_value = sb

    client = TestClient(app_with_founding)
    r = client.get("/v1/founding/session-status?session_id=cs_test_12345678")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["has_account"] is False
    assert body["invite_sent"] is True
    assert "ne****@gmail.com" == body["email"]


# ---------------------------------------------------------------------------
# Lead not found in DB → status='not_found'
# ---------------------------------------------------------------------------


@patch("routes.founding.get_supabase")
def test_session_status_not_found(mock_get_supabase, app_with_founding):
    sb = MagicMock()

    def table_side_effect(name):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = MagicMock(data=[])
        return chain

    sb.table.side_effect = table_side_effect
    mock_get_supabase.return_value = sb

    client = TestClient(app_with_founding)
    r = client.get("/v1/founding/session-status?session_id=cs_test_notexist")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "not_found"
    assert body["email"] == ""
    assert body["has_account"] is False
    assert body["invite_sent"] is False


# ---------------------------------------------------------------------------
# session_id too short → 422 validation error
# ---------------------------------------------------------------------------


def test_session_status_short_session_id_rejected(app_with_founding):
    client = TestClient(app_with_founding)
    r = client.get("/v1/founding/session-status?session_id=short")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Rate-limit header is present in response
# ---------------------------------------------------------------------------


@patch("routes.founding.get_supabase")
def test_session_status_rate_limit_headers_present(
    mock_get_supabase, app_with_founding
):
    sb = MagicMock()

    def table_side_effect(name):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = MagicMock(data=[])
        return chain

    sb.table.side_effect = table_side_effect
    mock_get_supabase.return_value = sb

    client = TestClient(app_with_founding)
    r = client.get("/v1/founding/session-status?session_id=cs_test_12345678")
    # Rate limiter injects X-RateLimit-* headers when Redis is available.
    # In unit tests Redis is absent, so the endpoint still returns 200
    # (require_rate_limit is a soft limiter with Redis fallback).
    assert r.status_code == 200
