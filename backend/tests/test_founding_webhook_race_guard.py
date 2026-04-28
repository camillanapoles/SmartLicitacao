"""BIZ-FOUND-002: tests for the post-completion race guard in
``webhooks.handlers.founding.mark_founding_lead_completed``.

Concurrent checkouts can both pass the pre-checkout availability gate when
seats_remaining is small. The first one closes the cohort; the second
finishes Stripe checkout AFTER the cap is full. The webhook handler must:
- detect the over-sell via post-completion RPC re-check,
- revert the founding_leads row to ``cap_violated``,
- issue a Stripe refund against the payment_intent,
- queue an apology email.

Other ``available=false`` reasons (paused, deadline, disabled) MUST NOT
trigger refunds (those are structural changes, not races).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")

from webhooks.handlers.founding import (  # noqa: E402
    mark_founding_lead_completed,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _founding_session(payment_intent: str = "pi_test_123") -> dict:
    """Stripe checkout.session.completed object with founding metadata."""
    return {
        "id": "cs_test_race_guard",
        "metadata": {"source": "founding"},
        "customer": "cus_42",
        "customer_email": "racer@empresa.com",
        "payment_intent": payment_intent,
    }


def _make_sb_with_rpc_sequence(rpc_data_per_call: list[list[dict]]) -> MagicMock:
    """Build a fake supabase client whose .rpc().execute() returns the next
    canned payload on each call. ``rpc_data_per_call`` is a list of payloads;
    the i-th call returns the i-th payload.
    """
    fake_sb = MagicMock()
    rpc_chain = MagicMock()
    fake_sb.rpc.return_value = rpc_chain

    results = [MagicMock(data=d) for d in rpc_data_per_call]
    rpc_chain.execute.side_effect = results

    # Default table().update().eq().execute() chain returns 1 row updated.
    fake_sb.table.return_value = fake_sb
    fake_sb.update.return_value = fake_sb
    fake_sb.eq.return_value = fake_sb
    fake_sb.select.return_value = fake_sb
    fake_sb.limit.return_value = fake_sb
    fake_sb.execute.return_value = MagicMock(data=[{"id": "lead-1"}])
    return fake_sb


# ---------------------------------------------------------------------------
# Race guard — happy paths
# ---------------------------------------------------------------------------


def test_skips_when_session_is_not_founding():
    """Non-founding session (regular checkout) — handler exits early, no RPC."""
    sb = MagicMock()
    session = {"id": "cs_test", "metadata": {"source": "regular"}, "customer": "cus_x"}
    mark_founding_lead_completed(sb, session)
    assert not sb.rpc.called
    assert not sb.update.called


@patch("webhooks.handlers.founding._send_cap_violation_email")
@patch("webhooks.handlers.founding._refund_session_charge")
def test_post_completion_rpc_available_no_refund(mock_refund, mock_email):
    """When post-completion RPC says available=true, NO refund/email."""
    sb = _make_sb_with_rpc_sequence([
        # Single RPC call (post-completion re-check).
        [
            {
                "available": True,
                "seats_remaining": 42,
                "seats_total": 50,
                "deadline_at": "2026-05-30T23:59:59-03:00",
                "paused": False,
                "reason": "available",
            }
        ]
    ])

    mark_founding_lead_completed(sb, _founding_session())

    # First update flips status to completed; no second update reverting.
    update_calls = sb.update.call_args_list
    assert any(call.args[0].get("checkout_status") == "completed" for call in update_calls)
    assert all(call.args[0].get("checkout_status") != "cap_violated" for call in update_calls)
    mock_refund.assert_not_called()
    mock_email.assert_not_called()


@patch("webhooks.handlers.founding._send_cap_violation_email")
@patch("webhooks.handlers.founding._refund_session_charge")
def test_post_completion_cap_violation_triggers_refund(mock_refund, mock_email):
    """available=false with reason=founding_cap_reached -> refund + email + revert."""
    mock_refund.return_value = True

    sb = _make_sb_with_rpc_sequence([
        # Post-completion re-check sees cap full.
        [
            {
                "available": False,
                "seats_remaining": 0,
                "seats_total": 50,
                "deadline_at": "2026-05-30T23:59:59-03:00",
                "paused": False,
                "reason": "founding_cap_reached",
            }
        ]
    ])

    mark_founding_lead_completed(sb, _founding_session())

    # 1st update: completed flip. 2nd update: revert to cap_violated.
    update_payloads = [call.args[0] for call in sb.update.call_args_list]
    assert any(p.get("checkout_status") == "completed" for p in update_payloads)
    assert any(p.get("checkout_status") == "cap_violated" for p in update_payloads)

    mock_refund.assert_called_once()
    mock_email.assert_called_once()


@patch("webhooks.handlers.founding._send_cap_violation_email")
@patch("webhooks.handlers.founding._refund_session_charge")
def test_post_completion_paused_does_not_refund(mock_refund, mock_email):
    """reason=founding_paused (operator pause) -> NO refund (structural, not race)."""
    sb = _make_sb_with_rpc_sequence([
        [
            {
                "available": False,
                "seats_remaining": 25,
                "seats_total": 50,
                "deadline_at": "2026-05-30T23:59:59-03:00",
                "paused": True,
                "reason": "founding_paused",
            }
        ]
    ])

    mark_founding_lead_completed(sb, _founding_session())

    mock_refund.assert_not_called()
    mock_email.assert_not_called()


@patch("webhooks.handlers.founding._send_cap_violation_email")
@patch("webhooks.handlers.founding._refund_session_charge")
def test_post_completion_deadline_passed_does_not_refund(mock_refund, mock_email):
    """reason=founding_deadline_passed -> NO refund (structural)."""
    sb = _make_sb_with_rpc_sequence([
        [
            {
                "available": False,
                "seats_remaining": 17,
                "seats_total": 50,
                "deadline_at": "2026-05-30T23:59:59-03:00",
                "paused": False,
                "reason": "founding_deadline_passed",
            }
        ]
    ])

    mark_founding_lead_completed(sb, _founding_session())

    mock_refund.assert_not_called()
    mock_email.assert_not_called()


@patch("webhooks.handlers.founding._send_cap_violation_email")
@patch("webhooks.handlers.founding._refund_session_charge")
def test_post_completion_rpc_unavailable_skips_refund(mock_refund, mock_email):
    """RPC returns None (DB flaky) -> fail closed: no refund."""
    fake_sb = MagicMock()
    fake_sb.rpc.return_value = MagicMock(execute=MagicMock(side_effect=Exception("db down")))
    fake_sb.table.return_value = fake_sb
    fake_sb.update.return_value = fake_sb
    fake_sb.eq.return_value = fake_sb
    fake_sb.execute.return_value = MagicMock(data=[{"id": "lead-1"}])

    mark_founding_lead_completed(fake_sb, _founding_session())

    mock_refund.assert_not_called()
    mock_email.assert_not_called()


@patch("webhooks.handlers.founding._send_cap_violation_email")
@patch("webhooks.handlers.founding._refund_session_charge")
def test_concurrent_checkouts_only_one_refunded(mock_refund, mock_email):
    """Simulate 2 concurrent webhooks when 1 seat remains.

    Sequence:
    - Webhook A fires first; post-completion RPC sees available=true (still 1 seat).
    - Webhook B fires second; post-completion RPC sees available=false (cap_reached).

    Only B should be refunded.
    """
    mock_refund.return_value = True

    # Webhook A: post-check -> still available (because B hasn't completed yet
    # in this simulation).
    sb_a = _make_sb_with_rpc_sequence([
        [
            {
                "available": True,
                "seats_remaining": 1,
                "seats_total": 50,
                "deadline_at": "2026-05-30T23:59:59-03:00",
                "paused": False,
                "reason": "available",
            }
        ]
    ])

    # Webhook B: post-check -> cap reached (because A already completed).
    sb_b = _make_sb_with_rpc_sequence([
        [
            {
                "available": False,
                "seats_remaining": 0,
                "seats_total": 50,
                "deadline_at": "2026-05-30T23:59:59-03:00",
                "paused": False,
                "reason": "founding_cap_reached",
            }
        ]
    ])

    mark_founding_lead_completed(sb_a, _founding_session(payment_intent="pi_a"))
    mark_founding_lead_completed(sb_b, _founding_session(payment_intent="pi_b"))

    # A: no refund. B: refunded once.
    assert mock_refund.call_count == 1
    assert mock_email.call_count == 1


# ---------------------------------------------------------------------------
# Refund helper — guards against missing payment_intent
# ---------------------------------------------------------------------------


def test_refund_helper_skips_when_payment_intent_missing():
    """No payment_intent in session -> helper exits without calling Stripe."""
    from webhooks.handlers.founding import _refund_session_charge

    session = {
        "id": "cs_test_no_pi",
        "metadata": {"source": "founding"},
        # No payment_intent
    }

    # Should not raise; should return False.
    assert _refund_session_charge(session) is False
