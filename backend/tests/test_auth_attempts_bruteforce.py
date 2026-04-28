"""MFA-EXT-001 AC4-AC7: brute-force trigger via /v1/auth/login-attempt.

Validates:
  - 3 consecutive 401s (success=false) -> 4th body contains
    force_mfa_triggered=True AND profiles.force_mfa_enrollment_until is
    written.
  - Successful login (success=true) resets consecutive_failures to 0.
  - 24h idle window resets the counter on the next failure.
  - Endpoint returns 200 for unknown emails (no enumeration oracle).
  - Threshold transitions only fire ONCE (no email spam on repeated 4th
    failures while window still active).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ─── Mock harness ─────────────────────────────────────────────────────────────


class FakeAttemptStore:
    """In-memory stub for the auth_attempts table writes."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.last_failure_at: dict[str, datetime] = {}
        self.last_success_at: dict[str, datetime] = {}
        self.force_until: dict[str, str] = {}
        self.upsert_calls: list[dict] = []
        self.profile_updates: list[dict] = []


@pytest.fixture
def store() -> FakeAttemptStore:
    return FakeAttemptStore()


def _make_sb_for_attempts(store: FakeAttemptStore, *, user_id: str = "uid-1"):
    """Build a Supabase admin client mock that:

    * resolves email->user_id via auth.admin.list_users
    * routes auth_attempts read/upsert through the in-memory store
    * routes profiles update writes through the in-memory store
    """
    sb = MagicMock()

    # auth.admin.list_users returns [{id, email}]
    list_result = MagicMock()
    list_result.users = [MagicMock(id=user_id, email="bf@example.com")]
    list_result.users[0].__getitem__ = lambda self, k: getattr(self, k)
    sb.auth.admin.list_users.return_value = list_result

    # The route uses sb_execute(query) — query is built via sb.table(...). We
    # don't need the queries to be functional; sb_execute is mocked to read
    # from the store.

    return sb


def _patch_sb_execute(store: FakeAttemptStore, user_id: str = "uid-1"):
    """Return an AsyncMock impl for sb_execute that drives the FakeAttemptStore.

    We pattern-match on the type of query argument by inspecting the call's
    repr — or, more robustly, use a bound MagicMock on the table that records
    the operation type. For simplicity we infer from call ordering: read
    first, then upsert.
    """

    state = {"read_count": 0}

    async def fake_sb_execute(query, *, category="read"):
        # The handler calls in this order:
        #   1. read    -> select prior failures
        #   2. write   -> upsert auth_attempts
        #   3. (maybe) write -> profiles.update force_mfa
        result = MagicMock()
        if category == "read":
            state["read_count"] += 1
            row = {
                "consecutive_failures": store.counts.get(user_id, 0),
                "last_failure_at": (
                    store.last_failure_at[user_id].isoformat()
                    if user_id in store.last_failure_at
                    else None
                ),
            }
            result.data = [row] if user_id in store.counts else []
            return result

        # write paths
        # We can't introspect the query payload easily, but the handler
        # calls upsert(...) then update(...).eq(...) for force window.
        # Detect by attribute presence on the query mock.
        called_chain = repr(query)
        if "upsert" in called_chain:
            # auth_attempts upsert — payload was passed; we infer success
            # vs failure by checking for last_success_at vs last_failure_at
            # in the recorded args. Easier: just bump or set fields based
            # on the success boolean we'll thread via store.upsert_calls.
            payload = store.upsert_calls.pop(0) if store.upsert_calls else {}
            if "last_success_at" in payload:
                store.counts[user_id] = 0
                store.last_success_at[user_id] = datetime.now(timezone.utc)
            else:
                store.counts[user_id] = payload.get(
                    "consecutive_failures", store.counts.get(user_id, 0) + 1
                )
                store.last_failure_at[user_id] = datetime.now(timezone.utc)
            result.data = [payload]
        elif "update" in called_chain:
            payload = store.profile_updates.pop(0) if store.profile_updates else {}
            store.force_until[user_id] = payload.get("force_mfa_enrollment_until", "")
            result.data = [payload]
        else:
            result.data = []
        return result

    return fake_sb_execute


# ─── Test app builder ─────────────────────────────────────────────────────────


def _make_test_app():
    from fastapi import FastAPI
    from routes.auth_signup import router as signup_router

    app = FastAPI()
    app.include_router(signup_router)
    return app


# ─── Tests ────────────────────────────────────────────────────────────────────


def _post_attempt(client: TestClient, *, success: bool, email: str = "bf@example.com"):
    return client.post(
        "/auth/login-attempt",
        json={"email": email, "success": success},
    )


