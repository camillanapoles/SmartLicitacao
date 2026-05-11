"""UX-303 AC7: Cache health check endpoint.
STORY-316 AC3: Public status endpoint.

GET /v1/health/cache — Returns status of each cache level with latency.
GET /v1/health — System health (internal, requires admin for details).
GET /v1/status — Public status page data (no auth).
GET /v1/status/incidents — Recent incidents (no auth).
GET /v1/status/uptime-history — Daily uptime for chart (no auth).
"""

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from schemas.health import MvCheckResult, SitemapHealthResponse
from schemas.parity import (
    BackgroundTasksHealthResponse,
    CacheHealthResponse,
    IncidentsResponse,
    PublicStatusResponse,
    SourcesHealthMapResponse,
    SystemHealthResponse,
    UptimeHistoryResponse,
)
from supabase_client import get_supabase, sb_execute

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=SystemHealthResponse)
async def system_health():
    """GTM-STAB-008 AC3: Comprehensive system health endpoint (AC4: internal, detailed).

    Returns component-level statuses (Redis, Supabase, ARQ Worker, PNCP)
    and overall health classification (healthy / degraded / unhealthy).
    """
    from health import get_system_health
    return await get_system_health()


@router.get("/status", response_model=PublicStatusResponse)
async def public_status():
    """STORY-316 AC3: Public status endpoint (no auth required).

    Returns per-source status, component health, uptime percentages,
    and last incident timestamp.
    """
    from health import get_public_status
    return await get_public_status()


@router.get("/status/incidents", response_model=IncidentsResponse)
async def recent_incidents():
    """STORY-316 AC13: Recent incidents for status page."""
    from health import get_recent_incidents
    incidents = await get_recent_incidents(days=30)
    return {"incidents": incidents}


@router.get("/status/uptime-history", response_model=UptimeHistoryResponse)
async def uptime_history():
    """STORY-316 AC12: Daily uptime data for status page chart."""
    from health import get_uptime_history
    history = await get_uptime_history(days=90)
    return {"history": history}


@router.get("/health/tasks", response_model=BackgroundTasksHealthResponse)
async def background_tasks_health():
    """DEBT-014 SYS-006: Background task health via TaskRegistry."""
    from task_registry import task_registry
    return task_registry.get_health()


@router.get("/health/sources", response_model=SourcesHealthMapResponse)
async def sources_health():
    """UX-428 AC5: Health status for all configured procurement sources.

    Returns enabled/disabled state and availability for each source.
    Read-only — no side effects.
    """
    from source_config.sources import source_health_registry, get_source_config
    cfg = get_source_config()
    result: dict = {}
    for src_config in [
        cfg.pncp,
        cfg.portal,
        cfg.licitar,
        cfg.compras_gov,
        cfg.portal_transparencia,
        cfg.bll,
        cfg.bnc,
        cfg.querido_diario,
    ]:
        code = src_config.code.value
        status = source_health_registry.get_status(code)
        result[code] = {
            "enabled": src_config.enabled,
            "status": status,
            "available": src_config.enabled and source_health_registry.is_available(code),
        }
    return {"sources": result}


@router.get("/health/cache", response_model=CacheHealthResponse)
async def cache_health():
    """AC7: Health check for all cache levels.

    Returns status of Supabase, Redis/InMemory, and Local file caches
    with latency measurements and error details.
    B-03 AC9: Includes degraded_keys_count and avg_fail_streak from health metadata.
    Note: warmup_coverage removed 2026-04-18 (STORY-CIG-BE-cache-warming-deprecate).
    """
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "supabase": await _check_supabase_cache(),
        "redis": _check_redis_cache(),
        "local": _check_local_cache(),
        "degradation": await _check_cache_degradation(),
    }

    # Determine overall status
    statuses = [result["supabase"]["status"], result["redis"]["status"], result["local"]["status"]]
    if all(s == "healthy" for s in statuses):
        result["overall"] = "healthy"
    elif all(s == "down" for s in statuses):
        result["overall"] = "down"
    else:
        result["overall"] = "degraded"

    return result


async def _check_supabase_cache() -> dict:
    """Probe Supabase search_results_cache table."""
    start = time.monotonic()
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()

        # Light probe: count recent entries
        response = await sb_execute(
            sb.table("search_results_cache")
            .select("id", count="exact")
            .limit(1)
        )

        latency_ms = round((time.monotonic() - start) * 1000)
        return {
            "status": "healthy",
            "latency_ms": latency_ms,
            "total_entries": response.count if hasattr(response, "count") and response.count is not None else len(response.data),
            "last_error": None,
        }
    except Exception as e:
        latency_ms = round((time.monotonic() - start) * 1000)
        logger.warning(f"Supabase cache health check failed: {e}")
        return {
            "status": "down",
            "latency_ms": latency_ms,
            "total_entries": 0,
            "last_error": str(e)[:200],
        }


