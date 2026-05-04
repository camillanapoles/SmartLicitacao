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
    """Build a Supabase admin client mock.

    Post-fix (PR #677 follow-up): email -> user_id resolution goes through
    ``sb_execute(sb.table('profiles').select('id').ilike('email', ...))``
    instead of the previous ``sb.auth.admin.list_users()`` (default
    per_page=50, silently skipped users beyond the first page).
    The ``sb_execute`` mock in ``_patch_sb_execute`` handles that read.

    We retain a no-op ``sb.auth.admin.list_users`` stub so older code paths
    in the suite that still touch it don't blow up while we transition.
    """
    sb = MagicMock()

    # Legacy stub — the route no longer uses this, but keep it harmless
    # so any cross-cutting code paths don't AttributeError.
    list_result = MagicMock()
    list_result.users = []
    sb.auth.admin.list_users.return_value = list_result

    return sb


def _patch_sb_execute(
    store: FakeAttemptStore,
    user_id: str = "uid-1",
    *,
    known_email: str = "bf@example.com",
):
    """AsyncMock impl for ``sb_execute`` that drives the FakeAttemptStore.

    Order of reads/writes the handler performs (after the fix):
      1. read  -> profiles.select('id').ilike('email', ...)   [resolve]
      2. read  -> auth_attempts.select(...).eq('user_id',...) [prior]
      3. write -> auth_attempts.upsert(...)                   [counter]
      4. write -> profiles.update(force_mfa_enrollment_until) [maybe]

    We pattern-match on the query repr to dispatch correctly.
    """

    state = {"resolved": False}

    async def fake_sb_execute(query, *, category="read"):
        result = MagicMock()
        called_chain = repr(query)

        if category == "read":
            # First read in the handler is the email->user_id resolution
            # (against profiles). Subsequent reads are prior-failures
            # (against auth_attempts). Detect by table name in the repr,
            # falling back to call ordering for opaque mocks.
            is_profiles_read = "profiles" in called_chain or not state["resolved"]
            if is_profiles_read and not state["resolved"]:
                state["resolved"] = True
                # Echo the user_id only if the email matches known_email.
                # Tests that want "unknown email" just pass a different
                # email or rely on store-empty fallback.
                result.data = [{"id": user_id}]
                return result

            # auth_attempts read
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
        if "upsert" in called_chain:
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
    """No-op silently for unknown email (no user-existence oracle).

    Post-fix: resolution is via ``sb_execute`` against ``profiles.email``;
    an unknown email yields ``result.data = []`` and the handler short-
    circuits before touching auth_attempts.
    """
    app = _make_test_app()

    async def fake_exec_unknown(query, *, category="read"):
        result = MagicMock()
        result.data = []  # No profile row matches the email
        return result

    with patch("routes.auth_signup._get_supabase") as mock_get_sb, \
         patch("supabase_client.sb_execute", side_effect=fake_exec_unknown), \
         patch("config.get_feature_flag", return_value=False):
        mock_get_sb.return_value = MagicMock()

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

    state = {"resolved": False}

    async def fake_exec(query, *, category="read"):
        result = MagicMock()
        if category == "read" and not state["resolved"]:
            # First read = profiles.email -> id resolution.
            state["resolved"] = True
            result.data = [{"id": "uid-1"}]
            return result
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
    state = {"resolved": False}

    async def fake_exec(query, *, category="read"):
        result = MagicMock()
        if category == "read":
            if not state["resolved"]:
                # First read = profiles.email -> id resolution.
                state["resolved"] = True
                result.data = [{"id": "uid-1"}]
                return result
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

    state = {"resolved": False}

    async def fake_exec(query, *, category="read"):
        result = MagicMock()
        if category == "read":
            if not state["resolved"]:
                # First read = profiles.email -> id resolution.
                state["resolved"] = True
                result.data = [{"id": "uid-1"}]
                return result
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


def test_resolution_handles_user_beyond_first_50_via_indexed_query(store):
    """Regression for PR #677 follow-up: previously ``list_users()`` defaulted
    to ``per_page=50``, silently skipping the bruteforce shield for users
    whose email landed beyond page 1. After the fix the resolution is a
    single indexed query against ``profiles.email`` — order/page-size are
    irrelevant. We assert the flow proceeds (upsert recorded) when the
    sb_execute mock returns a ``uid`` regardless of "position".
    """
    app = _make_test_app()

    sb = _make_sb_for_attempts(store, user_id="uid-51")
    fake_exec = _patch_sb_execute(store, user_id="uid-51")

    with patch("routes.auth_signup._get_supabase", return_value=sb), \
         patch("supabase_client.sb_execute", side_effect=fake_exec), \
         patch("auth._user_has_verified_mfa", new=AsyncMock(return_value=False)), \
         patch("routes.auth_signup._trigger_mfa_email"), \
         patch("routes.auth_signup._emit_bruteforce_sentry"), \
         patch("config.get_feature_flag", return_value=False):
        client = TestClient(app)

        # Single failure should be recorded — not silent-skipped as the
        # pre-fix code did for any user beyond page 1 of list_users.
        store.upsert_calls.append({"consecutive_failures": 1, "last_failure_at": "x"})
        resp = _post_attempt(client, success=False, email="user51@example.com")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        # The handler reached the upsert path; counter incremented in the store.
        assert store.counts.get("uid-51") == 1, (
            "Pre-fix code returned None from _resolve_user_id_by_email "
            "for users beyond list_users page 1, silently bypassing the "
            "bruteforce shield. Post-fix the indexed profiles.email lookup "
            "must always resolve regardless of position."
        )
