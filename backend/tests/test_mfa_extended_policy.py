"""MFA-EXT-001: end-to-end policy + cron tests.

Cross-cutting validation:
  - require_mfa: force_mfa_enrollment_until window enforces MFA.
  - require_mfa: expired force window does NOT enforce.
  - auth_cleanup cron: resets stale auth_attempts AND clears expired
    force_mfa_enrollment_until.
  - Email template renders both variants without raising.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── require_mfa: force_mfa_enrollment_until window ───────────────────────────


@pytest.mark.asyncio
async def test_force_window_active_blocks_with_bruteforce_reason():
    """force_mfa_enrollment_until in the future -> 403 with reason=bruteforce."""
    from fastapi import HTTPException
    from auth import require_mfa

    user = {"id": "bf-user", "email": "bf@example.com", "role": "authenticated", "aal": "aal1"}
    future = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()

    with patch("auth._get_profile_mfa_state", new=AsyncMock(return_value={
        "plan_type": "smartlic_pro",
        "force_mfa_enrollment_until": future,
    })), patch("authorization.check_user_roles", new=AsyncMock(return_value=(False, False))), \
         patch("auth._user_has_verified_mfa", new=AsyncMock(return_value=False)):
        with pytest.raises(HTTPException) as exc_info:
            await require_mfa(user)
        assert exc_info.value.status_code == 403
        assert exc_info.value.headers.get("X-MFA-Reason") == "bruteforce"


@pytest.mark.asyncio
async def test_force_window_expired_does_not_enforce():
    """force_mfa_enrollment_until in the past -> NOT enforced; pass through."""
    from auth import require_mfa

    user = {"id": "expired-user", "email": "x@example.com", "role": "authenticated", "aal": "aal1"}
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()

    with patch("auth._get_profile_mfa_state", new=AsyncMock(return_value={
        "plan_type": "smartlic_pro",
        "force_mfa_enrollment_until": past,
    })), patch("authorization.check_user_roles", new=AsyncMock(return_value=(False, False))), \
         patch("auth._user_has_verified_mfa", new=AsyncMock(return_value=False)):
        result = await require_mfa(user)
        assert result == user


@pytest.mark.asyncio
async def test_force_until_active_helper_handles_iso_string_with_z_suffix():
    """_force_until_active normalizes 'Z' suffix and naive datetimes."""
    from auth import _force_until_active

    future_z = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace(
        "+00:00", "Z"
    )
    assert _force_until_active(future_z) is True

    past_z = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace(
        "+00:00", "Z"
    )
    assert _force_until_active(past_z) is False

    assert _force_until_active(None) is False
    assert _force_until_active("") is False
    assert _force_until_active("not-a-date") is False


# ─── auth_cleanup cron ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cron_resets_stale_auth_attempts():
    """reset_stale_auth_attempts logs and returns reset count from sb_execute."""
    from jobs.cron.auth_cleanup import reset_stale_auth_attempts

    fake_result = MagicMock()
    fake_result.data = [{"user_id": "u1"}, {"user_id": "u2"}]

    sb = MagicMock()
    table = MagicMock()
    table.update.return_value = table
    table.gt.return_value = table
    table.lt.return_value = table
    sb.table.return_value = table

    # Patches must target supabase_client (where the lazy imports resolve to).
    with patch("supabase_client.get_supabase", return_value=sb), \
         patch("supabase_client.sb_execute", new=AsyncMock(return_value=fake_result)):
        out = await reset_stale_auth_attempts()
        assert out["reset"] == 2


@pytest.mark.asyncio
async def test_cron_clears_expired_force_mfa():
    """clear_expired_force_mfa returns cleared count."""
    from jobs.cron.auth_cleanup import clear_expired_force_mfa

    fake_result = MagicMock()
    fake_result.data = [{"id": "u1"}]

    sb = MagicMock()
    table = MagicMock()
    table.update.return_value = table
    table.lt.return_value = table
    sb.table.return_value = table

    with patch("supabase_client.get_supabase", return_value=sb), \
         patch("supabase_client.sb_execute", new=AsyncMock(return_value=fake_result)):
        out = await clear_expired_force_mfa()
        assert out["cleared"] == 1


@pytest.mark.asyncio
async def test_cron_run_once_aggregates_both_steps():
    """run_auth_cleanup_once returns both subresults."""
    from jobs.cron import auth_cleanup as mod

    with patch.object(mod, "reset_stale_auth_attempts", new=AsyncMock(return_value={"reset": 3})), \
         patch.object(mod, "clear_expired_force_mfa", new=AsyncMock(return_value={"cleared": 1})):
        out = await mod.run_auth_cleanup_once()
        assert out == {"attempts": {"reset": 3}, "force_mfa": {"cleared": 1}}


# ─── Email template ───────────────────────────────────────────────────────────


def test_email_template_consultoria_variant_renders():
    from templates.emails.mfa_enrollment_required import (
        render_mfa_enrollment_required_email,
    )

    html = render_mfa_enrollment_required_email(
        user_name="Maria",
        variant="consultoria",
        grace_days=14,
    )
    assert "Maria" in html
    assert "Consultoria" in html
    assert "14" in html
    assert "Configurar MFA" in html


def test_email_template_bruteforce_variant_renders():
    from templates.emails.mfa_enrollment_required import (
        render_mfa_enrollment_required_email,
    )

    html = render_mfa_enrollment_required_email(
        user_name="João",
        variant="bruteforce",
        grace_days=7,
    )
    assert "João" in html
    assert "tentativas" in html.lower() or "suspeita" in html.lower()
    assert "7" in html


# ─── /v1/mfa/status countdown surface ────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_endpoint_with_no_enforcement_returns_null_reason():
    """Regular user with no admin/master/consultoria/force -> enforce_reason=None."""
    from fastapi.testclient import TestClient
    from main import app
    from auth import require_auth

    user = {"id": "regular", "email": "r@example.com", "role": "authenticated", "aal": "aal1"}
    app.dependency_overrides[require_auth] = lambda: user

    sb = MagicMock()
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    factors_result = MagicMock()
    factors_result.data = []
    table.execute.return_value = factors_result
    sb.table.return_value = table

    try:
        with patch("auth._get_profile_mfa_state", new=AsyncMock(return_value={
            "plan_type": "smartlic_pro",
            "force_mfa_enrollment_until": None,
        })), patch("routes.mfa.check_user_roles", new=AsyncMock(return_value=(False, False))), \
             patch("routes.mfa._get_supabase", new=AsyncMock(return_value=sb)):
            client = TestClient(app)
            resp = client.get("/v1/mfa/status")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["enforce_reason"] is None
            assert data["mfa_required"] is False
    finally:
        app.dependency_overrides.clear()
