"""Datalake API Self-Service (#1372) — API key management + search endpoint.

Endpoints:
    POST   /v1/api-keys           — create a new API key
    GET    /v1/api-keys           — list user's API keys
    DELETE /v1/api-keys/{id}      — revoke an API key
    GET    /v1/api/search         — search via API key auth (X-API-Key header)

Rate limiting: per-key token bucket via Redis.
Feature flag: API_SELF_SERVICE_ENABLED (default false — fail-closed).
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from auth import require_auth
from schemas.datalake_api import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyListItem,
    ApiKeyListResponse,
    ApiKeyRevokeResponse,
    ApiSearchParams,
    ApiSearchResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["datalake-api"])

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_KEY_PREFIX = "sk_"
API_SELF_SERVICE_ENABLED = os.getenv("API_SELF_SERVICE_ENABLED", "false").lower() in (
    "true", "1", "yes",
)
API_SEARCH_RATE_LIMIT = int(os.getenv("API_SEARCH_RATE_LIMIT_PER_MIN", "60"))
API_SEARCH_RATE_WINDOW = int(os.getenv("API_SEARCH_RATE_WINDOW_S", "60"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_api_key() -> tuple[str, str]:
    """Generate an API key and its SHA-256 hash.

    Returns:
        (plaintext_key, sha256_hash) tuple.
        plaintext_key format: sk_<64 hex chars>
    """
    raw = secrets.token_hex(32)  # 64 hex chars
    plaintext = f"{API_KEY_PREFIX}{raw}"
    key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    return plaintext, key_hash


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Feature flag guard
# ---------------------------------------------------------------------------


def _check_feature_flag():
    """Raise 503 if API_SELF_SERVICE_ENABLED is false (fail-closed)."""
    if not API_SELF_SERVICE_ENABLED:
        raise HTTPException(status_code=503, detail="API Self-Service unavailable")


# ---------------------------------------------------------------------------
# API Key auth dependency (for search endpoint)
# ---------------------------------------------------------------------------


async def _get_api_key_user(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> dict:
    """Validate X-API-Key header and return the owning user dict.

    Used as a FastAPI dependency for API-authenticated endpoints.
    Returns {user_id, api_key_id} on success, raises 401 on failure.
    """
    _check_feature_flag()

    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")

    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        result = await sb_execute(
            sb.table("api_keys")
            .select("id, user_id, revoked_at")
            .eq("key_hash", key_hash)
            .limit(1)
        )
    except Exception as exc:
        logger.error("API key lookup failed: %s", exc)
        raise HTTPException(status_code=503, detail="Auth service unavailable")

    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid API key")

    row = result.data[0]
    if row.get("revoked_at"):
        raise HTTPException(status_code=401, detail="API key revoked")

    # Update last_used_at (best-effort, non-blocking)
    try:
        await sb_execute(
            sb.table("api_keys")
            .update({"last_used_at": _now_iso()})
            .eq("id", row["id"]),
            category="write",
        )
    except Exception:
        pass

    return {"user_id": row["user_id"], "api_key_id": row["id"]}


# ---------------------------------------------------------------------------
# Rate limiting for API keys (per-key, Redis token bucket)
# ---------------------------------------------------------------------------


async def _check_api_rate_limit(api_key_id: str) -> None:
    """Check and enforce rate limit for an API key.

    Uses Redis token bucket. Returns None if under limit, raises 429 if exceeded.
    """
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis is None:
            return  # Redis unavailable — allow through (fail-open for rate limit)

        key = f"api:rate_limit:{api_key_id}"
        now = time.monotonic()
        window_start = now - API_SEARCH_RATE_WINDOW

        # Remove old entries and count recent requests
        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        results = await pipe.execute()
        count = results[1] if len(results) > 1 else 0

        if count >= API_SEARCH_RATE_LIMIT:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"X-RateLimit-Remaining": "0", "Retry-After": str(API_SEARCH_RATE_WINDOW)},
            )

        # Record this request
        await redis.zadd(key, {str(now): now})
        await redis.expire(key, API_SEARCH_RATE_WINDOW + 10)
    except HTTPException:
        raise
    except Exception as exc:
        logger.debug("API rate limit check failed (non-blocking): %s", exc)
        # Fail-open: allow request through if Redis is down


# ---------------------------------------------------------------------------
# Endpoints — API Key Management
# ---------------------------------------------------------------------------


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreateRequest = ApiKeyCreateRequest(),
    user: dict = Depends(require_auth),
):
    """Create a new API key. The plaintext key is returned once and not stored."""
    _check_feature_flag()

    plaintext, key_hash = _generate_api_key()
    user_id = user.get("sub") or user.get("id", "")

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        result = await sb_execute(
            sb.table("api_keys")
            .insert({
                "user_id": user_id,
                "key_hash": key_hash,
                "name": body.name or "",
            })
            .select("id, name, created_at")
        )
    except Exception as exc:
        logger.error("Failed to create API key: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create API key")

    row = result.data[0] if result.data else {}
    return ApiKeyCreateResponse(
        id=row.get("id", ""),
        key=plaintext,
        name=row.get("name", body.name or ""),
        created_at=row.get("created_at", _now_iso()),
    )


@router.get("/api-keys", response_model=ApiKeyListResponse)
async def list_api_keys(user: dict = Depends(require_auth)):
    """List all API keys for the authenticated user."""
    user_id = user.get("sub") or user.get("id", "")

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        result = await sb_execute(
            sb.table("api_keys")
            .select("id, name, last_used_at, revoked_at, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
        )
    except Exception as exc:
        logger.error("Failed to list API keys: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to list API keys")

    keys = [
        ApiKeyListItem(
            id=r["id"],
            name=r.get("name", ""),
            last_used_at=r.get("last_used_at"),
            revoked_at=r.get("revoked_at"),
            created_at=r.get("created_at", _now_iso()),
        )
        for r in (result.data or [])
    ]
    return ApiKeyListResponse(keys=keys)


@router.delete("/api-keys/{key_id}", response_model=ApiKeyRevokeResponse)
async def revoke_api_key(key_id: str, user: dict = Depends(require_auth)):
    """Revoke an API key (soft-delete)."""
    _check_feature_flag()
    user_id = user.get("sub") or user.get("id", "")

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        # Verify ownership
        check = await sb_execute(
            sb.table("api_keys")
            .select("id, user_id, revoked_at")
            .eq("id", key_id)
            .limit(1)
        )
        if not check.data:
            raise HTTPException(status_code=404, detail="API key not found")
        row = check.data[0]
        if row.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Not your API key")
        if row.get("revoked_at"):
            return ApiKeyRevokeResponse(
                id=key_id, revoked=True, message="Key was already revoked"
            )

        await sb_execute(
            sb.table("api_keys")
            .update({"revoked_at": _now_iso()})
            .eq("id", key_id)
            .eq("user_id", user_id),
            category="write",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to revoke API key: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to revoke API key")

    return ApiKeyRevokeResponse(
        id=key_id, revoked=True, message="API key revoked successfully"
    )


# ---------------------------------------------------------------------------
# Endpoint — API Search (authenticated via X-API-Key)
# ---------------------------------------------------------------------------


@router.get("/api/search", response_model=ApiSearchResponse)
async def api_search(
    request: Request,
    params: ApiSearchParams = Depends(),
    api_user: dict = Depends(_get_api_key_user),
):
    """Search licitações via API key authentication.

    Same data source as the internal /buscar endpoint, adapted for
    programmatic access. Returns paginated results.
    """
    _check_feature_flag()

    # Rate limit per key
    api_key_id = api_user.get("api_key_id", "")
    await _check_api_rate_limit(api_key_id)

    # Build query params for datalake_query
    uf_list = [params.uf.upper()] if params.uf else None
    modalidade_list = (
        [m.strip() for m in params.modalidade.split(",") if m.strip()]
        if params.modalidade
        else None
    )

    try:
        from datalake_query import query_datalake

        results = await query_datalake(
            ufs=uf_list,
            data_inicial=params.data_inicial,
            data_final=params.data_final,
            modalidades=modalidade_list,
            keywords=params.q.split() if params.q else None,
            valor_min=params.valor_min,
            valor_max=params.valor_max,
            limit=params.tamanho * 2,  # fetch extra for pagination
        )
    except Exception as exc:
        logger.error("API search datalake query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Search query failed")

    # Paginate
    start = (params.pagina - 1) * params.tamanho
    end = start + params.tamanho
    page = results[start:end] if results else []

    return {
        "pagina": params.pagina,
        "tamanho": params.tamanho,
        "total": len(results),
        "resultados": page,
    }
