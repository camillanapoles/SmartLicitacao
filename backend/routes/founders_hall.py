"""Issue #1008 (COPY-HALL-009): public Hall of Founders + LGPD opt-in toggle.

Endpoints
---------

- ``GET  /api/founders/hall``           — public listing of founders that
                                          opted in via the consent flag.
                                          Anonymous, ISR-friendly (s-maxage).
- ``POST /api/founders/hall/consent``   — authenticated toggle for
                                          ``profiles.founder_public_listing_consent``.
                                          Accepts ``{consent: bool, display_name?, logo_url?}``
                                          so the user can opt in OR opt out.

Design notes
------------
- The Hall page (``/fundadores/hall``) is a server component using ISR
  ``revalidate=300`` — the public ``s-maxage=300`` keeps the CDN-rendered
  HTML aligned with the data freshness window.
- LGPD: default consent is FALSE. Opt-out is honored within 60s (cache
  invalidated on toggle, ISR window 300s).
- Audit log: every toggle writes ``lgpd.consent_change`` via
  ``audit_logger.log()`` so we have a privacy-safe, hashed trail.
- Forward-compat: PR #1014 (``routes/founders.py``) already queries the
  same column under a try/except. The two routers can ship in either order.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from auth import require_auth
from audit import audit_logger
from pipeline.budget import _run_with_budget
from rate_limiter import require_rate_limit
from supabase_client import get_supabase


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/founders/hall", tags=["founders"])


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CACHE_TTL_SECONDS = 60
CACHE_KEY = "founders:hall:listing:v1"
HALL_LIST_HARD_CAP = 100  # Defensive cap; founders policy cap is 50.
DISPLAY_NAME_MAX = 120
LOGO_URL_MAX = 500


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FounderHallEntry(BaseModel):
    """Public listing entry. Only populated when consent=TRUE."""

    display_name: str = Field(..., description="Razao social or chosen display name.")
    uf: Optional[str] = Field(default=None, description="State code (2 letters).")
    setor: Optional[str] = Field(
        default=None,
        description="Sector / category derived from CNAE (best-effort).",
    )
    logo_url: Optional[str] = Field(default=None, description="Optional logo URL.")
    founder_since: Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp of when the user became a founder.",
    )


class FoundersHallResponse(BaseModel):
    """Response shape for ``GET /api/founders/hall``."""

    founders: list[FounderHallEntry] = Field(default_factory=list)
    count: int = Field(default=0, description="Number of opt-in founders.")
    fallback: bool = Field(
        default=False,
        description="TRUE when DB unavailable; founders=[] returned conservatively.",
    )


class FounderConsentRequest(BaseModel):
    """Body for ``POST /api/founders/hall/consent`` toggle."""

    consent: bool = Field(
        ...,
        description="TRUE to opt in to public listing, FALSE to opt out.",
    )
    display_name: Optional[str] = Field(
        default=None,
        max_length=DISPLAY_NAME_MAX,
        description="Optional display name override (only persisted on opt-in).",
    )
    logo_url: Optional[str] = Field(
        default=None,
        max_length=LOGO_URL_MAX,
        description="Optional logo URL (only persisted on opt-in).",
    )

    @field_validator("display_name")
    @classmethod
    def _strip_display_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("logo_url")
    @classmethod
    def _validate_logo_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        # Reject obvious garbage; full URL parsing handled downstream.
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("logo_url deve ser uma URL http(s).")
        return v


class FounderConsentResponse(BaseModel):
    """Response for the consent toggle."""

    consent: bool
    display_name: Optional[str] = None
    logo_url: Optional[str] = None
    is_founder: bool = Field(
        default=False,
        description="Reflects profiles.is_founder so the UI can show context.",
    )


# ---------------------------------------------------------------------------
# Cache helpers (Redis, best-effort)
# ---------------------------------------------------------------------------


async def _get_cached_listing() -> dict | None:
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
        logger.debug(f"founders.hall: cache get failed (non-blocking): {exc}")
        return None


async def _set_cached_listing(payload: dict) -> None:
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis is None:
            return
        await redis.set(CACHE_KEY, json.dumps(payload), ex=CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.debug(f"founders.hall: cache set failed (non-blocking): {exc}")


async def _invalidate_listing_cache() -> None:
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis is None:
            return
        await redis.delete(CACHE_KEY)
    except Exception as exc:
        logger.debug(f"founders.hall: cache invalidate failed (non-blocking): {exc}")


# ---------------------------------------------------------------------------
# DB helpers (sync, wrapped via asyncio.to_thread + _run_with_budget)
# ---------------------------------------------------------------------------


def _query_hall_listing(sb: Any) -> list[dict]:
    """Sync DB query for the Hall listing.

    Returns a list of dicts ordered by ``founder_consent_changed_at DESC``
    (most recent opt-in first). Caller wraps in ``_run_with_budget``.
    """
    res = (
        sb.table("profiles")
        .select(
            "razao_social,uf,founder_since,founder_listing_display_name,"
            "founder_company_logo_url,founder_consent_changed_at,setor_principal"
        )
        .eq("is_founder", True)
        .eq("founder_public_listing_consent", True)
        .order("founder_consent_changed_at", desc=True)
        .limit(HALL_LIST_HARD_CAP)
        .execute()
    )
    return list(res.data or [])


def _row_to_entry(row: dict) -> dict:
    """Convert a profile row into the public Hall entry dict."""
    display = (
        (row.get("founder_listing_display_name") or "").strip()
        or (row.get("razao_social") or "").strip()
        or "Empresa Fundadora"
    )
    uf_raw = (row.get("uf") or "").strip().upper()[:2] or None
    setor = (row.get("setor_principal") or "").strip() or None
    logo = (row.get("founder_company_logo_url") or "").strip() or None
    fs_raw = row.get("founder_since")
    founder_since = fs_raw if isinstance(fs_raw, str) else (str(fs_raw) if fs_raw else None)
    return {
        "display_name": display,
        "uf": uf_raw,
        "setor": setor,
        "logo_url": logo,
        "founder_since": founder_since,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=FoundersHallResponse)
async def get_hall_listing(
    request: Request,
    response: Response,
    _rl=Depends(require_rate_limit(60, 60)),
) -> FoundersHallResponse:
    """Public Hall of Founders listing (issue #1008).

    Anonymous endpoint consumed by ``/fundadores/hall`` (ISR revalidate=300s).
    Returns up to 100 founders that opted in via
    ``founder_public_listing_consent=TRUE``.
    """
    # Aligned with the Next.js page ISR window (revalidate=300).
    response.headers["Cache-Control"] = "public, s-maxage=300, stale-while-revalidate=600"

    cached = await _get_cached_listing()
    if cached:
        return FoundersHallResponse(**cached)

    sb = get_supabase()
    try:
        rows = await _run_with_budget(
            asyncio.to_thread(_query_hall_listing, sb),
            budget=2.0,
            phase="route",
            source="founders.hall.listing",
        )
    except Exception as exc:
        logger.warning(f"founders.hall: DB query failed → fallback empty. err={exc}")
        # CRITICAL: do NOT let CDNs cache the fallback. If we serve the
        # fallback under `public, s-maxage=300`, an opt-out user could keep
        # showing up (or vice-versa) for up to 5 minutes after the DB recovers.
        response.headers["Cache-Control"] = "no-store, must-revalidate"
        return FoundersHallResponse(founders=[], count=0, fallback=True)

    entries = [_row_to_entry(r) for r in rows]
    payload = {
        "founders": entries,
        "count": len(entries),
        "fallback": False,
    }
    await _set_cached_listing(payload)
    return FoundersHallResponse(**payload)


def _client_ip(request: Request) -> Optional[str]:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("/consent", response_model=FounderConsentResponse)
async def toggle_consent(
    payload: FounderConsentRequest,
    request: Request,
    user: dict = Depends(require_auth),
    _rl=Depends(require_rate_limit(20, 60)),
) -> FounderConsentResponse:
    """Authenticated opt-in / opt-out toggle (issue #1008).

    Updates ``profiles.founder_public_listing_consent`` for the caller and,
    on opt-in, also persists optional display name and logo URL. Logs an
    LGPD audit event regardless of direction.
    """
    user_id = user.get("id") or user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Sessão inválida.")

    now_iso = datetime.now(tz=timezone.utc).isoformat()

    update_fields: dict[str, Any] = {
        "founder_public_listing_consent": payload.consent,
        "founder_consent_changed_at": now_iso,
    }
    # Use Pydantic's `model_fields_set` to distinguish "field omitted" from
    # "field explicitly set to null". Only fields the client actually sent
    # are written, and explicit nulls are honored so users can clear their
    # display_name / logo_url. Opt-out keeps stored values unless the client
    # passes an override alongside it.
    sent = payload.model_fields_set
    if payload.consent:
        if "display_name" in sent:
            update_fields["founder_listing_display_name"] = payload.display_name
        if "logo_url" in sent:
            update_fields["founder_company_logo_url"] = payload.logo_url
    else:
        # Opt-out: still allow the client to explicitly clear fields, but do
        # not auto-overwrite when omitted.
        if "display_name" in sent and payload.display_name is None:
            update_fields["founder_listing_display_name"] = None
        if "logo_url" in sent and payload.logo_url is None:
            update_fields["founder_company_logo_url"] = None

    sb = get_supabase()

    def _do_update() -> dict:
        res = (
            sb.table("profiles")
            .update(update_fields)
            .eq("id", user_id)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else {}

    try:
        updated = await _run_with_budget(
            asyncio.to_thread(_do_update),
            budget=3.0,
            phase="route",
            source="founders.hall.consent",
        )
    except Exception as exc:
        logger.warning(f"founders.hall.consent: DB update failed: {exc}")
        raise HTTPException(
            status_code=503,
            detail="Não foi possível atualizar a preferência agora. Tente novamente em alguns instantes.",
        )

    # Privacy-safe audit log — actor_id is hashed by the logger.
    try:
        await audit_logger.log(
            event_type="lgpd.consent_change",
            actor_id=str(user_id),
            target_id=str(user_id),
            ip_address=_client_ip(request),
            details={
                "consent_kind": "founder_public_listing",
                "consent": payload.consent,
                "has_display_name": payload.display_name is not None,
                "has_logo_url": payload.logo_url is not None,
            },
        )
    except Exception as exc:
        # Audit failure must never break the user-facing response.
        logger.warning(f"founders.hall.consent: audit log failed: {exc}")

    # Invalidate the public listing cache so opt-out is honored quickly.
    await _invalidate_listing_cache()

    return FounderConsentResponse(
        consent=payload.consent,
        display_name=updated.get("founder_listing_display_name") if updated else payload.display_name,
        logo_url=updated.get("founder_company_logo_url") if updated else payload.logo_url,
        is_founder=bool(updated.get("is_founder")) if updated else False,
    )
