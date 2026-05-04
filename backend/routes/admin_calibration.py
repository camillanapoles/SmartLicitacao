"""BIZ-METRIC-001 (AC3, AC4, AC11): admin calibration endpoints.

Surfaces three admin-only endpoints:
    GET   /v1/admin/survey/export-time-saved
        Aggregated histogram + summary statistics over the last
        ``range_days`` (default 90). Powers the
        ``/admin/calibration`` dashboard.

    PATCH /v1/admin/config/{key}
        Mutate one row in ``app_config`` (audit-logged via
        ``app_config.updated_by``). Drops the in-process TTL cache for
        the affected key after a successful update.

    POST  /v1/admin/calibration/recalibrate
        Compute the new ``hours_saved_per_search`` value from the
        survey distribution (IQR outlier removal + median per-bid
        normalisation). When ``apply=true`` writes the result back to
        ``app_config``.

All endpoints are admin-only (``require_admin``). The calibration
algorithm is intentionally duplicated between this endpoint and the
standalone ``scripts/recalibrate_hours_saved.py`` so the two stay in
sync — same input → same output.
"""

from __future__ import annotations

import asyncio
import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from admin import require_admin
from pipeline.budget import _run_with_budget
from supabase_client import get_supabase
from utils.app_config import (
    DEFAULT_HOURS_SAVED_PER_SEARCH,
    get_hours_saved_per_search,
    invalidate_app_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin", "calibration"])


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Minimum sample size required before recalibration is allowed
#: (mirrors story AC8/AC10 — n>=30 with IQR outlier removal).
MIN_SAMPLE_SIZE: int = 30

#: Histogram bucket edges in hours (right-exclusive, last bucket is +inf).
HISTOGRAM_BUCKETS: list[float] = [0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0, 50.0]

#: Allowed config keys for PATCH. Whitelist to avoid arbitrary writes.
ALLOWED_CONFIG_KEYS: set[str] = {"hours_saved_per_search"}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class HistogramBucket(BaseModel):
    range_label: str
    count: int


class SurveyAggregateResponse(BaseModel):
    """GET /v1/admin/survey/export-time-saved response."""

    range_days: int
    sample_size: int
    after_outlier_removal: int
    median_hours: Optional[float] = None
    mean_hours: Optional[float] = None
    iqr_q1: Optional[float] = None
    iqr_q3: Optional[float] = None
    iqr_lower_bound: Optional[float] = None
    iqr_upper_bound: Optional[float] = None
    median_per_bid: Optional[float] = None
    median_bid_count: Optional[float] = None
    histogram: list[HistogramBucket]
    current_constant: float


class AppConfigPatchRequest(BaseModel):
    """PATCH /v1/admin/config/{key} body."""

    value: Any = Field(
        ...,
        description="New JSONB value (scalar/array/object)",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional updated description",
    )

    model_config = ConfigDict(extra="ignore")


class AppConfigRow(BaseModel):
    key: str
    value: Any
    description: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class RecalibrateRequest(BaseModel):
    """POST /v1/admin/calibration/recalibrate body."""

    range_days: int = Field(default=90, ge=1, le=365)
    apply: bool = Field(
        default=False,
        description="When true, writes the new median to app_config.",
    )


class RecalibrateResponse(BaseModel):
    range_days: int
    sample_size: int
    after_outlier_removal: int
    eligible: bool
    reason: Optional[str] = None
    old_value: float
    new_value: Optional[float] = None
    diff_pct: Optional[float] = None
    applied: bool
    median_per_bid: Optional[float] = None
    median_bid_count: Optional[float] = None


# ---------------------------------------------------------------------------
# Pure helpers (also used by scripts/recalibrate_hours_saved.py)
# ---------------------------------------------------------------------------

def _quantile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolation quantile on a pre-sorted list (q in [0,1])."""
    if not sorted_values:
        raise ValueError("Cannot compute quantile of empty list")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = q * (len(sorted_values) - 1)
    lower_idx = int(pos)
    upper_idx = min(lower_idx + 1, len(sorted_values) - 1)
    frac = pos - lower_idx
    return float(sorted_values[lower_idx] + frac * (sorted_values[upper_idx] - sorted_values[lower_idx]))


def filter_outliers_iqr(values: list[float]) -> tuple[list[float], float, float, float, float]:
    """Tukey IQR outlier filter: keep [Q1 - 1.5*IQR, Q3 + 1.5*IQR].

    Returns (filtered_values, q1, q3, lower_bound, upper_bound).
    For samples with <4 points the bounds default to the input min/max
    so no rows are dropped.
    """
    if not values:
        return [], 0.0, 0.0, 0.0, 0.0

    sorted_vals = sorted(values)
    if len(sorted_vals) < 4:
        return list(sorted_vals), sorted_vals[0], sorted_vals[-1], sorted_vals[0], sorted_vals[-1]

    q1 = _quantile(sorted_vals, 0.25)
    q3 = _quantile(sorted_vals, 0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    filtered = [v for v in sorted_vals if lower <= v <= upper]
    return filtered, q1, q3, lower, upper


def compute_calibration(
    survey_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calibration pipeline:
        1. Compute per-row ``hours / max(bid_count, 1)`` per-bid value
           (when bid_count present) and the absolute hours value.
        2. IQR outlier removal on absolute hours.
        3. Median absolute hours = recalibrated single-search constant.
        4. Median per-bid + median bid_count surfaced for documentation.

    Returns a dict with all metrics; never raises.
    """
    abs_hours: list[float] = []
    per_bid: list[float] = []
    bid_counts: list[int] = []

    for row in survey_rows:
        try:
            h = float(row.get("estimated_manual_hours") or 0)
        except (TypeError, ValueError):
            continue
        if h <= 0 or h > 50:
            continue
        abs_hours.append(h)

        bid_count = row.get("bid_count")
        if isinstance(bid_count, (int, float)) and bid_count and bid_count > 0:
            bid_counts.append(int(bid_count))
            per_bid.append(h / float(bid_count))

    sample_size = len(abs_hours)
    filtered, q1, q3, lower, upper = filter_outliers_iqr(abs_hours)
    after = len(filtered)

    median_hours = float(statistics.median(filtered)) if filtered else None
    mean_hours = float(statistics.fmean(filtered)) if filtered else None
    median_per_bid = float(statistics.median(per_bid)) if per_bid else None
    median_bid_count = float(statistics.median(bid_counts)) if bid_counts else None

    return {
        "sample_size": sample_size,
        "after_outlier_removal": after,
        "median_hours": median_hours,
        "mean_hours": mean_hours,
        "iqr_q1": q1 if filtered else None,
        "iqr_q3": q3 if filtered else None,
        "iqr_lower_bound": lower if filtered else None,
        "iqr_upper_bound": upper if filtered else None,
        "median_per_bid": median_per_bid,
        "median_bid_count": median_bid_count,
    }


def build_histogram(values: list[float]) -> list[HistogramBucket]:
    """Bucket *values* into HISTOGRAM_BUCKETS (right-exclusive)."""
    counts = [0] * (len(HISTOGRAM_BUCKETS) + 1)
    edges = [0.0] + HISTOGRAM_BUCKETS
    for v in values:
        placed = False
        for i in range(len(HISTOGRAM_BUCKETS)):
            if v < HISTOGRAM_BUCKETS[i]:
                counts[i] += 1
                placed = True
                break
        if not placed:
            counts[-1] += 1

    out: list[HistogramBucket] = []
    for i, c in enumerate(counts):
        if i == 0:
            label = f"<{HISTOGRAM_BUCKETS[0]}h"
        elif i < len(HISTOGRAM_BUCKETS):
            label = f"{edges[i]}-{HISTOGRAM_BUCKETS[i]}h"
        else:
            label = f">={HISTOGRAM_BUCKETS[-1]}h"
        out.append(HistogramBucket(range_label=label, count=c))
    return out


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _fetch_recent_surveys(range_days: int) -> list[dict[str, Any]]:
    """Fetch surveys submitted in the last *range_days* days via service role.

    Returns an empty list on DB error or budget exceeded (admin endpoint
    never raises 5xx purely because the table is unavailable — operator
    can retry).

    Note on the cutoff: PostgREST does NOT evaluate SQL expressions in
    filter values; passing ``"now() - interval '90 days'"`` would be
    sent as a URL literal and silently match nothing. We compute the
    ISO-8601 cutoff in Python instead.

    Wrapped in ``_run_with_budget`` (RES-BE-001/015) so the sync
    Supabase ``.execute()`` does not block the async event loop and
    the call respects the 5s read budget.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=int(range_days))).isoformat()
    sb = get_supabase()

    def _sync_query():
        return (
            sb.table("export_time_saved_survey")
            .select("estimated_manual_hours, bid_count, submitted_at, export_type")
            .gte("submitted_at", cutoff)
            .order("submitted_at", desc=True)
            .limit(10_000)
            .execute()
        )

    try:
        result = await _run_with_budget(
            asyncio.to_thread(_sync_query),
            budget=5.0,
            phase="route",
            source="admin_calibration.fetch_recent_surveys",
        )
    except asyncio.TimeoutError:
        logger.warning(
            "admin_calibration: survey fetch exceeded 5s budget (range_days=%s)",
            range_days,
        )
        return []
    except Exception as exc:
        logger.warning("admin_calibration: survey fetch failed: %s", exc)
        return []
    return list(getattr(result, "data", None) or [])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/survey/export-time-saved",
    response_model=SurveyAggregateResponse,
)
async def list_export_surveys_aggregate(
    range_days: int = Query(default=90, ge=1, le=365),
    admin: dict = Depends(require_admin),
) -> SurveyAggregateResponse:
    """Aggregated histogram + summary stats for the calibration dashboard."""
    rows = await _fetch_recent_surveys(range_days)
    metrics = compute_calibration(rows)

    abs_hours: list[float] = []
    for r in rows:
        try:
            h = float(r.get("estimated_manual_hours") or 0)
        except (TypeError, ValueError):
            continue
        if 0 < h <= 50:
            abs_hours.append(h)

    histogram = build_histogram(abs_hours)
    current = get_hours_saved_per_search()

    return SurveyAggregateResponse(
        range_days=range_days,
        sample_size=metrics["sample_size"],
        after_outlier_removal=metrics["after_outlier_removal"],
        median_hours=metrics["median_hours"],
        mean_hours=metrics["mean_hours"],
        iqr_q1=metrics["iqr_q1"],
        iqr_q3=metrics["iqr_q3"],
        iqr_lower_bound=metrics["iqr_lower_bound"],
        iqr_upper_bound=metrics["iqr_upper_bound"],
        median_per_bid=metrics["median_per_bid"],
        median_bid_count=metrics["median_bid_count"],
        histogram=histogram,
        current_constant=current,
    )


@router.patch(
    "/config/{key}",
    response_model=AppConfigRow,
)
async def patch_app_config(
    key: str,
    body: AppConfigPatchRequest = Body(...),
    admin: dict = Depends(require_admin),
) -> AppConfigRow:
    """Update one row in ``app_config``. Whitelist enforced.

    On success the in-process TTL cache for *key* is invalidated so
    the new value becomes visible in this worker on the next read
    (other workers see it after their TTL expires).
    """
    if key not in ALLOWED_CONFIG_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"key='{key}' is not in the writable allowlist",
        )

    sb = get_supabase()

    update_payload: dict[str, Any] = {
        "value": body.value,
        "updated_by": admin.get("id"),
    }
    if body.description is not None:
        update_payload["description"] = body.description

    def _sync_patch():
        return (
            sb.table("app_config")
            .update(update_payload)
            .eq("key", key)
            .execute()
        )

    try:
        result = await _run_with_budget(
            asyncio.to_thread(_sync_patch),
            budget=3.0,
            phase="route",
            source="admin_calibration.patch_app_config",
        )
    except asyncio.TimeoutError:
        logger.warning(
            "admin_calibration: app_config PATCH exceeded 3s budget for %s", key,
        )
        raise HTTPException(status_code=503, detail="Database unavailable")
    except Exception as exc:
        logger.warning("admin_calibration: app_config PATCH failed for %s: %s", key, exc)
        raise HTTPException(status_code=503, detail="Database unavailable")

    rows = getattr(result, "data", None) or []
    if not rows:
        raise HTTPException(status_code=404, detail=f"app_config key='{key}' not found")

    invalidate_app_config(key)

    row = rows[0]
    return AppConfigRow(
        key=str(row.get("key", key)),
        value=row.get("value"),
        description=row.get("description"),
        updated_at=str(row["updated_at"]) if row.get("updated_at") is not None else None,
        updated_by=str(row["updated_by"]) if row.get("updated_by") is not None else None,
    )


@router.post(
    "/calibration/recalibrate",
    response_model=RecalibrateResponse,
)
async def recalibrate(
    body: RecalibrateRequest = Body(default_factory=RecalibrateRequest),
    admin: dict = Depends(require_admin),
) -> RecalibrateResponse:
    """Compute new ``hours_saved_per_search`` from survey distribution.

    Eligibility rules (mirrors AC6 + risk R3):
        * After IQR outlier removal there must be >= MIN_SAMPLE_SIZE rows.
        * The new median must be in (0, 50].

    When ``apply=true`` and eligible, persists the new value via
    ``app_config`` and drops the cache.
    """
    rows = await _fetch_recent_surveys(body.range_days)
    metrics = compute_calibration(rows)
    new_value = metrics["median_hours"]
    after = metrics["after_outlier_removal"]
    sample_size = metrics["sample_size"]

    old_value = get_hours_saved_per_search()

    eligible = (
        after >= MIN_SAMPLE_SIZE
        and new_value is not None
        and 0 < new_value <= 50
    )
    reason: Optional[str] = None
    if after < MIN_SAMPLE_SIZE:
        reason = f"insufficient_sample (after_outlier_removal={after}, required={MIN_SAMPLE_SIZE})"
    elif new_value is None:
        reason = "no_valid_responses"
    elif not (0 < new_value <= 50):
        reason = f"out_of_range (new_value={new_value})"

    diff_pct: Optional[float] = None
    if new_value is not None and old_value:
        diff_pct = round((new_value - old_value) / old_value * 100, 2)

    applied = False
    if eligible and body.apply and new_value is not None:
        sb = get_supabase()

        update_payload = {
            "value": new_value,
            "updated_by": admin.get("id"),
            "description": (
                "BIZ-METRIC-001: empirically calibrated via "
                f"scripts/recalibrate_hours_saved.py "
                f"(n={after}, range={body.range_days}d, median={new_value:.2f}h)"
            ),
        }

        def _sync_persist():
            return (
                sb.table("app_config")
                .update(update_payload)
                .eq("key", "hours_saved_per_search")
                .execute()
            )

        try:
            await _run_with_budget(
                asyncio.to_thread(_sync_persist),
                budget=3.0,
                phase="route",
                source="admin_calibration.recalibrate",
            )
            invalidate_app_config("hours_saved_per_search")
            applied = True
        except asyncio.TimeoutError:
            logger.warning(
                "admin_calibration: persist new value exceeded 3s budget",
            )
            raise HTTPException(status_code=503, detail="Database unavailable")
        except Exception as exc:
            logger.warning(
                "admin_calibration: persist new value failed: %s",
                exc,
            )
            raise HTTPException(status_code=503, detail="Database unavailable")

    return RecalibrateResponse(
        range_days=body.range_days,
        sample_size=sample_size,
        after_outlier_removal=after,
        eligible=eligible,
        reason=reason,
        old_value=old_value if old_value is not None else DEFAULT_HOURS_SAVED_PER_SEARCH,
        new_value=new_value,
        diff_pct=diff_pct,
        applied=applied,
        median_per_bid=metrics["median_per_bid"],
        median_bid_count=metrics["median_bid_count"],
    )
