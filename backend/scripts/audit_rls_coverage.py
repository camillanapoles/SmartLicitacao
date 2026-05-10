#!/usr/bin/env python3
"""Audit RLS coverage on the Supabase ``public`` schema (RLS-AUDIT-001 / #969).

Connects to Supabase via the Management API single-query endpoint
(``POST /v1/projects/{ref}/database/query``) using ``SUPABASE_ACCESS_TOKEN``
and ``SUPABASE_PROJECT_REF``. Exports per-table:

* ``rowsecurity`` flag (RLS enabled or not)
* policy count
* per-policy ``{name, roles, cmd}`` triples

Output:
    * ``_reversa_sdd/rls-coverage-<DATE>.md`` — markdown report grouped by
      coverage status (compliant / RLS-on no-policy / RLS-off / exempt).
    * Exit code ``0`` if every public table has either RLS enabled with
      ≥1 policy, or carries a ``-- rls-exempt: <reason>`` comment in
      ``supabase/migrations/`` (best-effort grep for the table name on the
      same line as the marker).
    * Exit code ``1`` otherwise.
    * Exit code ``2`` for usage / connectivity errors.

Policy reference: ``docs/adr/ADR-RLS-MANDATORY-001-policy.md``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

DEFAULT_REPORT_PATH = "_reversa_sdd/rls-coverage-{date}.md"
MANAGEMENT_API_BASE = "https://api.supabase.com/v1/projects"
EXEMPT_MARKER = "rls-exempt:"
RLS_AUDIT_QUERY = """
SELECT t.tablename,
       t.rowsecurity,
       COALESCE(p.policy_count, 0) AS policy_count,
       COALESCE(p.policies, '[]'::jsonb) AS policies
