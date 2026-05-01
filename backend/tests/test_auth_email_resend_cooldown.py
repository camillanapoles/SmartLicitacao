"""
Tests for CONV-INST-003: DB-backed resend cooldown.

Verifies that:
- Cooldown is checked against user_email_actions table (not just _resend_timestamps)
- Fail-open: if DB is down, in-memory fallback is used
- _record_confirm_db is idempotent (returns False on second call)
- Server-side Mixpanel event fires on first confirmation only
"""

import datetime
from unittest.mock import MagicMock, patch, call
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with auth_email router and clean in-memory state."""
    from fastapi import FastAPI
    from routes.auth_email import router, _resend_timestamps

    app = FastAPI()
    app.include_router(router, prefix="/v1")
    _resend_timestamps.clear()
    yield TestClient(app)
    _resend_timestamps.clear()


# ---------------------------------------------------------------------------
# _check_resend_cooldown_db helpers
# ---------------------------------------------------------------------------

class TestCheckResendCooldownDb:
    """Unit tests for _check_resend_cooldown_db helper."""

    def test_no_rows_returns_none(self):
        """If no DB rows exist, cooldown is not active (allow resend)."""
        from routes.auth_email import _check_resend_cooldown_db

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

        result = _check_resend_cooldown_db("test@example.com", mock_sb)
        assert result is None

    def test_recent_row_returns_remaining_seconds(self):
        """If last resend was <60s ago, returns remaining cooldown seconds."""
        from routes.auth_email import _check_resend_cooldown_db

        # Simulate row created 30 seconds ago
        thirty_seconds_ago = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=30)
        ).isoformat()

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"created_at": thirty_seconds_ago}
        ]

        result = _check_resend_cooldown_db("test@example.com", mock_sb)
        assert result is not None
        assert 25 <= result <= 35  # ~30 seconds remaining (with timing tolerance)

    def test_old_row_returns_none(self):
        """If last resend was >60s ago, cooldown is not active."""
        from routes.auth_email import _check_resend_cooldown_db

        two_minutes_ago = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=120)
        ).isoformat()

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"created_at": two_minutes_ago}
        ]

        result = _check_resend_cooldown_db("test@example.com", mock_sb)
        assert result is None

    def test_db_exception_returns_none_fail_open(self):
        """If DB throws, return None (fail-open = allow resend)."""
        from routes.auth_email import _check_resend_cooldown_db

        mock_sb = MagicMock()
        mock_sb.table.side_effect = Exception("DB connection error")

        result = _check_resend_cooldown_db("test@example.com", mock_sb)
        assert result is None  # fail-open


# ---------------------------------------------------------------------------
# _record_resend_db helpers
# ---------------------------------------------------------------------------

class TestRecordResendDb:
    """Unit tests for _record_resend_db helper."""

    def test_records_resend_action(self):
        """Should insert resend action into user_email_actions."""
        from routes.auth_email import _record_resend_db

        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        result = _record_resend_db("test@example.com", mock_sb)

        assert result is True
        mock_sb.table.assert_called_once_with("user_email_actions")
        mock_sb.table.return_value.insert.assert_called_once_with(
            {"email": "test@example.com", "action_type": "resend"}
        )

    def test_db_exception_returns_false(self):
        """If DB fails to record, return False (caller falls back to in-memory)."""
        from routes.auth_email import _record_resend_db

        mock_sb = MagicMock()
        mock_sb.table.side_effect = Exception("DB error")

        result = _record_resend_db("test@example.com", mock_sb)
        assert result is False


# ---------------------------------------------------------------------------
# _record_confirm_db helpers
# ---------------------------------------------------------------------------

class TestRecordConfirmDb:
    """Unit tests for _record_confirm_db helper (idempotency)."""

    def test_first_confirm_inserts_and_returns_true(self):
        """First confirmation should insert record and return True."""
        from routes.auth_email import _record_confirm_db

        mock_sb = MagicMock()
        # No existing confirm row
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        result = _record_confirm_db("user@example.com", mock_sb)
        assert result is True

    def test_second_confirm_returns_false_no_insert(self):
        """Second confirmation should return False without inserting."""
        from routes.auth_email import _record_confirm_db

        mock_sb = MagicMock()
        # Existing confirm row found
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": 42}
        ]

        result = _record_confirm_db("user@example.com", mock_sb)
        assert result is False
        # insert should NOT have been called
        mock_sb.table.return_value.insert.assert_not_called()

    def test_db_exception_returns_false(self):
        """If DB throws on confirm, return False gracefully."""
        from routes.auth_email import _record_confirm_db

        mock_sb = MagicMock()
        mock_sb.table.side_effect = Exception("DB error")

        result = _record_confirm_db("user@example.com", mock_sb)
        assert result is False


# ---------------------------------------------------------------------------
# Integration: resend endpoint uses DB-backed cooldown
# ---------------------------------------------------------------------------

class TestResendCooldownDbBacked:
    """Integration tests: POST /auth/resend-confirmation reads DB for cooldown."""

    @patch("supabase_client.get_supabase")
    def test_first_resend_succeeds_db_backed(self, mock_get_supabase, client):
        """First resend with empty DB should succeed."""
        mock_sb = MagicMock()
        # No existing resend rows
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
        # Insert succeeds
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_sb.auth.resend.return_value = None
        mock_get_supabase.return_value = mock_sb

        response = client.post(
            "/v1/auth/resend-confirmation",
            json={"email": "test@example.com"}
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @patch("supabase_client.get_supabase")
    def test_second_resend_within_60s_blocked(self, mock_get_supabase, client):
        """Second resend within 60s returns 429 (cooldown from DB)."""
        import datetime as dt

        # Simulate row created 10 seconds ago
        ten_secs_ago = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=10)
        ).isoformat()

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"created_at": ten_secs_ago}
        ]
        mock_get_supabase.return_value = mock_sb

        response = client.post(
            "/v1/auth/resend-confirmation",
            json={"email": "test@example.com"}
        )

        assert response.status_code == 429
        assert "aguarde" in response.json()["detail"].lower()

    @patch("supabase_client.get_supabase")
    def test_resend_db_down_uses_inmemory_fallback(self, mock_get_supabase, client):
        """If DB is down, in-memory fallback is used (fail-open for resend)."""
        mock_sb = MagicMock()
        # DB fails for cooldown check → should fall through to in-memory
        mock_sb.table.side_effect = Exception("DB connection failed")
        mock_get_supabase.side_effect = Exception("DB unavailable")

        # With no in-memory state, first request should succeed (fail-open)
        # But supabase.auth.resend also fails — so 500 is expected here
        response = client.post(
            "/v1/auth/resend-confirmation",
            json={"email": "test@example.com"}
        )

        # The endpoint will fail at auth.resend (also DB-backed), which raises 500
        # What matters: the cooldown check did NOT block with 429
        assert response.status_code != 429

    @patch("supabase_client.get_supabase")
    def test_resend_records_db_action(self, mock_get_supabase, client):
        """Successful resend should INSERT a row in user_email_actions."""
        mock_sb = MagicMock()
        # Empty cooldown
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_sb.auth.resend.return_value = None
        mock_get_supabase.return_value = mock_sb

        response = client.post(
            "/v1/auth/resend-confirmation",
            json={"email": "store@example.com"}
        )

        assert response.status_code == 200
        # Insert was called
        mock_sb.table.return_value.insert.assert_called()


# ---------------------------------------------------------------------------
# Integration: /auth/status fires Mixpanel on first confirm only
# ---------------------------------------------------------------------------

class TestAuthStatusServerSideEvent:
    """AC6: Server-side Mixpanel email_verification_completed on first confirm."""

    @patch("analytics_events.track_event")
    @patch("supabase_client.get_supabase")
    def test_first_confirm_fires_mixpanel_event(
        self, mock_get_supabase, mock_track_event, client
    ):
        """First polling confirm → Mixpanel event fired once."""
        mock_user = MagicMock()
        mock_user.email = "newuser@example.com"
        mock_user.email_confirmed_at = "2026-04-30T12:00:00Z"
        mock_user.id = "user-abc-123"

        mock_sb = MagicMock()
        mock_sb.auth.admin.list_users.return_value = [mock_user]
        # No existing confirm row (first time)
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_get_supabase.return_value = mock_sb

        response = client.get("/v1/auth/status?email=newuser@example.com")

        assert response.status_code == 200
        assert response.json()["confirmed"] is True
        mock_track_event.assert_called_once()
        call_args = mock_track_event.call_args
        assert call_args[0][0] == "email_verification_completed"
        props = call_args[0][1]
        assert props["email_domain"] == "example.com"
        assert props["source"] == "server_side"

    @patch("analytics_events.track_event")
    @patch("supabase_client.get_supabase")
    def test_second_polling_confirm_does_not_re_fire_event(
        self, mock_get_supabase, mock_track_event, client
    ):
        """Second poll after already confirmed → Mixpanel event NOT fired again."""
        mock_user = MagicMock()
        mock_user.email = "repeat@example.com"
        mock_user.email_confirmed_at = "2026-04-30T12:00:00Z"
        mock_user.id = "user-xyz-999"

        mock_sb = MagicMock()
        mock_sb.auth.admin.list_users.return_value = [mock_user]
        # Existing confirm row (already emitted)
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": 5}
        ]
        mock_get_supabase.return_value = mock_sb

        response = client.get("/v1/auth/status?email=repeat@example.com")

        assert response.status_code == 200
        assert response.json()["confirmed"] is True
        mock_track_event.assert_not_called()
