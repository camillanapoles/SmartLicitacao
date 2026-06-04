"""CONV-005b-2: Tests for checkout endpoint.

Coverage:
- SKU valido -> 200 + checkout_url
- SKU inexistente -> 404
- Produto inativo -> 400
- Sem autenticacao -> 401
- Stripe Session.create e chamado com parametros corretos
- Stripe Price cache (usa stripe_price_id existente)
- Stripe Price auto-criacao quando stripe_price_id e None
- Stripe InvalidRequestError -> 400
- Stripe StripeError -> 503
- Erro temporario Supabase -> 503
- Rate limit -> 429 apos 10 requests
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import require_auth
from routes.checkout import checkout_rate_limit

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_PRODUCT = {
    "id": "prod-123e4567-e89b-12d3-a456-426614174000",
    "sku": "relatorio-oportunidade",
    "name": "Relatorio de Oportunidade Setorial",
    "description": "Analise completa de oportunidades",
    "price_brl": 4700,
    "stripe_product_id": None,
    "stripe_price_id": None,
    "active": True,
    "preview_config": {"max_free_items": 3, "blurred_items": 3},
    "delivery_config": {"type": "pdf", "template": "relatorio-oportunidade"},
}

MOCK_PRODUCT_WITH_STRIPE_PRICE = {
    **MOCK_PRODUCT,
    "stripe_product_id": "prod_Fake123",
    "stripe_price_id": "price_FakePrice123",
}

MOCK_INACTIVE_PRODUCT = {
    **MOCK_PRODUCT,
    "active": False,
}

MOCK_USER = {
    "sub": "user-abc-123",
    "id": "user-abc-123",
    "email": "user@example.com",
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """FastAPI app with only the checkout router, auth + rate limit overridden."""
    from routes.checkout import router as checkout_router

    application = FastAPI()

    # Override auth dependency to return a mock user
    application.dependency_overrides[require_auth] = lambda: MOCK_USER

    # Override rate limit to always allow (no Redis in unit tests)
    application.dependency_overrides[checkout_rate_limit] = lambda: None

    application.include_router(checkout_router)
    return application


@pytest.fixture
def client(app):
    """TestClient for the checkout app."""
    return TestClient(app)


def _mock_supabase_product(mock_get_supabase, products: list[dict]) -> None:
    """Configure the supabase mock to return given products on table().eq(sku)...execute()."""
    mock_sb = MagicMock()
    mock_query = MagicMock()
    mock_sb.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.execute.return_value = MagicMock(data=products)
    mock_get_supabase.return_value = mock_sb


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuth:
    """Authentication gating."""

    def test_returns_401_without_auth(self):
        """POST without auth token should return 401."""
        from routes.checkout import router as checkout_router

        app_no_auth = FastAPI()
        app_no_auth.dependency_overrides[checkout_rate_limit] = lambda: None
        app_no_auth.include_router(checkout_router)
        client_no_auth = TestClient(app_no_auth)

        resp = client_no_auth.post(
            "/api/checkout/one-time",
            json={"sku": "relatorio-oportunidade"},
        )
        assert resp.status_code == 401
        assert "autenticacao" in resp.json()["detail"].lower()


@pytest.mark.usefixtures("app")
class TestCheckout:
    """POST /api/checkout/one-time behavior."""

    @patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @patch("routes.checkout.get_supabase")
    def test_valid_sku_returns_checkout_url(self, mock_get_supabase, client):
        """Valid SKU should return 200 with checkout_url."""
        _mock_supabase_product(mock_get_supabase, [MOCK_PRODUCT])

        with (
            patch("stripe.Product.create") as mock_product_create,
            patch("stripe.Price.create") as mock_price_create,
            patch("stripe.checkout.Session.create") as mock_session_create,
        ):
            mock_product_create.return_value = MagicMock(id="prod_Mocked123")
            mock_price_create.return_value = MagicMock(id="price_Mocked456")
            fake_session = MagicMock()
            fake_session.id = "cs_test_abc123"
            fake_session.url = "https://checkout.stripe.com/c/pay/cs_test_abc123"
            mock_session_create.return_value = fake_session

            resp = client.post(
                "/api/checkout/one-time",
                json={
                    "sku": "relatorio-oportunidade",
                    "context": {
                        "entity_type": "cnpj",
                        "entity_id": "12345678000199",
                    },
                },
            )

            assert resp.status_code == 200, resp.json()
            data = resp.json()
            assert "checkout_url" in data
            assert data["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_test_abc123"

            # Verify Stripe session was created with correct params
            mock_session_create.assert_called_once()
            kwargs = mock_session_create.call_args.kwargs
            assert kwargs["mode"] == "payment"
            assert "card" in kwargs["payment_method_types"]
            assert "boleto" in kwargs["payment_method_types"]
            assert "pix" in kwargs["payment_method_types"]
            assert kwargs["line_items"][0]["quantity"] == 1
            assert kwargs["metadata"]["sku"] == "relatorio-oportunidade"
            assert kwargs["metadata"]["product_sku"] == "relatorio-oportunidade"
            assert kwargs["metadata"]["user_id"] == "user-abc-123"
            assert kwargs["metadata"]["entity_type"] == "cnpj"
            assert kwargs["metadata"]["entity_id"] == "12345678000199"
            assert kwargs["customer_email"] == "user@example.com"
            assert kwargs["cancel_url"] is not None
            assert kwargs["success_url"] is not None
            assert "{CHECKOUT_SESSION_ID}" in kwargs["success_url"]

            # Verify Product and Price were created
            mock_product_create.assert_called_once()
            mock_price_create.assert_called_once()
            price_kwargs = mock_price_create.call_args.kwargs
            assert price_kwargs["currency"] == "brl"
            assert price_kwargs["unit_amount"] == 4700

    @patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @patch("routes.checkout.get_supabase")
    def test_uses_existing_stripe_price(self, mock_get_supabase, client):
        """When product has stripe_price_id, it should be reused."""
        _mock_supabase_product(mock_get_supabase, [MOCK_PRODUCT_WITH_STRIPE_PRICE])

        with (
            patch("stripe.checkout.Session.create") as mock_session_create,
            patch("stripe.Product.create") as mock_product_create,
            patch("stripe.Price.create") as mock_price_create,
        ):
            fake_session = MagicMock()
            fake_session.url = "https://checkout.stripe.com/c/pay/cs_test_abc"
            fake_session.id = "cs_test_abc"
            mock_session_create.return_value = fake_session

            resp = client.post(
                "/api/checkout/one-time",
                json={"sku": "relatorio-oportunidade"},
            )

            assert resp.status_code == 200, resp.json()

            # Should NOT create new Stripe Product or Price
            mock_product_create.assert_not_called()
            mock_price_create.assert_not_called()

            # Should use the existing price_id
            used_price = mock_session_create.call_args.kwargs["line_items"][0]["price"]
            assert used_price == "price_FakePrice123"

    @patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @patch("routes.checkout.get_supabase")
    @patch("stripe.Product.create")
    @patch("stripe.Price.create")
    def test_creates_stripe_price_when_missing(
        self,
        mock_price_create,
        mock_product_create,
        mock_get_supabase,
        client,
    ):
        """When product has no stripe_price_id, Stripe Product+Price should be created."""
        _mock_supabase_product(mock_get_supabase, [MOCK_PRODUCT])

        # Mock Stripe Product creation
        fake_product = MagicMock()
        fake_product.id = "prod_NewStripeProduct"
        mock_product_create.return_value = fake_product

        # Mock Stripe Price creation
        fake_price = MagicMock()
        fake_price.id = "price_NewStripePrice"
        mock_price_create.return_value = fake_price

        with patch("stripe.checkout.Session.create") as mock_session_create:
            fake_session = MagicMock()
            fake_session.url = "https://checkout.stripe.com/c/pay/cs_new"
            fake_session.id = "cs_new"
            mock_session_create.return_value = fake_session

            resp = client.post(
                "/api/checkout/one-time",
                json={"sku": "relatorio-oportunidade"},
            )

            assert resp.status_code == 200, resp.json()

            # Should create product and price
            mock_product_create.assert_called_once()
            mock_price_create.assert_called_once()

            # Verify price is created with correct params
            price_kwargs = mock_price_create.call_args.kwargs
            assert price_kwargs["currency"] == "brl"
            assert price_kwargs["unit_amount"] == 4700
            assert price_kwargs["product"] == "prod_NewStripeProduct"

            # Should use the new price_id
            used_price = mock_session_create.call_args.kwargs["line_items"][0]["price"]
            assert used_price == "price_NewStripePrice"

    @patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @patch("routes.checkout.get_supabase")
    def test_sku_not_found_returns_404(self, mock_get_supabase, client):
        """Non-existent SKU should return 404."""
        _mock_supabase_product(mock_get_supabase, [])

        resp = client.post(
            "/api/checkout/one-time",
            json={"sku": "sku-inexistente"},
        )
        assert resp.status_code == 404

    @patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @patch("routes.checkout.get_supabase")
    def test_inactive_product_returns_400(self, mock_get_supabase, client):
        """Inactive product should return 400."""
        _mock_supabase_product(mock_get_supabase, [MOCK_INACTIVE_PRODUCT])

        resp = client.post(
            "/api/checkout/one-time",
            json={"sku": "relatorio-oportunidade"},
        )
        assert resp.status_code == 400
        assert "indisponivel" in resp.json()["detail"].lower()

    @patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @patch("routes.checkout.get_supabase")
    def test_stripe_invalid_request_error_returns_400(self, mock_get_supabase, client):
        """Stripe InvalidRequestError should return 400."""
        import stripe as stripe_lib

        _mock_supabase_product(mock_get_supabase, [MOCK_PRODUCT])

        with (
            patch("stripe.Product.create") as mock_product_create,
            patch("stripe.Price.create") as mock_price_create,
            patch("stripe.checkout.Session.create") as mock_session_create,
        ):
            mock_product_create.return_value = MagicMock(id="prod_Mocked")
            mock_price_create.return_value = MagicMock(id="price_Mocked")
            mock_session_create.side_effect = stripe_lib.error.InvalidRequestError(
                message="Invalid product",
                param="price",
            )

            resp = client.post(
                "/api/checkout/one-time",
                json={"sku": "relatorio-oportunidade"},
            )
            assert resp.status_code == 400

    @patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @patch("routes.checkout.get_supabase")
    def test_stripe_error_returns_503(self, mock_get_supabase, client):
        """Stripe API error should return 503."""
        import stripe as stripe_lib

        _mock_supabase_product(mock_get_supabase, [MOCK_PRODUCT])

        with patch("stripe.checkout.Session.create") as mock_session_create:
            mock_session_create.side_effect = stripe_lib.error.StripeError("API error")

            resp = client.post(
                "/api/checkout/one-time",
                json={"sku": "relatorio-oportunidade"},
            )
            assert resp.status_code == 503


class TestSupabaseError:
    """Supabase transient errors."""

    @patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"})
    @patch("routes.checkout.get_supabase")
    def test_supabase_error_returns_503(self, mock_get_supabase, client):
        """Transient Supabase error should return 503."""
        mock_sb = MagicMock()
        mock_query = MagicMock()
        mock_sb.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.side_effect = Exception("Connection refused")
        mock_get_supabase.return_value = mock_sb

        resp = client.post(
            "/api/checkout/one-time",
            json={"sku": "relatorio-oportunidade"},
        )
        assert resp.status_code == 503


class TestRateLimit:
    """Rate limiting behavior (10 req/min per IP)."""

    @patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"})
    def test_rate_limit_enforced(self):
        """After 10 rapid requests, the 11th should return 429."""
        from routes.checkout import router as checkout_router

        rate_app = FastAPI()
        rate_app.dependency_overrides[require_auth] = lambda: MOCK_USER
        # Do NOT override rate limit — test with real limiter (in-memory fallback)
        rate_app.include_router(checkout_router)
        rate_client = TestClient(rate_app)

        with patch("routes.checkout.get_supabase") as mock_get_supabase:
            mock_sb = MagicMock()
            mock_query = MagicMock()
            mock_sb.table.return_value = mock_query
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=[])
            mock_get_supabase.return_value = mock_sb

            # Make 10 rapid requests (all will 404 because supabase returns empty)
            for _ in range(10):
                resp = rate_client.post(
                    "/api/checkout/one-time",
                    json={"sku": "relatorio-oportunidade"},
                )
                # All within rate limit -> either 404 (no product) or other 4xx
                assert resp.status_code in (200, 400, 404), f"Unexpected {resp.status_code} at request {_}"

            # 11th request should hit rate limit
            resp = rate_client.post(
                "/api/checkout/one-time",
                json={"sku": "relatorio-oportunidade"},
            )
            assert resp.status_code == 429
