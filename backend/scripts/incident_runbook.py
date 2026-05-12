#!/usr/bin/env python3
"""OPS-RUNBOOK-001: Automated incident runbook generator.

Queries ``health_checks`` and ``incidents`` tables (via Supabase Management API
single-query endpoint), auto-correlates multi-stage outages, and outputs a
structured runbook suitable for Slack alerts or on-call triage.

Usage:

    # Default — query Supabase via Management API
    python backend/scripts/incident_runbook.py

    # With Slack webhook for multi-stage alerts
    SLACK_WEBHOOK_URL=https://hooks.slack.com/... \\
        python backend/scripts/incident_runbook.py

    # Dry-run against local files (for testing)
    python backend/scripts/incident_runbook.py --dry-run

Requirements:
    - SUPABASE_ACCESS_TOKEN  env var (Supabase Management API)
    - SUPABASE_PROJECT_REF   env var (e.g. "fqqyovlzdzimiwfofdjk")
    - httpx                  (in backend/requirements.txt)

Tables consumed (source of truth: ``supabase/migrations/``):
    - ``health_checks``  (20260228150000) — periodic health probe results
    - ``incidents``      (20260228150001) — resolved/ongoing incidents
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

MANAGEMENT_API_BASE = "https://api.supabase.com/v1/projects"

# Stages that can degrade — mapped from health_checks.components_json keys
STAGES = {
    "ingestion": "pncp ingestion cron/last run",
    "search": "search pipeline / datalake query",
    "cache": "cache layer (Redis + Supabase search_results_cache)",
    "db": "database (Supabase Postgres / pg_cron)",
    "auth": "authentication / JWT validation",
    "llm": "LLM classification (GPT-4.1-nano)",
}

# Severity labels
SEVERITY_LABELS = {
    0: "HEALTHY",
    1: "DEGRADED",
    2: "UNHEALTHY",
}


def _management_query(token: str, project_ref: str, sql: str) -> list[dict[str, Any]]:
    """Run ``sql`` via the Supabase Management API and return the row list."""
    url = f"{MANAGEMENT_API_BASE}/{project_ref}/database/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, headers=headers, json={"query": sql})
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Management API HTTP {resp.status_code}: {resp.text[:500]}"
        )
    payload = resp.json()
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("result"), list):
        return payload["result"]
    raise RuntimeError(f"Unexpected Management API payload shape: {payload!r}")


def _table_exists(token: str, project_ref: str, table_name: str) -> bool:
    """Check if a table exists in the public schema."""
    sql = (
        "SELECT EXISTS ("
        "  SELECT FROM information_schema.tables "
        "  WHERE table_schema = 'public' AND table_name = :table"
        ");"
    ).replace(":table", f"'{table_name}'")
    try:
        rows = _management_query(token, project_ref, sql)
        return bool(rows and rows[0].get("exists"))
    except Exception:
        return False


def _fetch_health_checks(
    token: str, project_ref: str, hours: int = 24
) -> list[dict[str, Any]]:
    """Fetch health_checks rows from the last N hours."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    sql = (
        "SELECT id, checked_at, overall_status, sources_json, components_json, "
        "       latency_ms "
        "FROM health_checks "
        "WHERE checked_at >= :since "
        "ORDER BY checked_at DESC "
        "LIMIT 500;"
    ).replace(":since", f"'{since}'")
    return _management_query(token, project_ref, sql)


