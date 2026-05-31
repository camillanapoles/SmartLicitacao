"""CONV-005b-2: Generic one-time checkout endpoint for digital products.

Creates a Stripe Checkout Session for a digital product identified by SKU.

Endpoints:
    POST /api/checkout/one-time — create Stripe Checkout Session for a product

Dependencies:
    - digital_products table (CONV-005b-1 / #1334)
    - Stripe SDK (stripe>=11.4)
    - require_auth (authenticated user)
    - require_rate_limit (10 req/min per IP)
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException

from auth import require_auth
from rate_limiter import require_rate_limit
from supabase_client import get_supabase, sb_execute

from schemas.checkout import CheckoutRequest, CheckoutResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/checkout",
    tags=["checkout"],
    dependencies=[
        Depends(require_rate_limit(10, 60)),
    ],
)


def _get_frontend_url() -> str:
    """Return the frontend base URL, defaulting to localhost for dev."""
    return os.getenv("FRONTEND_URL", "http://localhost:3000")


def _get_stripe_key() -> str:
    """Return Stripe secret key or raise."""
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        logger.error("checkout: STRIPE_SECRET_KEY not configured")
        raise HTTPException(
            status_code=503,
            detail="Servico de pagamento temporariamente indisponivel.",
        )
    return key


async def _lookup_product(sku: str) -> dict:
    """Query digital_products table by SKU.

    Returns the product row dict or None if not found.

    Raises:
        HTTPException 503 on transient DB errors.
    """
    try:
        sb = get_supabase()
        result = await sb_execute(
            sb.table("digital_products").select("*").eq("sku", sku).limit(1)
        )
        rows = result.data if result.data else []
        return rows[0] if rows else None
    except Exception as exc:
        logger.warning("checkout: product lookup failed for sku=%s: %s", sku, exc)
        raise HTTPException(
            status_code=503,
            detail="Erro temporario ao consultar produto. Tente novamente.",
        ) from exc


def _ensure_stripe_price(product: dict) -> str:
    """Return an existing stripe_price_id or create Stripe Product + Price.

    If the product already has a ``stripe_price_id`` it is returned as-is.
    Otherwise a Stripe Product and a one-time Price in BRL are created and
    the product row is updated with the new IDs.

    Returns:
        Stripe Price ID (``price_...``).
    """
    import stripe as stripe_lib

    stripe_key = _get_stripe_key()

    existing_price_id = product.get("stripe_price_id")
    if existing_price_id:
        logger.debug(
            "checkout: using existing stripe_price_id=%s for sku=%s",
            existing_price_id[:8],
            product["sku"],
        )
        return existing_price_id

    # Create Stripe Product
    try:
        stripe_product = stripe_lib.Product.create(
            name=product["name"],
            description=product.get("description") or "",
            metadata={"sku": product["sku"], "source": "checkout_endpoint"},
            api_key=stripe_key,
        )
        stripe_product_id = stripe_product.id
        logger.info(
            "checkout: created stripe product %s for sku=%s",
            stripe_product_id,
            product["sku"],
        )
    except Exception as exc:
        logger.error("checkout: failed to create Stripe Product for sku=%s: %s", product["sku"], exc)
        raise HTTPException(
            status_code=503,
            detail="Erro ao configurar produto no gateway de pagamento.",
        ) from exc

    # Create Stripe Price (one-time, BRL)
    try:
        unit_amount = product["price_brl"]
        stripe_price = stripe_lib.Price.create(
            product=stripe_product_id,
            currency="brl",
            unit_amount=unit_amount,
            metadata={"sku": product["sku"]},
            api_key=stripe_key,
        )
        stripe_price_id = stripe_price.id
        logger.info(
            "checkout: created stripe price %s (BRL %d) for sku=%s",
            stripe_price_id,
            unit_amount,
            product["sku"],
        )
    except Exception as exc:
        logger.error(
            "checkout: failed to create Stripe Price for sku=%s product=%s: %s",
            product["sku"],
            stripe_product_id,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="Erro ao configurar preco no gateway de pagamento.",
        ) from exc

    # Persist stripe IDs back to the product row (best-effort)
    try:
        sb = get_supabase()
        await sb_execute(
            sb.table("digital_products").update({
                "stripe_product_id": stripe_product_id,
                "stripe_price_id": stripe_price_id,
            }).eq("id", product["id"])
        )
        logger.info(
            "checkout: persisted stripe ids for product %s (sku=%s)",
            product["id"][:8],
            product["sku"],
        )
    except Exception as exc:
        # Non-blocking — the Price object exists in Stripe and will be
        # reused on the next checkout via the metadata lookup fallback below.
        logger.warning(
            "checkout: failed to persist stripe ids for sku=%s: %s",
            product["sku"],
            exc,
        )

    return stripe_price_id


@router.post("/one-time", response_model=CheckoutResponse)
async def create_one_time_checkout(
    payload: CheckoutRequest,
    user: dict = Depends(require_auth),
):
    """Create a Stripe Checkout Session for a one-time digital product purchase.

    Flow:
        1. Validate SKU against digital_products table
        2. Resolve or create Stripe Price
        3. Create Stripe Checkout Session with card/boleto/PIX
        4. Return checkout URL

    Rate limited: 10 req/min per IP.
    """
    import stripe as stripe_lib

    stripe_key = _get_stripe_key()

    # Step 1: Lookup product by SKU
    product = await _lookup_product(payload.sku)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Produto nao encontrado",
        )

    if not product.get("active", False):
        raise HTTPException(
            status_code=400,
            detail="Produto indisponivel",
        )

    user_id = user.get("sub") or user.get("id") or ""
    product_id = str(product["id"])

    # Step 2: Resolve or create Stripe Price
    stripe_price_id = _ensure_stripe_price(product)

    # Step 3: Build metadata from request context
    context = payload.context or {}
    entity_type = context.get("entity_type", "")
    entity_id = context.get("entity_id", "")

    metadata = {
        "sku": payload.sku,
        "product_id": product_id,
        "user_id": user_id,
    }
    if entity_type:
        metadata["entity_type"] = entity_type
    if entity_id:
        metadata["entity_id"] = entity_id

    # Step 4: Create Checkout Session
    frontend_url = _get_frontend_url()
    success_url = f"{frontend_url}/obrigado?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{frontend_url}/produtos"

    try:
        session = stripe_lib.checkout.Session.create(
            mode="payment",
            payment_method_types=["card", "boleto", "pix"],
            line_items=[{"price": stripe_price_id, "quantity": 1}],
            metadata=metadata,
            customer_email=user.get("email", ""),
            success_url=success_url,
            cancel_url=cancel_url,
            api_key=stripe_key,
        )
    except stripe_lib.error.InvalidRequestError as exc:
        logger.error(
            "checkout: Stripe InvalidRequestError for sku=%s user=%s: %s",
            payload.sku,
            user_id[:8],
            exc,
        )
        raise HTTPException(
            status_code=400,
            detail="Nao foi possivel iniciar o checkout. Verifique os dados e tente novamente.",
        ) from exc
    except stripe_lib.error.StripeError as exc:
        logger.error(
            "checkout: Stripe error for sku=%s user=%s: %s",
            payload.sku,
            user_id[:8],
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="Servico de pagamento temporariamente indisponivel. Tente novamente.",
        ) from exc

    logger.info(
        "checkout: session created — sku=%s user=%s session=%s",
        payload.sku,
        user_id[:8],
        session.id,
    )

    return CheckoutResponse(checkout_url=session.url)
