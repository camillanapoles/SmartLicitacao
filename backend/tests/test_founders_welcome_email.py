"""Tests for founders welcome email — STORY-791.

Covers:
- Template renders correctly with user name
- send_founders_welcome_email idempotency (no double send)
- send_founders_welcome_email updates welcome_sent_at after send
- send_founders_welcome_email returns None when no completed lead found
- ARQ job send_founders_welcome dispatches email + Mixpanel set
"""

import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Template rendering tests
# ---------------------------------------------------------------------------

class TestRenderFoundersWelcomeEmail:
    def test_renders_with_user_name(self):
        from templates.emails.founders_welcome import render_founders_welcome_email

        html = render_founders_welcome_email("Carlos Silva")

        assert "Carlos Silva" in html
        assert "Fundadores" in html
        assert "smartlic.tech/buscar" in html
        assert "50%" in html

    def test_renders_different_names(self):
        from templates.emails.founders_welcome import render_founders_welcome_email

        html_a = render_founders_welcome_email("Ana")
        html_b = render_founders_welcome_email("Bruno")

        assert "Ana" in html_a
        assert "Ana" not in html_b
        assert "Bruno" in html_b

    def test_contains_key_content_blocks(self):
        from templates.emails.founders_welcome import render_founders_welcome_email

        html = render_founders_welcome_email("Teste")

        # Subject / main heading signal
        assert "Fundadores" in html
        # Bullet: lifetime access
        assert "vitalicio" in html
        # Bullet: consulting discount
        assert "Consultoria" in html
        # CTA link
        assert "/buscar" in html
        # Personal reply invitation
        assert "Responda" in html

    def test_personal_from_signature(self):
        from templates.emails.founders_welcome import render_founders_welcome_email

        html = render_founders_welcome_email("X")

        # Tiago signs the email
        assert "Tiago" in html

    def test_subject_constant(self):
        from templates.emails.founders_welcome import FOUNDERS_WELCOME_SUBJECT

        assert "Fundadores" in FOUNDERS_WELCOME_SUBJECT
        assert "SmartLic" in FOUNDERS_WELCOME_SUBJECT

    def test_plain_text_version(self):
        from templates.emails.founders_welcome import render_founders_welcome_plain

        text = render_founders_welcome_plain("Daniela")

        assert "Daniela" in text
        assert "50%" in text
        assert "smartlic.tech/buscar" in text
        assert "Tiago" in text
        # Plain text should not contain HTML tags
        assert "<" not in text
        assert ">" not in text


# ---------------------------------------------------------------------------
# send_founders_welcome_email — idempotency & DB interaction
# ---------------------------------------------------------------------------

class TestSendFoundersWelcomeEmail:
    """Tests for email_service.send_founders_welcome_email."""

    def _make_db_mock(self, lead_row: dict | None = None):
        """Helper: build a Supabase mock returning lead_row from .execute()."""
        db = MagicMock()
        result = MagicMock()
        result.data = [lead_row] if lead_row else []
        (
            db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .limit.return_value
            .execute.return_value
        ) = result
        return db

    def test_skips_when_already_sent(self):
        """No email sent if welcome_sent_at is already set."""
        lead = {"id": "lead-1", "welcome_sent_at": "2026-05-07T10:00:00+00:00"}
        db_mock = self._make_db_mock(lead)

        with (
            patch("email_service._is_configured", return_value=True),
            patch("supabase_client.get_supabase", return_value=db_mock),
            patch("email_service.send_email") as mock_send,
        ):
            from email_service import send_founders_welcome_email

            result = send_founders_welcome_email("founder@example.com", "Fundador")

        assert result is None
        mock_send.assert_not_called()

    def test_skips_when_no_completed_lead(self):
        """No email sent if no completed founding_lead row found."""
        db_mock = self._make_db_mock(lead_row=None)  # empty list

        with (
            patch("email_service._is_configured", return_value=True),
            patch("supabase_client.get_supabase", return_value=db_mock),
            patch("email_service.send_email") as mock_send,
        ):
            from email_service import send_founders_welcome_email

            result = send_founders_welcome_email("nolead@example.com", "Ghost")

        assert result is None
        mock_send.assert_not_called()

    def test_sends_and_updates_welcome_sent_at(self):
        """Email is sent and welcome_sent_at is set on the lead."""
        lead = {"id": "lead-42", "welcome_sent_at": None}
        db_mock = self._make_db_mock(lead)

        # Simulate the UPDATE call chain
        update_chain = MagicMock()
        db_mock.table.return_value.update.return_value.eq.return_value = update_chain

        with (
            patch("email_service._is_configured", return_value=True),
            patch("supabase_client.get_supabase", return_value=db_mock),
            patch("email_service.send_email", return_value="email-id-xyz") as mock_send,
        ):
            from email_service import send_founders_welcome_email

            result = send_founders_welcome_email("ok@example.com", "Bom Fundador")

        assert result == "email-id-xyz"
        mock_send.assert_called_once()

        # Verify UPDATE was attempted on the lead row
        db_mock.table.return_value.update.assert_called_once()
        update_payload = db_mock.table.return_value.update.call_args[0][0]
        assert "welcome_sent_at" in update_payload

    def test_no_update_when_send_fails(self):
        """welcome_sent_at is NOT updated if email send returns None."""
        lead = {"id": "lead-7", "welcome_sent_at": None}
        db_mock = self._make_db_mock(lead)

        with (
            patch("email_service._is_configured", return_value=True),
            patch("supabase_client.get_supabase", return_value=db_mock),
            patch("email_service.send_email", return_value=None),
        ):
            from email_service import send_founders_welcome_email

            result = send_founders_welcome_email("fail@example.com", "Fundador Falhou")

        assert result is None
        # UPDATE should not have been called
        db_mock.table.return_value.update.assert_not_called()

    def test_returns_none_when_not_configured(self):
        """Returns None immediately when email service is disabled."""
        with patch("email_service._is_configured", return_value=False):
            from email_service import send_founders_welcome_email

            result = send_founders_welcome_email("x@example.com", "X")

        assert result is None

    def test_sends_from_tiago_address(self):
        """Email is sent from Tiago's personal address."""
        lead = {"id": "lead-99", "welcome_sent_at": None}
        db_mock = self._make_db_mock(lead)
        db_mock.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with (
            patch("email_service._is_configured", return_value=True),
            patch("supabase_client.get_supabase", return_value=db_mock),
            patch("email_service.send_email", return_value="id-abc") as mock_send,
        ):
            from email_service import send_founders_welcome_email

            send_founders_welcome_email("vip@example.com", "VIP")

        _, kwargs = mock_send.call_args
        assert kwargs.get("from_email") == "Tiago do SmartLic <tiago@smartlic.tech>"
        assert kwargs.get("reply_to") == "tiago.sasaki@gmail.com"


