"""BILL-SYNC-001 (AC6/AC7): tests for daily reconciliation cron.

Coverage:
    AC6 — drift detection (price_mismatch, archived_mismatch, db_missing_in_stripe,
                          stripe_missing_in_db).
    AC6 — auto-fix high-confidence drift, manual flag for ambiguous.
    AC6 — dry-run mode never mutates DB.
    AC7 — Sentry alert fires when drifts > 0; no alert when clean.
    Lock contention — second concurrent run is skipped.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ---------------------------------------------------------------------------
# Supabase mock with deterministic table chain
# ---------------------------------------------------------------------------
def _make_supabase(*, db_rows: list[dict] | None = None,
                  inserted_run_id: str = "run-1"):
    sb = MagicMock()
    update_calls: list[tuple[str, dict]] = []

    def _make_chain(table_name: str):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.insert.return_value = chain
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain

        def update_side_effect(payload):
            chain._pending_update = payload
            return chain

        chain.update.side_effect = update_side_effect
        chain._pending_update = None

        def eq_then_capture(_col, val):
            if chain._pending_update is not None:
                update_calls.append((val, dict(chain._pending_update)))
                chain._pending_update = None
            return chain

        chain.eq.side_effect = eq_then_capture

        if table_name == "plan_billing_periods":
            chain.execute.return_value = MagicMock(data=db_rows or [])
        elif table_name == "billing_reconciliation_runs":
            # First call (insert running row) returns id; later updates return [].
            results = [MagicMock(data=[{"id": inserted_run_id}]), MagicMock(data=[])]
            chain.execute.side_effect = lambda: results.pop(0) if results else MagicMock(data=[])
        else:
            chain.execute.return_value = MagicMock(data=[])
        return chain

    table_mocks: dict[str, MagicMock] = {}

    def table_factory(name):
        if name not in table_mocks:
            table_mocks[name] = _make_chain(name)
        return table_mocks[name]

    sb.table = MagicMock(side_effect=table_factory)
    sb.update_calls = update_calls
    return sb


def _stripe_price(price_id: str, *, unit_amount: int, active: bool = True,
                  product: str = "prod_x") -> dict:
    return {
        "id": price_id,
        "unit_amount": unit_amount,
        "active": active,
        "product": product,
        "currency": "brl",
    }


# ---------------------------------------------------------------------------
# Lock helper patched globally to bypass Redis.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _bypass_redis_lock():
    with patch(
        "jobs.cron.billing_reconciliation._acquire_lock",
        new_callable=AsyncMock,
    ) as acquire, patch(
        "jobs.cron.billing_reconciliation._release_lock",
        new_callable=AsyncMock,
    ):
        acquire.return_value = True
        yield


# ---------------------------------------------------------------------------
class TestReconciliationDriftDetection:
    @pytest.mark.asyncio
    async def test_in_sync_no_drift(self):
        from jobs.cron.billing_reconciliation import reconcile_stripe_prices

        db = [
            {
                "id": "row-1",
                "plan_id": "smartlic_pro",
                "billing_period": "monthly",
                "price_cents": 199900,
                "stripe_price_id": "price_a",
                "stripe_product_id": "prod_x",
                "is_archived": False,
            }
        ]
        stripe_prices = [_stripe_price("price_a", unit_amount=199900, active=True)]

        sb = _make_supabase(db_rows=db)
        with patch("supabase_client.get_supabase", return_value=sb), patch(
            "jobs.cron.billing_reconciliation._list_all_stripe_prices",
            return_value=stripe_prices,
        ):
            result = await reconcile_stripe_prices(dry_run=False)

        assert result["status"] == "completed"
        assert result["drifts_detected"] == 0
        assert result["drifts_fixed"] == 0
        assert result["drifts_manual"] == 0
        assert result["rows_checked"] == 1

    @pytest.mark.asyncio
    async def test_price_mismatch_flagged_manual(self):
        from jobs.cron.billing_reconciliation import reconcile_stripe_prices

        db = [
            {
                "id": "row-1",
                "plan_id": "smartlic_pro",
                "billing_period": "monthly",
                "price_cents": 199900,
                "stripe_price_id": "price_a",
                "stripe_product_id": "prod_x",
                "is_archived": False,
            }
        ]
        stripe_prices = [_stripe_price("price_a", unit_amount=219900, active=True)]
        sb = _make_supabase(db_rows=db)
        with patch("supabase_client.get_supabase", return_value=sb), patch(
            "jobs.cron.billing_reconciliation._list_all_stripe_prices",
            return_value=stripe_prices,
        ):
            result = await reconcile_stripe_prices(dry_run=False)

        assert result["drifts_detected"] == 1
        assert result["drifts_fixed"] == 0
        assert result["drifts_manual"] == 1
        assert result["drift_report"][0]["type"] == "price_mismatch"

    @pytest.mark.asyncio
    async def test_archived_mismatch_auto_fixed(self):
        from jobs.cron.billing_reconciliation import reconcile_stripe_prices

        db = [
            {
                "id": "row-1",
                "plan_id": "smartlic_pro",
                "billing_period": "monthly",
                "price_cents": 199900,
                "stripe_price_id": "price_a",
                "stripe_product_id": "prod_x",
                "is_archived": False,
            }
        ]
        # Stripe says inactive, DB says not archived => archived_mismatch.
        stripe_prices = [_stripe_price("price_a", unit_amount=199900, active=False)]
        sb = _make_supabase(db_rows=db)
        with patch("supabase_client.get_supabase", return_value=sb), patch(
            "jobs.cron.billing_reconciliation._list_all_stripe_prices",
            return_value=stripe_prices,
        ):
            result = await reconcile_stripe_prices(dry_run=False)

        assert result["drifts_detected"] == 1
        assert result["drifts_fixed"] == 1
        assert result["drifts_manual"] == 0
        # Confirm row was actually updated to is_archived=True.
        assert any(
            r == "row-1" and p.get("is_archived") is True for r, p in sb.update_calls
        )

    @pytest.mark.asyncio
    async def test_db_missing_in_stripe_archives_db_row(self):
        from jobs.cron.billing_reconciliation import reconcile_stripe_prices

        db = [
            {
                "id": "row-1",
                "plan_id": "smartlic_pro",
                "billing_period": "monthly",
                "price_cents": 199900,
                "stripe_price_id": "price_phantom",
                "stripe_product_id": "prod_x",
                "is_archived": False,
            }
        ]
        # Stripe doesn't have price_phantom.
        sb = _make_supabase(db_rows=db)
        with patch("supabase_client.get_supabase", return_value=sb), patch(
            "jobs.cron.billing_reconciliation._list_all_stripe_prices",
            return_value=[],
        ):
            result = await reconcile_stripe_prices(dry_run=False)

        assert result["drifts_detected"] == 1
        assert result["drifts_fixed"] == 1
        assert result["drift_report"][0]["type"] == "db_missing_in_stripe"

    @pytest.mark.asyncio
    async def test_dry_run_does_not_mutate(self):
        from jobs.cron.billing_reconciliation import reconcile_stripe_prices

        db = [
            {
                "id": "row-1",
                "plan_id": "smartlic_pro",
                "billing_period": "monthly",
                "price_cents": 199900,
                "stripe_price_id": "price_a",
                "stripe_product_id": "prod_x",
                "is_archived": False,
            }
        ]
        stripe_prices = [_stripe_price("price_a", unit_amount=199900, active=False)]
        sb = _make_supabase(db_rows=db)
        with patch("supabase_client.get_supabase", return_value=sb), patch(
            "jobs.cron.billing_reconciliation._list_all_stripe_prices",
            return_value=stripe_prices,
        ):
            result = await reconcile_stripe_prices(dry_run=True)

        assert result["dry_run"] is True
        assert result["drifts_detected"] == 1
        # Should have flagged but NOT updated plan_billing_periods.
        # (Only billing_reconciliation_runs row inserts/updates.)
        assert all(
            r != "row-1" or "is_archived" not in p for r, p in sb.update_calls
        )

    @pytest.mark.asyncio
    async def test_stripe_only_orphan_flagged_when_known_product(self):
        from jobs.cron.billing_reconciliation import reconcile_stripe_prices

        db = [
            {
                "id": "row-1",
                "plan_id": "smartlic_pro",
                "billing_period": "monthly",
                "price_cents": 199900,
                "stripe_price_id": "price_a",
                "stripe_product_id": "prod_x",
                "is_archived": False,
            }
        ]
        stripe_prices = [
            _stripe_price("price_a", unit_amount=199900, active=True, product="prod_x"),
            # Orphan price under same product.
            _stripe_price("price_orphan", unit_amount=219900, active=True, product="prod_x"),
        ]
        sb = _make_supabase(db_rows=db)
        with patch("supabase_client.get_supabase", return_value=sb), patch(
            "jobs.cron.billing_reconciliation._list_all_stripe_prices",
            return_value=stripe_prices,
        ):
            result = await reconcile_stripe_prices(dry_run=False)

        assert result["drifts_detected"] == 1
        assert result["drift_report"][0]["type"] == "stripe_missing_in_db"


class TestReconciliationLock:
    @pytest.mark.asyncio
    async def test_skipped_when_lock_held(self):
        from jobs.cron.billing_reconciliation import reconcile_stripe_prices

        with patch(
            "jobs.cron.billing_reconciliation._acquire_lock",
            new_callable=AsyncMock,
        ) as acquire:
            acquire.return_value = False
            result = await reconcile_stripe_prices(dry_run=False)
        assert result["status"] == "skipped"
        assert result["reason"] == "lock_held"


class TestSentryAlert:
    @pytest.mark.asyncio
    async def test_alert_fires_when_drift_detected(self):
        from jobs.cron.billing_reconciliation import reconcile_stripe_prices

        db = [
            {
                "id": "row-1",
                "plan_id": "smartlic_pro",
                "billing_period": "monthly",
                "price_cents": 199900,
                "stripe_price_id": "price_a",
                "stripe_product_id": "prod_x",
                "is_archived": False,
            }
        ]
        stripe_prices = [_stripe_price("price_a", unit_amount=219900, active=True)]
        sb = _make_supabase(db_rows=db)
        with patch("supabase_client.get_supabase", return_value=sb), patch(
            "jobs.cron.billing_reconciliation._list_all_stripe_prices",
            return_value=stripe_prices,
        ), patch(
            "jobs.cron.billing_reconciliation._emit_sentry_alert"
        ) as alert:
            await reconcile_stripe_prices(dry_run=False)
            alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_alert_silent_when_clean(self):
        from jobs.cron.billing_reconciliation import reconcile_stripe_prices

        db = [
            {
                "id": "row-1",
                "plan_id": "smartlic_pro",
                "billing_period": "monthly",
                "price_cents": 199900,
                "stripe_price_id": "price_a",
                "stripe_product_id": "prod_x",
                "is_archived": False,
            }
        ]
        stripe_prices = [_stripe_price("price_a", unit_amount=199900, active=True)]
        sb = _make_supabase(db_rows=db)
        with patch("supabase_client.get_supabase", return_value=sb), patch(
            "jobs.cron.billing_reconciliation._list_all_stripe_prices",
            return_value=stripe_prices,
        ), patch(
            "jobs.cron.billing_reconciliation._emit_sentry_alert"
        ) as alert:
            await reconcile_stripe_prices(dry_run=False)
            alert.assert_not_called()
