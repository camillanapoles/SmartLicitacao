"""S14: SEO metrics API for admin dashboard."""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from pipeline.budget import _run_with_budget

from auth import require_auth
from admin import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(tags=["seo_admin"])


class SEOMetricRow(BaseModel):
    date: str
    impressions: int
    clicks: int
    ctr: float
    avg_position: float
    pages_indexed: int
    top_queries: list
    top_pages: list


class SEOMetricsResponse(BaseModel):
    metrics: list[SEOMetricRow]
    total: int
    latest_date: Optional[str] = None


@router.get("/admin/seo-metrics", response_model=SEOMetricsResponse)
async def get_seo_metrics(
    days: int = Query(default=90, ge=1, le=365),
    user=Depends(require_auth),
    _admin=Depends(require_admin),
):
    """Return SEO metrics for the last N days. Admin-only."""
    try:
        from supabase_client import get_supabase

        supabase = get_supabase()

        def _sync_query():
            return supabase.table("seo_metrics").select("*").order("date", desc=True).limit(days).execute()

        response = await _run_with_budget(
            asyncio.to_thread(_sync_query),
            budget=5.0,
            phase="route",
            source="seo_admin.get_seo_metrics",
        )
        rows = response.data or []

        return SEOMetricsResponse(
            metrics=[SEOMetricRow(**row) for row in rows],
            total=len(rows),
            latest_date=rows[0]["date"] if rows else None,
        )
    except Exception as exc:
        logger.error("Failed to fetch SEO metrics: %s", exc)
        return SEOMetricsResponse(metrics=[], total=0, latest_date=None)
