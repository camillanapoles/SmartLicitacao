"""Create (idempotent) a Stripe Product + Price for the Founding Lifetime offer.

Usage:
    STRIPE_SECRET_KEY=sk_live_... python scripts/create_founding_lifetime_price.py
    STRIPE_SECRET_KEY=sk_live_... python scripts/create_founding_lifetime_price.py --dry-run
    STRIPE_SECRET_KEY=sk_live_... python scripts/create_founding_lifetime_price.py \\
        --product-id prod_existing_id

After a successful run the script prints:

    FOUNDING_ONE_TIME_PRICE_ID=price_xxx

Set that value as a Railway environment variable for the backend service.

Idempotency:
- Product: searches by name "SmartLic Founding Lifetime". Reuses if found.
- Price: lists active prices for the product, filtered by amount (99700 cents),
  currency (brl), and type (one_time). Reuses if found.
- Running multiple times is safe — no duplicates are created.
"""

from __future__ import annotations

import argparse
import os
import sys


PRODUCT_NAME = "SmartLic Founding Lifetime"
PRICE_UNIT_AMOUNT = 99700  # R$997,00 in BRL cents
CURRENCY = "brl"
DESCRIPTION = (
    "Acesso vitalício ao SmartLic Pro — oferta exclusiva founding. "
    "Pagamento único, sem mensalidade."
)


def _find_existing_product(stripe_lib, api_key: str, name: str) -> str | None:
    """Return product id if a product with this exact name already exists."""
    try:
        results = stripe_lib.Product.search(
            query=f'name:"{name}"',
            limit=5,
            api_key=api_key,
        )
        for p in results.data:
            if p.name == name and p.active:
                return p.id
    except stripe_lib.error.InvalidRequestError:
        # search API not available on older API versions — fall back to list
        pass
    try:
        for p in stripe_lib.Product.list(limit=100, active=True, api_key=api_key).auto_paging_iter():
            if p.name == name:
                return p.id
    except Exception:
        pass
    return None


def _find_existing_price(stripe_lib, api_key: str, product_id: str) -> str | None:
    """Return price id if a matching one-time BRL price already exists."""
    for price in stripe_lib.Price.list(
        product=product_id,
        active=True,
        limit=100,
        api_key=api_key,
    ).auto_paging_iter():
        if (
            price.unit_amount == PRICE_UNIT_AMOUNT
            and price.currency == CURRENCY
            and price.type == "one_time"
        ):
            return price.id
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision Stripe Founding Lifetime price")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without calling Stripe",
    )
    parser.add_argument(
        "--product-id",
        default=None,
        help="Reuse an existing Stripe product ID instead of creating a new one",
    )
    args = parser.parse_args()

    api_key = os.environ.get("STRIPE_SECRET_KEY")
    if not api_key:
        print("ERROR: STRIPE_SECRET_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("[dry-run] Would create/reuse:")
        print(f"  Product: {PRODUCT_NAME!r}")
        print(f"  Price:   {PRICE_UNIT_AMOUNT} {CURRENCY.upper()} one_time")
        print()
        print("Set in Railway:")
        print("  FOUNDING_ONE_TIME_PRICE_ID=price_<to be determined>")
        return

    import stripe as stripe_lib

    product_id = args.product_id

    if not product_id:
        existing_product = _find_existing_product(stripe_lib, api_key, PRODUCT_NAME)
        if existing_product:
            print(f"[reuse] Product already exists: {existing_product}")
            product_id = existing_product
        else:
            product = stripe_lib.Product.create(
                name=PRODUCT_NAME,
                description=DESCRIPTION,
                metadata={
                    "offer": "founding_lifetime",
                    "version": "v2",
                },
                api_key=api_key,
            )
            product_id = product.id
            print(f"[created] Product: {product_id}")
    else:
        print(f"[provided] Using product: {product_id}")

    existing_price = _find_existing_price(stripe_lib, api_key, product_id)
    if existing_price:
        print(f"[reuse] Price already exists: {existing_price}")
        price_id = existing_price
    else:
        price = stripe_lib.Price.create(
            product=product_id,
            unit_amount=PRICE_UNIT_AMOUNT,
            currency=CURRENCY,
            metadata={
                "offer": "founding_lifetime",
                "version": "v2",
            },
            api_key=api_key,
        )
        price_id = price.id
        print(f"[created] Price: {price_id}")

    print()
    print("=" * 60)
    print("Set the following Railway environment variable:")
    print()
    print(f"FOUNDING_ONE_TIME_PRICE_ID={price_id}")
    print("=" * 60)


if __name__ == "__main__":
    main()
