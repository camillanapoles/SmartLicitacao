"""BILL-SYNC-001: Stripe -> DB forward sync handlers.

Events handled:
    - product.updated
    - price.created
    - price.updated
    - price.deleted (soft-delete via is_archived = TRUE)

These handlers are invoked from `webhooks/stripe.py::stripe_webhook` AFTER
the dispatcher has already enforced idempotency via `stripe_webhook_events`
(INSERT ... ON CONFLICT DO NOTHING). Therefore the handler bodies can be
re-execution safe `UPDATE`s — they never need their own dedup check.

Design notes
------------
* AC9 (24h race guard): if `last_reverse_synced_at` is younger than 24h we
  SKIP the forward write. This prevents "I just pushed DB -> Stripe and
  Stripe immediately echoes the event back" loops. A Sentry warning fires
  so operators can investigate ambiguous cases.
* AC1 (out-of-order): we compare `event.created` against
  `last_forward_synced_at` and only apply if the incoming event is newer.
  Stripe doesn't guarantee event ordering, so this defends against an old
  webhook arriving after a fresh one.
* Stripe never supports updating a price's `unit_amount`. `price.updated`
  in practice only carries metadata / nickname / active toggles. Real
  price changes are price.created + price.deleted (archive old).
* All operations here are pure DB updates. We deliberately do NOT call
  Stripe API from inside these handlers — the webhook dispatcher wraps us
  in `asyncio.wait_for(..., 30s)` and Stripe API latency would risk
  timeouts. Reconciliation cron and the reverse-sync route do all the
  outbound Stripe work.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

import stripe

from log_sanitizer import get_sanitized_logger

logger = get_sanitized_logger(__name__)


# AC9: forward sync skipped if a reverse sync ran within the last 24h.
RACE_GUARD_WINDOW = timedelta(hours=24)


def _stripe_event_created_at(event: stripe.Event) -> datetime | None:
    """Return Stripe's `event.created` (unix seconds) as an aware datetime."""
    created = getattr(event, "created", None)
    if created is None:
        return None
    try:
        return datetime.fromtimestamp(int(created), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _parse_pg_timestamp(value: Any) -> datetime | None:
    """Parse a PostgREST timestamp string (with optional 'Z') into datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _interval_to_billing_period(interval: str | None, interval_count: int | None) -> str | None:
    """Map Stripe (recurring.interval, interval_count) -> our billing_period enum."""
    if interval == "year":
        return "annual"
    if interval == "month":
        if interval_count == 6:
            return "semiannual"
        if interval_count == 1 or interval_count is None:
            return "monthly"
    return None


def _race_guard_blocks(row: dict, event_created_at: datetime | None) -> bool:
    """AC9: skip forward sync if last_reverse_synced_at is within the 24h window."""
    last_reverse = _parse_pg_timestamp(row.get("last_reverse_synced_at"))
    if last_reverse is None:
        return False
    now = event_created_at or datetime.now(timezone.utc)
    return (now - last_reverse) < RACE_GUARD_WINDOW


def _is_stale_event(row: dict, event_created_at: datetime | None) -> bool:
    """AC1 (R1): drop events older than the row's last forward sync."""
    if event_created_at is None:
        return False
    last_forward = _parse_pg_timestamp(row.get("last_forward_synced_at"))
    if last_forward is None:
        return False
    return event_created_at < last_forward


def _emit_sentry_warning(message: str, **tags: Any) -> None:
    """AC5/AC7: best-effort Sentry alert. Never raises."""
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for k, v in tags.items():
                if v is not None:
                    scope.set_tag(k, str(v))
            scope.fingerprint = ["billing_sync", str(tags.get("event_type", "unknown"))]
            sentry_sdk.capture_message(message, level="warning")
    except Exception as e:  # pragma: no cover — logging only
        logger.debug(f"Sentry emit skipped: {e}")


# ---------------------------------------------------------------------------
# product.updated
# ---------------------------------------------------------------------------
async def handle_product_updated(sb, event: stripe.Event) -> dict:
    """Forward sync for `product.updated`.

    Stripe products carry name/description/metadata — none of which are
    stored on `plan_billing_periods` directly. This handler:
      1. Locates rows by `stripe_product_id`.
      2. Enforces 24h race guard + staleness check.
      3. Updates `last_forward_synced_at` so reconciliation knows the row
         is fresh.
      4. Emits a Sentry warning describing the diff (visibility, AC5).
    """
    product = event.data.object
    product_id = product.get("id") if hasattr(product, "get") else getattr(product, "id", None)
    if not product_id:
        logger.warning("product.updated missing product id")
        return {"status": "skipped", "reason": "no_product_id"}

    event_created_at = _stripe_event_created_at(event)

    rows_result = (
        sb.table("plan_billing_periods")
        .select("id, plan_id, billing_period, last_forward_synced_at, last_reverse_synced_at")
        .eq("stripe_product_id", product_id)
        .execute()
    )
    rows = rows_result.data or []
    if not rows:
        logger.info(f"product.updated: no plan_billing_periods rows for product={product_id}")
        return {"status": "skipped", "reason": "no_matching_rows", "product_id": product_id}

    updated = 0
    skipped_race = 0
    skipped_stale = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for row in rows:
        if _race_guard_blocks(row, event_created_at):
            skipped_race += 1
            continue
        if _is_stale_event(row, event_created_at):
            skipped_stale += 1
            continue

        sb.table("plan_billing_periods").update(
            {"last_forward_synced_at": now_iso}
        ).eq("id", row["id"]).execute()
        updated += 1

    _emit_sentry_warning(
        f"billing.sync.product_updated product={product_id} "
        f"updated={updated} skipped_race={skipped_race} skipped_stale={skipped_stale}",
        event_type="product.updated",
        product_id=product_id,
    )

    return {
        "status": "ok" if not (skipped_race or skipped_stale) else "partial",
        "product_id": product_id,
        "updated": updated,
        "skipped_race_guard": skipped_race,
        "skipped_stale_event": skipped_stale,
    }


# ---------------------------------------------------------------------------
# price.created
# ---------------------------------------------------------------------------
async def handle_price_created(sb, event: stripe.Event) -> dict:
    """Forward sync for `price.created`.

    A new Stripe Price was minted (manually in the dashboard, or via API).
    We don't auto-attach it to a plan_billing_period — Stripe alone cannot
    tell us which (plan_id, billing_period) the new price replaces. The
    correct flow is the reverse-sync route which writes
    last_reverse_synced_at + new stripe_price_id atomically.

    However we DO update the matching row's `last_forward_synced_at` if a
    row already references this price id (e.g. admin pre-populated DB then
    Stripe echoes the event). That keeps reconciliation drift = 0.
    """
    price = event.data.object
    price_id = price.get("id") if hasattr(price, "get") else getattr(price, "id", None)
    if not price_id:
        logger.warning("price.created missing price id")
        return {"status": "skipped", "reason": "no_price_id"}

    event_created_at = _stripe_event_created_at(event)
    now_iso = datetime.now(timezone.utc).isoformat()

    existing = (
        sb.table("plan_billing_periods")
        .select("id, plan_id, billing_period, last_forward_synced_at, last_reverse_synced_at")
        .eq("stripe_price_id", price_id)
        .execute()
    ).data or []

    if not existing:
        # New orphan price — log + Sentry for operator awareness.
        _emit_sentry_warning(
            f"billing.sync.price_created orphan price={price_id} "
            f"product={price.get('product') if hasattr(price, 'get') else None}",
            event_type="price.created",
            price_id=price_id,
        )
        return {"status": "skipped", "reason": "orphan_price", "price_id": price_id}

    updated = 0
    skipped_race = 0
    for row in existing:
        if _race_guard_blocks(row, event_created_at):
            skipped_race += 1
            continue
        sb.table("plan_billing_periods").update(
            {"last_forward_synced_at": now_iso}
        ).eq("id", row["id"]).execute()
        updated += 1

    return {
        "status": "ok",
        "price_id": price_id,
        "updated": updated,
        "skipped_race_guard": skipped_race,
    }


# ---------------------------------------------------------------------------
# price.updated
# ---------------------------------------------------------------------------
async def handle_price_updated(sb, event: stripe.Event) -> dict:
    """Forward sync for `price.updated`.

    Stripe prices are mostly immutable, but `nickname`, `metadata`, and
    `active` (true|false) can change. We sync `is_archived` (mirror of
    `active=false`), `stripe_product_id` and refresh `last_forward_synced_at`.
    The price/interval/currency themselves cannot be mutated server-side,
    so we don't even try to update those columns here.
    """
    price = event.data.object
    price_get = price.get if hasattr(price, "get") else (lambda k, d=None: getattr(price, k, d))
    price_id = price_get("id")
    if not price_id:
        logger.warning("price.updated missing price id")
        return {"status": "skipped", "reason": "no_price_id"}

    event_created_at = _stripe_event_created_at(event)
    is_active = price_get("active", True)
    product_id = price_get("product")

    rows = (
        sb.table("plan_billing_periods")
        .select("id, plan_id, billing_period, stripe_product_id, "
                "last_forward_synced_at, last_reverse_synced_at, is_archived")
        .eq("stripe_price_id", price_id)
        .execute()
    ).data or []

    if not rows:
        logger.info(f"price.updated: no plan_billing_periods rows for price={price_id}")
        return {"status": "skipped", "reason": "no_matching_rows", "price_id": price_id}

    updated = 0
    skipped_race = 0
    skipped_stale = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for row in rows:
        if _race_guard_blocks(row, event_created_at):
            skipped_race += 1
            continue
        if _is_stale_event(row, event_created_at):
            skipped_stale += 1
            continue

        update_data: dict[str, Any] = {"last_forward_synced_at": now_iso}
        if product_id and row.get("stripe_product_id") != product_id:
            update_data["stripe_product_id"] = product_id

        new_archived = not bool(is_active)
        if bool(row.get("is_archived")) != new_archived:
            update_data["is_archived"] = new_archived

        sb.table("plan_billing_periods").update(update_data).eq("id", row["id"]).execute()
        updated += 1

    _emit_sentry_warning(
        f"billing.sync.price_updated price={price_id} active={is_active} "
        f"updated={updated} skipped_race={skipped_race} skipped_stale={skipped_stale}",
        event_type="price.updated",
        price_id=price_id,
    )

    return {
        "status": "ok" if not (skipped_race or skipped_stale) else "partial",
        "price_id": price_id,
        "updated": updated,
        "skipped_race_guard": skipped_race,
        "skipped_stale_event": skipped_stale,
    }


# ---------------------------------------------------------------------------
# price.deleted
# ---------------------------------------------------------------------------
async def handle_price_deleted(sb, event: stripe.Event) -> dict:
    """Forward sync for `price.deleted` (Stripe semantically: archived).

    Stripe never hard-deletes a price (would break historical invoices).
    The `price.deleted` event fires when a price is archived in the
    dashboard. We mirror that by setting `is_archived = TRUE`.
    """
    price = event.data.object
    price_id = price.get("id") if hasattr(price, "get") else getattr(price, "id", None)
    if not price_id:
        logger.warning("price.deleted missing price id")
        return {"status": "skipped", "reason": "no_price_id"}

    event_created_at = _stripe_event_created_at(event)
    now_iso = datetime.now(timezone.utc).isoformat()

    rows = (
        sb.table("plan_billing_periods")
        .select("id, plan_id, billing_period, last_forward_synced_at, last_reverse_synced_at, is_archived")
        .eq("stripe_price_id", price_id)
        .execute()
    ).data or []

    if not rows:
        logger.info(f"price.deleted: no plan_billing_periods rows for price={price_id}")
        return {"status": "skipped", "reason": "no_matching_rows", "price_id": price_id}

    archived = 0
    skipped_race = 0
    for row in rows:
        if _race_guard_blocks(row, event_created_at):
            skipped_race += 1
            continue
        sb.table("plan_billing_periods").update(
            {"is_archived": True, "last_forward_synced_at": now_iso}
        ).eq("id", row["id"]).execute()
        archived += 1

    _emit_sentry_warning(
        f"billing.sync.price_deleted price={price_id} archived={archived}",
        event_type="price.deleted",
        price_id=price_id,
    )

    return {
        "status": "ok" if not skipped_race else "partial",
        "price_id": price_id,
        "archived": archived,
        "skipped_race_guard": skipped_race,
    }
