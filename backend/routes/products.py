"""CONV-005b-1: Public digital products listing for checkout.

Endpoint:
    GET /v1/products — lista produtos digitais ativos com dados de preview

Cache: Redis 1h TTL (best-effort, graceful fallback).
Publico (sem auth).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from public_rate_limit import rate_limit_public

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["products"],
    dependencies=[
        Depends(
            rate_limit_public(
                limit_unauth=60,
                limit_auth=600,
                endpoint_name="products",
            )
        )
    ],
)

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS = 60 * 60  # 1h
_CACHE_KEY = "v1:products:listing"
_products_cache: tuple[dict, float] | None = None  # (data, timestamp)


async def _get_cached_products() -> dict | None:
    """Read cached products from Redis (best-effort)."""
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis is None:
            return None
        raw = await redis.get(_CACHE_KEY)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    except Exception as exc:
        logger.debug("products: cache get failed (non-blocking): %s", exc)
        return None


async def _set_cached_products(payload: dict) -> None:
    """Write cached products to Redis (best-effort)."""
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis is None:
            return
        await redis.set(_CACHE_KEY, json.dumps(payload), ex=_CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.debug("products: cache set failed (non-blocking): %s", exc)


async def _invalidate_cache() -> None:
    """Invalidate products cache (used by admin mutations)."""
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis is None:
            return
        await redis.delete(_CACHE_KEY)
    except Exception as exc:
        logger.debug("products: cache invalidate failed (non-blocking): %s", exc)


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class DigitalProductOut(BaseModel):
    """Public representation of a digital product for checkout."""

    sku: str
    name: str
    description: Optional[str] = None
    price_brl: int
    preview_config: dict = {}
    delivery_config: dict = {}


class ProductsResponse(BaseModel):
    products: list[DigitalProductOut]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/products", response_model=ProductsResponse)
async def list_products():
    """List active digital products available for one-time purchase.

    Public (no auth required). Results cached in Redis for 1 hour.
    """
    # Try cache first
    cached = await _get_cached_products()
    if cached is not None:
        return ProductsResponse(**cached)

    # Fallback: query Supabase directly
    try:
        from supabase_client import get_supabase

        sb = get_supabase()
        result = sb.table("digital_products").select(
            "sku, name, description, price_brl, preview_config, delivery_config"
        ).eq("active", True).execute()

        products = result.data if result.data else []
    except Exception as exc:
        logger.warning("products: supabase query failed: %s", exc)
        products = []

    payload = {"products": products}

    # Populate cache (best-effort)
    await _set_cached_products(payload)

    return ProductsResponse(**payload)