def _fetch_incidents(
    token: str, project_ref: str, hours: int = 72
) -> list[dict[str, Any]]:
    """Fetch incidents from the last N hours."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    sql = (
        "SELECT id, started_at, resolved_at, status, affected_sources, description "
        "FROM incidents "
        "WHERE started_at >= :since "
        "ORDER BY started_at DESC "
        "LIMIT 50;"
    ).replace(":since", f"'{since}'")
    return _management_query(token, project_ref, sql)


def _fetch_cron_health(
    token: str, project_ref: str
) -> list[dict[str, Any]]:
    """Fetch cron_job_health view entries if it exists."""
    sql = (
        "SELECT jobname, last_status, last_run_at, runs_24h, failures_24h, "
        "       latency_avg_ms "
        "FROM cron_job_health "
        "ORDER BY jobname;"
    )
    try:
        return _management_query(token, project_ref, sql)
    except Exception:
        return []


def _determine_stage_status(
    components_json: dict[str, Any] | None,
) -> dict[str, int]:
    """Extract per-stage status from components_json.

    Returns dict of stage -> severity (0=healthy, 1=degraded, 2=unhealthy).
    Falls back to sources_json if components_json is empty.
    """
    stage_status: dict[str, int] = {s: 0 for s in STAGES}

    if not components_json:
        return stage_status

    for stage_key in STAGES:
        entry = components_json.get(stage_key)
        if entry is None:
            continue
        if isinstance(entry, dict):
            status = str(entry.get("status", "")).lower()
            if status in ("unhealthy", "down", "error"):
                stage_status[stage_key] = 2
            elif status in ("degraded", "slow", "warning"):
                stage_status[stage_key] = 1
        elif isinstance(entry, str):
            status = entry.lower()
            if status in ("unhealthy", "down", "error"):
                stage_status[stage_key] = 2
            elif status in ("degraded", "slow", "warning"):
                stage_status[stage_key] = 1

    return stage_status


def _format_timestamp(ts_str: str | None) -> str:
    """Format an ISO timestamp for human-readable output."""
    if not ts_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        return str(ts_str)[:19]


# ---------------------------------------------------------------------------
# Runbook generation
# ---------------------------------------------------------------------------


def generate_runbook(
    health_rows: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    cron_health: list[dict[str, Any]],
) -> str:
    """Generate a structured incident runbook from raw data."""
    lines: list[str] = []
    seen_stage_failures: dict[str, int] = {}
    multi_stage_detected = False

    # --- Header ---
    lines.append("=" * 72)
    lines.append("  INCIDENT RUNBOOK — OPS-RUNBOOK-001")
    lines.append(f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("=" * 72)
    lines.append("")

    # --- Section 1: Health Checks Summary ---
    lines.append("---")
    lines.append("SECTION 1: HEALTH CHECKS (last 24h)")
    lines.append("---")
    lines.append("")

    if not health_rows:
        lines.append("  [INFO] No health check entries in the last 24h.")
        lines.append("         The health_checks table may be empty or the")
        lines.append("         health canary may not be running.")
        lines.append("")
    else:
        total = len(health_rows)
        healthy_count = sum(
            1 for r in health_rows if r.get("overall_status") == "healthy"
        )
        degraded_count = sum(
            1 for r in health_rows if r.get("overall_status") == "degraded"
        )
        unhealthy_count = sum(
            1 for r in health_rows if r.get("overall_status") == "unhealthy"
        )

        lines.append(f"  Total checks : {total}")
        lines.append(f"  Healthy      : {healthy_count}")
        lines.append(f"  Degraded     : {degraded_count}")
        lines.append(f"  Unhealthy    : {unhealthy_count}")
        lines.append("")

        # Per-stage breakdown from the most recent check
        latest = health_rows[0]
        latency = latest.get("latency_ms")
        if latency is not None:
            lines.append(f"  Latest latency: {latency}ms")
            lines.append("")

        components = latest.get("components_json")
        if isinstance(components, str):
            try:
                components = json.loads(components)
            except (json.JSONDecodeError, TypeError):
                components = None

        stage_status = _determine_stage_status(components)

        lines.append("  Stage status (from latest check):")
        for stage, severity in stage_status.items():
            label = SEVERITY_LABELS.get(severity, "UNKNOWN")
            icon = "  OK" if severity == 0 else "  ** " if severity == 2 else "  *  "
            lines.append(f"    {icon} {stage:15s} → {label}")
            if severity > 0:
                seen_stage_failures[stage] = severity
        lines.append("")

        # Accumulate stage failures across all checks
        for row in health_rows:
            row_components = row.get("components_json")
            if isinstance(row_components, str):
                try:
                    row_components = json.loads(row_components)
                except (json.JSONDecodeError, TypeError):
                    row_components = None
            row_status = _determine_stage_status(row_components)
            for stage, severity in row_status.items():
                if severity > 0:
                    seen_stage_failures[stage] = max(
                        seen_stage_failures.get(stage, 0), severity
                    )

    # --- Section 2: Incidents ---
    lines.append("---")
    lines.append("SECTION 2: INCIDENTS (last 72h)")
    lines.append("---")
    lines.append("")

    if not incidents:
        lines.append("  [INFO] No incidents recorded in the last 72h.")
        lines.append("")
    else:
        ongoing = [i for i in incidents if i.get("status") == "ongoing"]
        resolved = [i for i in incidents if i.get("status") == "resolved"]

        if ongoing:
            lines.append(f"  ONGOING INCIDENTS ({len(ongoing)}):")
            for inc in ongoing:
                lines.append(f"    - {inc.get('description', '(no description)')}")
                lines.append(f"      Started: {_format_timestamp(inc.get('started_at'))}")
                affected = inc.get("affected_sources", [])
                if affected:
                    if isinstance(affected, str):
                        try:
                            affected = json.loads(affected)
                        except (json.JSONDecodeError, TypeError):
                            affected = [affected]
                    lines.append(f"      Affected stages: {', '.join(affected)}")
                lines.append("")
        else:
            lines.append("  No ongoing incidents.")
            lines.append("")

        if resolved:
            lines.append(f"  RECENTLY RESOLVED INCIDENTS ({len(resolved)}):")
            for inc in resolved[:5]:  # Top 5
                lines.append(f"    - {inc.get('description', '(no description)')}")
                lines.append(f"      Period: {_format_timestamp(inc.get('started_at'))} → "
                             f"{_format_timestamp(inc.get('resolved_at'))}")
                lines.append("")
        else:
            lines.append("  No resolved incidents in window.")
            lines.append("")

    # --- Section 3: Cron Health ---
    lines.append("---")
    lines.append("SECTION 3: PG_CRON JOB HEALTH")
    lines.append("---")
    lines.append("")

    if cron_health:
        for job in cron_health:
            jobname = job.get("jobname", "?")
            last_status = job.get("last_status", "?")
            last_run = _format_timestamp(job.get("last_run_at"))
            runs = job.get("runs_24h", 0)
            failures = job.get("failures_24h", 0)
            latency = job.get("latency_avg_ms")
            latency_str = f"{latency:.0f}ms" if latency is not None else "N/A"

            icon = "  OK" if last_status == "success" else "  ** "
            lines.append(
                f"    {icon} {jobname:30s} status={last_status:8s}"
                f" runs={runs} failures={failures}"
                f" latency={latency_str} last_run={last_run}"
            )
            if last_status == "failed":
                seen_stage_failures.setdefault("ingestion", 1)
    else:
        lines.append("  [INFO] cron_job_health view not available or empty.")
        lines.append("  Expected columns: jobname, last_status, last_run_at,")
        lines.append("  runs_24h, failures_24h, latency_avg_ms.")
        lines.append("  Created in migration: 20260414120000_cron_job_health.sql")
        lines.append("")

    # --- Section 4: Multi-Stage Correlation ---
    lines.append("---")
    lines.append("SECTION 4: STAGE CORRELATION & ROOT CAUSE ANALYSIS")
    lines.append("---")
    lines.append("")

    affected_stages = [s for s, sev in seen_stage_failures.items() if sev > 0]

    if len(affected_stages) >= 2:
        multi_stage_detected = True
        lines.append("  ** MULTI-STAGE OUTAGE DETECTED **")
        lines.append(f"  Affected stages ({len(affected_stages)}): {', '.join(affected_stages)}")
        lines.append("")
        lines.append("  Stage ordering (top-down root cause inference):")
        lines.append("    Order: ingestion → cache → db → search → auth → llm")
        lines.append("")
        for stage in ["ingestion", "db", "cache", "search", "auth", "llm"]:
            if stage in seen_stage_failures:
                severity = seen_stage_failures[stage]
                lines.append(
                    f"    [{SEVERITY_LABELS[severity]}] {stage}"
                )
        lines.append("")
        lines.append("  Probable root cause (based on stage ordering):")
        first_failed = None
        for stage in ["ingestion", "db", "cache", "search", "auth", "llm"]:
            if stage in seen_stage_failures:
                first_failed = stage
                break
        if first_failed:
            lines.append(
                f"    First affected stage: {first_failed} — suggests root"
            )
            lines.append("    cause in that layer. Investigate logs for errors")
            lines.append("    in this component first, then trace downstream.")
        lines.append("")
    elif len(affected_stages) == 1:
        lines.append(f"  Single stage affected: {affected_stages[0]}")
        lines.append("  Isolated issue — likely not a system-wide outage.")
        lines.append("")
    else:
        lines.append("  All stages healthy — no correlation needed.")
        lines.append("")

    # --- Section 5: Recommended Actions ---
    lines.append("---")
    lines.append("SECTION 5: RECOMMENDED ACTIONS")
    lines.append("---")
    lines.append("")

    if multi_stage_detected:
        lines.append("  ** MULTI-STAGE OUTAGE — ESCALATE IMMEDIATELY **")
        lines.append("")
        lines.append("  1. Check Sentry for recent errors across all services")
        lines.append("  2. Verify Railway dashboard for deployment status")
        lines.append("  3. Check Supabase status page for database issues")
        lines.append("  4. Review Redis availability (connection pool)")
        lines.append("  5. Run: railway logs --service bidiq-backend -e production")
        lines.append("  6. If ingestion-related: check ARQ worker logs")
        lines.append("     (railway logs --service bidiq-worker -e production)")
        lines.append("")
    elif any(s in seen_stage_failures for s in seen_stage_failures):
        lines.append("  Single-stage degradation detected:")
        for stage in sorted(seen_stage_failures.keys()):
            lines.append(f"    - {stage}: Review component logs and metrics")
        lines.append("")
        lines.append("  Suggested diagnostic commands:")
        lines.append("    1. Check Sentry: https://confenge.sentry.io/")
        lines.append("    2. Railway: railway logs --service bidiq-backend -e production")
        if "ingestion" in seen_stage_failures:
            lines.append(
                "    3. Worker: railway logs --service bidiq-worker -e production"
            )
        lines.append("")
    else:
        lines.append("  No action required — all systems healthy.")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Slack webhook
# ---------------------------------------------------------------------------


def _send_slack_alert(webhook_url: str, runbook: str) -> None:
    """Send a snippet of the runbook to a Slack webhook."""
    # Extract the multi-stage section (first 2000 chars)
    alert_text = (
        "*OPS-RUNBOOK-001: Multi-Stage Outage Detected*\n\n"
        f"```\n{runbook[:1800]}\n```\n"
        "_Full runbook: run `python backend/scripts/incident_runbook.py`_"
    )
    payload = {"text": alert_text}
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(webhook_url, json=payload)
        if resp.status_code not in (200, 201, 204):
            print(f"Slack webhook returned HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="OPS-RUNBOOK-001: Automated incident runbook generator"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use static test data instead of querying Supabase",
    )
    parser.add_argument(
        "--slack-webhook",
        default=os.getenv("SLACK_WEBHOOK_URL", ""),
        help="Slack webhook URL for multi-stage outage alerts",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Write runbook to file instead of stdout",
    )
    args = parser.parse_args()

    if args.dry_run:
        health_rows = [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "overall_status": "degraded",
                "sources_json": "{}",
                "components_json": json.dumps({
                    "ingestion": {"status": "unhealthy"},
                    "cache": {"status": "healthy"},
                    "db": {"status": "healthy"},
                    "search": {"status": "healthy"},
                    "auth": {"status": "healthy"},
                    "llm": {"status": "healthy"},
                }),
                "latency_ms": 450,
            },
        ]
        incidents = [
            {
                "id": "00000000-0000-0000-0000-000000000002",
                "started_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                "resolved_at": None,
                "status": "ongoing",
                "affected_sources": '{"ingestion"}',
                "description": "Ingestion pipeline degraded — PNCP crawl failures",
            },
        ]
        cron_health = [
            {"jobname": "purge-old-bids", "last_status": "success", "last_run_at": datetime.now(timezone.utc).isoformat(), "runs_24h": 1, "failures_24h": 0, "latency_avg_ms": 3200},
            {"jobname": "incremental-crawl", "last_status": "failed", "last_run_at": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(), "runs_24h": 3, "failures_24h": 2, "latency_avg_ms": 15000},
        ]
    else:
        token = os.getenv("SUPABASE_ACCESS_TOKEN", "")
        project_ref = os.getenv("SUPABASE_PROJECT_REF", "")

        if not token or not project_ref:
            print(
                "ERROR: SUPABASE_ACCESS_TOKEN and SUPABASE_PROJECT_REF must be set.",
                file=sys.stderr,
            )
            return 2

        # Check which tables exist
        has_health = _table_exists(token, project_ref, "health_checks")
        has_incidents = _table_exists(token, project_ref, "incidents")

        health_rows = []
        if has_health:
            try:
                health_rows = _fetch_health_checks(token, project_ref)
            except Exception as e:
                print(f"WARNING: Could not fetch health_checks: {e}", file=sys.stderr)
        else:
            print("INFO: health_checks table not found — querying available data sources.", file=sys.stderr)

        incidents = []
        if has_incidents:
            try:
                incidents = _fetch_incidents(token, project_ref)
            except Exception as e:
                print(f"WARNING: Could not fetch incidents: {e}", file=sys.stderr)
        else:
            print("INFO: incidents table not found — skipping incident correlation.", file=sys.stderr)

        # Always attempt cron_job_health (view, not table)
        try:
            cron_health = _fetch_cron_health(token, project_ref)
        except Exception as e:
            print(f"WARNING: Could not fetch cron_job_health: {e}", file=sys.stderr)
            cron_health = []

    runbook = generate_runbook(health_rows, incidents, cron_health)

    # Detect multi-stage for Slack alert
    has_multi_stage = runbook.count("** MULTI-STAGE OUTAGE DETECTED **") > 0

    if args.output:
        with open(args.output, "w") as f:
            f.write(runbook)
        print(f"Runbook written to {args.output}")
    else:
        print(runbook)

    # Slack alert for multi-stage
    if has_multi_stage and args.slack_webhook:
        _send_slack_alert(args.slack_webhook, runbook)
        print("\n[Slack alert sent]")

    return 1 if has_multi_stage else 0  # Exit 1 if outage, 0 if clean


if __name__ == "__main__":
    sys.exit(main())
