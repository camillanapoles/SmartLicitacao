"""BIZ-FOUND-002: idempotent provisioner for the Stripe FOUNDING_LIFETIME coupon.

Creates (or verifies) the canonical Stripe coupon used by the founding
cohort:

    id          = FOUNDING_LIFETIME
    percent_off = 50
    duration    = forever
    name        = SmartLic Founding Member - 50% off forever
    metadata    = {source: 'biz-found-002'}

The script is safe to re-run: if the coupon already exists, it logs the
current configuration and exits 0. It does NOT modify an existing coupon
to avoid clobbering operator overrides.

Usage:
    STRIPE_SECRET_KEY=sk_test_... python scripts/create_founding_lifetime_coupon.py
    STRIPE_SECRET_KEY=sk_test_... python scripts/create_founding_lifetime_coupon.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys


COUPON_ID = "FOUNDING_LIFETIME"
COUPON_NAME = "SmartLic Founding Member - 50% off forever"
COUPON_PERCENT_OFF = 50
COUPON_DURATION = "forever"
COUPON_METADATA = {"source": "biz-found-002", "story": "BIZ-FOUND-002"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Idempotent Stripe FOUNDING_LIFETIME coupon provisioner."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Probe Stripe; don't create the coupon if it's missing.",
    )
    parser.add_argument(
        "--coupon-id",
        default=COUPON_ID,
        help=f"Override coupon id (default: {COUPON_ID}).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    api_key = os.getenv("STRIPE_SECRET_KEY")
    if not api_key:
        print("ERROR: STRIPE_SECRET_KEY not set in env.", file=sys.stderr)
        return 2

    try:
        import stripe  # type: ignore[import-not-found]
    except ImportError:
        print(
            "ERROR: stripe package not installed. Run `pip install stripe`.",
            file=sys.stderr,
        )
        return 2

    stripe.api_key = api_key
    coupon_id = args.coupon_id

    # Try retrieve first (idempotency).
    try:
        existing = stripe.Coupon.retrieve(coupon_id)
        print(
            f"OK: coupon {coupon_id!r} already exists — "
            f"percent_off={existing.percent_off} "
            f"duration={existing.duration} "
            f"valid={existing.valid}"
        )
        if existing.percent_off != COUPON_PERCENT_OFF or existing.duration != COUPON_DURATION:
            print(
                "WARNING: existing coupon has divergent config — operator must "
                "decide whether to delete + recreate. Aborting without changes.",
                file=sys.stderr,
            )
            return 1
        return 0
    except stripe.error.InvalidRequestError as e:
        # Stripe returns "No such coupon" on missing id.
        msg = str(e)
        if "No such coupon" not in msg and "no such coupon" not in msg.lower():
            print(f"ERROR: unexpected Stripe error retrieving coupon: {e}", file=sys.stderr)
            return 2

    if args.dry_run:
        print(
            f"DRY-RUN: coupon {coupon_id!r} does not exist — would create with "
            f"percent_off={COUPON_PERCENT_OFF} duration={COUPON_DURATION}."
        )
        return 0

    # Create.
    try:
        created = stripe.Coupon.create(
            id=coupon_id,
            name=COUPON_NAME,
            percent_off=COUPON_PERCENT_OFF,
            duration=COUPON_DURATION,
            metadata=COUPON_METADATA,
        )
        print(
            f"CREATED: coupon {created.id!r} percent_off={created.percent_off} "
            f"duration={created.duration} valid={created.valid}"
        )
        return 0
    except stripe.error.StripeError as e:
        print(f"ERROR: failed to create coupon: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
