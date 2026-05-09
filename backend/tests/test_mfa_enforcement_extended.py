"""MFA-ENFORCE-EXT-001 AC3: integration tests for the high-impact MFA wrapper.

Validates that:
  - `require_mfa_high_impact` returns 403 + X-MFA-Required when MFA policy
    enforces (admin/master/consultoria/bruteforce window).
  - It passes through when aal2 is satisfied OR no enforcement trigger fires.
  - Mixpanel `mfa_challenge_satisfied` is emitted on pass-through (AC4).
  - Endpoints listed in `docs/audits/2026-05-mfa-coverage.md` are wired:
      * POST /v1/billing-portal
      * POST /v1/change-password
      * DELETE /v1/me
      * POST /v1/api/subscriptions/cancel
      * POST /v1/api/subscriptions/update-billing-period

Uses conftest autouse override `_bypass_require_mfa_high_impact` as the
"OK path" baseline; pops the override locally to exercise the real chain
for the negative path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Direct unit tests on the wrapper ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_require_mfa_high_impact_passes_through_when_aal2():
    """aal2 user passes through and emits mfa_challenge_satisfied event."""
    from auth import require_mfa_high_impact

    user = {"id": "u1", "email": "u1@example.com", "role": "authenticated", "aal": "aal2"}

    # require_mfa returns the user as-is when aal=aal2 (no probes needed).
    with patch("auth.require_mfa", new=AsyncMock(return_value=user)):
        with patch("analytics_events.track_event") as mock_track:
            result = await require_mfa_high_impact(user=user)
            assert result == user
            mock_track.assert_called_once()
            args, _ = mock_track.call_args
            assert args[0] == "mfa_challenge_satisfied"


@pytest.mark.asyncio
async def test_require_mfa_high_impact_telemetry_failure_does_not_block():
    """Mixpanel down -> still pass through (fire-and-forget)."""
    from auth import require_mfa_high_impact

    user = {"id": "u2", "email": "u2@example.com", "role": "authenticated", "aal": "aal2"}

    with patch(
        "analytics_events.track_event",
        side_effect=RuntimeError("mixpanel down"),
    ):
        result = await require_mfa_high_impact(user=user)
        assert result == user


@pytest.mark.asyncio
async def test_require_mfa_high_impact_blocks_admin_without_factor():
    """Admin without verified factor -> 403 X-MFA-Required (chain via require_mfa)."""
    from fastapi import HTTPException
    from auth import require_mfa

    user = {"id": "admin-1", "email": "a@example.com", "role": "authenticated", "aal": "aal1"}

    with patch("auth._get_profile_mfa_state", new=AsyncMock(return_value={
        "plan_type": "admin",
        "force_mfa_enrollment_until": None,
    })), patch("authorization.check_user_roles", new=AsyncMock(return_value=(True, True))), \
         patch("auth._user_has_verified_mfa", new=AsyncMock(return_value=False)):
        with pytest.raises(HTTPException) as exc:
            await require_mfa(user)
        assert exc.value.status_code == 403
        assert exc.value.headers.get("X-MFA-Required") == "true"
        assert exc.value.headers.get("X-MFA-Reason") == "admin"


# ─── TestClient integration tests ─────────────────────────────────────────────


def _install_strict_mfa_chain(*, plan_type: str, is_admin: bool, force_until=None,
                               has_factor: bool = False, aal: str = "aal1"):
    """Helper: pop conftest bypass + install real require_mfa chain mocks."""
    from main import app
    from auth import require_auth, require_mfa_high_impact

    test_user = {
        "id": "test-strict-mfa",
        "email": "strict@example.com",
        "role": "authenticated",
        "aal": aal,
    }

    # Remove the conftest autouse bypass so the real require_mfa runs.
    app.dependency_overrides.pop(require_mfa_high_impact, None)
    app.dependency_overrides[require_auth] = lambda: test_user

    return test_user, [
        patch("auth._get_profile_mfa_state", new=AsyncMock(return_value={
            "plan_type": plan_type,
            "force_mfa_enrollment_until": force_until,
        })),
        patch(
            "authorization.check_user_roles",
            new=AsyncMock(return_value=(is_admin, is_admin)),
        ),
        patch("auth._user_has_verified_mfa", new=AsyncMock(return_value=has_factor)),
    ]


def _teardown():
    from main import app
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/v1/billing-portal"),
        ("post", "/v1/change-password"),
        ("delete", "/v1/me"),
        ("post", "/v1/api/subscriptions/cancel"),
        ("post", "/v1/api/subscriptions/update-billing-period"),
    ],
)
def test_high_impact_endpoint_blocks_admin_without_mfa(method, path):
    """Each high-impact endpoint returns 403 + X-MFA-Required for admin w/o MFA."""
    from fastapi.testclient import TestClient
    from main import app

    _user, patches = _install_strict_mfa_chain(
        plan_type="smartlic_pro", is_admin=True, has_factor=False
    )
    client = TestClient(app)

    try:
        for p in patches:
            p.start()
        if method == "post":
            resp = client.post(path, json={})
        else:
            resp = client.delete(path)
        # Expect 403 from require_mfa; X-MFA-Required header present.
        assert resp.status_code == 403, (
            f"{method.upper()} {path} expected 403 got {resp.status_code} body={resp.text}"
        )
        assert resp.headers.get("X-MFA-Required") == "true"
    finally:
        for p in patches:
            try:
                p.stop()
            except RuntimeError:
                pass
        _teardown()


def test_high_impact_endpoint_allows_aal2_user_with_factor(monkeypatch):
    """Pass-through path: aal2 user gets through to the route handler.

    We probe `/v1/billing-portal`. The route then looks up a Stripe
    subscription — we mock the supabase chain to return empty so the
    route returns 404 ("nenhuma assinatura ativa"), NOT 403. The 404
    proves the MFA gate let the request through to the handler.
    """
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake_for_mfa_passthrough")
    from fastapi.testclient import TestClient
    from main import app
    from database import get_db

    _user, patches = _install_strict_mfa_chain(
        plan_type="smartlic_pro", is_admin=False, has_factor=True, aal="aal2"
    )

    sb_mock = MagicMock()
    # No active subscription -> route returns 404.
    sb_mock.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    app.dependency_overrides[get_db] = lambda: sb_mock

    client = TestClient(app)

    try:
        for p in patches:
            p.start()
        with patch("supabase_client.get_supabase", return_value=sb_mock):
            resp = client.post("/v1/billing-portal")
        # 404 = handler reached (not 403/blocked by MFA).
        assert resp.status_code == 404, (
            f"Expected handler reached (404), got {resp.status_code} body={resp.text}"
        )
        # No X-MFA-Required header because gate passed.
        assert resp.headers.get("X-MFA-Required") is None
    finally:
        for p in patches:
            try:
                p.stop()
            except RuntimeError:
                pass
        _teardown()


def test_high_impact_endpoint_blocks_consultoria_without_mfa():
    """Consultoria plan w/o MFA -> 403 X-MFA-Reason=consultoria."""
    from fastapi.testclient import TestClient
    from main import app

    _user, patches = _install_strict_mfa_chain(
        plan_type="consultoria", is_admin=False, has_factor=False
    )
    client = TestClient(app)

    try:
        for p in patches:
            p.start()
        resp = client.post("/v1/billing-portal")
        assert resp.status_code == 403
        assert resp.headers.get("X-MFA-Required") == "true"
        assert resp.headers.get("X-MFA-Reason") == "consultoria"
    finally:
        for p in patches:
            try:
                p.stop()
            except RuntimeError:
                pass
        _teardown()


def test_high_impact_endpoint_blocks_bruteforce_window():
    """force_mfa_enrollment_until in future -> 403 X-MFA-Reason=bruteforce."""
    from fastapi.testclient import TestClient
    from main import app

    future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    _user, patches = _install_strict_mfa_chain(
        plan_type="smartlic_pro",
        is_admin=False,
        force_until=future,
        has_factor=False,
    )
    client = TestClient(app)

    try:
        for p in patches:
            p.start()
        resp = client.post("/v1/api/subscriptions/cancel")
        assert resp.status_code == 403
        assert resp.headers.get("X-MFA-Reason") == "bruteforce"
    finally:
        for p in patches:
            try:
                p.stop()
            except RuntimeError:
                pass
        _teardown()


def test_audit_event_emitted_on_pass_through(monkeypatch):
    """AC4: mfa_challenge_satisfied emitted to Mixpanel on aal2 pass-through."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake_for_mfa_audit")
    from fastapi.testclient import TestClient
    from main import app
    from database import get_db

    _user, patches = _install_strict_mfa_chain(
        plan_type="smartlic_pro", is_admin=False, has_factor=True, aal="aal2"
    )

    sb_mock = MagicMock()
    sb_mock.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    app.dependency_overrides[get_db] = lambda: sb_mock

    client = TestClient(app)

    try:
        for p in patches:
            p.start()
        with patch("supabase_client.get_supabase", return_value=sb_mock), \
             patch("analytics_events.track_event") as mock_track:
            client.post("/v1/billing-portal")
            # Verify event emitted at least once with the right name.
            event_names = [c.args[0] for c in mock_track.call_args_list]
            assert "mfa_challenge_satisfied" in event_names
    finally:
        for p in patches:
            try:
                p.stop()
            except RuntimeError:
                pass
        _teardown()
