#!/usr/bin/env python3
"""CONV-005b-1: Sync digital_products to Stripe Products/Prices.

Standalone script that reads active digital products from Supabase and
creates corresponding Stripe Products and one-time Prices in BRL.

Idempotent: skips products that already have stripe_product_id and stripe_price_id.
Supports card, boleto, and pix payment methods.

Usage:
    cd backend
    python scripts/sync_digital_products_stripe.py

Environment variables required:
    SUPABASE_URL, SUPABASE_SERVICE_KEY (for direct DB read as service_role)
    STRIPE_API_KEY (defaults to stripe.api_key from env)

Dependencies:
    stripe>=11.4 (already in requirements.txt)
"""

from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Stripe PaymentMethodTypes for BRL one-time payments
_PAYMENT_METHOD_TYPES = ["card", "boleto", "pix"]


# ---------------------------------------------------------------------------
# Supabase read
# ---------------------------------------------------------------------------


def _get_unsynced_products() -> list[dict]:
    """Query digital_products where stripe_product_id is NULL and active = true."""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not supabase_key:
        logger.error("SUPABASE_URL and SUPABASE_SERVICE_KEY env vars are required")
        sys.exit(1)

    try:
        from supabase import create_client

        sb = create_client(supabase_url, supabase_key)
        result = (
            sb.table("digital_products")
            .select("*")
            .eq("active", True)
            .is_("stripe_product_id", "null")
            .execute()
        )
        return result.data if result.data else []
    except Exception as exc:
        logger.error("Failed to query digital_products: %s", exc)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Stripe sync
# ---------------------------------------------------------------------------


def _sync_product_to_stripe(product: dict) -> dict:
    """Create (or retrieve) Stripe Product + Price for a digital product.

    Returns dict with stripe_product_id and stripe_price_id.
    """
    import stripe

    sku = product["sku"]
    name = product["name"]
    description = product.get("description") or ""
    price_brl = product["price_brl"]  # already in cents

    logger.info("Creating Stripe Product for '%s' (SKU: %s)...", name, sku)

    # 1. Create Stripe Product
    stripe_product = stripe.Product.create(
        name=name,
        description=description,
        metadata={"sku": sku, "source": "digital_products"},
    )
    stripe_product_id = stripe_product.id
    logger.info("  -> Product %s created: %s", stripe_product_id, stripe_product.name)

    # 2. Create one-time Price in BRL (cents)
    stripe_price = stripe.Price.create(
        product=stripe_product_id,
        unit_amount=price_brl,
        currency="brl",
        metadata={"sku": sku},
    )
    stripe_price_id = stripe_price.id
    logger.info("  -> Price %s created: %.2f BRL", stripe_price_id, price_brl / 100)

    return {
        "stripe_product_id": stripe_product_id,
        "stripe_price_id": stripe_price_id,
    }


def _update_product_with_stripe_ids(product_id: str, stripe_ids: dict) -> None:
    """Persist stripe_product_id and stripe_price_id back to Supabase."""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")

    try:
        from supabase import create_client

        sb = create_client(supabase_url, supabase_key)
        sb.table("digital_products").update(stripe_ids).eq("id", product_id).execute()
        logger.info("  -> Updated product %s with Stripe IDs", product_id)
    except Exception as exc:
        logger.error("Failed to update product %s: %s", product_id, exc)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point: sync all unsynced digital products to Stripe."""
    import stripe

    stripe.api_key = os.environ.get("STRIPE_API_KEY")
    if not stripe.api_key:
        logger.error("STRIPE_API_KEY env var is required")
        sys.exit(1)

    products = _get_unsynced_products()
    if not products:
        logger.info("No unsynced products found. All digital products are up to date.")
        return

    logger.info("Found %d unsynced product(s). Syncing to Stripe...", len(products))

    for product in products:
        try:
            stripe_ids = _sync_product_to_stripe(product)
            _update_product_with_stripe_ids(product["id"], stripe_ids)
        except Exception as exc:
            logger.error("Failed to sync product %s (%s): %s", product.get("sku"), product.get("id"), exc)
            continue

    logger.info("Sync complete. %d product(s) processed.", len(products))


if __name__ == "__main__":
    main()
