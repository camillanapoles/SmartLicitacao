"""S14 + STORY-SEO-005: SEO metrics API for admin dashboard."""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from datetime import date, timedelta

from pipeline.budget import _run_with_budget
from utils.postgrest_paginate import paginate_full

from auth import require_auth
from admin import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(tags=["seo_admin"])


# ---------------------------------------------------------------------
# Legacy S14: aggregated seo_metrics daily rollup (kept for /admin/seo)
# ---------------------------------------------------------------------
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
    """Return SEO metrics for the last N days (legacy S14 daily rollup). Admin-only."""
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


# ---------------------------------------------------------------------
# STORY-SEO-005: Google Search Console raw query/page performance
# Populated by backend/jobs/cron/gsc_sync.py weekly.
# ---------------------------------------------------------------------
class GSCQueryRow(BaseModel):
    query: str
    impressions: int
    clicks: int
    ctr: float
    position: float


class GSCPageRow(BaseModel):
    page: str
    impressions: int
    clicks: int
    ctr: float
    position: float


class GSCLowCTROpportunity(BaseModel):
    page: str
    impressions: int
    clicks: int
    ctr: float


class GSCSummaryResponse(BaseModel):
    top_queries: list[GSCQueryRow]
    top_pages_ctr: list[GSCPageRow]
    low_ctr_opportunities: list[GSCLowCTROpportunity]
    last_sync_at: Optional[str] = None
    days: int
    enabled: bool


def _fallback_gsc_summary(days: int, reason: str) -> GSCSummaryResponse:
    logger.info("gsc_summary: fallback empty response — reason=%s", reason)
    return GSCSummaryResponse(
        top_queries=[],
        top_pages_ctr=[],
        low_ctr_opportunities=[],
        last_sync_at=None,
        days=days,
        enabled=False,
    )