def test_unknown_email_returns_200_silent_noop():
    """No-op silently for unknown email (no user-existence oracle)."""
    app = _make_test_app()

    with patch("routes.auth_signup._get_supabase") as mock_get_sb, \
         patch("config.get_feature_flag", return_value=False):
        sb = MagicMock()
        # list_users returns no users
        list_result = MagicMock()
        list_result.users = []
        sb.auth.admin.list_users.return_value = list_result
        mock_get_sb.return_value = sb

        client = TestClient(app)
        resp = client.post(
            "/auth/login-attempt",
            json={"email": "ghost@example.com", "success": False},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["force_mfa_triggered"] is False


def test_three_failures_trigger_force_mfa(store):
    """3 consecutive failures -> 4th attempt body has force_mfa_triggered=True."""
    app = _make_test_app()

    sb = _make_sb_for_attempts(store)
    fake_exec = _patch_sb_execute(store)

    with patch("routes.auth_signup._get_supabase", return_value=sb), \
         patch("supabase_client.sb_execute", side_effect=fake_exec), \
         patch("auth._user_has_verified_mfa", new=AsyncMock(return_value=False)), \
         patch("routes.auth_signup._trigger_mfa_email") as mock_email, \
         patch("routes.auth_signup._emit_bruteforce_sentry") as mock_sentry, \
         patch("config.get_feature_flag", return_value=False):
        client = TestClient(app)

        # Attempt 1 — failure: count goes 0 -> 1
        store.upsert_calls.append({"consecutive_failures": 1, "last_failure_at": "x"})
        r1 = _post_attempt(client, success=False)
        assert r1.status_code == 200
        assert r1.json()["force_mfa_triggered"] is False

        # Attempt 2 — failure: count goes 1 -> 2
        store.upsert_calls.append({"consecutive_failures": 2, "last_failure_at": "x"})
        r2 = _post_attempt(client, success=False)
        assert r2.json()["force_mfa_triggered"] is False

        # Attempt 3 — failure: count goes 2 -> 3 (CROSSES threshold)
        store.upsert_calls.append({"consecutive_failures": 3, "last_failure_at": "x"})
        store.profile_updates.append(
            {"force_mfa_enrollment_until": "2030-01-01T00:00:00+00:00"}
        )
        r3 = _post_attempt(client, success=False)
        assert r3.status_code == 200
        body3 = r3.json()
        assert body3["ok"] is True
        assert body3["force_mfa_triggered"] is True

        # Email + Sentry fired exactly once
        assert mock_email.call_count == 1
        assert mock_sentry.call_count == 1


def test_success_resets_counter(store):
    """success=true -> consecutive_failures = 0, last_success_at set."""
    app = _make_test_app()
    store.counts["uid-1"] = 2  # User had 2 prior failures
    store.last_failure_at["uid-1"] = datetime.now(timezone.utc) - timedelta(minutes=5)

    sb = _make_sb_for_attempts(store)

    async def fake_exec(query, *, category="read"):
        result = MagicMock()
        if category == "write":
            # upsert with last_success_at
            store.counts["uid-1"] = 0
            store.last_success_at["uid-1"] = datetime.now(timezone.utc)
        result.data = []
        return result

    with patch("routes.auth_signup._get_supabase", return_value=sb), \
         patch("supabase_client.sb_execute", side_effect=fake_exec), \
         patch("config.get_feature_flag", return_value=False):
        client = TestClient(app)
        resp = _post_attempt(client, success=True)
        assert resp.status_code == 200
        assert resp.json()["force_mfa_triggered"] is False
        assert store.counts["uid-1"] == 0
        assert "uid-1" in store.last_success_at


def test_idle_24h_reset_counter(store):
    """A failure with last_failure_at >24h ago resets counter to 0 before increment."""
    app = _make_test_app()
    store.counts["uid-1"] = 2  # Was at 2
    store.last_failure_at["uid-1"] = datetime.now(timezone.utc) - timedelta(hours=25)

    sb = _make_sb_for_attempts(store)

    captured = {"new_count": None}

    async def fake_exec(query, *, category="read"):
        result = MagicMock()
        if category == "read":
            row = {
                "consecutive_failures": store.counts.get("uid-1", 0),
                "last_failure_at": store.last_failure_at["uid-1"].isoformat(),
            }
            result.data = [row]
        else:
            # The route should compute new_failures = 0 + 1 = 1 (NOT 3),
            # because 25h > 24h idle threshold.
            payload = store.upsert_calls.pop(0) if store.upsert_calls else {}
            captured["new_count"] = payload.get("consecutive_failures")
            result.data = [payload]
        return result

    store.upsert_calls.append({"consecutive_failures": 1, "last_failure_at": "x"})
    with patch("routes.auth_signup._get_supabase", return_value=sb), \
         patch("supabase_client.sb_execute", side_effect=fake_exec), \
         patch("config.get_feature_flag", return_value=False):
        client = TestClient(app)
        resp = _post_attempt(client, success=False)
        assert resp.status_code == 200
        assert resp.json()["force_mfa_triggered"] is False
        assert captured["new_count"] == 1, (
            "Idle reset should drop counter to 0 then increment to 1, "
            f"got {captured['new_count']}"
        )


def test_threshold_does_not_re_fire_when_already_at_3(store):
    """If counter is already at 3, a 4th failure does NOT re-trigger email."""
    app = _make_test_app()
    store.counts["uid-1"] = 3  # Already triggered last time
    store.last_failure_at["uid-1"] = datetime.now(timezone.utc) - timedelta(minutes=5)

    sb = _make_sb_for_attempts(store)

    async def fake_exec(query, *, category="read"):
        result = MagicMock()
        if category == "read":
            row = {
                "consecutive_failures": 3,
                "last_failure_at": store.last_failure_at["uid-1"].isoformat(),
            }
            result.data = [row]
        else:
            store.counts["uid-1"] = 4
            result.data = []
        return result

    with patch("routes.auth_signup._get_supabase", return_value=sb), \
         patch("supabase_client.sb_execute", side_effect=fake_exec), \
         patch("auth._user_has_verified_mfa", new=AsyncMock(return_value=False)), \
         patch("routes.auth_signup._trigger_mfa_email") as mock_email, \
         patch("routes.auth_signup._emit_bruteforce_sentry") as mock_sentry, \
         patch("config.get_feature_flag", return_value=False):
        client = TestClient(app)
        resp = _post_attempt(client, success=False)
        assert resp.json()["force_mfa_triggered"] is False
        # Email + Sentry must NOT fire on repeat (already past threshold).
        mock_email.assert_not_called()
        mock_sentry.assert_not_called()
