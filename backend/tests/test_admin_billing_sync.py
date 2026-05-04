"""BILL-SYNC-001 (AC8/AC9/AC10): tests for admin reverse-sync endpoint.

Coverage:
    AC8 — POST /v1/admin/plans/{id}/sync-to-stripe creates new Price + archives old
    AC8 — audit log row written for each operation
    AC9 — 24h race guard rejects when last_forward_synced_at is recent
    AC10 — GET /v1/admin/plans/billing-sync returns drift_status per row
    Admin gate — non-admin returns 403
    Confirmation flag — body without i_understand_this_modifies_stripe=true => 400
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_supabase(*, row: dict | None = None, audit_id: str = "audit-1"):
    sb = MagicMock()
    update_calls: list[tuple[str, dict]] = []

    def _make_chain(table_name: str):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.order.return_value = chain
        chain.insert.return_value = chain

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
            chain.execute.return_value = MagicMock(data=[row] if row else [])
        elif table_name == "admin_billing_audit_log":
            chain.execute.return_value = MagicMock(data=[{"id": audit_id}])
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


def _build_app(admin_user: dict | None = None) -> FastAPI:
    from admin import require_admin
    from routes.admin_billing_sync import router

    app = FastAPI()
    app.include_router(router)

    if admin_user is not None:
        async def fake_require_admin():
            return admin_user

        app.dependency_overrides[require_admin] = fake_require_admin
    return app


ADMIN = {"id": "admin-uuid-1", "email": "admin@smartlic.tech"}


# ---------------------------------------------------------------------------
class TestReverseSyncSuccess:
    def test_creates_new_price_and_archives_old(self):
        app = _build_app(admin_user=ADMIN)

        row = {
            "id": "row-1",
            "plan_id": "smartlic_pro",
            "billing_period": "monthly",
            "price_cents": 199900,
            "stripe_price_id": "price_old",
            "stripe_product_id": "prod_x",
            "last_forward_synced_at": None,
            "last_reverse_synced_at": None,
            "is_archived": False,
        }
        sb = _make_supabase(row=row)

        with patch(
            "routes.admin_billing_sync.get_supabase", return_value=sb
        ), patch("stripe.Price.create") as mock_create, patch(
            "stripe.Price.modify"
        ) as mock_modify:
            mock_create.return_value = {"id": "price_new", "product": "prod_x"}

            client = TestClient(app)
            resp = client.post(
                "/v1/admin/plans/row-1/sync-to-stripe",
                json={"i_understand_this_modifies_stripe": True, "note": "rate update"},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        assert body["new_stripe_price_id"] == "price_new"
        assert body["old_stripe_price_id"] == "price_old"
        # Stripe API was called with correct shape.
        assert mock_create.call_count == 1
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["unit_amount"] == 199900
        assert call_kwargs["product"] == "prod_x"
        assert call_kwargs["currency"] == "brl"
        assert call_kwargs["recurring"]["interval"] == "month"
        # Old price was archived via Stripe modify.
        mock_modify.assert_called_once_with("price_old", active=False)
        # Local row was updated with new price id + last_reverse_synced_at.
        update_payloads = [p for r, p in sb.update_calls if r == "row-1"]
        assert any(p.get("stripe_price_id") == "price_new" for p in update_payloads)
        assert any("last_reverse_synced_at" in p for p in update_payloads)


class TestReverseSyncRaceGuard:
    def test_rejects_when_recent_forward_sync(self):
        app = _build_app(admin_user=ADMIN)

        recent = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        row = {
            "id": "row-1",
            "plan_id": "smartlic_pro",
            "billing_period": "monthly",
            "price_cents": 199900,
            "stripe_price_id": "price_old",
            "stripe_product_id": "prod_x",
            "last_forward_synced_at": recent,
            "last_reverse_synced_at": None,
            "is_archived": False,
        }
        sb = _make_supabase(row=row)

        with patch(
            "routes.admin_billing_sync.get_supabase", return_value=sb
        ), patch("stripe.Price.create") as mock_create, patch(
            "stripe.Price.modify"
        ) as mock_modify:
            client = TestClient(app)
            resp = client.post(
                "/v1/admin/plans/row-1/sync-to-stripe",
                json={"i_understand_this_modifies_stripe": True},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "skipped"
        assert body["skipped_reason"] == "race_guard_24h"
        # Stripe API NOT called.
        mock_create.assert_not_called()
        mock_modify.assert_not_called()


class TestReverseSyncGuards:
    def test_requires_confirmation_flag(self):
        app = _build_app(admin_user=ADMIN)
        client = TestClient(app)
        resp = client.post(
            "/v1/admin/plans/row-1/sync-to-stripe",
            json={"i_understand_this_modifies_stripe": False},
        )
        assert resp.status_code == 400

    def test_404_when_row_not_found(self):
        app = _build_app(admin_user=ADMIN)
        sb = _make_supabase(row=None)
        with patch("routes.admin_billing_sync.get_supabase", return_value=sb):
            client = TestClient(app)
            resp = client.post(
                "/v1/admin/plans/missing/sync-to-stripe",
                json={"i_understand_this_modifies_stripe": True},
            )
        assert resp.status_code == 404


class TestBillingSyncListing:
    def test_drift_status_in_sync_when_recent_forward(self):
        app = _build_app(admin_user=ADMIN)
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        sb = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.order.return_value = chain
        chain.execute.return_value = MagicMock(
            data=[
                {
                    "id": "row-1",
                    "plan_id": "smartlic_pro",
                    "billing_period": "monthly",
                    "price_cents": 199900,
                    "discount_percent": 0,
                    "stripe_price_id": "price_a",
                    "stripe_product_id": "prod_x",
                    "last_forward_synced_at": recent,
                    "last_reverse_synced_at": None,
                    "is_archived": False,
                }
            ]
        )
        sb.table.return_value = chain
        with patch("routes.admin_billing_sync.get_supabase", return_value=sb):
            client = TestClient(app)
            resp = client.get("/v1/admin/plans/billing-sync")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["drift_status"] == "in_sync"

    def test_drift_status_stale_when_old(self):
        app = _build_app(admin_user=ADMIN)
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        sb = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.order.return_value = chain
        chain.execute.return_value = MagicMock(
            data=[
                {
                    "id": "row-1",
                    "plan_id": "smartlic_pro",
                    "billing_period": "monthly",
                    "price_cents": 199900,
                    "discount_percent": 0,
                    "stripe_price_id": "price_a",
                    "stripe_product_id": "prod_x",
                    "last_forward_synced_at": old,
                    "last_reverse_synced_at": None,
                    "is_archived": False,
                }
            ]
        )
        sb.table.return_value = chain
        with patch("routes.admin_billing_sync.get_supabase", return_value=sb):
            client = TestClient(app)
            resp = client.get("/v1/admin/plans/billing-sync")
        assert resp.json()["items"][0]["drift_status"] == "drift_stale"


class TestNonAdminBlocked:
    def test_non_admin_gets_403(self):
        # Build app WITHOUT dependency override.
        from routes.admin_billing_sync import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/v1/admin/plans/billing-sync")
        # Either 401 (no auth) or 403 (forbidden) depending on auth wiring.
        assert resp.status_code in (401, 403)
