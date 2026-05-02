#!/usr/bin/env python3
"""RES-BE-013: audit Railway production env vars against block/allow lists.

Origin: incident P0 2026-04-27 Stage 2 — ``PYTHONASYNCIODEBUG=1`` was found
in ``bidiq-backend`` prod with no commit/PR trail. Memory
``feedback_audit_env_vars_after_incident``.

Operating modes
---------------

1. Live (default) — invokes ``railway variables --service <svc> --kv`` and audits
   the keys returned. Requires ``RAILWAY_TOKEN`` env + ``railway`` CLI on PATH.

2. ``--from-file <path>`` — reads ``KEY=VALUE`` lines from a file (or ``-`` for
   stdin). Used by tests and for offline audit.

Exit codes
----------

* ``0`` — no blocklisted vars found (warnings about allowlist drift are
  non-fatal).
* ``1`` — at least one blocklisted var detected.
* ``2`` — usage / IO error (missing list file, Railway CLI failure, etc.).

Output
------

* ``::error::`` annotation per blocklisted var (visible inline on GitHub PRs).
* ``::warning::`` annotation per env var not present in the allowlist.
* JSON summary on the final line of stdout when ``--json`` is passed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BLOCKLIST_DEFAULT = REPO_ROOT / ".github" / "audit" / "prod-env-blocklist.txt"
ALLOWLIST_DEFAULT = REPO_ROOT / ".github" / "audit" / "prod-env-allowlist.txt"


def _load_list(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"audit list not found: {path}")
    entries: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def _pattern_to_regex(pattern: str) -> re.Pattern[str]:
    # Escape everything, then turn the literal '\*' back into '.*'.
    escaped = re.escape(pattern).replace(r"\*", ".*")
    return re.compile(rf"^{escaped}$")


def _matches_any(name: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(p.match(name) for p in patterns)


def _fetch_railway_keys(service: str) -> list[str]:
    try:
        result = subprocess.run(
            ["railway", "variables", "--service", service, "--kv"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except FileNotFoundError as exc:
        print(f"::error::railway CLI not on PATH: {exc}", file=sys.stderr)
        sys.exit(2)
    except subprocess.CalledProcessError as exc:
        print(
            f"::error::railway variables failed (exit={exc.returncode}): "
            f"{exc.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(2)
    except subprocess.TimeoutExpired:
        print("::error::railway variables timed out after 30s", file=sys.stderr)
        sys.exit(2)
    return _parse_kv_lines(result.stdout)


def _parse_kv_lines(text: str) -> list[str]:
    keys: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.append(key)
    return sorted(set(keys))


def _read_keys_from_file(path: str) -> list[str]:
    if path == "-":
        text = sys.stdin.read()
    else:
        text = Path(path).read_text(encoding="utf-8")
    return _parse_kv_lines(text)


def audit(
    keys: list[str],
    blocklist: list[str],
    allowlist: list[str],
) -> tuple[list[tuple[str, str]], list[str]]:
    """Return (violations, warnings).

    * violations: list of ``(key, blocklist_pattern)`` for keys hit by
      blocklist entries.
    * warnings: list of keys not present in allowlist (advisory only).
    """
    block_patterns = [(p, _pattern_to_regex(p)) for p in blocklist]
    allow_regex = [_pattern_to_regex(p) for p in allowlist]

    violations: list[tuple[str, str]] = []
    warnings: list[str] = []
    for key in keys:
        for raw, regex in block_patterns:
            if regex.match(key):
                violations.append((key, raw))
                break
        if not _matches_any(key, allow_regex):
            warnings.append(key)
    return violations, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--service",
        default="bidiq-backend",
        help="Railway service name (default: bidiq-backend)",
    )
    parser.add_argument(
        "--from-file",
        help="Read KEY=VALUE lines from a file (or '-' for stdin) instead of "
        "calling Railway CLI",
    )
    parser.add_argument(
        "--blocklist",
        default=str(BLOCKLIST_DEFAULT),
        help="Path to blocklist file",
    )
    parser.add_argument(
        "--allowlist",
        default=str(ALLOWLIST_DEFAULT),
        help="Path to allowlist file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON summary to stdout",
    )
    parser.add_argument(
        "--strict-allowlist",
        action="store_true",
        help="Treat allowlist drift as failure (exit 1) instead of warning",
    )
    args = parser.parse_args(argv)

    try:
        blocklist = _load_list(Path(args.blocklist))
        allowlist = _load_list(Path(args.allowlist))
    except FileNotFoundError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    if args.from_file:
        keys = _read_keys_from_file(args.from_file)
    else:
        keys = _fetch_railway_keys(args.service)

    violations, warnings = audit(keys, blocklist, allowlist)

    for key, pattern in violations:
        print(
            f"::error::Forbidden env var '{key}' detected in '{args.service}' "
            f"(matches blocklist pattern '{pattern}'). Remove it from Railway."
        )
    for key in warnings:
        print(
            f"::warning::Env var '{key}' in '{args.service}' is not in the "
            f"allowlist. Add it to .github/audit/prod-env-allowlist.txt or "
            f"remove it from Railway."
        )

    summary = {
        "service": args.service,
        "total_keys": len(keys),
        "violations": [
            {"key": k, "pattern": p} for k, p in violations
        ],
        "allowlist_drift": warnings,
    }

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            f"audit summary: service={args.service} total={len(keys)} "
            f"violations={len(violations)} drift={len(warnings)}"
        )

    if violations:
        return 1
    if warnings and args.strict_allowlist:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
