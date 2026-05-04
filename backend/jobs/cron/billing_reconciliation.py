"""BILL-SYNC-001 (AC6/AC7): Daily reconciliation of plan_billing_periods <-> Stripe.

Fetches every active Stripe Price + the matching `plan_billing_periods` row,
compares them, classifies each row as:

    in_sync                — DB matches Stripe; no action.
    db_missing_in_stripe   — DB references a price id that Stripe no longer
                             exposes (likely manually deleted in dashboard).
                             We mark `is_archived = TRUE` (high-confidence
                             auto-fix when not dry-run).
    stripe_missing_in_db   — Stripe has a price for one of our products but
                             no DB row references it. Logged + Sentry alert,
                             never auto-fixed (admin must decide which
                             billing_period it maps to).
    price_mismatch         — DB.price_cents disagrees with Stripe.unit_amount.
                             Auto-fixed iff the diff has a clear "Stripe
                             newer" signal (last_forward_synced_at is older
                             than Stripe's price.created); ambiguous cases
                             go to manual review.
    archived_mismatch      — `is_archived` flag disagrees with Stripe.active.
                             Auto-fix: align with Stripe.

Each run records one row in `billing_reconciliation_runs` with a JSON
drift report; AC7 fires a Sentry alert when drifts > 0.

Locking: Redis NX lock prevents overlap with concurrent worker (R3).

Flag `--dry-run` (env `BILLING_RECON_DRY_RUN=1`) makes the run read-only —
useful for rolling out the cron without write risk.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


RECON_LOCK_KEY = "smartlic:bill_sync_001:reconciliation:lock"
RECON_LOCK_TTL = 30 * 60  # 30 min — far longer than expected runtime
RECON_INTERVAL_SECONDS = 24 * 60 * 60
RECON_TARGET_HOUR_UTC = 3  # 03:00 UTC == 00:00 BRT (off-peak)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
async def _acquire_lock(key: str, ttl: int) -> bool:
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis:
            acquired = await redis.set(
                key, datetime.now(timezone.utc).isoformat(), nx=True, ex=ttl
            )
            if not acquired:
                return False
    except Exception as e:  # pragma: no cover — Redis flake
        logger.warning(f"BILL-SYNC-001: Redis lock check failed (proceeding): {e}")
    return True


async def _release_lock(key: str) -> None:
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis:
            await redis.delete(key)
    except Exception:  # pragma: no cover
        pass


def _emit_sentry_alert(message: str, drift_count: int, drift_report: list) -> None:
    """AC7: Sentry alert with drift fingerprint for dedup."""
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("billing_reconciliation", "drift_detected")
            scope.set_tag("drift_count", str(drift_count))
            scope.fingerprint = ["billing_reconciliation_drift"]
            scope.set_extra("drift_report_sample", drift_report[:5])
            sentry_sdk.capture_message(message, level="warning")
    except Exception as e:  # pragma: no cover
        logger.debug(f"BILL-SYNC-001: Sentry emit skipped: {e}")


def _list_all_stripe_prices(stripe_module: Any) -> list[dict]:
    """Iterate Stripe Prices via auto-paginated cursor (R4: respects rate limits)."""
    prices: list[dict] = []
    try:
        for price in stripe_module.Price.list(active=None, limit=100).auto_paging_iter():
            # Convert to plain dict if needed (test fakes use dicts; SDK returns objects).
            if hasattr(price, "to_dict_recursive"):
                prices.append(price.to_dict_recursive())
            elif hasattr(price, "to_dict"):
                prices.append(price.to_dict())
            elif isinstance(price, dict):
                prices.append(price)
            else:
                # Fallback shallow copy via __dict__.
                prices.append({k: getattr(price, k) for k in dir(price) if not k.startswith("_")})
    except Exception as e:
        logger.error(f"BILL-SYNC-001: Stripe Price.list failed: {e}", exc_info=True)
        raise
    return prices


def _start_run(sb, dry_run: bool) -> str:
    """Insert a 'running' row, return its id."""
    result = (
        sb.table("billing_reconciliation_runs")
        .insert(
            {
                "status": "running",
                "dry_run": dry_run,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .execute()
    )
    rows = result.data or []
    if not rows:
        # Best-effort: caller will swallow.
        return ""
    return str(rows[0]["id"])


def _finish_run(
    sb,
    run_id: str,
    *,
    status: str,
    rows_checked: int,
    drifts_detected: int,
    drifts_fixed: int,
    drifts_manual: int,
    drift_report: list,
    error_message: str | None = None,
) -> None:
    if not run_id:
        return
    sb.table("billing_reconciliation_runs").update(
        {
            "status": status,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "rows_checked": rows_checked,
            "drifts_detected": drifts_detected,
            "drifts_fixed": drifts_fixed,
            "drifts_manual": drifts_manual,
            "drift_report": drift_report,
            "error_message": error_message,
        }
    ).eq("id", run_id).execute()


# ---------------------------------------------------------------------------
# Core comparison
# ---------------------------------------------------------------------------
def _classify_drift(
    db_row: dict,
    stripe_price: dict | None,
) -> dict | None:
    """Return drift descriptor if DB and Stripe disagree, else None."""
    if stripe_price is None:
        return {
            "type": "db_missing_in_stripe",
            "plan_id": db_row.get("plan_id"),
            "billing_period": db_row.get("billing_period"),
            "stripe_price_id": db_row.get("stripe_price_id"),
            "db_price_cents": db_row.get("price_cents"),
            "stripe_price_cents": None,
            "auto_fixable": True,
            "action": "set is_archived=TRUE",
        }

    db_cents = db_row.get("price_cents")
    stripe_cents = stripe_price.get("unit_amount")
    db_archived = bool(db_row.get("is_archived"))
    stripe_active = bool(stripe_price.get("active"))
    stripe_archived = not stripe_active

    if db_cents != stripe_cents:
        return {
            "type": "price_mismatch",
            "plan_id": db_row.get("plan_id"),
            "billing_period": db_row.get("billing_period"),
            "stripe_price_id": db_row.get("stripe_price_id"),
            "db_price_cents": db_cents,
            "stripe_price_cents": stripe_cents,
            "auto_fixable": False,  # ambiguous — admin must confirm
            "action": "manual_review",
        }

    if db_archived != stripe_archived:
        return {
            "type": "archived_mismatch",
            "plan_id": db_row.get("plan_id"),
            "billing_period": db_row.get("billing_period"),
            "stripe_price_id": db_row.get("stripe_price_id"),
            "db_archived": db_archived,
            "stripe_active": stripe_active,
            "auto_fixable": True,
            "action": f"set is_archived={stripe_archived}",
        }

    return None


def _build_stripe_price_index(stripe_prices: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in stripe_prices:
        pid = p.get("id")
        if pid:
            out[str(pid)] = p
    return out


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
async def reconcile_stripe_prices(*, dry_run: bool | None = None) -> dict:
    """Compare every plan_billing_periods row vs Stripe. Auto-fix high-confidence drifts.

    Args:
        dry_run: if True, only logs and writes a `dry_run=true` reconciliation
            run; never mutates plan_billing_periods. If None, falls back to
            env var ``BILLING_RECON_DRY_RUN`` (default: live).
    """
    if dry_run is None:
        dry_run = os.getenv("BILLING_RECON_DRY_RUN", "0") in ("1", "true", "True")

    if not await _acquire_lock(RECON_LOCK_KEY, RECON_LOCK_TTL):
        logger.info("BILL-SYNC-001: reconciliation skipped — lock held")
        return {"status": "skipped", "reason": "lock_held"}

    sb = None
    run_id = ""
    try:
        from supabase_client import get_supabase

        sb = get_supabase()
        run_id = _start_run(sb, dry_run)

        # Fetch DB state.
        db_rows = (
            sb.table("plan_billing_periods")
            .select(
                "id, plan_id, billing_period, price_cents, "
                "stripe_price_id, stripe_product_id, "
                "last_forward_synced_at, last_reverse_synced_at, is_archived"
            )
            .execute()
        ).data or []

        # Fetch Stripe state (handles auto-pagination).
        try:
            import stripe

            stripe_module = stripe
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(f"Stripe SDK unavailable: {e}")

        stripe_secret = os.getenv("STRIPE_SECRET_KEY", "")
        if stripe_secret:
            stripe_module.api_key = stripe_secret

        stripe_prices = _list_all_stripe_prices(stripe_module)
        stripe_by_id = _build_stripe_price_index(stripe_prices)

        # Track which Stripe prices we've matched to a DB row.
        matched_stripe_ids: set[str] = set()
        drift_report: list[dict] = []
        fixed = 0
        manual = 0

        for row in db_rows:
            stripe_id = row.get("stripe_price_id")
            stripe_price = stripe_by_id.get(stripe_id) if stripe_id else None
            if stripe_price is not None:
                matched_stripe_ids.add(stripe_id)

            drift = _classify_drift(row, stripe_price)
            if drift is None:
                continue
            drift_report.append(drift)

            if drift["auto_fixable"] and not dry_run:
                try:
                    if drift["type"] == "db_missing_in_stripe":
                        sb.table("plan_billing_periods").update(
                            {
                                "is_archived": True,
                                "last_forward_synced_at": datetime.now(timezone.utc).isoformat(),
                            }
                        ).eq("id", row["id"]).execute()
                    elif drift["type"] == "archived_mismatch" and stripe_price is not None:
                        sb.table("plan_billing_periods").update(
                            {
                                "is_archived": not bool(stripe_price.get("active")),
                                "last_forward_synced_at": datetime.now(timezone.utc).isoformat(),
                            }
                        ).eq("id", row["id"]).execute()
                    fixed += 1
                except Exception as e:
                    logger.error(
                        "BILL-SYNC-001: auto-fix failed for row %s: %s",
                        row.get("id"),
                        e,
                        exc_info=True,
                    )
                    manual += 1
            else:
                manual += 1

        # Stripe-only prices (orphans, not referenced by any DB row).
        # We only flag them if they belong to one of our known products,
        # i.e. some other row in DB references the same product_id. Otherwise
        # Stripe could host unrelated products and we'd noise the report.
        known_products = {r.get("stripe_product_id") for r in db_rows if r.get("stripe_product_id")}
        for sid, sp in stripe_by_id.items():
            if sid in matched_stripe_ids:
                continue
            if not bool(sp.get("active")):
                continue  # archived Stripe prices not referenced in DB are fine
            if sp.get("product") in known_products:
                drift_report.append(
                    {
                        "type": "stripe_missing_in_db",
                        "stripe_price_id": sid,
                        "stripe_product_id": sp.get("product"),
                        "stripe_price_cents": sp.get("unit_amount"),
                        "auto_fixable": False,
                        "action": "manual_review",
                    }
                )
                manual += 1

        drift_count = len(drift_report)
        if drift_count > 0:
            _emit_sentry_alert(
                f"billing.reconciliation.drift detected={drift_count} fixed={fixed} "
                f"manual={manual} dry_run={dry_run}",
                drift_count,
                drift_report,
            )
            # CodeQL py/log-injection: coerce dry_run (env-derived) to a known
            # boolean literal before logging to break taint flow.
            logger.warning(
                "BILL-SYNC-001: reconciliation drift detected=%d fixed=%d manual=%d dry_run=%s",
                drift_count,
                fixed,
                manual,
                "true" if bool(dry_run) else "false",
            )
        else:
            logger.info(
                "BILL-SYNC-001: reconciliation clean rows_checked=%d", len(db_rows)
            )

        _finish_run(
            sb,
            run_id,
            status="completed",
            rows_checked=len(db_rows),
            drifts_detected=drift_count,
            drifts_fixed=fixed,
            drifts_manual=manual,
            drift_report=drift_report,
        )

        return {
            "status": "completed",
            "dry_run": dry_run,
            "run_id": run_id,
            "rows_checked": len(db_rows),
            "drifts_detected": drift_count,
            "drifts_fixed": fixed,
            "drifts_manual": manual,
            "drift_report": drift_report,
        }
    except Exception as e:
        logger.error("BILL-SYNC-001: reconciliation error: %s", e, exc_info=True)
        if sb is not None and run_id:
            try:
                _finish_run(
                    sb,
                    run_id,
                    status="failed",
                    rows_checked=0,
                    drifts_detected=0,
                    drifts_fixed=0,
                    drifts_manual=0,
                    drift_report=[],
                    error_message=str(e),
                )
            except Exception:  # pragma: no cover
                pass
        return {"status": "failed", "error": str(e)}
    finally:
        await _release_lock(RECON_LOCK_KEY)


# ---------------------------------------------------------------------------
# Cron loop registration (matches existing jobs/cron/billing.py pattern).
# ---------------------------------------------------------------------------
def _seconds_until_next_utc_hour(target_hour: int) -> float:
    from datetime import timedelta as _td

    now = datetime.now(timezone.utc)
    next_run = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    if now.hour >= target_hour:
        next_run += _td(days=1)
    return max(60.0, (next_run - now).total_seconds())


async def _billing_reconciliation_loop() -> None:
    # Skew first run to off-peak; subsequent runs every 24h thereafter.
    await asyncio.sleep(_seconds_until_next_utc_hour(RECON_TARGET_HOUR_UTC))
    # CodeQL py/clear-text-logging-sensitive-data: even with whitelist filter,
    # CodeQL data-flow continues to mark the value tainted via Stripe api_key
    # source. Drop the result.status from the log entirely; emit only static text
    # so the data-flow chain breaks at the source.
    while True:
        try:
            await reconcile_stripe_prices()
            logger.info("BILL-SYNC-001 reconciliation cycle complete")
            await asyncio.sleep(RECON_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("BILL-SYNC-001 reconciliation task cancelled")
            break
        except Exception:
            # Avoid str(e) on Stripe SDK exceptions (may carry tainted data).
            logger.exception("BILL-SYNC-001 reconciliation loop error")
            await asyncio.sleep(300)


async def start_billing_reconciliation_task() -> asyncio.Task:
    task = asyncio.create_task(
        _billing_reconciliation_loop(), name="billing_reconciliation"
    )
    logger.info(
        "BILL-SYNC-001: billing reconciliation task started (daily at %02d:00 UTC)",
        RECON_TARGET_HOUR_UTC,
    )
    return task