@router.get("/admin/seo/summary", response_model=GSCSummaryResponse)
async def get_gsc_summary(
    days: int = Query(default=30, ge=7, le=90),
    user=Depends(require_auth),
    _admin=Depends(require_admin),
):
    """Return aggregated GSC analytics from gsc_metrics cache. Admin-only.

    STORY-SEO-005 AC4. Populated weekly by backend/jobs/cron/gsc_sync.py.
    """
    try:
        from supabase_client import get_supabase
    except Exception as exc:
        logger.error("gsc_summary: supabase_client import failed: %s", exc)
        return _fallback_gsc_summary(days, "supabase_import_failed")

    supabase = get_supabase()
    if supabase is None:
        return _fallback_gsc_summary(days, "supabase_unavailable")

    def _sync_gsc_summary() -> GSCSummaryResponse:
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        try:
            probe = (
                supabase.table("gsc_metrics")
                .select("id", count="exact")
                .limit(1)
                .execute()
            )
            total = getattr(probe, "count", None)
            if not total:
                return _fallback_gsc_summary(days, "no_rows")
        except Exception as exc:
            logger.warning("gsc_summary: probe failed — %s", exc)
            return _fallback_gsc_summary(days, "probe_failed")

        top_queries: list[GSCQueryRow] = []
        top_pages: list[GSCPageRow] = []
        low_ctr: list[GSCLowCTROpportunity] = []
        last_sync_at: Optional[str] = None

        try:
            q_resp = (
                supabase.table("gsc_metrics")
                .select("query,impressions,clicks,ctr,position")
                .gte("date", cutoff)
                .order("impressions", desc=True)
                .limit(500)
                .execute()
            )
            agg: dict[str, dict] = {}
            for row in (q_resp.data or []):
                q = (row.get("query") or "").strip()
                if not q:
                    continue
                b = agg.setdefault(q, {"impressions": 0, "clicks": 0, "position_w": 0.0})
                b["impressions"] += int(row.get("impressions", 0))
                b["clicks"] += int(row.get("clicks", 0))
                b["position_w"] += float(row.get("position", 0.0)) * int(row.get("impressions", 0))

            top_list = sorted(agg.items(), key=lambda kv: kv[1]["impressions"], reverse=True)[:50]
            for q, v in top_list:
                imp = v["impressions"]
                clk = v["clicks"]
                ctr = (clk / imp) if imp > 0 else 0.0
                pos = (v["position_w"] / imp) if imp > 0 else 0.0
                top_queries.append(
                    GSCQueryRow(
                        query=q,
                        impressions=imp,
                        clicks=clk,
                        ctr=round(ctr, 5),
                        position=round(pos, 2),
                    )
                )
        except Exception as exc:
            logger.warning("gsc_summary: top_queries query failed — %s", exc)

        try:
            # DATA-CAP-001: paginate via .range() — over a 90d window the
            # gsc_metrics page-level rollup easily exceeds 1000 rows; the
            # previous .limit(5000) was silently capped at 1000 by PostgREST,
            # under-counting impressions/clicks per page in the admin panel.
            p_builder = (
                supabase.table("gsc_metrics")
                .select("page,impressions,clicks,ctr,position")
                .gte("date", cutoff)
            )
            p_rows = paginate_full(
                p_builder,
                batch_size=1000,
                max_total=10_000,
                route="seo_admin.gsc_summary_pages",
                entity_type="gsc_metrics",
            )
            pg_agg: dict[str, dict] = {}
            for row in (p_rows or []):
                p = (row.get("page") or "").strip()
                if not p:
                    continue
                b = pg_agg.setdefault(p, {"impressions": 0, "clicks": 0, "position_w": 0.0})
                b["impressions"] += int(row.get("impressions", 0))
                b["clicks"] += int(row.get("clicks", 0))
                b["position_w"] += float(row.get("position", 0.0)) * int(row.get("impressions", 0))

            pages_with_traffic = [
                (p, v) for p, v in pg_agg.items() if v["impressions"] >= 10
            ]
            by_ctr = sorted(
                pages_with_traffic,
                key=lambda kv: (kv[1]["clicks"] / kv[1]["impressions"]) if kv[1]["impressions"] else 0,
                reverse=True,
            )[:50]
            for p, v in by_ctr:
                imp = v["impressions"]
                clk = v["clicks"]
                ctr = (clk / imp) if imp else 0.0
                pos = (v["position_w"] / imp) if imp else 0.0
                top_pages.append(
                    GSCPageRow(
                        page=p,
                        impressions=imp,
                        clicks=clk,
                        ctr=round(ctr, 5),
                        position=round(pos, 2),
                    )
                )

            low_pool = [
                (p, v) for p, v in pg_agg.items() if v["impressions"] >= 100
            ]
            low_pool_scored = [
                (p, v, (v["clicks"] / v["impressions"]) if v["impressions"] else 0)
                for p, v in low_pool
            ]
            low_ctr_sorted = sorted(
                [x for x in low_pool_scored if x[2] < 0.01],
                key=lambda x: x[1]["impressions"],
                reverse=True,
            )[:50]
            for p, v, ctr in low_ctr_sorted:
                low_ctr.append(
                    GSCLowCTROpportunity(
                        page=p,
                        impressions=v["impressions"],
                        clicks=v["clicks"],
                        ctr=round(ctr, 5),
                    )
                )
        except Exception as exc:
            logger.warning("gsc_summary: top_pages query failed — %s", exc)

        try:
            sync_resp = (
                supabase.table("gsc_metrics")
                .select("fetched_at")
                .order("fetched_at", desc=True)
                .limit(1)
                .execute()
            )
            if sync_resp.data:
                last_sync_at = sync_resp.data[0].get("fetched_at")
        except Exception:  # last_sync_at optional — proceed with None if DB unavailable
            pass

        return GSCSummaryResponse(
            top_queries=top_queries,
            top_pages_ctr=top_pages,
            low_ctr_opportunities=low_ctr,
            last_sync_at=last_sync_at,
            days=days,
            enabled=True,
        )

    return await _run_with_budget(
        asyncio.to_thread(_sync_gsc_summary),
        budget=10.0,
        phase="route",
        source="seo_admin.get_gsc_summary",
    )


# ---------------------------------------------------------------------------
# On-demand ISR revalidation — #1037
# ---------------------------------------------------------------------------


class RevalidateSEORequest(BaseModel):
    paths: list[str]


class RevalidateSEOResponse(BaseModel):
    status: str
    paths: list[str]


@router.post("/admin/revalidate-seo", response_model=RevalidateSEOResponse)
async def admin_revalidate_seo(
    body: RevalidateSEORequest,
    user=Depends(require_auth),
    _admin=Depends(require_admin),
):
    """Manually trigger ISR revalidation for the given frontend paths.

    Calls the Next.js ``POST /api/revalidate`` endpoint (secret-gated).
    Fire-and-forget — the HTTP call is made but result is not awaited for
    user-facing errors.  Any failure is logged as a warning.

    Requires admin role.  Raises HTTP 400 if ``paths`` is empty.
    """
    if not body.paths:
        from fastapi import HTTPException as _HTTPException

        raise _HTTPException(status_code=400, detail="paths must not be empty")

    from utils.revalidate_client import revalidate_paths

    await revalidate_paths(body.paths)
    return RevalidateSEOResponse(status="ok", paths=body.paths)
