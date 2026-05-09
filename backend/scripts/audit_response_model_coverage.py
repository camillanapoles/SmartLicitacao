"""PARITY-BE-FE-001 (AC1): Audit `response_model=` coverage on FastAPI routes.

Walks ``backend/routes/*.py`` and parses each module's AST to count:
    * Total `@router.<verb>(...)` decorators (HTTP-handling routes).
    * How many of those declare `response_model=` (truthy or None — both count
      as explicitly typed; `response_model=None` is the documented escape
      hatch for raw / streaming responses, see story AC2).
    * Per-file coverage % and the list of `path` strings that are still
      missing the kwarg.

Why an AST walk and not import-the-app?
    * The script must run in CI without env vars / DB / Redis.
    * AST stays dependency-free and deterministic — same output across
      Linux / macOS / Windows, regardless of feature-flag state.
    * False negatives (e.g. routes registered via a helper) are rare
      in this codebase: every router uses ``@router.<verb>("/path", ...)``.

Usage:

    # Print human-readable table to stdout.
    python backend/scripts/audit_response_model_coverage.py

    # Emit machine-readable JSON to a path (used to commit the baseline
    # snapshot consumed by the future CI gate).
    python backend/scripts/audit_response_model_coverage.py \
        --json backend/scripts/audit_response_model_coverage_baseline.json

    # Compare against a previously-committed baseline and exit non-zero
    # when coverage shrinks (intended for the CI gate in AC3).
    python backend/scripts/audit_response_model_coverage.py \
        --check-against backend/scripts/audit_response_model_coverage_baseline.json
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

#: HTTP verbs that produce a typed response in OpenAPI. ``websocket`` and
#: ``api_route`` are excluded — the former does not surface response_model
#: in OpenAPI, and the latter is virtually unused in this codebase.
HTTP_VERBS: frozenset[str] = frozenset(
    {"get", "post", "put", "patch", "delete", "head", "options"}
)


@dataclass
class RouteEntry:
    """One ``@router.<verb>(...)`` decorator we found in a route module."""

    verb: str
    path: str
    has_response_model: bool
    lineno: int


@dataclass
class FileReport:
    """Aggregated audit data for a single route module."""

    file: str
    routes: list[RouteEntry] = field(default_factory=list)

    @property
    def router_count(self) -> int:
        return len(self.routes)

    @property
    def response_model_count(self) -> int:
        return sum(1 for r in self.routes if r.has_response_model)

    @property
    def coverage_pct(self) -> float:
        if not self.routes:
            return 100.0  # vacuously typed (helper / aggregator file)
        return round(100.0 * self.response_model_count / self.router_count, 2)

    @property
    def missing_paths(self) -> list[str]:
        return [r.path for r in self.routes if not r.has_response_model]

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "router_count": self.router_count,
            "response_model_count": self.response_model_count,
            "coverage_pct": self.coverage_pct,
            "missing_paths": self.missing_paths,
        }


def _is_router_call(node: ast.AST) -> tuple[bool, str | None]:
    """Match ``@router.<verb>(...)`` and ``@<some_router>.<verb>(...)``.

    Returns ``(matched, verb)``. We accept any attribute access on a Name
    target ending in ``_router`` or named exactly ``router`` — covers the
    occasional ``api_router.get(...)`` / ``public_router.get(...)`` patterns.
    """
    if not isinstance(node, ast.Call):
        return False, None
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False, None
    verb = func.attr
    if verb not in HTTP_VERBS:
        return False, None
    target = func.value
    if isinstance(target, ast.Name):
        name = target.id
        if name == "router" or name.endswith("_router"):
            return True, verb
    return False, None


def _has_response_model_kwarg(call: ast.Call) -> bool:
    """``response_model=`` declared explicitly (any value, incl. ``None``)."""
    return any(kw.arg == "response_model" for kw in call.keywords)


def _extract_path(call: ast.Call) -> str:
    """Return the first positional string arg of the decorator, e.g. ``"/me"``.

    The audit treats the path as a label only — exact normalization (leading
    slash, trailing slash, prefix mounting) does not matter for coverage
    counting.
    """
    if call.args:
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return "<unknown>"


def audit_file(path: Path) -> FileReport:
    """AST-walk one route module. Never raises; reports skip via empty routes."""
    report = FileReport(file=str(path))
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        # Surface the failure in the report file but keep the script moving:
        # a single broken file should not abort an org-wide audit.
        sys.stderr.write(f"[audit] skip {path}: {exc}\n")
        return report

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            matched, verb = _is_router_call(deco)
            if not matched:
                continue
            assert isinstance(deco, ast.Call)  # narrowed by _is_router_call
            assert verb is not None
            report.routes.append(
                RouteEntry(
                    verb=verb,
                    path=_extract_path(deco),
                    has_response_model=_has_response_model_kwarg(deco),
                    lineno=node.lineno,
                )
            )
    return report


def audit_routes_dir(routes_dir: Path) -> list[FileReport]:
    """Audit every ``*.py`` (excluding ``__pycache__``) under ``routes_dir``.

    File paths are normalized to ``backend/routes/<name>.py`` so the JSON
    baseline stays reproducible across worktrees / CI checkouts that have
    different absolute paths.
    """
    files = sorted(
        p for p in routes_dir.glob("*.py") if p.name != "__init__.py"
    )
    reports: list[FileReport] = []
    for p in files:
        report = audit_file(p)
        # Always render as ``backend/routes/<name>.py`` regardless of CWD.
        report.file = f"backend/routes/{p.name}"
        reports.append(report)
    return reports


def aggregate(reports: Iterable[FileReport]) -> dict:
    """Roll up totals + per-file rows into a JSON-serializable summary."""
    rows = [r for r in reports if r.router_count > 0]
    helpers = [r for r in reports if r.router_count == 0]
    total_routers = sum(r.router_count for r in rows)
    total_typed = sum(r.response_model_count for r in rows)
    coverage_pct = (
        round(100.0 * total_typed / total_routers, 2) if total_routers else 100.0
    )
    return {
        "summary": {
            "files_scanned": len(rows) + len(helpers),
            "files_with_routes": len(rows),
            "helper_files_excluded": [h.file for h in helpers],
            "total_routes": total_routers,
            "total_with_response_model": total_typed,
            "coverage_pct": coverage_pct,
        },
        "files": [r.to_dict() for r in sorted(rows, key=lambda x: x.coverage_pct)],
    }


def render_table(summary: dict) -> str:
    """Pretty-print the summary as a single ASCII table for human review."""
    lines: list[str] = []
    s = summary["summary"]
    lines.append(
        f"== response_model coverage ({s['coverage_pct']}% over "
        f"{s['total_routes']} routes in {s['files_with_routes']} files) =="
    )
    lines.append(
        f"{'file':<55}{'routes':>8}{'typed':>8}{'cov%':>8}  missing"
    )
    lines.append("-" * 100)
    for row in summary["files"]:
        missing = ", ".join(row["missing_paths"]) if row["missing_paths"] else ""
        # Truncate to a sane terminal width but keep the leading paths.
        if len(missing) > 60:
            missing = missing[:57] + "..."
        lines.append(
            f"{row['file']:<55}{row['router_count']:>8}"
            f"{row['response_model_count']:>8}{row['coverage_pct']:>8.2f}  {missing}"
        )
    if s["helper_files_excluded"]:
        lines.append("")
        lines.append(
            f"# {len(s['helper_files_excluded'])} helper/aggregator files excluded "
            "(zero @router.* decorators)"
        )
    return "\n".join(lines)


def check_against_baseline(current: dict, baseline_path: Path) -> int:
    """Compare ``current`` summary against the JSON baseline file.

    Returns a Unix exit code:
        0 — coverage stayed the same or improved (allowed)
        1 — coverage shrank, OR a previously-typed file lost typed routes,
            OR a brand-new route was added without response_model
    """
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    base_pct = baseline["summary"]["coverage_pct"]
    cur_pct = current["summary"]["coverage_pct"]
    failures: list[str] = []

    if cur_pct + 0.01 < base_pct:
        failures.append(
            f"coverage decreased: {base_pct}% -> {cur_pct}% "
            "(new routes must declare response_model=)"
        )

    base_files = {row["file"]: row for row in baseline["files"]}
    cur_files = {row["file"]: row for row in current["files"]}

    for file, cur_row in cur_files.items():
        base_row = base_files.get(file)
        if base_row is None:
            # New file added — every route must be typed.
            if cur_row["missing_paths"]:
                failures.append(
                    f"new file {file} added with {len(cur_row['missing_paths'])} "
                    f"untyped routes: {cur_row['missing_paths']}"
                )
            continue
        # Existing file — typed-route count must not decrease.
        if cur_row["response_model_count"] < base_row["response_model_count"]:
            failures.append(
                f"{file}: typed routes dropped from "
                f"{base_row['response_model_count']} to "
                f"{cur_row['response_model_count']}"
            )

    if failures:
        sys.stderr.write("response_model coverage gate FAILED:\n")
        for f in failures:
            sys.stderr.write(f"  - {f}\n")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--routes-dir",
        type=Path,
        default=None,
        help="Override target directory (default: backend/routes/ relative to this script).",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Write JSON output to this path instead of stdout table.",
    )
    parser.add_argument(
        "--check-against",
        type=Path,
        default=None,
        help="Compare against an existing baseline JSON and exit 1 on regression.",
    )
    args = parser.parse_args(argv)

    if args.routes_dir is None:
        # __file__ = backend/scripts/audit_response_model_coverage.py
        args.routes_dir = Path(__file__).resolve().parent.parent / "routes"

    if not args.routes_dir.is_dir():
        sys.stderr.write(f"routes dir not found: {args.routes_dir}\n")
        return 2

    reports = audit_routes_dir(args.routes_dir)
    summary = aggregate(reports)

    if args.json is not None:
        args.json.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        print(render_table(summary))

    if args.check_against is not None:
        return check_against_baseline(summary, args.check_against)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
