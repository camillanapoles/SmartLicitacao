#!/usr/bin/env python3
"""Sentry FE baseline check (OPS-MTTR-001 / issue #970).

Calls the Sentry stats_v2 API to print accepted vs filtered FE event counts for
the last 24h. Used to validate that the post-PR-#944 quota fix unblocks event
ingestion in real-world conditions (memory `feedback_sentry_quiescent_quota_pattern`:
0 events != SDK morto; quota check first).

Usage:
    SENTRY_API_TOKEN=... python scripts/sentry_baseline_check.py
    python scripts/sentry_baseline_check.py --dry-run   # prints URL only

Env vars:
    SENTRY_API_TOKEN   Sentry user/internal-integration token (prefix sntryu_).
    SENTRY_ORG_SLUG    Defaults to "confenge".
    SENTRY_FE_PROJECT_ID  Defaults to 4510878216224768 (smartlic-frontend).

Pure stdlib. No external deps. Exit 0 on success, 1 on HTTP/auth failure, 2 if
accepted events == 0 (still quiescent — escalate per RCA flip pattern).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

DEFAULT_ORG = "confenge"
DEFAULT_FE_PROJECT_ID = "4510878216224768"
STATS_V2_BASE = "https://sentry.io/api/0/organizations/{org}/stats_v2/"


def build_url(org: str, project_id: str, hours: int = 24) -> str:
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    params = {
        "field": "sum(quantity)",
        "groupBy": "outcome",
        "category": "error",
        "interval": "1h",
        "project": project_id,
        "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return STATS_V2_BASE.format(org=org) + "?" + urllib.parse.urlencode(params)


def parse_outcomes(payload: dict) -> dict[str, int]:
    """Sum quantity per outcome across the time series."""
    totals: dict[str, int] = {}
    for group in payload.get("groups", []) or []:
        outcome = group.get("by", {}).get("outcome", "unknown")
        qty = int(group.get("totals", {}).get("sum(quantity)", 0) or 0)
        totals[outcome] = totals.get(outcome, 0) + qty
    return totals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the request URL and exit without calling the API.",
    )
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--org", default=os.environ.get("SENTRY_ORG_SLUG", DEFAULT_ORG))
    parser.add_argument(
        "--project-id",
        default=os.environ.get("SENTRY_FE_PROJECT_ID", DEFAULT_FE_PROJECT_ID),
    )
    args = parser.parse_args(argv)

    url = build_url(args.org, args.project_id, args.hours)
    if args.dry_run:
        print(f"DRY-RUN: would GET {url}")
        return 0

    token = os.environ.get("SENTRY_API_TOKEN")
    if not token:
        print("ERROR: SENTRY_API_TOKEN env var required (or use --dry-run)", file=sys.stderr)
        return 1

    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"HTTPError {exc.code}: {exc.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"URLError: {exc.reason}", file=sys.stderr)
        return 1

    totals = parse_outcomes(payload)
    accepted = totals.get("accepted", 0)
    filtered = totals.get("filtered", 0)
    rate_limited = totals.get("rate_limited", 0)
    invalid = totals.get("invalid", 0)

    print(f"Sentry FE event baseline (last {args.hours}h, project {args.project_id}):")
    print(f"  accepted     = {accepted}")
    print(f"  filtered     = {filtered}")
    print(f"  rate_limited = {rate_limited}")
    print(f"  invalid      = {invalid}")
    print(f"  other        = {sum(v for k, v in totals.items() if k not in {'accepted','filtered','rate_limited','invalid'})}")

    if accepted == 0:
        print("WARNING: accepted == 0 — still quiescent; check beforeSend filter / DSN.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
