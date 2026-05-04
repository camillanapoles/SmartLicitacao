"""BIZ-FOUND-002: admin endpoints for the canonical founding policy.

Endpoints (all admin-only via ``require_admin``):
- ``GET  /v1/admin/founding/policy``       — current policy snapshot.
- ``GET  /v1/admin/founding/leads``        — list of founding leads + completion state.
- ``POST /v1/admin/founding/pause``        — pause checkouts (paused_at = NOW()).
- ``POST /v1/admin/founding/resume``       — resume checkouts (paused_at = NULL).

The pause/resume toggle is intentionally separate from a ``PATCH`` over the
whole row — operators should never edit ``seat_limit`` or ``deadline_at``
through a generic update without going through the database (those values
are encoded in the ADR; changing them is a product decision).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admin import require_admin
from pipeline.budget import _run_with_budget
from supabase_client import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin/founding", tags=["admin", "founding"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class FoundingPolicySnapshot(BaseModel):
    seat_limit: int
    deadline_at: str
    discount_pct: int
    coupon_code: str
    active: bool
    paused: bool
    paused_at: str | None
    paused_by: str | None
    paused_reason: str | None
    seats_taken: int
    seats_remaining: int
    completion_pct: float


class FoundingLeadEntry(BaseModel):
    id: str
    email: str
    nome: str
    cnpj: str
    razao_social: str | None = None
    checkout_status: str
    created_at: str
    completed_at: str | None = None
    stripe_customer_id: str | None = None


class FoundingLeadsListResponse(BaseModel):
    count: int
    completed_count: int
    pending_count: int
    leads: list[FoundingLeadEntry]


class FoundingPauseRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class FoundingPolicyMutationResponse(BaseModel):
    ok: bool
    paused: bool
    paused_at: str | None
    paused_reason: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _isoformat(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _fetch_policy_row(sb) -> dict[str, Any]:
    res = (
        sb.table("founding_policy")
        .select("*")
        .eq("id", 1)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        raise HTTPException(
            status_code=503,
            detail="founding_policy row missing — run migration 20260428100000.",
        )
    return rows[0]


def _count_completed(sb) -> int:
    res = (
        sb.table("founding_leads")
        .select("id", count="exact")
        .eq("checkout_status", "completed")
        .execute()
    )
    if hasattr(res, "count") and res.count is not None:
        return int(res.count)
    return len(res.data or [])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/policy", response_model=FoundingPolicySnapshot)
async def get_founding_policy(_admin=Depends(require_admin)) -> Any:
    """Snapshot of the canonical policy + live seat usage."""
    sb = get_supabase()
    row = _fetch_policy_row(sb)
    seats_taken = _count_completed(sb)
    seat_limit = int(row.get("seat_limit") or 0)
    completion_pct = (
        round((seats_taken / seat_limit) * 100, 2) if seat_limit > 0 else 0.0
    )
    deadline_iso = _isoformat(row.get("deadline_at")) or ""

    return FoundingPolicySnapshot(
        seat_limit=seat_limit,
        deadline_at=deadline_iso,
        discount_pct=int(row.get("discount_pct") or 0),
        coupon_code=str(row.get("coupon_code") or ""),
        active=bool(row.get("active")),
        paused=bool(row.get("paused_at")),
        paused_at=_isoformat(row.get("paused_at")),
        paused_by=str(row.get("paused_by")) if row.get("paused_by") else None,
        paused_reason=row.get("paused_reason"),
        seats_taken=seats_taken,
        seats_remaining=max(0, seat_limit - seats_taken),
        completion_pct=completion_pct,
    )


@router.get("/leads", response_model=FoundingLeadsListResponse)
async def list_founding_leads(
    _admin=Depends(require_admin),
    limit: int = 100,
    status: str | None = None,
) -> Any:
    """List founding leads ordered by creation desc.

    Optional ``status`` filter restricts to one of the checkout_status enum
    values (pending|completed|abandoned|failed|cap_violated).
    """
    sb = get_supabase()
    capped_limit = max(1, min(limit, 500))

    def _sync_query():
        query = (
            sb.table("founding_leads")
            .select(
                "id, email, nome, cnpj, razao_social, checkout_status, created_at, "
                "completed_at, stripe_customer_id"
            )
            .order("created_at", desc=True)
            .limit(capped_limit)
        )
        if status:
            query = query.eq("checkout_status", status)
        return query.execute()

    try:
        res = await _run_with_budget(
            asyncio.to_thread(_sync_query),
            budget=5.0,
            phase="route",
            source="admin_founding.list_founding_leads",
        )
    except asyncio.TimeoutError:
        logger.warning("admin_founding list_founding_leads exceeded 5.0s budget")
        raise HTTPException(status_code=503, detail="founding leads query timed out")
    except Exception as e:
        logger.error("admin_founding list_founding_leads DB query failed: %s", e)
        raise HTTPException(status_code=500, detail="founding leads query failed")
    rows = res.data or []

    leads = [
        FoundingLeadEntry(
            id=str(r.get("id") or ""),
            email=str(r.get("email") or ""),
            nome=str(r.get("nome") or ""),
            cnpj=str(r.get("cnpj") or ""),
            razao_social=r.get("razao_social"),
            checkout_status=str(r.get("checkout_status") or "pending"),
            created_at=_isoformat(r.get("created_at")) or "",
            completed_at=_isoformat(r.get("completed_at")),
            stripe_customer_id=r.get("stripe_customer_id"),
        )
        for r in rows
    ]

    completed = sum(1 for entry in leads if entry.checkout_status == "completed")
    pending = sum(1 for entry in leads if entry.checkout_status == "pending")

    return FoundingLeadsListResponse(
        count=len(leads),
        completed_count=completed,
        pending_count=pending,
        leads=leads,
    )


@router.post("/pause", response_model=FoundingPolicyMutationResponse)
async def pause_founding(
    payload: FoundingPauseRequest | None = None,
    admin: dict = Depends(require_admin),
) -> Any:
    """Soft-pause founding checkouts. Idempotent."""
    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()
    reason = (payload.reason if payload else None) or None
    admin_id = str(admin.get("id") or "") or None

    update = {
        "paused_at": now_iso,
        "paused_by": admin_id,
        "paused_reason": reason,
    }

    def _sync_query():
        return sb.table("founding_policy").update(update).eq("id", 1).execute()

    try:
        await _run_with_budget(
            asyncio.to_thread(_sync_query),
            budget=3.0,
            phase="route",
            source="admin_founding.pause_founding",
        )
    except asyncio.TimeoutError:
        logger.warning("admin_founding pause_founding exceeded 3.0s budget")
        raise HTTPException(status_code=503, detail="founding pause timed out")
    except Exception as e:
        logger.error("admin_founding pause_founding DB update failed: %s", e)
        raise HTTPException(status_code=500, detail="founding pause failed")

    logger.info(f"founding admin: paused by admin_id={admin_id} reason={reason!r}")

    return FoundingPolicyMutationResponse(
        ok=True,
        paused=True,
        paused_at=now_iso,
        paused_reason=reason,
    )


@router.post("/resume", response_model=FoundingPolicyMutationResponse)
async def resume_founding(admin: dict = Depends(require_admin)) -> Any:
    """Resume founding checkouts (clear paused_at + paused_by + paused_reason)."""
    sb = get_supabase()
    update = {
        "paused_at": None,
        "paused_by": None,
        "paused_reason": None,
    }

    def _sync_query():
        return sb.table("founding_policy").update(update).eq("id", 1).execute()

    try:
        await _run_with_budget(
            asyncio.to_thread(_sync_query),
            budget=3.0,
            phase="route",
            source="admin_founding.resume_founding",
        )
    except asyncio.TimeoutError:
        logger.warning("admin_founding resume_founding exceeded 3.0s budget")
        raise HTTPException(status_code=503, detail="founding resume timed out")
    except Exception as e:
        logger.error("admin_founding resume_founding DB update failed: %s", e)
        raise HTTPException(status_code=500, detail="founding resume failed")

    logger.info(f"founding admin: resumed by admin_id={admin.get('id')}")

    return FoundingPolicyMutationResponse(
        ok=True,
        paused=False,
        paused_at=None,
        paused_reason=None,
    )
