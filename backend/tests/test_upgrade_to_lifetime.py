"""Tests for POST /v1/api/subscriptions/upgrade-to-lifetime + preview (#1011).

Covers:
- happy path: active Pro sub, cap available, not founder -> cancel + checkout
- already founder: 409
- no active subscription: 409
- cap reached: 410
- stripe cancel failure: 502 (no double-charge — sub stays active)
- preview eligibility states
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_user():
    return {"id": "test-user-upgrade-001", "email": "upgrade@test.com"}


@pytest.fixture
def client(test_user):
    from main import app
    from auth import require_auth, require_mfa_high_impact

    app.dependency_overrides[require_auth] = lambda: test_user
    app.dependency_overrides[require_mfa_high_impact] = lambda: test_user
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _seats_available_row():
    return [{
        "available": True,
        "seats_total": 50,
        "seats_remaining": 12,
        "deadline_at": None,
        "paused": False,
        "reason": "ok",
        "offer_mode": "lifetime",
        "price_brl_cents": 99700,
    }]


def _seats_full_row():
    return [{
        "available": False,
        "seats_total": 50,
        "seats_remaining": 0,
        "deadline_at": None,
        "paused": False,
        "reason": "founding_cap_reached",
        "offer_mode": "lifetime",
        "price_brl_cents": 99700,
    }]


def _make_sb(*, profile_is_founder=False, has_sub=True, seats_rows=None):
    sb = MagicMock()
    seats_rows = seats_rows if seats_rows is not None else _seats_available_row()

    # rpc('check_founding_availability')
    sb.rpc.return_value.execute.return_value = Mock(data=seats_rows)

    # ---- table('profiles').select('is_founder').eq('id', user_id).limit(1).execute()
    profiles_chain = (
        sb.table.return_value.select.return_value
        .eq.return_value.limit.return_value.execute
    )
    profiles_chain.return_value = Mock(
        data=[{"is_founder": profile_is_founder}] if has_sub or profile_is_founder else []
    )

    # ---- table('user_subscriptions').select(...).eq.eq.order.limit.execute
    sub_data = []
    if has_sub:
        sub_data = [{
            "id": "sub-local-001",
            "stripe_subscription_id": "sub_stripe_test_001",
            "expires_at": None,
            "plan_id": "smartlic_pro",
        }]
    sub_chain = (
        sb.table.return_value.select.return_value
        .eq.return_value.eq.return_value
        .order.return_value.limit.return_value.execute
    )
    sub_chain.return_value = Mock(data=sub_data)
    return sb


class TestUpgradeToLifetimeHappyPath:
    @patch("routes.upgrade_to_lifetime.os.getenv")
    @patch("supabase_client.get_supabase")
    def test_happy_path(self, mock_get_sb, mock_getenv, client):
        # NOTE: do NOT use `import stripe as stripe_lib` here — earlier suites
        # (e.g. test_story420_stripe_pix_removed.py) replace
        # `sys.modules["stripe"]` with a SimpleNamespace, which leaks to any
        # subsequent fresh import. We patch via the route module which already
        # holds a reference to the real `stripe` from app startup.
        env = {
            "STRIPE_SECRET_KEY": "sk_test_x",
            "FOUNDING_ONE_TIME_PRICE_ID": "price_x",
            "FRONTEND_URL": "http://localhost:3000",
        }
        mock_getenv.side_effect = lambda k, d=None: env.get(k, d)
        sb = _make_sb()
        mock_get_sb.return_value = sb

        # Stripe Subscription.retrieve -> object with customer + items
        item = Mock()
        item.price = Mock(unit_amount=39700)
        items = Mock()
        items.data = [item]
        retrieved = Mock()
        retrieved.current_period_start = 1_700_000_000
        retrieved.current_period_end = 1_700_000_000 + 30 * 86400
        retrieved.items = items
        retrieved.customer = "cus_xyz"

        with (
            patch("config.features.get_feature_flag", return_value=True),
            patch("routes.upgrade_to_lifetime.stripe_lib.Subscription.retrieve", return_value=retrieved),
            patch(
                "routes.upgrade_to_lifetime.stripe_lib.Subscription.delete",
                return_value=Mock(),
                create=True,
            ) as mock_delete,
            patch(
                "routes.upgrade_to_lifetime.stripe_lib.checkout.Session.create",
                return_value=Mock(id="cs_test_001", url="https://checkout.stripe.com/c/cs_test_001"),
            ) as mock_create,
        ):
            r = client.post("/v1/api/subscriptions/upgrade-to-lifetime", json={"confirmed": True})

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["session_id"] == "cs_test_001"
        # CodeQL py/incomplete-url-substring-sanitization: parse the URL and
        # check the host explicitly instead of substring matching.
        assert urlparse(body["checkout_url"]).hostname == "checkout.stripe.com"
        assert body["net_charge_brl_cents"] <= 99700
        assert body["estimated_credit_brl_cents"] >= 0

        # Stripe cancel called with prorate=True
        mock_delete.assert_called_once()
        kwargs = mock_delete.call_args.kwargs
        assert kwargs.get("prorate") is True
        # Checkout uses the right price + metadata
        ckwargs = mock_create.call_args.kwargs
        assert ckwargs["mode"] == "payment"
        assert ckwargs["line_items"][0]["price"] == "price_x"
        assert ckwargs["metadata"]["source"] == "founding"
        assert ckwargs["metadata"]["checkout_source"] == "upgrade_pro_to_lifetime"


class TestUpgradeAlreadyFounder:
    @patch("routes.upgrade_to_lifetime.os.getenv")
    @patch("supabase_client.get_supabase")
    def test_already_founder_returns_409(self, mock_get_sb, mock_getenv, client):
        env = {"STRIPE_SECRET_KEY": "sk_x", "FOUNDING_ONE_TIME_PRICE_ID": "price_x"}
        mock_getenv.side_effect = lambda k, d=None: env.get(k, d)
        sb = _make_sb(profile_is_founder=True)
        mock_get_sb.return_value = sb

        with patch("config.features.get_feature_flag", return_value=True):
            r = client.post("/v1/api/subscriptions/upgrade-to-lifetime", json={"confirmed": True})
        assert r.status_code == 409
        detail = r.json()["detail"]
        # detail might be a dict (HTTPException with structured detail)
        if isinstance(detail, dict):
            assert detail["error_code"] == "already_founder"


class TestUpgradeNoActiveSub:
    @patch("routes.upgrade_to_lifetime.os.getenv")
    @patch("supabase_client.get_supabase")
    def test_no_active_sub_returns_409(self, mock_get_sb, mock_getenv, client):
        env = {"STRIPE_SECRET_KEY": "sk_x", "FOUNDING_ONE_TIME_PRICE_ID": "price_x"}
        mock_getenv.side_effect = lambda k, d=None: env.get(k, d)
        sb = _make_sb(has_sub=False)
        mock_get_sb.return_value = sb

        with patch("config.features.get_feature_flag", return_value=True):
            r = client.post("/v1/api/subscriptions/upgrade-to-lifetime", json={"confirmed": True})
        assert r.status_code == 409
        detail = r.json()["detail"]
        if isinstance(detail, dict):
            assert detail["error_code"] == "no_active_subscription"


class TestUpgradeCapReached:
    @patch("routes.upgrade_to_lifetime.os.getenv")
    @patch("supabase_client.get_supabase")
    def test_cap_reached_returns_410(self, mock_get_sb, mock_getenv, client):
        env = {"STRIPE_SECRET_KEY": "sk_x", "FOUNDING_ONE_TIME_PRICE_ID": "price_x"}
        mock_getenv.side_effect = lambda k, d=None: env.get(k, d)
        sb = _make_sb(seats_rows=_seats_full_row())
        mock_get_sb.return_value = sb

        with patch("config.features.get_feature_flag", return_value=True):
            r = client.post("/v1/api/subscriptions/upgrade-to-lifetime", json={"confirmed": True})
        assert r.status_code == 410
        detail = r.json()["detail"]
        if isinstance(detail, dict):
            assert detail["error_code"] == "founding_cap_reached"


class TestUpgradeStripeCancelFailure:
    @patch("routes.upgrade_to_lifetime.os.getenv")
    @patch("supabase_client.get_supabase")
    def test_stripe_cancel_failure_returns_502(self, mock_get_sb, mock_getenv, client):
        # See note in test_happy_path — patch via the route module to dodge
        # `sys.modules["stripe"]` pollution from earlier suites.
        from routes.upgrade_to_lifetime import stripe_lib as _real_stripe

        env = {"STRIPE_SECRET_KEY": "sk_x", "FOUNDING_ONE_TIME_PRICE_ID": "price_x"}
        mock_getenv.side_effect = lambda k, d=None: env.get(k, d)
        sb = _make_sb()
        mock_get_sb.return_value = sb

        retrieved = Mock(items=Mock(data=[]), current_period_start=1, current_period_end=2, customer=None)
        with (
            patch("config.features.get_feature_flag", return_value=True),
            patch("routes.upgrade_to_lifetime.stripe_lib.Subscription.retrieve", return_value=retrieved),
            patch(
                "routes.upgrade_to_lifetime.stripe_lib.Subscription.delete",
                side_effect=_real_stripe.error.StripeError("boom"),
                create=True,
            ),
            patch("routes.upgrade_to_lifetime.stripe_lib.checkout.Session.create") as mock_create,
        ):
            r = client.post("/v1/api/subscriptions/upgrade-to-lifetime", json={"confirmed": True})

        assert r.status_code == 502
        # Critically: checkout was NOT created (no double-charge risk)
        mock_create.assert_not_called()


class TestUpgradePreview:
    @patch("routes.upgrade_to_lifetime.os.getenv")
    @patch("supabase_client.get_supabase")
    def test_preview_eligible(self, mock_get_sb, mock_getenv, client):
        env = {"STRIPE_SECRET_KEY": "sk_x", "FOUNDING_ONE_TIME_PRICE_ID": "price_x"}
        mock_getenv.side_effect = lambda k, d=None: env.get(k, d)
        sb = _make_sb()
        mock_get_sb.return_value = sb

        item = Mock(price=Mock(unit_amount=39700))
        retrieved = Mock(
            current_period_start=1_700_000_000,
            current_period_end=1_700_000_000 + 30 * 86400,
            items=Mock(data=[item]),
            customer="cus_x",
        )
        with (
            patch("config.features.get_feature_flag", return_value=True),
            patch("routes.upgrade_to_lifetime.stripe_lib.Subscription.retrieve", return_value=retrieved),
        ):
            r = client.get("/v1/api/subscriptions/upgrade-to-lifetime/preview")
        assert r.status_code == 200
        body = r.json()
        assert body["eligible"] is True
        assert body["lifetime_price_brl_cents"] == 99700
        assert body["has_active_subscription"] is True

    @patch("routes.upgrade_to_lifetime.os.getenv")
    @patch("supabase_client.get_supabase")
    def test_preview_already_founder_not_eligible(self, mock_get_sb, mock_getenv, client):
        env = {"STRIPE_SECRET_KEY": "sk_x", "FOUNDING_ONE_TIME_PRICE_ID": "price_x"}
        mock_getenv.side_effect = lambda k, d=None: env.get(k, d)
        sb = _make_sb(profile_is_founder=True)
        mock_get_sb.return_value = sb

        with patch("config.features.get_feature_flag", return_value=True):
            r = client.get("/v1/api/subscriptions/upgrade-to-lifetime/preview")
        assert r.status_code == 200
        body = r.json()
        assert body["eligible"] is False
        assert body["reason"] == "already_founder"
        assert body["is_already_founder"] is True
