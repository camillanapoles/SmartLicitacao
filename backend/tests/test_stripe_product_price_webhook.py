"""BILL-SYNC-001: tests for the 4 new Stripe webhook handlers.

Coverage:
    AC1  — handler updates plan_billing_periods on product.updated
    AC1  — handler updates plan_billing_periods on price.updated
    AC2  — dispatcher routes the 4 new event types
    AC3  — webhook signature verification preserved end-to-end
    AC9  — 24h race guard skips writes when last_reverse_synced_at < 24h ago
    AC1/R1 — out-of-order event protection (stale event ignored)
    Idempotency: same event_id processed 2x => DB unchanged after 2nd dispatch.
    price.deleted => is_archived=TRUE.

Mocking patterns (matches test_stripe_webhook.py):
    - @patch('webhooks.stripe.STRIPE_WEBHOOK_SECRET', 'whsec_test')
    - @patch('webhooks.stripe.stripe.Webhook.construct_event')
    - @patch('webhooks.stripe.get_supabase')
    - AsyncMock for request.body()
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, AsyncMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_request():
    request = AsyncMock()
    request.body = AsyncMock(return_value=b'{"id":"evt_bill_001"}')
    request.headers = {"stripe-signature": "t=1,v1=sig"}
    return request


def _build_supabase_mock(rows: list[dict] | None = None, *, idempotency_already=False):
    """Supabase chain mock that tracks update() payloads per row id."""
    sb = MagicMock()
    update_calls: list[tuple[str, dict]] = []
    select_calls: list[str] = []

    def _make_chain(table_name: str):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.insert.return_value = chain
        chain.upsert.return_value = chain
        chain.delete.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.order.return_value = chain
        chain.single.return_value = chain

        # Track update payloads per table.
        def update_side_effect(payload):
            chain._pending_update = payload
            return chain

        chain.update.side_effect = update_side_effect
        chain._pending_update = None

        if table_name == "stripe_webhook_events":
            # Dispatcher idempotency upsert.
            if idempotency_already:
                chain.execute.return_value = Mock(data=[])
            else:
                chain.execute.return_value = Mock(data=[{"id": "evt_bill_001"}])
        elif table_name == "plan_billing_periods":
            # First select returns the rows. Subsequent updates return data=[].
            chain.execute.side_effect = lambda: Mock(
                data=rows if rows is not None else []
            )

            def eq_then_execute(_col, val):
                # When .update().eq("id", val).execute() is called, capture.
                if chain._pending_update is not None:
                    update_calls.append((val, dict(chain._pending_update)))
                    chain._pending_update = None
                    chain.execute.side_effect = lambda: Mock(data=[])
                return chain

            chain.eq.side_effect = eq_then_execute
        else:
            chain.execute.return_value = Mock(data=[])
        return chain

    table_mocks: dict[str, MagicMock] = {}

    def table_factory(name):
        if name not in table_mocks:
            table_mocks[name] = _make_chain(name)
        return table_mocks[name]

    sb.table = MagicMock(side_effect=table_factory)
    sb.update_calls = update_calls  # exposed for assertions
    sb.select_calls = select_calls
    return sb


def _make_event(event_id="evt_bill_001", event_type="price.updated", data_object=None,
                created: int | None = None):
    event = Mock()
    event.id = event_id
    event.type = event_type
    event.created = created if created is not None else int(
        datetime.now(timezone.utc).timestamp()
    )
    if data_object is None:
        data_object = {"id": "price_default", "active": True, "product": "prod_default"}
    event.data = Mock()
    event.data.object = data_object
    return event


# ---------------------------------------------------------------------------
# Direct handler tests (unit level, no dispatcher)
# ---------------------------------------------------------------------------
class TestProductUpdatedHandler:
    @pytest.mark.asyncio
    async def test_updates_last_forward_synced_at(self):
        from webhooks.handlers.stripe_product_price import handle_product_updated

        rows = [
            {
                "id": "row-1",
                "plan_id": "smartlic_pro",
                "billing_period": "monthly",
                "last_forward_synced_at": None,
                "last_reverse_synced_at": None,
            }
        ]
        sb = _build_supabase_mock(rows=rows)
        event = _make_event(
            event_type="product.updated",
            data_object={"id": "prod_test_1", "name": "SmartLic Pro"},
        )
        result = await handle_product_updated(sb, event)

        assert result["status"] == "ok"
        assert result["updated"] == 1
        assert result["product_id"] == "prod_test_1"
        assert any(
            row_id == "row-1" and "last_forward_synced_at" in payload
            for row_id, payload in sb.update_calls
        )

    @pytest.mark.asyncio
    async def test_no_matching_rows_returns_skipped(self):
        from webhooks.handlers.stripe_product_price import handle_product_updated

        sb = _build_supabase_mock(rows=[])
        event = _make_event(
            event_type="product.updated",
            data_object={"id": "prod_orphan"},
        )
        result = await handle_product_updated(sb, event)
        assert result["status"] == "skipped"
        assert result["reason"] == "no_matching_rows"


class TestPriceUpdatedHandler:
    @pytest.mark.asyncio
    async def test_archives_when_active_false(self):
        from webhooks.handlers.stripe_product_price import handle_price_updated

        rows = [
            {
                "id": "row-1",
                "plan_id": "smartlic_pro",
                "billing_period": "monthly",
                "stripe_product_id": "prod_x",
                "last_forward_synced_at": None,
                "last_reverse_synced_at": None,
                "is_archived": False,
            }
        ]
        sb = _build_supabase_mock(rows=rows)
        event = _make_event(
            event_type="price.updated",
            data_object={"id": "price_x", "active": False, "product": "prod_x"},
        )
        result = await handle_price_updated(sb, event)

        assert result["status"] == "ok"
        assert result["updated"] == 1
        # Last update on row-1 should set is_archived=True.
        last_for_row = [p for r, p in sb.update_calls if r == "row-1"][-1]
        assert last_for_row.get("is_archived") is True

    @pytest.mark.asyncio
    async def test_race_guard_skips_recent_reverse_sync(self):
        from webhooks.handlers.stripe_product_price import handle_price_updated

        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        rows = [
            {
                "id": "row-1",
                "plan_id": "smartlic_pro",
                "billing_period": "monthly",
                "stripe_product_id": "prod_x",
                "last_forward_synced_at": None,
                "last_reverse_synced_at": recent,
                "is_archived": False,
            }
        ]
        sb = _build_supabase_mock(rows=rows)
        event = _make_event(
            event_type="price.updated",
            data_object={"id": "price_x", "active": True, "product": "prod_x"},
        )
        result = await handle_price_updated(sb, event)

        assert result["skipped_race_guard"] == 1
        assert result["updated"] == 0
        # No update calls executed against row-1.
        assert all(r != "row-1" for r, _ in sb.update_calls)

    @pytest.mark.asyncio
    async def test_stale_event_ignored(self):
        from webhooks.handlers.stripe_product_price import handle_price_updated

        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        rows = [
            {
                "id": "row-1",
                "plan_id": "smartlic_pro",
                "billing_period": "monthly",
                "stripe_product_id": "prod_x",
                "last_forward_synced_at": future,
                "last_reverse_synced_at": None,
                "is_archived": False,
            }
        ]
        sb = _build_supabase_mock(rows=rows)
        # Event timestamp = NOW (older than the row's last_forward_synced_at=future)
        event = _make_event(
            event_type="price.updated",
            data_object={"id": "price_x", "active": True, "product": "prod_x"},
        )
        result = await handle_price_updated(sb, event)
        assert result["skipped_stale_event"] == 1
        assert result["updated"] == 0


class TestPriceCreatedHandler:
    @pytest.mark.asyncio
    async def test_orphan_price_skipped(self):
        from webhooks.handlers.stripe_product_price import handle_price_created

        sb = _build_supabase_mock(rows=[])
        event = _make_event(
            event_type="price.created",
            data_object={"id": "price_new", "active": True, "product": "prod_x"},
        )
        result = await handle_price_created(sb, event)
        assert result["status"] == "skipped"
        assert result["reason"] == "orphan_price"

    @pytest.mark.asyncio
    async def test_known_price_refreshes_timestamp(self):
        from webhooks.handlers.stripe_product_price import handle_price_created

        rows = [
            {
                "id": "row-1",
                "plan_id": "smartlic_pro",
                "billing_period": "monthly",
                "last_forward_synced_at": None,
                "last_reverse_synced_at": None,
            }
        ]
        sb = _build_supabase_mock(rows=rows)
        event = _make_event(
            event_type="price.created",
            data_object={"id": "price_x", "active": True, "product": "prod_x"},
        )
        result = await handle_price_created(sb, event)
        assert result["status"] == "ok"
        assert result["updated"] == 1


class TestPriceDeletedHandler:
    @pytest.mark.asyncio
    async def test_sets_is_archived_true(self):
        from webhooks.handlers.stripe_product_price import handle_price_deleted

        rows = [
            {
                "id": "row-1",
                "plan_id": "smartlic_pro",
                "billing_period": "monthly",
                "last_forward_synced_at": None,
                "last_reverse_synced_at": None,
                "is_archived": False,
            }
        ]
        sb = _build_supabase_mock(rows=rows)
        event = _make_event(
            event_type="price.deleted",
            data_object={"id": "price_x"},
        )
        result = await handle_price_deleted(sb, event)
        assert result["status"] == "ok"
        assert result["archived"] == 1
        last_for_row = [p for r, p in sb.update_calls if r == "row-1"][-1]
        assert last_for_row.get("is_archived") is True


# ---------------------------------------------------------------------------
# Dispatcher integration tests (signature verify + routing + idempotency)
# ---------------------------------------------------------------------------
class TestDispatcherRouting:
    @pytest.mark.asyncio
    @patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("webhooks.stripe.stripe.Webhook.construct_event")
    @patch("webhooks.stripe.get_supabase")
    async def test_product_updated_routed_to_handler(
        self, mock_get_sb, mock_construct, mock_request
    ):
        from webhooks.stripe import stripe_webhook

        sb = _build_supabase_mock(rows=[])
        mock_get_sb.return_value = sb
        mock_construct.return_value = _make_event(
            event_type="product.updated",
            data_object={"id": "prod_xyz"},
        )

        with patch(
            "webhooks.stripe._handle_product_updated", new_callable=AsyncMock
        ) as h:
            await stripe_webhook(mock_request)
            h.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("webhooks.stripe.stripe.Webhook.construct_event")
    @patch("webhooks.stripe.get_supabase")
    async def test_price_updated_routed(self, mock_get_sb, mock_construct, mock_request):
        from webhooks.stripe import stripe_webhook

        sb = _build_supabase_mock(rows=[])
        mock_get_sb.return_value = sb
        mock_construct.return_value = _make_event(
            event_type="price.updated",
            data_object={"id": "price_x", "active": True, "product": "prod_x"},
        )
        with patch(
            "webhooks.stripe._handle_price_updated", new_callable=AsyncMock
        ) as h:
            await stripe_webhook(mock_request)
            h.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("webhooks.stripe.stripe.Webhook.construct_event")
    @patch("webhooks.stripe.get_supabase")
    async def test_price_created_routed(self, mock_get_sb, mock_construct, mock_request):
        from webhooks.stripe import stripe_webhook

        sb = _build_supabase_mock(rows=[])
        mock_get_sb.return_value = sb
        mock_construct.return_value = _make_event(
            event_type="price.created",
            data_object={"id": "price_x", "active": True, "product": "prod_x"},
        )
        with patch(
            "webhooks.stripe._handle_price_created", new_callable=AsyncMock
        ) as h:
            await stripe_webhook(mock_request)
            h.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("webhooks.stripe.stripe.Webhook.construct_event")
    @patch("webhooks.stripe.get_supabase")
    async def test_price_deleted_routed(self, mock_get_sb, mock_construct, mock_request):
        from webhooks.stripe import stripe_webhook

        sb = _build_supabase_mock(rows=[])
        mock_get_sb.return_value = sb
        mock_construct.return_value = _make_event(
            event_type="price.deleted",
            data_object={"id": "price_x"},
        )
        with patch(
            "webhooks.stripe._handle_price_deleted", new_callable=AsyncMock
        ) as h:
            await stripe_webhook(mock_request)
            h.assert_awaited_once()


class TestSignatureVerificationPreserved:
    @pytest.mark.asyncio
    @patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test")
    async def test_invalid_signature_blocks_new_handlers(self, mock_request):
        """Tampered payload must reject before any handler runs.

        BTS-011 (isolation): A previous test in the suite may have replaced
        ``sys.modules['stripe']`` with a ``MagicMock`` / ``SimpleNamespace`` that
        does not expose ``stripe.error.SignatureVerificationError``. We resolve
        the exception via the production module's own attribute chain (which
        is what the ``except`` clause checks against); if even that is missing,
        we install a minimal fallback class so both ``raise`` and ``except``
        reference the same identity.
        """
        from fastapi import HTTPException
        from webhooks import stripe as wh_stripe_mod

        try:
            SigErr = wh_stripe_mod.stripe.error.SignatureVerificationError
            sig_args: tuple = ("bad sig", "sig_header")
        except AttributeError:
            class SigErr(Exception):  # type: ignore[no-redef]
                def __init__(self, message, sig_header=""):
                    super().__init__(message)
                    self.sig_header = sig_header

            # Ensure both production code (`raise`) and the test (`except`) see
            # the same class — install it on the imported module's stripe.error
            # namespace so the production handler's except clause matches.
            if not hasattr(wh_stripe_mod.stripe, "error"):
                from types import SimpleNamespace
                wh_stripe_mod.stripe.error = SimpleNamespace()
            wh_stripe_mod.stripe.error.SignatureVerificationError = SigErr
            sig_args = ("bad sig",)

        with patch("webhooks.stripe.stripe.Webhook.construct_event") as mock_construct:
            mock_construct.side_effect = SigErr(*sig_args)
            with pytest.raises(HTTPException) as exc:
                await wh_stripe_mod.stripe_webhook(mock_request)
            assert exc.value.status_code == 400


class TestIdempotency:
    @pytest.mark.asyncio
    @patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test")
    @patch("webhooks.stripe.stripe.Webhook.construct_event")
    @patch("webhooks.stripe.get_supabase")
    async def test_duplicate_event_skipped(
        self, mock_get_sb, mock_construct, mock_request
    ):
        """Same event_id processed twice => second call returns already_processed
        AND does NOT re-invoke the handler."""
        from webhooks.stripe import stripe_webhook

        # First run: idempotency_already=False (claim succeeds).
        sb_first = _build_supabase_mock(rows=[], idempotency_already=False)
        mock_get_sb.return_value = sb_first
        mock_construct.return_value = _make_event(
            event_type="price.updated",
            data_object={"id": "price_x", "active": True, "product": "prod_x"},
        )
        with patch(
            "webhooks.stripe._handle_price_updated", new_callable=AsyncMock
        ) as h:
            response_first = await stripe_webhook(mock_request)
            assert response_first["status"] == "success"
            assert h.await_count == 1

        # Second run: idempotency_already=True (claim returns empty),
        # also patch the stuck check to return a 'completed' status so the
        # dispatcher returns already_processed without re-routing.
        sb_second = _build_supabase_mock(rows=[], idempotency_already=True)
        # Override stripe_webhook_events to return a row with status='completed'
        # for the stuck-check query.
        events_chain = sb_second.table("stripe_webhook_events")
        events_chain.execute.return_value = Mock(data=[])  # initial upsert returns empty
        # Replace the chain's stuck-check select chain so it returns the existing event.
        select_chain = MagicMock()
        select_chain.select.return_value = select_chain
        select_chain.eq.return_value = select_chain
        select_chain.limit.return_value = select_chain
        select_chain.execute.return_value = Mock(
            data=[{"id": "evt_bill_001", "status": "completed",
                   "received_at": datetime.now(timezone.utc).isoformat()}]
        )

        # Make table('stripe_webhook_events') return select_chain on the second call.
        first_call = [True]

        def alt_table(name):
            if name == "stripe_webhook_events":
                if first_call[0]:
                    first_call[0] = False
                    return events_chain
                return select_chain
            return sb_second.table.return_value

        sb_second.table = MagicMock(side_effect=alt_table)
        mock_get_sb.return_value = sb_second

        with patch(
            "webhooks.stripe._handle_price_updated", new_callable=AsyncMock
        ) as h2:
            response_second = await stripe_webhook(mock_request)
            assert response_second["status"] == "already_processed"
            assert h2.await_count == 0