# ---------------------------------------------------------------------------
# ARQ job: send_founders_welcome
# ---------------------------------------------------------------------------

class TestSendFoundersWelcomeJob:
    """Tests for jobs.queue.jobs.send_founders_welcome."""

    @pytest.mark.asyncio
    async def test_job_sends_email_and_mixpanel(self):
        """Job dispatches email and calls Mixpanel people set on success."""
        with (
            patch("email_service.send_founders_welcome_email", return_value="e-123") as mock_email,
            patch.dict("os.environ", {"MIXPANEL_TOKEN": "test-token"}),
            patch("analytics_events.set_user_profile") as mock_mp,
        ):
            from jobs.queue.jobs import send_founders_welcome

            result = await send_founders_welcome(
                ctx={},
                user_email="founder@smartlic.tech",
                user_name="Tester",
            )

        assert result["status"] == "sent"
        assert result["email_id"] == "e-123"
        mock_email.assert_called_once_with(
            user_email="founder@smartlic.tech", user_name="Tester"
        )
        mock_mp.assert_called_once_with(
            "founder@smartlic.tech", {"is_founder": True, "plan": "founders"}
        )

    @pytest.mark.asyncio
    async def test_job_skipped_returns_skipped_status(self):
        """Job returns skipped when email function returns None (already sent)."""
        with (
            patch("email_service.send_founders_welcome_email", return_value=None),
            patch.dict("os.environ", {"MIXPANEL_TOKEN": ""}),
        ):
            from jobs.queue.jobs import send_founders_welcome

            result = await send_founders_welcome(
                ctx={},
                user_email="dup@example.com",
                user_name="Dup User",
            )

        assert result["status"] == "skipped"
        assert result["email_id"] is None

    @pytest.mark.asyncio
    async def test_job_handles_email_exception(self):
        """Job returns error status without raising when email throws."""
        with patch(
            "email_service.send_founders_welcome_email",
            side_effect=RuntimeError("SMTP down"),
        ):
            from jobs.queue.jobs import send_founders_welcome

            result = await send_founders_welcome(
                ctx={},
                user_email="err@example.com",
                user_name="Error Case",
            )

        assert result["status"] == "error"
        assert "SMTP down" in result["error"]

    @pytest.mark.asyncio
    async def test_job_no_mixpanel_when_token_absent(self):
        """Mixpanel set is NOT called when MIXPANEL_TOKEN is not set."""
        with (
            patch("email_service.send_founders_welcome_email", return_value="id-1"),
            patch.dict("os.environ", {"MIXPANEL_TOKEN": ""}),
            patch("analytics_events.set_user_profile") as mock_mp,
        ):
            from jobs.queue.jobs import send_founders_welcome

            await send_founders_welcome(
                ctx={},
                user_email="nmp@example.com",
                user_name="No MP",
            )

        mock_mp.assert_not_called()


# ---------------------------------------------------------------------------
# set_user_profile in analytics_events
# ---------------------------------------------------------------------------

class TestSetUserProfile:
    def test_calls_mixpanel_people_set(self):
        """set_user_profile delegates to mp.people_set."""
        from analytics_events import reset_for_testing

        reset_for_testing()

        mp_mock = MagicMock()
        with patch("analytics_events._get_mixpanel", return_value=mp_mock):
            from analytics_events import set_user_profile

            set_user_profile("user-abc", {"is_founder": True})

        mp_mock.people_set.assert_called_once_with("user-abc", {"is_founder": True})

    def test_no_op_when_mixpanel_unavailable(self):
        """set_user_profile is a silent no-op when Mixpanel client is None."""
        from analytics_events import reset_for_testing

        reset_for_testing()

        with patch("analytics_events._get_mixpanel", return_value=None):
            from analytics_events import set_user_profile

            # Should not raise
            set_user_profile("user-xyz", {"is_founder": True})

    def test_never_raises_on_exception(self):
        """set_user_profile swallows exceptions (fire-and-forget contract)."""
        from analytics_events import reset_for_testing

        reset_for_testing()

        mp_mock = MagicMock()
        mp_mock.people_set.side_effect = RuntimeError("Mixpanel API down")
        with patch("analytics_events._get_mixpanel", return_value=mp_mock):
            from analytics_events import set_user_profile

            # Must not raise
            set_user_profile("user-err", {"is_founder": True})