FROM pg_tables t
LEFT JOIN (
  SELECT tablename,
         COUNT(*) AS policy_count,
         jsonb_agg(jsonb_build_object('name', policyname, 'roles', roles, 'cmd', cmd)) AS policies
  FROM pg_policies
  WHERE schemaname = 'public'
  GROUP BY tablename
) p USING (tablename)
WHERE t.schemaname = 'public'
ORDER BY t.tablename;
""".strip()


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
    # API returns either a list of rows directly or {"result": [...]} depending on version
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("result"), list):
        return payload["result"]
    raise RuntimeError(f"Unexpected Management API payload shape: {payload!r}")


def _scan_exemptions(repo_root: Path) -> dict[str, str]:
    """Best-effort scan of ``supabase/migrations/*.sql`` for ``-- rls-exempt: <reason>``.

    Returns a mapping ``{table_name: reason}``. We pair the marker with a
    table name found on the same line (after the marker) or on the next
    non-empty line that mentions ``CREATE TABLE`` / ``ALTER TABLE``. This
    is intentionally permissive — the goal is grace, not enforcement.
    """
    exemptions: dict[str, str] = {}
    migrations_dir = repo_root / "supabase" / "migrations"
    if not migrations_dir.exists():
        return exemptions
    table_pat = re.compile(
        r"(?:CREATE\s+TABLE|ALTER\s+TABLE)\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"(?:public\.)?\"?([A-Za-z_][A-Za-z0-9_]*)\"?",
        re.IGNORECASE,
    )
    for sql_file in migrations_dir.glob("*.sql"):
        try:
            text = sql_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            if EXEMPT_MARKER not in line.lower():
                continue
            reason = line.split(EXEMPT_MARKER, 1)[1].strip(" -:\t")
            # Look for an explicit table after the marker (same line) first.
            match = table_pat.search(line)
            if not match:
                # Fall back to the next 5 non-empty lines.
                for follow in lines[idx + 1 : idx + 6]:
                    match = table_pat.search(follow)
                    if match:
                        break
            if match:
                exemptions.setdefault(match.group(1).lower(), reason or "exempt")
    return exemptions


def _classify(rows: list[dict[str, Any]], exemptions: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "compliant": [],
        "rls_on_no_policy": [],
        "rls_off": [],
        "exempt": [],
    }
    for row in rows:
        table = row.get("tablename")
        rls_on = bool(row.get("rowsecurity"))
        policy_count = int(row.get("policy_count") or 0)
        policies = row.get("policies") or []
        # `policies` may arrive as a JSON string depending on the API path.
        if isinstance(policies, str):
            try:
                policies = json.loads(policies)
            except json.JSONDecodeError:
                policies = []
        record = {
            "tablename": table,
            "rowsecurity": rls_on,
            "policy_count": policy_count,
            "policies": policies,
            "exempt_reason": exemptions.get((table or "").lower()),
        }
        if rls_on and policy_count > 0:
            buckets["compliant"].append(record)
        elif record["exempt_reason"]:
            buckets["exempt"].append(record)
        elif rls_on and policy_count == 0:
            buckets["rls_on_no_policy"].append(record)
        else:
            buckets["rls_off"].append(record)
    return buckets


def _format_policies(policies: list[dict[str, Any]]) -> str:
    if not policies:
        return "—"
    parts = []
    for pol in policies:
        name = pol.get("name", "?")
        cmd = pol.get("cmd", "?")
        roles = pol.get("roles") or []
        if isinstance(roles, str):
            roles_str = roles
        else:
            roles_str = ",".join(str(r) for r in roles)
        parts.append(f"`{name}` ({cmd} → {roles_str or '∅'})")
    return "; ".join(parts)


def _render_report(buckets: dict[str, list[dict[str, Any]]], generated_at: str, project_ref: str) -> str:
    total = sum(len(v) for v in buckets.values())
    compliant = len(buckets["compliant"])
    exempt = len(buckets["exempt"])
    failing = len(buckets["rls_on_no_policy"]) + len(buckets["rls_off"])
    coverage_pct = round(((compliant + exempt) / total) * 100, 1) if total else 0.0
    lines: list[str] = []
    lines.append("# RLS Coverage Audit — `public` schema")
    lines.append("")
    lines.append(f"- **Generated:** {generated_at}")
    lines.append(f"- **Project ref:** `{project_ref}`")
    lines.append(f"- **Total tables:** {total}")
    lines.append(f"- **Compliant (RLS on + ≥1 policy):** {compliant}")
    lines.append(f"- **Documented exempt (`-- rls-exempt:`):** {exempt}")
    lines.append(f"- **Failing:** {failing}")
    lines.append(f"- **Coverage:** {coverage_pct}%")
    lines.append("")
    lines.append("Source: ADR-RLS-MANDATORY-001 (`docs/adr/ADR-RLS-MANDATORY-001-policy.md`).")
    lines.append("Generator: `backend/scripts/audit_rls_coverage.py` (RLS-AUDIT-001 / #969).")
    lines.append("")

    section_titles = {
        "rls_off": "## ❌ RLS disabled (failing)",
        "rls_on_no_policy": "## ❌ RLS enabled but no policies (failing — effectively closed to non-bypass roles, gap on intent)",
        "compliant": "## ✅ Compliant (RLS on + ≥1 policy)",
        "exempt": "## ⚠️ Documented exemptions (`-- rls-exempt:` in migrations)",
    }
    order = ["rls_off", "rls_on_no_policy", "exempt", "compliant"]
    for key in order:
        rows = buckets[key]
        lines.append(section_titles[key])
        lines.append("")
        if not rows:
            lines.append("_None._")
            lines.append("")
            continue
        lines.append("| Table | RLS | Policies | Detail |")
        lines.append("|-------|-----|---------:|--------|")
        for row in sorted(rows, key=lambda r: r["tablename"] or ""):
            detail = (
                row["exempt_reason"]
                if key == "exempt"
                else _format_policies(row["policies"])
            )
            lines.append(
                f"| `{row['tablename']}` | {'on' if row['rowsecurity'] else 'off'} | "
                f"{row['policy_count']} | {detail} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RLS coverage audit (RLS-AUDIT-001 / #969).")
    parser.add_argument(
        "--output",
        default=None,
        help="Override report path (default: _reversa_sdd/rls-coverage-<UTC date>.md).",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root used to scan ``supabase/migrations/`` for "
        "exemption markers (default: cwd).",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Skip writing the report file (still prints summary to stdout).",
    )
    args = parser.parse_args(argv)

    token = os.environ.get("SUPABASE_ACCESS_TOKEN")
    project_ref = os.environ.get("SUPABASE_PROJECT_REF")
    if not token or not project_ref:
        print(
            "ERROR: SUPABASE_ACCESS_TOKEN and SUPABASE_PROJECT_REF env vars are required.",
            file=sys.stderr,
        )
        return 2

    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()
    try:
        rows = _management_query(token, project_ref, RLS_AUDIT_QUERY)
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"ERROR: Management API call failed: {exc}", file=sys.stderr)
        return 2

    exemptions = _scan_exemptions(repo_root)
    buckets = _classify(rows, exemptions)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    report_path = (
        Path(args.output)
        if args.output
        else repo_root / DEFAULT_REPORT_PATH.format(date=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    )
    report = _render_report(buckets, generated_at, project_ref)

    if not args.no_write:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        print(f"Report written: {report_path}")

    failing = len(buckets["rls_on_no_policy"]) + len(buckets["rls_off"])
    print(
        f"Tables: {sum(len(v) for v in buckets.values())} | "
        f"compliant={len(buckets['compliant'])} "
        f"exempt={len(buckets['exempt'])} "
        f"failing={failing}"
    )
    if failing:
        print("FAIL: tables without RLS coverage and no exemption marker.", file=sys.stderr)
        for row in buckets["rls_off"] + buckets["rls_on_no_policy"]:
            print(f"  - {row['tablename']} (rls={'on' if row['rowsecurity'] else 'off'}, "
                  f"policies={row['policy_count']})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
