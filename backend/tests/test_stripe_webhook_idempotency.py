"""
AC5 test for GitHub issue #718:
Simulates a webhook replay of checkout.session.completed for an Intel Report
one-time payment and asserts that:
1. The second (replayed) call returns {"status": "already_processed", "event_id": ...}
2. intel_report_purchases.insert is called exactly ONCE (not twice)

The dispatcher (webhooks/stripe.py) gates idempotency via the stripe_webhook_events
table using INSERT ON CONFLICT DO NOTHING (upsert with ignore_duplicates=True).

Call 1 — new event:
  upsert → data=[{id: evt_xxx}]  (row claimed, proceed to handler)
  handler runs → intel_report_purchases.insert called
  stripe_webhook_events updated to status=completed

Call 2 — replay of same event_id:
  upsert → data=[]  (row already exists, ON CONFLICT DO NOTHING)
  stuck-check query → returns status=completed
  dispatcher returns {"status": "already_processed"} immediately
  handler NOT called → intel_report_purchases.insert NOT called again
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

EVENT_ID = "evt_intel_test_718"
EVENT_TYPE = "checkout.session.completed"

SESSION_DATA = {
    "id": "cs_test_abc123",
    "mode": "payment",
    "payment_intent": "pi_test_xyz",
    "payment_status": "paid",
    "metadata": {
        "product_type": "sector_uf_intel",
        "entity_key": "limpeza:SP",
        "user_id": "user-718-test",
    },
}


def _make_stripe_event():
    """Build a minimal Stripe event Mock that passes _validate_event_envelope."""
    event = Mock()
    event.id = EVENT_ID
    event.type = EVENT_TYPE
    event.data = Mock()
    event.data.object = SESSION_DATA  # plain dict — handler uses .get()
    return event


def _make_request():
    """Mock FastAPI Request with async body() and stripe-signature header."""
    request = AsyncMock()
    request.body = AsyncMock(return_value=b'{"id":"' + EVENT_ID.encode() + b'"}')
    request.headers = {"stripe-signature": "t=1234,v1=fakesig"}
    return request


# ────────────────────────────────────────────────────────────────────────────
# Test class
# ────────────────────────────────────────────────────────────────────────────

class TestIntelReportWebhookReplayIdempotency:
    """AC5 / Issue #718 — checkout.session.completed replay must not duplicate purchase."""

    @pytest.mark.asyncio
    @patch("webhooks.stripe.redis_cache")
    @patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test_718")
    @patch("webhooks.stripe.get_supabase")
    @patch("webhooks.stripe.stripe.Webhook.construct_event")
    async def test_replay_returns_already_processed_and_no_duplicate_purchase(
        self,
        mock_construct,
        mock_get_sb,
        mock_redis,     # noqa: ARG002
    ):
        """
        Simulate two sequential deliveries of the same event_id.

        After call 1:  intel_report_purchases.insert called once, status=success.
        After call 2:  response is already_processed, insert NOT called again.
        """
        from webhooks.stripe import stripe_webhook

        event = _make_stripe_event()
        mock_construct.return_value = event

        # Patch get_arq_pool at job_queue level (handler imports it inline with
        # `from job_queue import get_arq_pool`). Returning None means the handler
        # skips enqueue silently — the purchase row is still persisted.
        import sys
        import types
        fake_jq = types.ModuleType("job_queue")
        fake_jq.get_arq_pool = AsyncMock(return_value=None)
        sys.modules.setdefault("job_queue", fake_jq)

        # ── Build Supabase mock ────────────────────────────────────────────
        # We need per-call routing because each call to sb.table("stripe_webhook_events")
        # must behave differently for the upsert on round 1 vs round 2.

        # Track intel_report_purchases.insert calls
        insert_call_count = {"n": 0}

        # stripe_webhook_events upsert results: round 1 → data, round 2 → empty
        upsert_results = [
            Mock(data=[{"id": EVENT_ID}]),  # call 1: event claimed
            Mock(data=[]),                  # call 2: already exists
        ]
        upsert_call_index = {"n": 0}

        # stuck-check result (status=completed so second call returns already_processed)
        completed_iso = datetime.now(timezone.utc).isoformat()
        stuck_check_result = Mock(data=[{
            "id": EVENT_ID,
            "status": "completed",
            "received_at": completed_iso,
        }])

        def _make_events_chain():
            """Return a fresh chain wired to the current call index."""
            chain = MagicMock()
            # Capture current index at closure time
            _idx = upsert_call_index["n"]

            def _upsert(*_a, **_kw):
                uc = MagicMock()
                uc.execute.return_value = upsert_results[_idx]
                return uc

            chain.upsert = MagicMock(side_effect=_upsert)

            # select path (stuck-check) — always returns completed
            select_chain = MagicMock()
            select_chain.eq.return_value = select_chain
            select_chain.limit.return_value = select_chain
            select_chain.execute.return_value = stuck_check_result
            chain.select.return_value = select_chain

            # update path (mark completed/failed) — benign
            update_chain = MagicMock()
            update_chain.eq.return_value = update_chain
            update_chain.execute.return_value = Mock(data=[])
            chain.update = MagicMock(return_value=update_chain)

            return chain

        def _make_purchases_chain():
            """intel_report_purchases chain — tracks insert calls."""
            chain = MagicMock()

            def _insert(row):
                insert_call_count["n"] += 1
                ic = MagicMock()
                ic.execute.return_value = Mock(data=[{"id": "purchase-uuid-001"}])
                return ic

            chain.insert = MagicMock(side_effect=_insert)
            return chain

        def _make_default_chain():
            """Benign default for any other table (plans, profiles, etc.)."""
            chain = MagicMock()
            chain.select.return_value = chain
            chain.insert.return_value = chain
            chain.update.return_value = chain
            chain.eq.return_value = chain
            chain.limit.return_value = chain
            chain.single.return_value = chain
            chain.execute.return_value = Mock(data=[])
            return chain

        def _table_factory(name):
            if name == "stripe_webhook_events":
                c = _make_events_chain()
                return c
            if name == "intel_report_purchases":
                return _make_purchases_chain()
            return _make_default_chain()

        sb = MagicMock()
        sb.table = MagicMock(side_effect=_table_factory)
        mock_get_sb.return_value = sb

        # ── Call 1: first delivery ────────────────────────────────────────
        result1 = await stripe_webhook(_make_request())

        assert result1["status"] == "success", (
            f"First delivery must succeed; got {result1!r}"
        )
        assert result1["event_id"] == EVENT_ID
        assert insert_call_count["n"] == 1, (
            "intel_report_purchases.insert should be called exactly once on first delivery"
        )

        # ── Prepare round 2: upsert must return empty (already exists) ────
        upsert_call_index["n"] = 1  # point to upsert_results[1] → data=[]

        # ── Call 2: replay (duplicate) ────────────────────────────────────
        result2 = await stripe_webhook(_make_request())

        assert result2["status"] == "already_processed", (
            f"Replay must return already_processed; got {result2!r}"
        )
        assert result2["event_id"] == EVENT_ID

        # The critical assertion for AC5: no second insert row created
        assert insert_call_count["n"] == 1, (
            f"intel_report_purchases.insert should still be called exactly once "
            f"after replay; got {insert_call_count['n']} calls"
        )