def _check_redis_cache() -> dict:
    """Probe Redis/InMemory cache.

    STORY-332 AC3: Includes redis_status ("connected" | "fallback")
    and fallback_duration_seconds.
    """
    start = time.monotonic()
    try:
        from redis_pool import (
            get_fallback_cache,
            get_redis_status,
            get_fallback_duration_seconds,
            _emit_fallback_warning_if_needed,
            _update_redis_metrics,
        )
        cache = get_fallback_cache()

        alive = cache.ping()
        latency_ms = round((time.monotonic() - start) * 1000)
        entries = len(cache)
        redis_status = get_redis_status()

        # STORY-332 AC1+AC2: Update metrics on each health check
        _update_redis_metrics(available=(redis_status == "connected"))
        # STORY-332 AC5: Emit periodic warning if in fallback
        _emit_fallback_warning_if_needed()

        result = {
            "status": "healthy" if alive else "down",
            "latency_ms": latency_ms,
            "entries": entries,
            "last_error": None,
            "redis_status": redis_status,
        }
        if redis_status == "fallback":
            result["fallback_duration_seconds"] = round(
                get_fallback_duration_seconds(), 1
            )
        return result
    except Exception as e:
        latency_ms = round((time.monotonic() - start) * 1000)
        return {
            "status": "down",
            "latency_ms": latency_ms,
            "entries": 0,
            "last_error": str(e)[:200],
            "redis_status": "fallback",
        }


def _check_local_cache() -> dict:
    """Probe local file cache directory."""
    start = time.monotonic()
    try:
        from cache.local_file import get_local_cache_stats
        stats = get_local_cache_stats()
        latency_ms = round((time.monotonic() - start) * 1000)

        return {
            "status": "healthy",
            "latency_ms": latency_ms,
            "files_count": stats["files_count"],
            "total_size_mb": stats["total_size_mb"],
            "last_error": None,
        }
    except Exception as e:
        latency_ms = round((time.monotonic() - start) * 1000)
        return {
            "status": "down",
            "latency_ms": latency_ms,
            "files_count": 0,
            "total_size_mb": 0.0,
            "last_error": str(e)[:200],
        }


async def _check_cache_degradation() -> dict:
    """B-03 AC9: Aggregate fail_streak and degradation metrics from Supabase.
    B-02 AC10: Includes priority_distribution {hot, warm, cold}.
    """
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()

        # Count keys where degraded_until > now()
        now_iso = datetime.now(timezone.utc).isoformat()
        degraded_resp = await sb_execute(
            sb.table("search_results_cache")
            .select("id", count="exact")
            .gt("degraded_until", now_iso)
            .limit(0)
        )
        degraded_count = degraded_resp.count if hasattr(degraded_resp, "count") and degraded_resp.count is not None else 0

        # Aggregate fail_streak stats (only for keys with fail_streak > 0)
        streak_resp = await sb_execute(
            sb.table("search_results_cache")
            .select("fail_streak")
            .gt("fail_streak", 0)
        )
        streaks = [row.get("fail_streak", 0) for row in (streak_resp.data or [])]
        avg_streak = round(sum(streaks) / len(streaks), 1) if streaks else 0.0

        # B-02 AC10: Priority distribution
        priority_resp = await sb_execute(
            sb.table("search_results_cache")
            .select("priority")
        )
        priority_counts = {"hot": 0, "warm": 0, "cold": 0}
        for row in (priority_resp.data or []):
            p = row.get("priority", "cold")
            if p in priority_counts:
                priority_counts[p] += 1
            else:
                priority_counts["cold"] += 1

        return {
            "degraded_keys_count": degraded_count,
            "avg_fail_streak": avg_streak,
            "keys_with_failures": len(streaks),
            "priority_distribution": priority_counts,
        }
    except Exception as e:
        logger.warning(f"Cache degradation check failed: {e}")
        return {
            "degraded_keys_count": 0,
            "avg_fail_streak": 0.0,
            "keys_with_failures": 0,
            "priority_distribution": {"hot": 0, "warm": 0, "cold": 0},
            "error": str(e)[:200],
        }


_SITEMAP_MVS = [
    "mv_sitemap_cnpjs",
    "mv_sitemap_orgaos",
    "mv_sitemap_fornecedores",
    "mv_sitemap_municipios",
]


@router.get("/health/sitemap", response_model=SitemapHealthResponse)
async def sitemap_health():
    """SEO-SITEMAP-TELEMETRY-001: Health check for all sitemap materialized views.

    Returns per-MV status (ok/empty/error) and overall status (ok/degraded).
    Used by Sentry monitors and Railway probes to detect empty sitemap
    responses before they reach GSC.
    """
    sb = get_supabase()

    checks: dict = {}
    for mv_name in _SITEMAP_MVS:
        try:
            resp = await sb_execute(
                sb.table(mv_name).select("*", count="exact").limit(0)
            )
            mv_count = resp.count if hasattr(resp, 'count') and resp.count is not None else len(resp.data or [])
            checks[mv_name] = {
                "status": "ok" if mv_count and mv_count > 0 else "empty",
                "count": mv_count,
            }
        except Exception as e:
            error_msg = str(e)[:200]
            checks[mv_name] = {
                "status": "error",
                "count": 0,
                "error": error_msg,
            }

    all_ok = all(v["status"] == "ok" for v in checks.values())
    return JSONResponse(
        content={
            "status": "ok" if all_ok else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
        },
        status_code=200 if all_ok else 503,
    )
