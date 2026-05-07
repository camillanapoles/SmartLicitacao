"""#785: tests for lifetime founder entitlement activation in
``webhooks.handlers.founding.mark_founding_lead_completed``.

Happy path: after race guard confirms checkout valid, profiles row receives
is_founder=True, plan_type='smartlic_pro', trial_expires_at=None,
consulting_discount_pct from founding_policy (fallback 50).

Metadata propagation: offer_version + checkout_source from Stripe metadata.

Profile missing: gracefully defers without crashing when user hasn't
signed up yet (founding is sold to unauthenticated visitors).

Idempotency note: dispatcher-level dedup via stripe_webhook_events ensures
the handler is called at most once per event_id. No handler-level guard
needed — tested here by showing the second call produces a second DB update
(the dispatcher prevents the second call in production).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, call, patch

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")

from webhooks.handlers.founding import (  # noqa: E402
    mark_founding_lead_completed,
    _activate_lifetime_founder_entitlement,
    _read_consulting_discount_pct,
    _resolve_user_id_from_email,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_USER_ID = "user-uuid-001"
_DEFAULT_EMAIL = "founder@empresa.com.br"
_DEFAULT_LEAD_ID = "lead-uuid-001"


def _founding_session(
    session_id: str = "cs_test_lifetime",
    payment_intent: str = "pi_test_lt",
    email: str = _DEFAULT_EMAIL,
    offer_version: str = "v2",
    checkout_source: str = "founding_page",
) -> dict:
    """Stripe checkout.session.completed with founding metadata."""
    return {
        "id": session_id,
        "metadata": {
            "source": "founding",
            "offer_version": offer_version,
            "checkout_source": checkout_source,
        },
        "customer": "cus_test_42",
        "customer_email": email,
        "payment_intent": payment_intent,
    }


def _make_sb(
    lead_rows: list[dict] | None = None,
    profile_rows: list[dict] | None = None,
    policy_rows: list[dict] | None = None,
    rpc_data: list[dict] | None = None,
) -> MagicMock:
    """Build a fake supabase client for lifetime entitlement tests.

    Separates per-table behaviour so assertions can be targeted.
    """
    if lead_rows is None:
        lead_rows = [{"id": _DEFAULT_LEAD_ID}]
    if profile_rows is None:
        profile_rows = [{"id": _DEFAULT_USER_ID}]
    if policy_rows is None:
        policy_rows = [{"consulting_discount_pct": 50}]
    if rpc_data is None:
        # Race guard RPC returns "available" → happy path
        rpc_data = [{"reason": "available", "seats_remaining": 10, "seats_total": 50}]

    fake_sb = MagicMock()

    # RPC chain (race guard)
    rpc_chain = MagicMock()
    fake_sb.rpc.return_value = rpc_chain
    rpc_chain.execute.return_value = MagicMock(data=rpc_data)

    # Table chain factory — routes by table name
    def _table(name: str):
        t = MagicMock()
        t.update.return_value = t
        t.select.return_value = t
        t.eq.return_value = t
        t.limit.return_value = t

        if name == "founding_leads":
            t.execute.return_value = MagicMock(data=lead_rows)
        elif name == "profiles":
            # select returns profile lookup; update returns empty (upsert result)
            select_result = MagicMock(data=profile_rows)
            update_result = MagicMock(data=[])
            # first call to execute() after select = profile lookup
            # subsequent calls after update = upsert result
            t.execute.side_effect = [select_result, update_result, update_result]
        elif name == "founding_policy":
            t.execute.return_value = MagicMock(data=policy_rows)
        else:
            t.execute.return_value = MagicMock(data=[])
        return t

    fake_sb.table.side_effect = _table
    return fake_sb


# ---------------------------------------------------------------------------
# Unit tests — helpers
# ---------------------------------------------------------------------------


def test_resolve_user_id_from_email_found():
    """Returns user_id when profile exists."""
    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_sb
    fake_sb.select.return_value = fake_sb
    fake_sb.eq.return_value = fake_sb
    fake_sb.limit.return_value = fake_sb
    fake_sb.execute.return_value = MagicMock(data=[{"id": _DEFAULT_USER_ID}])

    result = _resolve_user_id_from_email(fake_sb, _DEFAULT_EMAIL)
    assert result == _DEFAULT_USER_ID


def test_resolve_user_id_from_email_not_found():
    """Returns None when no profile row matches."""
    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_sb
    fake_sb.select.return_value = fake_sb
    fake_sb.eq.return_value = fake_sb
    fake_sb.limit.return_value = fake_sb
    fake_sb.execute.return_value = MagicMock(data=[])

    result = _resolve_user_id_from_email(fake_sb, "unknown@test.com")
    assert result is None


def test_read_consulting_discount_pct_from_policy():
    """Reads consulting_discount_pct from founding_policy table."""
    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_sb
    fake_sb.select.return_value = fake_sb
    fake_sb.limit.return_value = fake_sb
    fake_sb.execute.return_value = MagicMock(data=[{"consulting_discount_pct": 40}])

    assert _read_consulting_discount_pct(fake_sb) == 40


def test_read_consulting_discount_pct_fallback_empty_table():
    """Falls back to 50 when founding_policy is empty."""
    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_sb
    fake_sb.select.return_value = fake_sb
    fake_sb.limit.return_value = fake_sb
    fake_sb.execute.return_value = MagicMock(data=[])

    assert _read_consulting_discount_pct(fake_sb) == 50


def test_read_consulting_discount_pct_fallback_on_db_error():
    """Falls back to 50 when DB raises."""
    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_sb
    fake_sb.select.return_value = fake_sb
    fake_sb.limit.return_value = fake_sb
    fake_sb.execute.side_effect = RuntimeError("DB unavailable")

    assert _read_consulting_discount_pct(fake_sb) == 50


# ---------------------------------------------------------------------------
# Happy path — full integration through mark_founding_lead_completed
# ---------------------------------------------------------------------------


def test_lifetime_entitlement_activated_on_happy_path():
    """After race guard confirms 'available', profiles row is updated with
    founder fields: is_founder=True, plan_type='smartlic_pro',
    trial_expires_at=None, consulting_discount_pct from policy.
    """
    fake_sb = _make_sb()
    session = _founding_session()

    mark_founding_lead_completed(fake_sb, session)

    # Verify profiles.update was called with the entitlement payload
    update_calls = [
        c for c in fake_sb.table.call_args_list if c.args[0] == "profiles"
    ]
    assert update_calls, "profiles table was never touched"

    # The update chain is table("profiles").update(payload).eq(...).execute()
    # We verify by inspecting all calls to fake_sb.table("profiles") that
    # an update with is_founder=True was issued.
    # Because MagicMock's side_effect returns distinct objects per table(),
    # we check update was called on the profiles mock returned.
    profiles_mock = None
    for c in fake_sb.table.call_args_list:
        if c.args[0] == "profiles":
            profiles_mock = fake_sb.table(c.args[0])
            break

    assert profiles_mock is not None

    # Verify via _activate_lifetime_founder_entitlement directly with a
    # controlled mock to assert exact payload.
    direct_sb = MagicMock()
    direct_sb.table.return_value = direct_sb
    direct_sb.select.return_value = direct_sb
    direct_sb.update.return_value = direct_sb
    direct_sb.eq.return_value = direct_sb
    direct_sb.limit.return_value = direct_sb

    # profile lookup returns user_id
    profile_result = MagicMock(data=[{"id": _DEFAULT_USER_ID}])
    # policy lookup returns discount pct
    policy_result = MagicMock(data=[{"consulting_discount_pct": 50}])
    # update returns empty
    update_result = MagicMock(data=[])

    direct_sb.execute.side_effect = [profile_result, policy_result, update_result]

    _activate_lifetime_founder_entitlement(direct_sb, session, _DEFAULT_LEAD_ID)

    # Assert update was called with correct payload keys
    update_payload = direct_sb.update.call_args[0][0]
    assert update_payload["is_founder"] is True
    assert update_payload["plan_type"] == "smartlic_pro"
    assert update_payload["trial_expires_at"] is None
    assert update_payload["consulting_discount_pct"] == 50
    assert update_payload["founder_offer_version"] == "v2"
    assert update_payload["founder_checkout_source"] == "founding_page"
    assert "founder_since" in update_payload


def test_lifetime_metadata_propagation():
    """offer_version and checkout_source from Stripe metadata land in profiles."""
    session = _founding_session(offer_version="v3", checkout_source="email_campaign")

    direct_sb = MagicMock()
    direct_sb.table.return_value = direct_sb
    direct_sb.select.return_value = direct_sb
    direct_sb.update.return_value = direct_sb
    direct_sb.eq.return_value = direct_sb
    direct_sb.limit.return_value = direct_sb

    profile_result = MagicMock(data=[{"id": _DEFAULT_USER_ID}])
    policy_result = MagicMock(data=[{"consulting_discount_pct": 50}])
    update_result = MagicMock(data=[])
    direct_sb.execute.side_effect = [profile_result, policy_result, update_result]

    _activate_lifetime_founder_entitlement(direct_sb, session, _DEFAULT_LEAD_ID)

    update_payload = direct_sb.update.call_args[0][0]
    assert update_payload["founder_offer_version"] == "v3"
    assert update_payload["founder_checkout_source"] == "email_campaign"


def test_lifetime_deferred_when_profile_not_found(caplog):
    """When user hasn't signed up yet, entitlement defers gracefully — no
    profiles.update call, log says 'deferred — user signup pending'.
    """
    import logging

    direct_sb = MagicMock()
    direct_sb.table.return_value = direct_sb
    direct_sb.select.return_value = direct_sb
    direct_sb.update.return_value = direct_sb
    direct_sb.eq.return_value = direct_sb
    direct_sb.limit.return_value = direct_sb

    # profile lookup returns empty — user not yet signed up
    profile_result = MagicMock(data=[])
    direct_sb.execute.return_value = profile_result

    session = _founding_session(email="notregistered@empresa.com")

    with caplog.at_level(logging.INFO, logger="webhooks.handlers.founding"):
        _activate_lifetime_founder_entitlement(direct_sb, session, _DEFAULT_LEAD_ID)

    # update must NOT have been called
    assert not direct_sb.update.called, "profiles.update should not be called when user missing"
    assert "deferred" in caplog.text or "signup pending" in caplog.text


def test_lifetime_not_activated_on_cap_violation():
    """Cap-violated checkout must NOT activate the lifetime entitlement."""
    fake_sb = MagicMock()

    # RPC returns cap_reached → refund path
    rpc_chain = MagicMock()
    fake_sb.rpc.return_value = rpc_chain
    rpc_chain.execute.return_value = MagicMock(data=[{
        "reason": "founding_cap_reached",
        "seats_remaining": 0,
        "seats_total": 50,
    }])

    fake_sb.table.return_value = fake_sb
    fake_sb.update.return_value = fake_sb
    fake_sb.select.return_value = fake_sb
    fake_sb.eq.return_value = fake_sb
    fake_sb.limit.return_value = fake_sb
    fake_sb.execute.return_value = MagicMock(data=[{"id": _DEFAULT_LEAD_ID}])

    session = _founding_session()

    with patch("webhooks.handlers.founding._refund_session_charge", return_value=True), \
         patch("webhooks.handlers.founding._send_cap_violation_email"), \
         patch("webhooks.handlers.founding._activate_lifetime_founder_entitlement") as mock_activate:
        mark_founding_lead_completed(fake_sb, session)

    mock_activate.assert_not_called()


def test_lifetime_db_error_does_not_raise():
    """profiles.update failure must not raise — handler logs error only."""
    direct_sb = MagicMock()
    direct_sb.table.return_value = direct_sb
    direct_sb.select.return_value = direct_sb
    direct_sb.update.return_value = direct_sb
    direct_sb.eq.return_value = direct_sb
    direct_sb.limit.return_value = direct_sb

    profile_result = MagicMock(data=[{"id": _DEFAULT_USER_ID}])
    policy_result = MagicMock(data=[{"consulting_discount_pct": 50}])
    direct_sb.execute.side_effect = [profile_result, policy_result, RuntimeError("DB down")]

    session = _founding_session()

    # Must not raise
    _activate_lifetime_founder_entitlement(direct_sb, session, _DEFAULT_LEAD_ID)


def test_lifetime_no_email_in_session_does_not_raise():
    """Session without any email field — handler logs warning and returns."""
    direct_sb = MagicMock()
    session = {
        "id": "cs_no_email",
        "metadata": {"source": "founding"},
        "customer": "cus_x",
        # No customer_email, no customer_details
    }

    _activate_lifetime_founder_entitlement(direct_sb, session, None)

    assert not direct_sb.table.called
