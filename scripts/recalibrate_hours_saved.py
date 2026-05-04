#!/usr/bin/env python3
"""BIZ-METRIC-001 (AC6): empirical re-calibration of ``hours_saved_per_search``.

Reads survey responses from ``export_time_saved_survey``, applies IQR
outlier removal on the absolute hours distribution, computes the median
as the new value, and (optionally) writes the result back to the
``app_config.hours_saved_per_search`` row.

Usage::

    # Dry-run (default): prints the markdown report to stdout, no writes.
    python scripts/recalibrate_hours_saved.py --range-days 90

    # Persist the new median:
    python scripts/recalibrate_hours_saved.py --apply

    # Save the markdown report to docs/reports/
    python scripts/recalibrate_hours_saved.py --output-dir docs/reports

Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in env. The algorithm
matches ``backend/routes/admin_calibration.py::compute_calibration``
1:1 — same input → same output. The admin endpoint and this script
import the helpers from the same module to guarantee consistency.

Eligibility:
    * After IQR filter, sample size must be >= MIN_SAMPLE_SIZE (30).
    * New median must be in (0, 50].

Methodology rationale: ``docs/methodology/hours-saved-calibration.md``
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow ``python scripts/recalibrate_hours_saved.py`` to import backend modules.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

# noqa: E402 - sys.path manipulation must precede backend imports.
from routes.admin_calibration import (  # noqa: E402
    HISTOGRAM_BUCKETS,
    MIN_SAMPLE_SIZE,
    build_histogram,
    compute_calibration,
)
from utils.app_config import (  # noqa: E402
    DEFAULT_HOURS_SAVED_PER_SEARCH,
    get_hours_saved_per_search,
    invalidate_app_config,
)


def _fetch_rows(range_days: int) -> list[dict[str, Any]]:
    from datetime import timedelta

    from supabase_client import get_supabase

    # PostgREST sends filter values as URL literals — cannot use SQL
    # ``now() - interval '...'`` here. Compute the ISO cutoff in Python.
    cutoff = (datetime.now(timezone.utc) - timedelta(days=int(range_days))).isoformat()

    sb = get_supabase()
    result = (
        sb.table("export_time_saved_survey")
        .select("estimated_manual_hours, bid_count, submitted_at, export_type")
        .gte("submitted_at", cutoff)
        .order("submitted_at", desc=True)
        .limit(50_000)
        .execute()
    )
    return list(getattr(result, "data", None) or [])


def _persist_value(new_value: float, *, sample_size: int, range_days: int) -> None:
    from supabase_client import get_supabase

    sb = get_supabase()
    description = (
        "BIZ-METRIC-001: empirically calibrated via "
        "scripts/recalibrate_hours_saved.py "
        f"(n={sample_size}, range={range_days}d, median={new_value:.2f}h)"
    )
    sb.table("app_config").update(
        {
            "value": new_value,
            "description": description,
        }
    ).eq("key", "hours_saved_per_search").execute()
    invalidate_app_config("hours_saved_per_search")


def _render_markdown_report(
    *,
    range_days: int,
    metrics: dict[str, Any],
    histogram: list[Any],
    old_value: float,
    new_value: float | None,
    eligible: bool,
    reason: str | None,
    applied: bool,
) -> str:
    lines: list[str] = []
    lines.append(f"# hours_saved_per_search calibration — {datetime.now(timezone.utc).date()}")
    lines.append("")
    lines.append(f"- Window: last **{range_days} days**")
    lines.append(f"- Sample size (raw): **{metrics['sample_size']}**")
    lines.append(f"- After IQR outlier removal: **{metrics['after_outlier_removal']}**")
    lines.append(f"- Required minimum: {MIN_SAMPLE_SIZE}")
    lines.append("")
    lines.append("## Summary statistics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Median (new value candidate) | {metrics['median_hours']!r} h |")
    lines.append(f"| Mean | {metrics['mean_hours']!r} h |")
    lines.append(f"| IQR Q1 | {metrics['iqr_q1']!r} h |")
    lines.append(f"| IQR Q3 | {metrics['iqr_q3']!r} h |")
    lines.append(f"| IQR lower bound | {metrics['iqr_lower_bound']!r} h |")
    lines.append(f"| IQR upper bound | {metrics['iqr_upper_bound']!r} h |")
    lines.append(f"| Median per-bid | {metrics['median_per_bid']!r} h/bid |")
    lines.append(f"| Median bid count | {metrics['median_bid_count']!r} bids/export |")
    lines.append("")
    lines.append("## Histogram")
    lines.append("")
    lines.append("| Bucket | Count |")
    lines.append("|--------|-------|")
    for b in histogram:
        lines.append(f"| {b.range_label} | {b.count} |")
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    diff_str = ""
    if new_value is not None and old_value:
        diff_pct = (new_value - old_value) / old_value * 100
        diff_str = f" (Δ {diff_pct:+.1f}%)"
    lines.append(f"- Old value: **{old_value:.2f} h**")
    lines.append(f"- New value: **{new_value!r} h**{diff_str}")
    lines.append(f"- Eligible: **{eligible}**")
    if reason:
        lines.append(f"- Reason: `{reason}`")
    lines.append(f"- Applied (writes to app_config): **{applied}**")
    lines.append("")
    lines.append(
        "*Reference: `docs/methodology/hours-saved-calibration.md` for "
        "rationale (IQR over Tukey, median over mean, n>=30 threshold).*"
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--range-days",
        type=int,
        default=90,
        help="Number of days of survey responses to consider (default: 90)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist the new value to app_config (admin only). Without "
        "this flag the script is a dry-run.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="When set, writes the markdown report to "
        "<output-dir>/hours-saved-calibration-YYYY-MM-DD.md",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON to stdout instead of markdown.",
    )
    args = parser.parse_args()

    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        print(
            "ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.",
            file=sys.stderr,
        )
        return 2

    rows = _fetch_rows(args.range_days)
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

    new_value = metrics["median_hours"]
    after = metrics["after_outlier_removal"]

    old_value = get_hours_saved_per_search()
    if old_value is None:
        old_value = DEFAULT_HOURS_SAVED_PER_SEARCH

    eligible = (
        after >= MIN_SAMPLE_SIZE
        and new_value is not None
        and 0 < new_value <= 50
    )
    reason: str | None = None
    if after < MIN_SAMPLE_SIZE:
        reason = f"insufficient_sample (after={after}, required={MIN_SAMPLE_SIZE})"
    elif new_value is None:
        reason = "no_valid_responses"
    elif not (0 < new_value <= 50):
        reason = f"out_of_range (new_value={new_value})"

    applied = False
    if eligible and args.apply and new_value is not None:
        try:
            _persist_value(new_value, sample_size=after, range_days=args.range_days)
            applied = True
        except Exception as exc:
            print(f"ERROR: failed to persist new value: {exc}", file=sys.stderr)
            return 3

    if args.json:
        out = {
            "range_days": args.range_days,
            **metrics,
            "old_value": old_value,
            "new_value": new_value,
            "eligible": eligible,
            "reason": reason,
            "applied": applied,
            "histogram": [{"range_label": b.range_label, "count": b.count} for b in histogram],
        }
        print(json.dumps(out, indent=2, default=str))
    else:
        report = _render_markdown_report(
            range_days=args.range_days,
            metrics=metrics,
            histogram=histogram,
            old_value=old_value,
            new_value=new_value,
            eligible=eligible,
            reason=reason,
            applied=applied,
        )
        if args.output_dir:
            out_dir = Path(args.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            fname = f"hours-saved-calibration-{datetime.now(timezone.utc).date()}.md"
            (out_dir / fname).write_text(report, encoding="utf-8")
            print(f"Report written to {out_dir / fname}")
        else:
            print(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
