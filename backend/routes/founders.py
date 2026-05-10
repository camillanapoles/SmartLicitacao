"""Issue #1002 (API-FOUND-003): public availability endpoint for the
Plano Fundadores landing page / cross-sell banners / SEO programmatic footer.

GET /api/founders/availability
------------------------------

Anonymous (no auth). Returns a snapshot of seat counter + countdown that the
landing page, /planos cross-sell banner, programmatic SEO footer, dashboard
trial banner, and day-10 trial emails all consume.

Source of truth:
- Seats taken: count of ``profiles.is_founder = TRUE``.
- Cap: 50 (docs/founders-policy.md).
- Deadline: ``FOUNDERS_DEADLINE`` env var, default 2026-06-30T23:59:59-03:00.
- Public listing opt-in: ``profiles.founder_public_listing_consent = TRUE``
  (LGPD opt-in flag — column is added by a follow-up migration; absent for now,
  so ``ultimasVagasOptIn`` returns an empty list in the meantime).

Resilience:
- Redis-cached for 60s (per AC: <500ms p95).
- DB query wrapped in ``_run_with_budget`` with a 2s budget.
- On any DB/Redis error → fallback payload with ``vagasRestantes=null``,
  ``fallback=true``, conservative message — surfaced via 200 (NOT 503) so
  the landing page can still render the conservative banner without breaking
  the page. (The frontend hook treats ``fallback=true`` as a soft-down state.)
- Cache-Control: public, s-maxage=30 (Googlebot fanout protection).

Rate limit: 60 req/min per IP (anti-scraping).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from pipeline.budget import _run_with_budget
from rate_limiter import require_rate_limit
from supabase_client import get_supabase


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/founders", tags=["founders"])


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FOUNDERS_CAP_TOTAL = 50  # docs/founders-policy.md
DEFAULT_FOUNDERS_DEADLINE = "2026-06-30T23:59:59-03:00"
CACHE_TTL_SECONDS = 60
CACHE_KEY = "founders:availability:v1"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class UltimaVagaOptIn(BaseModel):
    """LGPD-safe public listing entry (only included when consent=TRUE)."""

    empresa: str = Field(..., description="Display name (razao_social or 'empresa').")
    uf: str = Field(..., description="State code, 2 letters.")
    preenchidaEm: str = Field(..., description="ISO-8601 timestamp.")


class FoundersAvailabilityResponse(BaseModel):
    """Response shape for ``GET /api/founders/availability`` (issue #1002).

    On the happy path all numeric fields are populated and ``fallback=false``.
    On DB/Redis failure ``vagasRestantes=null`` + ``fallback=true`` and the
    frontend renders the conservative copy ("Vagas limitadas — encerra 30/06").
    """

    vagasRestantes: int | None = Field(
        default=None,
        description="Seats still available (50 - taken). NULL when fallback=true.",
    )
    vagasTotal: int = Field(default=FOUNDERS_CAP_TOTAL, description="Hard cap (50).")
    vagasPreenchidas: int | None = Field(
        default=None,
        description="Seats already taken (count of is_founder=TRUE profiles).",
    )
    diasRestantes: int | None = Field(
        default=None, description="Whole days until the deadline."
    )
    horasRestantes: int | None = Field(
        default=None, description="Whole hours until the deadline."
    )
    deadline: str = Field(
        default=DEFAULT_FOUNDERS_DEADLINE,
        description="ISO-8601 deadline (FOUNDERS_DEADLINE env var or default).",
    )
    ultimaVagaEm: str | None = Field(
        default=None,
        description="ISO-8601 timestamp of the most recent founder_since.",
    )
    ultimasVagasOptIn: list[UltimaVagaOptIn] = Field(
        default_factory=list,
        description=(
            "Up to 5 most recent founders who explicitly opted in via "
            "founder_public_listing_consent=TRUE (LGPD)."
        ),
    )
    sold_out: bool = Field(
        default=False,
        description="TRUE when vagasPreenchidas >= cap (50).",
    )
    fallback: bool = Field(
        default=False,
        description=(
            "TRUE when DB or Redis is unavailable. Frontend should render the "
            "conservative copy without a number."
        ),
    )
    message: str | None = Field(
        default=None,
        description="Conservative copy returned when fallback=true.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_deadline_iso() -> str:
    """Return the FOUNDERS_DEADLINE env var or the documented default."""
    raw = os.getenv("FOUNDERS_DEADLINE", "").strip()
    return raw or DEFAULT_FOUNDERS_DEADLINE


def _parse_deadline(raw: str) -> datetime | None:
    """Parse ISO-8601 deadline with graceful fallback."""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _compute_remaining(deadline_iso: str) -> tuple[int | None, int | None]:
    """Return (dias, horas) from now until deadline. None if unparseable."""
    deadline = _parse_deadline(deadline_iso)
    if deadline is None:
        return (None, None)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    delta = deadline - datetime.now(tz=timezone.utc)
    if delta.total_seconds() <= 0:
        return (0, 0)
    horas = int(delta.total_seconds() // 3600)
    dias = delta.days
    return (max(0, dias), max(0, horas))


def _query_seats_snapshot(sb: Any) -> dict:
    """Synchronous DB query — count founders + fetch most-recent opt-ins.

    Wrapped via ``asyncio.to_thread`` + ``_run_with_budget`` by the caller.
    Returns a dict consumed by the route. Raises on DB error so the route
    can downgrade to ``fallback=true``.
    """
    # Count seats taken.
    count_res = (
        sb.table("profiles")
        .select("id", count="exact")
        .eq("is_founder", True)
        .execute()
    )
    seats_taken: int = int(getattr(count_res, "count", None) or len(count_res.data or []))

    # Most recent founder_since (any founder, regardless of consent).
    last_res = (
        sb.table("profiles")
        .select("founder_since")
        .eq("is_founder", True)
        .order("founder_since", desc=True)
        .limit(1)
        .execute()
    )
    last_rows = last_res.data or []
    ultima_vaga_em: str | None = None
    if last_rows and last_rows[0].get("founder_since"):
        raw = last_rows[0]["founder_since"]
        ultima_vaga_em = raw if isinstance(raw, str) else str(raw)

    # Opt-in public listing — gracefully handle missing column (404 from
    # PostgREST when founder_public_listing_consent has not been migrated yet).
    opt_in: list[dict] = []
    try:
        opt_res = (
            sb.table("profiles")
            .select("razao_social,uf,founder_since")
            .eq("is_founder", True)
            .eq("founder_public_listing_consent", True)
            .order("founder_since", desc=True)
            .limit(5)
            .execute()
        )
        for row in opt_res.data or []:
            empresa = (row.get("razao_social") or "Empresa Fundadora").strip() or "Empresa Fundadora"
            uf = (row.get("uf") or "").strip().upper()[:2]
            preenchida = row.get("founder_since")
            if preenchida is None:
                continue
            opt_in.append(
                {
                    "empresa": empresa,
                    "uf": uf,
                    "preenchidaEm": preenchida if isinstance(preenchida, str) else str(preenchida),
                }
            )
    except Exception as exc:  # column not present yet — non-blocking
        logger.info(f"founders.availability: opt-in query skipped (likely missing column): {exc}")

    return {
        "seats_taken": seats_taken,
        "ultima_vaga_em": ultima_vaga_em,
        "opt_in": opt_in,
    }


async def _get_cached() -> dict | None:
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis is None:
            return None
        raw = await redis.get(CACHE_KEY)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    except Exception as exc:
        logger.debug(f"founders.availability: cache get failed (non-blocking): {exc}")
        return None


async def _set_cached(payload: dict) -> None:
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis is None:
            return
        await redis.set(CACHE_KEY, json.dumps(payload), ex=CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.debug(f"founders.availability: cache set failed (non-blocking): {exc}")


def _fallback_payload() -> dict:
    """Conservative response when DB/Redis are unavailable."""
    deadline_iso = _get_deadline_iso()
    dias, horas = _compute_remaining(deadline_iso)
    return {
        "vagasRestantes": None,
        "vagasTotal": FOUNDERS_CAP_TOTAL,
        "vagasPreenchidas": None,
        "diasRestantes": dias,
        "horasRestantes": horas,
        "deadline": deadline_iso,
        "ultimaVagaEm": None,
        "ultimasVagasOptIn": [],
        "sold_out": False,
        "fallback": True,
        "message": "Vagas limitadas — encerra 30/06",
    }


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get("/availability", response_model=FoundersAvailabilityResponse)
async def founders_availability(
    request: Request,
    response: Response,
    _rl=Depends(require_rate_limit(60, 60)),
) -> Any:
    """Public seat counter + countdown feed (issue #1002)."""
    response.headers["Cache-Control"] = "public, s-maxage=30"

    # 1) Try Redis cache first.
    cached = await _get_cached()
    if cached:
        # Recompute time-sensitive fields so the timer still ticks even within
        # the 60s cache window.
        deadline_iso = cached.get("deadline") or _get_deadline_iso()
        dias, horas = _compute_remaining(deadline_iso)
        cached["diasRestantes"] = dias
        cached["horasRestantes"] = horas
        return FoundersAvailabilityResponse(**cached)

    # 2) Cache miss — query DB under the time budget.
    deadline_iso = _get_deadline_iso()
    sb = get_supabase()

    try:
        snapshot = await _run_with_budget(
            asyncio.to_thread(_query_seats_snapshot, sb),
            budget=2.0,
            phase="route",
            source="founders.availability",
        )
    except Exception as exc:
        logger.warning(f"founders.availability: DB query failed → fallback. err={exc}")
        return FoundersAvailabilityResponse(**_fallback_payload())

    seats_taken: int = int(snapshot["seats_taken"])
    seats_taken = max(0, seats_taken)
    seats_remaining = max(0, FOUNDERS_CAP_TOTAL - seats_taken)
    sold_out = seats_taken >= FOUNDERS_CAP_TOTAL

    dias, horas = _compute_remaining(deadline_iso)

    payload: dict = {
        "vagasRestantes": 0 if sold_out else seats_remaining,
        "vagasTotal": FOUNDERS_CAP_TOTAL,
        "vagasPreenchidas": seats_taken,
        "diasRestantes": dias,
        "horasRestantes": horas,
        "deadline": deadline_iso,
        "ultimaVagaEm": snapshot.get("ultima_vaga_em"),
        "ultimasVagasOptIn": snapshot.get("opt_in", []),
        "sold_out": sold_out,
        "fallback": False,
        "message": None,
    }

    # 3) Cache the result (best-effort).
    await _set_cached(payload)

    return FoundersAvailabilityResponse(**payload)
