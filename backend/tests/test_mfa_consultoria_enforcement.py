"""MFA-EXT-001 AC1/AC2/AC8: Consultoria plan-based MFA enforcement.

Validates that:
  - require_mfa enforces 403 for plan_type='consultoria' without MFA factor.
  - The 403 carries `X-MFA-Reason: consultoria` so the banner picks the
    right variant.
  - Users on other plans (e.g. smartlic_pro) without admin role are NOT
    blocked.
  - Users on consultoria with verified MFA pass through (aal2 path).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_user(*, aal: str = "aal1", uid: str = "consultoria-user-1") -> dict:
    return {"id": uid, "email": "consult@example.com", "role": "authenticated", "aal": aal}


# ─── require_mfa: consultoria enforcement ─────────────────────────────────────


@pytest.mark.asyncio
async def test_consultoria_without_mfa_is_blocked():
    """plan_type='consultoria' + aal1 + no factor -> 403 mfa_enrollment_required."""
    from fastapi import HTTPException
    from auth import require_mfa

    user = _make_user()

    with patch("auth._get_profile_mfa_state", new=AsyncMock(return_value={
        "plan_type": "consultoria",
        "force_mfa_enrollment_until": None,
    })), patch("authorization.check_user_roles", new=AsyncMock(return_value=(False, False))), \
         patch("auth._user_has_verified_mfa", new=AsyncMock(return_value=False)):
        with pytest.raises(HTTPException) as exc_info:
            await require_mfa(user)

        assert exc_info.value.status_code == 403
        assert exc_info.value.headers.get("X-MFA-Required") == "true"
        assert exc_info.value.headers.get("X-MFA-Reason") == "consultoria"
        assert "Consultoria" in exc_info.value.detail


@pytest.mark.asyncio
async def test_consultoria_with_verified_mfa_passes_through_at_aal2():
    """Consultoria user already at aal2 should not be blocked."""
    from auth import require_mfa

    user = _make_user(aal="aal2")
    # No DB calls expected — aal2 short-circuits.
    result = await require_mfa(user)
    assert result == user


@pytest.mark.asyncio
async def test_consultoria_with_verified_mfa_at_aal1_needs_step_up():
    """Consultoria + factor verified + aal1 -> 403 to force step-up."""
    from fastapi import HTTPException
    from auth import require_mfa

    user = _make_user()

    with patch("auth._get_profile_mfa_state", new=AsyncMock(return_value={
        "plan_type": "consultoria",
        "force_mfa_enrollment_until": None,
    })), patch("authorization.check_user_roles", new=AsyncMock(return_value=(False, False))), \
         patch("auth._user_has_verified_mfa", new=AsyncMock(return_value=True)):
        with pytest.raises(HTTPException) as exc_info:
            await require_mfa(user)
        assert exc_info.value.status_code == 403
        assert exc_info.value.headers.get("X-MFA-Reason") == "consultoria"
        assert "Verificação MFA" in exc_info.value.detail


@pytest.mark.asyncio
async def test_smartlic_pro_user_is_not_blocked():
    """plan_type='smartlic_pro' (not consultoria) -> pass-through when no factor."""
    from auth import require_mfa

    user = _make_user(uid="pro-user-1")

    with patch("auth._get_profile_mfa_state", new=AsyncMock(return_value={
        "plan_type": "smartlic_pro",
        "force_mfa_enrollment_until": None,
    })), patch("authorization.check_user_roles", new=AsyncMock(return_value=(False, False))), \
         patch("auth._user_has_verified_mfa", new=AsyncMock(return_value=False)):
        result = await require_mfa(user)
        assert result == user


@pytest.mark.asyncio
async def test_admin_takes_precedence_over_consultoria():
    """is_admin=True + consultoria plan -> reason='admin' (precedence)."""
    from fastapi import HTTPException
    from auth import require_mfa

    user = _make_user(uid="admin-consultoria")

    with patch("auth._get_profile_mfa_state", new=AsyncMock(return_value={
        "plan_type": "consultoria",
        "force_mfa_enrollment_until": None,
    })), patch("authorization.check_user_roles", new=AsyncMock(return_value=(True, False))), \
         patch("auth._user_has_verified_mfa", new=AsyncMock(return_value=False)):
        with pytest.raises(HTTPException) as exc_info:
            await require_mfa(user)
        assert exc_info.value.headers.get("X-MFA-Reason") == "admin"


# ─── /v1/mfa/status: enforce_reason exposure ──────────────────────────────────


@pytest.mark.asyncio
async def test_status_endpoint_exposes_consultoria_reason():
    """GET /v1/mfa/status returns enforce_reason=consultoria + grace days."""
    from datetime import datetime, timedelta, timezone
    from fastapi.testclient import TestClient
    from main import app
    from auth import require_auth

    user = _make_user()
    app.dependency_overrides[require_auth] = lambda: user

    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()

    try:
        with patch(
            "auth._get_profile_mfa_state",
            new=AsyncMock(return_value={
                "plan_type": "consultoria",
                "force_mfa_enrollment_until": future,
            }),
        ), patch(
            "routes.mfa.check_user_roles",
            new=AsyncMock(return_value=(False, False)),
        ), patch("routes.mfa._get_supabase", new=AsyncMock(return_value=_mock_sb_no_factors())):
            client = TestClient(app)
            resp = client.get("/v1/mfa/status")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["enforce_reason"] == "consultoria"
            assert data["mfa_enabled"] is False
            assert data["grace_days_remaining"] is not None
            # 10 day window -> at least 9 days, at most 10
            assert 9 <= data["grace_days_remaining"] <= 10
    finally:
        app.dependency_overrides.clear()


def _mock_sb_no_factors():
    """Build a mock Supabase client that returns no MFA factors."""
    sb = MagicMock()
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    result = MagicMock()
    result.data = []
    table.execute.return_value = result
    sb.table.return_value = table
    return sb
