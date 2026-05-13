"""SEO-COVERAGE-MANIFEST-001 (#1039): Daily cron job — rebuild seo_coverage_manifest.

Runs at 06:00 UTC (3am BRT) daily, after the ingestion pipeline has completed.
Aggregates bid counts per entity type/slug from pncp_raw_bids and upserts into
seo_coverage_manifest.

AC3: Registered as start_seo_coverage_manifest_task in scheduler.py (06:00 UTC).
AC4: Monitored by cron_job_health view — Sentry alert triggers if >25h without run.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from supabase_client import sb_execute

logger = logging.getLogger(__name__)

# Run once per day; loop sleeps until 06:00 UTC each day
_JOB_NAME = "seo_coverage_manifest_job"

# Thresholds for coverage_status classification
_FULL_THRESHOLD = 100    # bid_count > 100 → full
_PARTIAL_THRESHOLD = 1   # bid_count >= 1  → partial
# bid_count == 0 → empty (or historical_empty if was previously indexed)


async def run_seo_coverage_manifest() -> dict:
    """Rebuild seo_coverage_manifest from pncp_raw_bids aggregates.

    Queries bid counts per orgao_cnpj (entity_type='cnpj') and municipio
    (entity_type='municipio') and upserts into seo_coverage_manifest.
    Preserves historical_empty status for slugs that previously had data.
    """
    start = datetime.now(timezone.utc)
    logger.info("%s: starting rebuild at %s", _JOB_NAME, start.isoformat())

    try:
        result = await asyncio.to_thread(_sync_rebuild)
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info(
            "%s: done in %.1fs — %d entities upserted",
            _JOB_NAME,
            elapsed,
            result.get("upserted", 0),
        )

        # Record job run in cron_job_health (for AC4 monitoring)
        await asyncio.to_thread(_record_cron_run, result)

        return result

    except Exception as exc:
        logger.error("%s failed: %s", _JOB_NAME, exc, exc_info=True)
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc, tags={"cron_job": _JOB_NAME})
        except Exception:
            pass
        raise


def _sync_rebuild() -> dict:
    """Synchronous rebuild — called via asyncio.to_thread."""
    try:
        from supabase_client import get_supabase

        sb = get_supabase()
        rows_to_upsert: list[dict] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # -----------------------------------------------------------------------
        # 1. Aggregate CNPJ bid counts from pncp_raw_bids
        # -----------------------------------------------------------------------
        cnpj_counts = _aggregate_cnpj_counts(sb)
        for cnpj, count in cnpj_counts.items():
            status = _classify_status(count)
            rows_to_upsert.append({
                "entity_type": "cnpj",
                "slug": cnpj,
                "coverage_status": status,
                "bid_count": count,
                "last_updated": now_iso,
            })

        # -----------------------------------------------------------------------
        # 2. Aggregate fornecedor CNPJ counts from pncp_supplier_contracts
        #    Uses entity_type='fornecedor' to avoid collision with buyer CNPJs.
        # -----------------------------------------------------------------------
        fornecedor_counts = _aggregate_fornecedor_counts(sb)
        for cnpj, count in fornecedor_counts.items():
            status = _classify_status(count)
            rows_to_upsert.append({
                "entity_type": "fornecedor",
                "slug": cnpj,
                "coverage_status": status,
                "bid_count": count,
                "last_updated": now_iso,
            })

        # -----------------------------------------------------------------------
        # 3. Aggregate municipio bid counts (slug = municipio name/slug)
        # -----------------------------------------------------------------------
        municipio_counts = _aggregate_municipio_counts(sb)
        for slug, count in municipio_counts.items():
            status = _classify_status(count)
            rows_to_upsert.append({
                "entity_type": "municipio",
                "slug": slug,
                "coverage_status": status,
                "bid_count": count,
                "last_updated": now_iso,
            })

        # -----------------------------------------------------------------------
        # 3. Preserve historical_empty: if existing status was not empty and new
        #    count is 0, mark as historical_empty instead of empty.
        # -----------------------------------------------------------------------
        rows_to_upsert = _apply_historical_empty(sb, rows_to_upsert)

        # -----------------------------------------------------------------------
        # 4. Upsert in batches of 500 (PostgREST payload limit)
        # -----------------------------------------------------------------------
        upserted = 0
        batch_size = 500
        for i in range(0, len(rows_to_upsert), batch_size):
            batch = rows_to_upsert[i:i + batch_size]
            asyncio.run(
                sb_execute(
                    sb.table("seo_coverage_manifest").upsert(
                        batch,
                        on_conflict="entity_type,slug",
                    ),
                    category="write",
                )
            )
            upserted += len(batch)

        logger.info(
            "%s: upserted %d rows (%d cnpj, %d fornecedor, %d municipio)",
            _JOB_NAME,
            upserted,
            len(cnpj_counts),
            len(fornecedor_counts),
            len(municipio_counts),
        )

        return {
            "status": "ok",
            "upserted": upserted,
            "cnpj_count": len(cnpj_counts),
            "fornecedor_count": len(fornecedor_counts),
            "municipio_count": len(municipio_counts),
        }

    except Exception as exc:
        logger.error("%s _sync_rebuild failed: %s", _JOB_NAME, exc)
        raise


def _classify_status(count: int) -> str:
    """Classify bid count into coverage status tier."""
    if count > _FULL_THRESHOLD:
        return "full"
    if count >= _PARTIAL_THRESHOLD:
        return "partial"
    return "empty"


def _aggregate_cnpj_counts(sb) -> dict[str, int]:
    """Aggregate distinct orgao_cnpj bid counts from pncp_raw_bids.

    Uses paginated SELECT to avoid PostgREST 1000-row cap.
    Returns: {cnpj: bid_count}
    """
    counts: dict[str, int] = {}
    page_size = 1000
    offset = 0

    try:
        # First try the materialized view if available
        resp = asyncio.run(sb_execute(sb.table("mv_sitemap_cnpjs").select("cnpj,bid_count")))
        if resp.data:
            for row in resp.data:
                cnpj = (row.get("cnpj") or "").strip()
                if cnpj:
                    counts[cnpj] = int(row.get("bid_count") or 0)
            logger.info(
                "%s: loaded %d CNPJ counts from mv_sitemap_cnpjs",
                _JOB_NAME, len(counts),
            )
            return counts
    except Exception as mv_exc:
        logger.warning(
            "%s: mv_sitemap_cnpjs unavailable (%s), falling back to raw aggregate",
            _JOB_NAME, mv_exc,
        )

    # Fallback: paginated scan of pncp_raw_bids
    while True:
        resp = asyncio.run(sb_execute(
            sb.table("pncp_raw_bids")
            .select("orgao_cnpj")
            .neq("orgao_cnpj", "")
            .not_.is_("orgao_cnpj", "null")
            .range(offset, offset + page_size - 1)
        ))
        if not resp.data:
            break
        for row in resp.data:
            cnpj = (row.get("orgao_cnpj") or "").strip()
            if cnpj:
                counts[cnpj] = counts.get(cnpj, 0) + 1
        if len(resp.data) < page_size:
            break
        offset += page_size

    return counts


def _aggregate_fornecedor_counts(sb) -> dict[str, int]:
    """Aggregate distinct ni_fornecedor contract counts from pncp_supplier_contracts.

    Returns: {cnpj: contract_count}
    Uses entity_type='fornecedor' (not 'cnpj') to avoid collision with buyer pages.
    """
    counts: dict[str, int] = {}
    page_size = 1000
    offset = 0

    while True:
        resp = asyncio.run(sb_execute(
            sb.table("pncp_supplier_contracts")
            .select("ni_fornecedor")
            .neq("ni_fornecedor", "")
            .not_.is_("ni_fornecedor", "null")
            .range(offset, offset + page_size - 1)
        ))
        if not resp.data:
            break
        for row in resp.data:
            cnpj = (row.get("ni_fornecedor") or "").strip()
            if cnpj:
                counts[cnpj] = counts.get(cnpj, 0) + 1
        if len(resp.data) < page_size:
            break
        offset += page_size

    logger.info(
        "%s: loaded %d fornecedor counts from pncp_supplier_contracts",
        _JOB_NAME, len(counts),
    )
    return counts


def _aggregate_municipio_counts(sb) -> dict[str, int]:
    """Aggregate bid counts per municipio slug from mv_sitemap_municipios (if available)."""
    counts: dict[str, int] = {}

    try:
        resp = asyncio.run(sb_execute(sb.table("mv_sitemap_municipios").select("slug,bid_count")))
        if resp.data:
            for row in resp.data:
                slug = (row.get("slug") or "").strip()
                if slug:
                    counts[slug] = int(row.get("bid_count") or 0)
            logger.info(
                "%s: loaded %d municipio counts from mv_sitemap_municipios",
                _JOB_NAME, len(counts),
            )
    except Exception as exc:
        logger.warning(
            "%s: mv_sitemap_municipios unavailable (%s) — skipping municipio aggregate",
            _JOB_NAME, exc,
        )

    return counts


def _apply_historical_empty(sb, rows: list[dict]) -> list[dict]:
    """For rows with coverage_status='empty', check if the entity previously had
    data in the manifest (was 'full' or 'partial'). If so, mark as 'historical_empty'
    instead of 'empty' so the sitemap gate keeps the URL with reduced priority.

    AC7: /observatorio/raio-x-marco-2026 stays accessible with historical_empty.
    """
    # Build lookup of (entity_type, slug) -> new status for rows being empty
    empty_keys = {
        (r["entity_type"], r["slug"])
        for r in rows
        if r["coverage_status"] == "empty"
    }
    if not empty_keys:
        return rows

    # Fetch existing rows from DB for the empty set
    existing_statuses: dict[tuple[str, str], str] = {}
    try:
        # Query in chunks to avoid URI length limits
        entity_types = list({k[0] for k in empty_keys})
        for etype in entity_types:
            slugs = [k[1] for k in empty_keys if k[0] == etype]
            page_size = 500
            for i in range(0, len(slugs), page_size):
                batch = slugs[i:i + page_size]
                resp = asyncio.run(sb_execute(
                    sb.table("seo_coverage_manifest")
                    .select("entity_type,slug,coverage_status")
                    .eq("entity_type", etype)
                    .in_("slug", batch)
                ))
                for row in (resp.data or []):
                    existing_statuses[(row["entity_type"], row["slug"])] = row["coverage_status"]
    except Exception as exc:
        logger.warning(
            "%s: _apply_historical_empty lookup failed (%s) — skipping promotion",
            _JOB_NAME, exc,
        )
        return rows

    # Promote empty → historical_empty where the existing status was full/partial
    for row in rows:
        key = (row["entity_type"], row["slug"])
        if row["coverage_status"] == "empty":
            existing = existing_statuses.get(key)
            if existing in ("full", "partial", "historical_empty"):
                row["coverage_status"] = "historical_empty"

    return rows


def _record_cron_run(result: dict) -> None:
    """Record this job run in cron_job_health for AC4 monitoring.

    cron_job_health is a view/table read by the health endpoint.
    If the table doesn't exist yet, log a warning and continue.
    """
    try:
        from supabase_client import get_supabase

        sb = get_supabase()
        asyncio.run(sb_execute(
            sb.table("cron_job_health").upsert(
                {
                    "job_name": _JOB_NAME,
                    "last_run_at": datetime.now(timezone.utc).isoformat(),
                    "last_status": result.get("status", "unknown"),
                    "last_result": str(result),
                },
                on_conflict="job_name",
            ),
            category="write",
        ))
    except Exception as exc:
        # cron_job_health may not exist yet — don't fail the job
        logger.warning("%s: cron_job_health upsert failed (non-fatal): %s", _JOB_NAME, exc)


def _seconds_until_next_06_utc() -> float:
    """Return seconds until next 06:00 UTC."""
    now = datetime.now(timezone.utc)
    target = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return (target - now).total_seconds()


async def _seo_coverage_manifest_loop() -> None:
    """Background loop: run at 06:00 UTC daily.

    On first startup, waits until 06:00 UTC to avoid running during boot
    contention with other cron jobs.
    """
    while True:
        sleep_s = _seconds_until_next_06_utc()
        logger.info(
            "%s: sleeping %.0f s until next 06:00 UTC run",
            _JOB_NAME, sleep_s,
        )
        await asyncio.sleep(sleep_s)

        try:
            await run_seo_coverage_manifest()
        except asyncio.CancelledError:
            logger.info("%s: task cancelled", _JOB_NAME)
            break
        except Exception as exc:
            logger.error(
                "%s: unhandled error in loop — will retry next day: %s",
                _JOB_NAME, exc,
            )
            # Safety sleep: avoid tight loop on persistent errors
            await asyncio.sleep(60)


async def start_seo_coverage_manifest_task() -> asyncio.Task:
    """Create and return the background cron task.

    AC3: schedules seo_coverage_manifest_job at 06:00 UTC daily.
    """
    task = asyncio.create_task(
        _seo_coverage_manifest_loop(),
        name=_JOB_NAME,
    )
    logger.info(
        "%s: cron task started — runs daily at 06:00 UTC (3am BRT)",
        _JOB_NAME,
    )
    return task
