"""BILL-SYNC-001 (AC8/AC9/AC10): Admin endpoints for bidirectional Stripe sync.

Endpoints (all admin-only):
    GET    /v1/admin/plans/billing-sync                            -- list rows + drift indicator
    GET    /v1/admin/plans/reconciliation-runs                     -- last 30 cron runs
    POST   /v1/admin/plans/{plan_billing_period_id}/sync-to-stripe -- reverse sync (DB -> Stripe)
    POST   /v1/admin/plans/reconcile-now                           -- ad-hoc reconciliation trigger

Reverse sync semantics:
    Stripe Prices are immutable in `unit_amount`. To "update" a price we
    create a NEW Stripe Price (with the DB's price_cents) and archive the
    old Stripe Price (`active=false`). DB then points at the new price id.

24h race guard (AC9):
    If `last_forward_synced_at` is younger than 24h, the reverse-sync is
    REJECTED (status 409) — admin needs to investigate the recent webhook
    activity first to avoid loops. Audit log records the rejection.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from admin import require_admin
from pipeline.budget import _run_with_budget
from supabase_client import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin/plans", tags=["admin", "billing"])


# RES-BE-001 / RES-BE-015: per-query budget for admin billing sync routes.
# Admin endpoints called rarely; 5s is well below the 8s service-role
# statement_timeout and leaves headroom for response serialization.
_QUERY_BUDGET_S: float = 5.0
REVERSE_SYNC_RACE_GUARD = timedelta(hours=24)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class BillingSyncRow(BaseModel):
    id: str
    plan_id: str
    billing_period: str
    price_cents: int
    discount_percent: int = 0
    stripe_price_id: Optional[str] = None
    stripe_product_id: Optional[str] = None
    last_forward_synced_at: Optional[datetime] = None
    last_reverse_synced_at: Optional[datetime] = None
    is_archived: bool = False
    drift_status: str = Field(
        default="unknown",
        description="in_sync | drift_recent | drift_stale | unknown",
    )

    model_config = ConfigDict(extra="ignore")


class BillingSyncListResponse(BaseModel):
    items: list[BillingSyncRow]


class ReconciliationRun(BaseModel):
    id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str
    dry_run: bool = False
    rows_checked: int = 0
    drifts_detected: int = 0
    drifts_fixed: int = 0
    drifts_manual: int = 0
    drift_report: Any = None
    error_message: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class ReconciliationRunsResponse(BaseModel):
    items: list[ReconciliationRun]


class ReverseSyncRequest(BaseModel):
    i_understand_this_modifies_stripe: bool = Field(
        default=False,
        description="Admin must explicitly confirm intent to mutate Stripe.",
    )
    note: Optional[str] = Field(default=None, max_length=2000)


class ReverseSyncResponse(BaseModel):
    status: str
    plan_billing_period_id: str
    old_stripe_price_id: Optional[str] = None
    new_stripe_price_id: Optional[str] = None
    skipped_reason: Optional[str] = None
    audit_log_id: Optional[str] = None


class ReconcileNowResponse(BaseModel):
    status: str
    dry_run: bool
    drifts_detected: int = 0
    drifts_fixed: int = 0
    drifts_manual: int = 0
    run_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_pg_timestamp(value: Any) -> Optional[datetime]:
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


def _classify_drift_status(row: dict) -> str:
    """AC10: visual indicator state."""
    last_forward = _parse_pg_timestamp(row.get("last_forward_synced_at"))
    last_reverse = _parse_pg_timestamp(row.get("last_reverse_synced_at"))
    if last_forward is None and last_reverse is None:
        return "unknown"
    now = datetime.now(timezone.utc)
    most_recent = max(filter(None, [last_forward, last_reverse]))
    if (now - most_recent) < timedelta(hours=24):
        return "in_sync"
    if (now - most_recent) < timedelta(days=7):
        return "drift_recent"
    return "drift_stale"


def _audit_log(
    sb,
    *,
    plan_billing_period_id: Optional[str],
    plan_id: Optional[str],
    billing_period: Optional[str],
    action: str,
    old_stripe_price_id: Optional[str],
    new_stripe_price_id: Optional[str],
    actor_user_id: Optional[str],
    actor_email: Optional[str],
    note: Optional[str] = None,
    payload: Optional[dict] = None,
) -> Optional[str]:
    try:
        result = (
            sb.table("admin_billing_audit_log")
            .insert(
                {
                    "plan_billing_period_id": plan_billing_period_id,
                    "plan_id": plan_id,
                    "billing_period": billing_period,
                    "action": action,
                    "old_stripe_price_id": old_stripe_price_id,
                    "new_stripe_price_id": new_stripe_price_id,
                    "actor_user_id": actor_user_id,
                    "actor_email": actor_email,
                    "note": note,
                    "payload": payload,
                }
            )
            .execute()
        )
        rows = result.data or []
        return rows[0]["id"] if rows else None
    except Exception as e:
        logger.error("BILL-SYNC-001: audit log insert failed: %s", e, exc_info=True)
        return None


def _stripe_recurring_for(billing_period: str) -> Any:
    """Return recurring kwargs for stripe.Price.create. Typed as Any because
    the Stripe SDK's TypedDict only accepts literal `interval` values; we
    pass a normal dict for runtime simplicity and downcast for the SDK."""
    if billing_period == "annual":
        return {"interval": "year", "interval_count": 1}
    if billing_period == "semiannual":
        return {"interval": "month", "interval_count": 6}
    return {"interval": "month", "interval_count": 1}


# ---------------------------------------------------------------------------
# GET /billing-sync
# ---------------------------------------------------------------------------
@router.get("/billing-sync", response_model=BillingSyncListResponse)
async def list_billing_sync_rows(
    admin: dict = Depends(require_admin),
) -> BillingSyncListResponse:
    """Return every plan_billing_periods row enriched with drift_status."""
    sb = get_supabase()

    def _sync_query():
        return (
            sb.table("plan_billing_periods")
            .select(
                "id, plan_id, billing_period, price_cents, discount_percent, "
                "stripe_price_id, stripe_product_id, "
                "last_forward_synced_at, last_reverse_synced_at, is_archived"
            )
            .order("plan_id")
            .order("billing_period")
            .execute()
        )

    try:
        result = await _run_with_budget(
            asyncio.to_thread(_sync_query),
            budget=_QUERY_BUDGET_S,
            phase="route",
            source="admin_billing_sync.list_billing_sync_rows",
        )
    except asyncio.TimeoutError:
        logger.warning(
            "BILL-SYNC-001: list_billing_sync_rows exceeded %.1fs budget",
            _QUERY_BUDGET_S,
        )
        raise HTTPException(status_code=503, detail="billing sync query timed out")
    except Exception as e:
        logger.error("BILL-SYNC-001: list_billing_sync_rows DB error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="failed to load billing sync rows")

    items = []
    for row in result.data or []:
        row["drift_status"] = _classify_drift_status(row)
        items.append(BillingSyncRow.model_validate(row))
    return BillingSyncListResponse(items=items)


# ---------------------------------------------------------------------------
# GET /reconciliation-runs
# ---------------------------------------------------------------------------
@router.get("/reconciliation-runs", response_model=ReconciliationRunsResponse)
async def list_reconciliation_runs(
    admin: dict = Depends(require_admin),
    limit: int = Query(default=30, ge=1, le=200),
) -> ReconciliationRunsResponse:
    sb = get_supabase()

    def _sync_query():
        return (
            sb.table("billing_reconciliation_runs")
            .select(
                "id, started_at, finished_at, status, dry_run, rows_checked, "
                "drifts_detected, drifts_fixed, drifts_manual, drift_report, error_message"
            )
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
        )

    try:
        result = await _run_with_budget(
            asyncio.to_thread(_sync_query),
            budget=_QUERY_BUDGET_S,
            phase="route",
            source="admin_billing_sync.list_reconciliation_runs",
        )
    except asyncio.TimeoutError:
        logger.warning(
            "BILL-SYNC-001: list_reconciliation_runs exceeded %.1fs budget",
            _QUERY_BUDGET_S,
        )
        raise HTTPException(status_code=503, detail="reconciliation runs query timed out")
    except Exception as e:
        logger.error(
            "BILL-SYNC-001: list_reconciliation_runs DB error: %s", e, exc_info=True
        )
        raise HTTPException(status_code=500, detail="failed to load reconciliation runs")

    items = [ReconciliationRun.model_validate(r) for r in (result.data or [])]
    return ReconciliationRunsResponse(items=items)


# ---------------------------------------------------------------------------
# POST /{id}/sync-to-stripe (reverse sync)
# ---------------------------------------------------------------------------
@router.post(
    "/{plan_billing_period_id}/sync-to-stripe",
    response_model=ReverseSyncResponse,
)
async def sync_to_stripe(
    plan_billing_period_id: str,
    body: ReverseSyncRequest,
    admin: dict = Depends(require_admin),
) -> ReverseSyncResponse:
    """AC8/AC9: Push DB price -> Stripe by creating a new Price + archiving old."""
    if not body.i_understand_this_modifies_stripe:
        raise HTTPException(
            status_code=400,
            detail="Admin must set i_understand_this_modifies_stripe=true",
        )

    sb = get_supabase()
    actor_user_id = str(admin.get("id") or "") or None
    actor_email = admin.get("email")

    # Load row.
    def _sync_load_row():
        return (
            sb.table("plan_billing_periods")
            .select(
                "id, plan_id, billing_period, price_cents, "
                "stripe_price_id, stripe_product_id, "
                "last_forward_synced_at, last_reverse_synced_at, is_archived"
            )
            .eq("id", plan_billing_period_id)
            .limit(1)
            .execute()
        )

    try:
        row_result = await _run_with_budget(
            asyncio.to_thread(_sync_load_row),
            budget=_QUERY_BUDGET_S,
            phase="route",
            source="admin_billing_sync.sync_to_stripe.load_row",
        )
    except asyncio.TimeoutError:
        logger.warning(
            "BILL-SYNC-001: sync_to_stripe load_row exceeded %.1fs budget",
            _QUERY_BUDGET_S,
        )
        raise HTTPException(status_code=503, detail="plan_billing_period load timed out")
    except Exception as e:
        logger.error(
            "BILL-SYNC-001: sync_to_stripe load_row DB error: %s", e, exc_info=True
        )
        raise HTTPException(status_code=500, detail="failed to load plan_billing_period")

    rows = row_result.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="plan_billing_period not found")
    row = rows[0]

    # AC9: race guard.
    last_forward = _parse_pg_timestamp(row.get("last_forward_synced_at"))
    if last_forward is not None and (datetime.now(timezone.utc) - last_forward) < REVERSE_SYNC_RACE_GUARD:
        audit_id = _audit_log(
            sb,
            plan_billing_period_id=plan_billing_period_id,
            plan_id=row.get("plan_id"),
            billing_period=row.get("billing_period"),
            action="reverse_sync_skipped_race_guard",
            old_stripe_price_id=row.get("stripe_price_id"),
            new_stripe_price_id=None,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            note=body.note,
        )
        return ReverseSyncResponse(
            status="skipped",
            plan_billing_period_id=plan_billing_period_id,
            old_stripe_price_id=row.get("stripe_price_id"),
            new_stripe_price_id=None,
            skipped_reason="race_guard_24h",
            audit_log_id=audit_id,
        )

    # Resolve product id.
    product_id = row.get("stripe_product_id")
    if not product_id and row.get("stripe_price_id"):
        try:
            import stripe as stripe_module

            existing_price = stripe_module.Price.retrieve(row["stripe_price_id"])
            product_id = (
                existing_price.get("product")
                if hasattr(existing_price, "get")
                else getattr(existing_price, "product", None)
            )
        except Exception as e:
            logger.error("BILL-SYNC-001: failed to resolve product for reverse sync: %s", e)

    if not product_id:
        _audit_log(
            sb,
            plan_billing_period_id=plan_billing_period_id,
            plan_id=row.get("plan_id"),
            billing_period=row.get("billing_period"),
            action="reverse_sync_failed",
            old_stripe_price_id=row.get("stripe_price_id"),
            new_stripe_price_id=None,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            note="missing_product_id",
        )
        raise HTTPException(
            status_code=400,
            detail="stripe_product_id missing — populate it before reverse sync",
        )

    # Create new Stripe Price.
    try:
        import stripe as stripe_module

        new_price = stripe_module.Price.create(
            product=product_id,
            unit_amount=row["price_cents"],
            currency="brl",
            recurring=_stripe_recurring_for(row["billing_period"]),
            metadata={
                "plan_id": row["plan_id"],
                "billing_period": row["billing_period"],
                "source": "BILL-SYNC-001:reverse_sync",
            },
        )
    except Exception as e:
        logger.error("BILL-SYNC-001: Stripe Price.create failed: %s", e, exc_info=True)
        _audit_log(
            sb,
            plan_billing_period_id=plan_billing_period_id,
            plan_id=row.get("plan_id"),
            billing_period=row.get("billing_period"),
            action="reverse_sync_failed",
            old_stripe_price_id=row.get("stripe_price_id"),
            new_stripe_price_id=None,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            note=f"stripe_create_failed: {e}",
        )
        raise HTTPException(status_code=502, detail=f"Stripe API error: {e}")

    new_price_id = (
        new_price.get("id") if hasattr(new_price, "get") else getattr(new_price, "id", None)
    )
    old_price_id = row.get("stripe_price_id")

    # Archive old Stripe Price (best-effort — never block on failure).
    if old_price_id:
        try:
            import stripe as stripe_module

            stripe_module.Price.modify(old_price_id, active=False)
            _audit_log(
                sb,
                plan_billing_period_id=plan_billing_period_id,
                plan_id=row.get("plan_id"),
                billing_period=row.get("billing_period"),
                action="reverse_sync_archive_price",
                old_stripe_price_id=old_price_id,
                new_stripe_price_id=new_price_id,
                actor_user_id=actor_user_id,
                actor_email=actor_email,
                note=body.note,
            )
        except Exception as e:
            logger.warning(
                "BILL-SYNC-001: failed to archive old price %s (continuing): %s",
                old_price_id,
                e,
            )

    # Update DB pointer + last_reverse_synced_at.
    now_iso = datetime.now(timezone.utc).isoformat()

    def _sync_update_pointer():
        return (
            sb.table("plan_billing_periods")
            .update(
                {
                    "stripe_price_id": new_price_id,
                    "stripe_product_id": product_id,
                    "last_reverse_synced_at": now_iso,
                    "is_archived": False,
                }
            )
            .eq("id", plan_billing_period_id)
            .execute()
        )

    try:
        await _run_with_budget(
            asyncio.to_thread(_sync_update_pointer),
            budget=_QUERY_BUDGET_S,
            phase="route",
            source="admin_billing_sync.sync_to_stripe.update_pointer",
        )
    except asyncio.TimeoutError:
        logger.warning(
            "BILL-SYNC-001: sync_to_stripe update_pointer exceeded %.1fs budget — "
            "Stripe price was created but DB pointer NOT updated; reconciliation cron will detect drift",
        )
        raise HTTPException(
            status_code=503,
            detail="DB update timed out after Stripe price create; reconciliation cron will fix drift",
        )
    except Exception as e:
        logger.error(
            "BILL-SYNC-001: sync_to_stripe update_pointer DB error: %s", e, exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="DB update failed after Stripe price create; manual reconciliation required",
        )

    audit_id = _audit_log(
        sb,
        plan_billing_period_id=plan_billing_period_id,
        plan_id=row.get("plan_id"),
        billing_period=row.get("billing_period"),
        action="reverse_sync_create_price",
        old_stripe_price_id=old_price_id,
        new_stripe_price_id=new_price_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        note=body.note,
    )

    return ReverseSyncResponse(
        status="ok",
        plan_billing_period_id=plan_billing_period_id,
        old_stripe_price_id=old_price_id,
        new_stripe_price_id=new_price_id,
        skipped_reason=None,
        audit_log_id=audit_id,
    )


# ---------------------------------------------------------------------------
# POST /reconcile-now
# ---------------------------------------------------------------------------
@router.post("/reconcile-now", response_model=ReconcileNowResponse)
async def reconcile_now(
    admin: dict = Depends(require_admin),
    dry_run: bool = Query(default=False),
) -> ReconcileNowResponse:
    from jobs.cron.billing_reconciliation import reconcile_stripe_prices

    result = await reconcile_stripe_prices(dry_run=dry_run)
    return ReconcileNowResponse(
        status=result.get("status", "unknown"),
        dry_run=bool(result.get("dry_run", dry_run)),
        drifts_detected=int(result.get("drifts_detected", 0)),
        drifts_fixed=int(result.get("drifts_fixed", 0)),
        drifts_manual=int(result.get("drifts_manual", 0)),
        run_id=result.get("run_id"),
    )
