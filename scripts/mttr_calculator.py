#!/usr/bin/env python3
"""Railway log-based MTTR tracker (OPS-MTTR-001 / issue #970, AC3).

Parses Railway-style access log lines and computes MTTR (Mean Time To Recovery)
per endpoint by detecting 5xx → 2xx transitions. Outputs a markdown summary
with rolling 7d MTTR per endpoint.

Usage:
    railway logs --tail 1000 | python scripts/mttr_calculator.py
    python scripts/mttr_calculator.py --file logs.txt
    python scripts/mttr_calculator.py --sample              # built-in fixture

Exit codes:
    0  always on success
    2  if any endpoint MTTR > SLO (default 30 minutes)

Pure stdlib. SLO target documented in
``_reversa_sdd/operational-reliability-2026-05.md`` (memory
`reference_railway_pro_plan_actual.md`: Pro plan provides headroom for <30min MTTR).
"""
from __future__ import annotations

import argparse
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable

# Match common Railway access log shapes. Two flavors are supported:
#   1) ISO-ish timestamp + method + path + status:
#      2026-05-09T19:55:00 ... GET /buscar 200 ...
#   2) Bracketed timestamp:
#      [2026-05-09 19:55:00] GET /buscar 500
LOG_PATTERNS = [
    re.compile(
        r"(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)"
        r"[^\n]*?\b(?P<method>GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+"
        r"(?P<path>/[^\s\"]*)\s+"
        r"(?P<status>[1-5]\d{2})\b"
    ),
]

SLO_MTTR_MINUTES = 30
ROLLING_WINDOW_DAYS = 7

SAMPLE_LOG = """
2026-05-09T19:55:00 GET /buscar 500 100ms
2026-05-09T19:56:30 GET /buscar 500 100ms
2026-05-09T19:58:00 GET /buscar 200 80ms
2026-05-09T20:30:00 GET /health/ready 503 10ms
2026-05-09T20:35:00 GET /health/ready 200 5ms
2026-05-08T10:00:00 GET /buscar 502 1200ms
2026-05-08T10:45:00 GET /buscar 200 90ms
2026-05-07T14:00:00 GET /buscar 200 70ms
""".strip()


def parse_timestamp(raw: str) -> datetime:
    raw = raw.replace("T", " ").split(".", 1)[0]
    return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def parse_log_lines(lines: Iterable[str]) -> list[tuple[datetime, str, int]]:
    """Return list of (timestamp, normalized_path, status) tuples."""
    events: list[tuple[datetime, str, int]] = []
    for raw_line in lines:
        line = raw_line.rstrip("\n")
        if not line.strip():
            continue
        for pattern in LOG_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            try:
                ts = parse_timestamp(match.group("ts"))
            except ValueError:
                break
            path = normalize_path(match.group("path"))
            status = int(match.group("status"))
            events.append((ts, path, status))
            break
    events.sort(key=lambda x: x[0])
    return events


def normalize_path(path: str) -> str:
    """Drop query string and collapse numeric/uuid segments to :id placeholder."""
    path = path.split("?", 1)[0]
    parts = []
    for seg in path.split("/"):
        if not seg:
            parts.append(seg)
            continue
        if seg.isdigit() or re.fullmatch(r"[0-9a-fA-F-]{8,}", seg):
            parts.append(":id")
        else:
            parts.append(seg)
    return "/".join(parts) or "/"


def compute_mttr(
    events: list[tuple[datetime, str, int]],
    window_days: int = ROLLING_WINDOW_DAYS,
    now: datetime | None = None,
) -> dict[str, dict[str, float | int]]:
    """For each endpoint, find 5xx → 2xx transitions and compute durations.

    Returns map of path -> {incidents, mttr_seconds, max_seconds}.
    Only counts transitions whose recovery falls inside the rolling window.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    by_path: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    for ts, path, status in events:
        by_path[path].append((ts, status))

    summary: dict[str, dict[str, float | int]] = {}
    for path, series in by_path.items():
        durations: list[float] = []
        first_5xx_ts: datetime | None = None
        for ts, status in series:
            if status >= 500 and first_5xx_ts is None:
                first_5xx_ts = ts
            elif status < 400 and first_5xx_ts is not None:
                if ts >= cutoff:
                    durations.append((ts - first_5xx_ts).total_seconds())
                first_5xx_ts = None
        if not durations:
            continue
        summary[path] = {
            "incidents": len(durations),
            "mttr_seconds": statistics.mean(durations),
            "max_seconds": max(durations),
        }
    return summary


def render_markdown(summary: dict[str, dict[str, float | int]], window_days: int) -> tuple[str, bool]:
    """Render a markdown table and signal whether SLO was breached."""
    lines = [
        f"# MTTR Report — rolling {window_days}d",
        "",
        f"_SLO target: MTTR < {SLO_MTTR_MINUTES} min per endpoint._",
        "",
    ]
    if not summary:
        lines.append("No 5xx → 2xx recoveries detected in window.")
        return "\n".join(lines) + "\n", False

    lines.append("| Endpoint | Incidents | MTTR (min) | Max (min) | SLO |")
    lines.append("|---|---:|---:|---:|:---:|")
    breach = False
    for path in sorted(summary):
        row = summary[path]
        mttr_min = row["mttr_seconds"] / 60
        max_min = row["max_seconds"] / 60
        ok = mttr_min < SLO_MTTR_MINUTES
        breach = breach or not ok
        lines.append(
            f"| `{path}` | {row['incidents']} | {mttr_min:.1f} | {max_min:.1f} | "
            f"{'PASS' if ok else 'BREACH'} |"
        )
    return "\n".join(lines) + "\n", breach


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--file", help="Read log lines from FILE instead of stdin.")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use built-in synthetic log fixture (self-test).",
    )
    parser.add_argument("--window-days", type=int, default=ROLLING_WINDOW_DAYS)
    args = parser.parse_args(argv)

    if args.sample:
        lines = SAMPLE_LOG.splitlines()
        # Anchor "now" so the sample is reproducible.
        now = datetime(2026, 5, 9, 21, 0, 0, tzinfo=timezone.utc)
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as fp:
            lines = fp.readlines()
        now = None
    else:
        lines = sys.stdin.readlines()
        now = None

    events = parse_log_lines(lines)
    summary = compute_mttr(events, window_days=args.window_days, now=now)
    report, breach = render_markdown(summary, args.window_days)
    sys.stdout.write(report)
    return 2 if breach else 0


if __name__ == "__main__":
    sys.exit(main())
