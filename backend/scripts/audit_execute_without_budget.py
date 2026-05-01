#!/usr/bin/env python3
"""RES-BE-015 / RES-BE-001: Audit raw `.execute()` and `wait_for(to_thread(...))`
in `backend/routes/*.py` that lack `_run_with_budget` protection.

The 2026-04-27 to 2026-04-30 outage cycle (Stage 2-8) traced back to this anti-
pattern: sync supabase `.execute()` in an `async def` handler, optionally
wrapped only in `asyncio.wait_for(asyncio.to_thread(...))`. The caller-side
`wait_for` cancels the *await* but never the underlying Python thread, and the
thread keeps consuming a Supabase connection until the server statement_timeout
(15s) fires. Cleanup of the cancelled future then runs **inline** on the event
loop, blocking ticks for 14-48s and freezing every Railway proxy probe. The
fix is `_run_with_budget(asyncio.to_thread(...), budget=<budget>)` plus an
explicit ``try/except asyncio.TimeoutError: return _empty_response()``.

This script is deterministic, AST-based, and used both as a developer CLI and
as a CI gate (`.github/workflows/audit-execute-without-budget.yml`). It exits
non-zero when any violation is found in the routes listed in
``TARGET_ROUTES`` (which corresponds 1:1 with the RES-BE-015 sweep scope).

Usage
-----

    # Audit every route file (default scope):
    python backend/scripts/audit_execute_without_budget.py

    # Audit a single file (path can be relative to repo root or to backend):
    python backend/scripts/audit_execute_without_budget.py --file routes/blog_stats.py

    # Emit JSON for CI annotations (one line per violation):
    python backend/scripts/audit_execute_without_budget.py --json

    # Audit ALL routes (not only the RES-BE-015 sweep scope):
    python backend/scripts/audit_execute_without_budget.py --all-routes

Exit codes
----------

    0   no violations in the configured scope
    1   one or more violations found
    2   invalid invocation / IO error
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# Configuration: scope of the sweep (RES-BE-015 + RES-BE-001).
# ---------------------------------------------------------------------------

# Files in scope for the CI gate. Listed without the `routes/` prefix so the
# script can run from either the repo root or the `backend/` directory.
TARGET_ROUTES: tuple[str, ...] = (
    "blog_stats.py",
    "contratos_publicos.py",
    "empresa_publica.py",
    "orgao_publico.py",
    "observatorio.py",
    "dados_publicos.py",
    "municipios_publicos.py",
    "itens_publicos.py",
    "compliance_publicos.py",
    "alertas_publicos.py",
    "sectors_public.py",
)


# ---------------------------------------------------------------------------
# Violation record.
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    file: str
    line: int
    col: int
    kind: str  # "bare_execute" | "wait_for_to_thread"
    detail: str

    def format_human(self) -> str:
        return f"{self.file}:{self.line}:{self.col}: [{self.kind}] {self.detail}"


# ---------------------------------------------------------------------------
# AST helpers.
# ---------------------------------------------------------------------------


def _attr_chain(node: ast.AST) -> Optional[str]:
    """Return ``a.b.c`` for a chained ``Attribute`` node, else ``None``."""
    parts: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _is_call_to(node: ast.Call, *names: str) -> bool:
    """True iff ``node.func`` resolves to ``a.b...`` ending in any ``names``.

    Matches dotted names (``asyncio.wait_for``) and bare names (``wait_for``).
    """
    chain = _attr_chain(node.func) if isinstance(node.func, ast.Attribute) else None
    if chain is not None:
        for name in names:
            if chain == name or chain.endswith("." + name):
                return True
    if isinstance(node.func, ast.Name):
        for name in names:
            if node.func.id == name or name.endswith("." + node.func.id):
                return True
    return False


def _is_run_with_budget(node: ast.Call) -> bool:
    return _is_call_to(node, "_run_with_budget", "pipeline.budget._run_with_budget")


def _is_to_thread_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and _is_call_to(node, "asyncio.to_thread", "to_thread")
    )


# ---------------------------------------------------------------------------
# Visitors.
# ---------------------------------------------------------------------------


class _RouteVisitor(ast.NodeVisitor):
    """Walks a single route file and collects violations.

    Violations:
      1. ``wait_for_to_thread`` — ``asyncio.wait_for(asyncio.to_thread(...))``
         anywhere in the file. This pattern is unconditionally banned: the
         caller-side cancel does not release the Supabase connection. (See the
         module docstring.)
      2. ``bare_execute`` — a ``.execute()`` method call that:
         * is **not** wrapped by an enclosing ``_run_with_budget`` call, and
         * is **not** an argument to ``sb_execute(...)`` /
           ``sb_execute_direct(...)`` / ``await asyncio.to_thread(...)``-style
           helpers that already enforce a budget.
    """

    def __init__(self, file: str, source: str) -> None:
        self.file = file
        self._lines = source.splitlines()
        self.violations: list[Violation] = []
        # Stack of "in scope" guards: True iff a ``_run_with_budget`` call is
        # an *ancestor* of the current node (e.g. the visitor is inside the
        # awaitable being budgeted).
        self._budget_stack: list[bool] = []

    # -- core node walks --------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        # Pattern 1: asyncio.wait_for(asyncio.to_thread(...), ...)
        if _is_call_to(node, "asyncio.wait_for", "wait_for"):
            inner = node.args[0] if node.args else None
            if inner is not None and _is_to_thread_call(inner):
                self.violations.append(
                    Violation(
                        file=self.file,
                        line=node.lineno,
                        col=node.col_offset,
                        kind="wait_for_to_thread",
                        detail=(
                            "asyncio.wait_for(asyncio.to_thread(...)) — caller "
                            "cancel does not release the Supabase connection. "
                            "Use _run_with_budget(asyncio.to_thread(...), "
                            "budget=N) instead."
                        ),
                    )
                )

        # Pattern 2: bare .execute() not wrapped in _run_with_budget /
        # sb_execute / asyncio.to_thread.
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            and not node.args  # .execute() takes no positional args
            and not any(self._budget_stack)  # not inside _run_with_budget
        ):
            # Skip if this .execute() is itself the argument to a helper that
            # offloads to a thread (sb_execute / sb_execute_direct /
            # asyncio.to_thread / _run_with_budget). The visitor's budget_stack
            # only reflects ancestors; the immediate parent check is done via
            # ``_skip_by_parent`` in the wrapping pass below.
            self.violations.append(
                Violation(
                    file=self.file,
                    line=node.lineno,
                    col=node.col_offset,
                    kind="bare_execute",
                    detail=(
                        "bare .execute() in async route — wrap with "
                        "_run_with_budget(asyncio.to_thread(_sync_query), "
                        "budget=5.0, phase='route', source='<module>.<endpoint>'). "
                        "The sync supabase-py client blocks the event loop."
                    ),
                )
            )

        # Recurse — but mark "inside budget" if this call IS _run_with_budget.
        is_budget = _is_run_with_budget(node)
        self._budget_stack.append(is_budget)
        try:
            self.generic_visit(node)
        finally:
            self._budget_stack.pop()


def _strip_protected_executes(source: str, violations: list[Violation]) -> list[Violation]:
    """Second pass: drop ``bare_execute`` violations whose immediate textual
    context shows the caller IS already a protected helper.

    The AST visitor errs on the side of false positives because it cannot
    cheaply determine "this Call's parent is `sb_execute(...)` or
    `asyncio.to_thread(...)`" — those wrap the *whole call chain*, not just
    the trailing `.execute()`. We do a conservative line-window check:

    * If the line containing the `.execute()` is the *last* line of a call
      chain whose start is `sb_execute(` or `asyncio.to_thread(` or
      `await asyncio.to_thread(`, treat as protected.
    * If the bare `.execute()` is inside a sync `def _query_sync(...):`
      function (no `async`), it's by-design called via
      `asyncio.to_thread(_query_sync)` — treat as protected.

    Otherwise, the violation stands.
    """
    lines = source.splitlines()
    survivors: list[Violation] = []

    # Pre-compute for each line index, whether its enclosing function is
    # synchronous (def, not async def). This is a cheap line-scan upward.
    def _enclosing_def(line_no: int) -> Optional[tuple[str, int]]:
        """Walk upward to find the closest function definition. Returns
        (kind, indent) where kind is 'def' | 'async def'.
        """
        target_indent = None
        for i in range(line_no - 1, -1, -1):
            line = lines[i]
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(stripped)
            if target_indent is None:
                target_indent = indent
            if indent < target_indent and (
                stripped.startswith("def ") or stripped.startswith("async def ")
            ):
                kind = "async def" if stripped.startswith("async def") else "def"
                return (kind, indent)
            if indent == 0 and (
                stripped.startswith("def ") or stripped.startswith("async def ")
            ):
                kind = "async def" if stripped.startswith("async def") else "def"
                return (kind, indent)
        return None

    def _line_window_starts_with(line_no: int, prefixes: Iterable[str]) -> bool:
        """Look at the (up to) 25 lines preceding (and including) ``line_no``
        for an unindented ``await sb_execute(`` / ``asyncio.to_thread(`` /
        ``await asyncio.to_thread(`` opener that would textually wrap the
        ``.execute()`` at ``line_no``.
        """
        prefixes = tuple(prefixes)
        for i in range(max(0, line_no - 25), line_no):
            stripped = lines[i].strip()
            if any(stripped.startswith(p) for p in prefixes):
                return True
            # Also accept assignment forms: ``x = await sb_execute(``
            for p in prefixes:
                if f"= {p}" in stripped or f"=await {p}" in stripped or f"= await {p}" in stripped:
                    return True
        return False

    for v in violations:
        if v.kind != "bare_execute":
            survivors.append(v)
            continue

        enc = _enclosing_def(v.line)
        if enc is not None and enc[0] == "def":
            # Sync helper — caller is responsible for offloading via to_thread.
            continue

        if _line_window_starts_with(
            v.line,
            (
                "await sb_execute(",
                "sb_execute(",
                "await sb_execute_direct(",
                "sb_execute_direct(",
                "await asyncio.to_thread(",
                "asyncio.to_thread(",
                "await _run_with_budget(",
                "_run_with_budget(",
            ),
        ):
            continue

        survivors.append(v)

    return survivors


# ---------------------------------------------------------------------------
# Driver.
# ---------------------------------------------------------------------------


def _resolve_routes_dir() -> Path:
    """Find ``backend/routes`` relative to this script."""
    here = Path(__file__).resolve()
    # Script lives in backend/scripts/...
    backend_dir = here.parent.parent
    routes = backend_dir / "routes"
    if not routes.is_dir():
        raise SystemExit(f"routes directory not found at {routes}")
    return routes


def audit_file(path: Path) -> list[Violation]:
    """Audit a single Python file. Returns a list of violations."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"failed to read {path}: {exc}") from exc

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise SystemExit(f"syntax error in {path}: {exc}") from exc

    visitor = _RouteVisitor(file=str(path), source=source)
    visitor.visit(tree)
    return _strip_protected_executes(source, visitor.violations)


def audit_paths(paths: Iterable[Path]) -> list[Violation]:
    out: list[Violation] = []
    for p in paths:
        out.extend(audit_file(p))
    return out


def _select_files(args: argparse.Namespace) -> list[Path]:
    routes_dir = _resolve_routes_dir()

    if args.file:
        # Accept relative paths from repo root, backend/, or just basename.
        candidates: list[Path] = []
        raw = Path(args.file)
        candidates.append(raw)
        candidates.append(routes_dir / raw.name)
        candidates.append(routes_dir.parent / raw)
        for c in candidates:
            if c.is_file():
                return [c.resolve()]
        raise SystemExit(f"file not found: {args.file}")

    if args.all_routes:
        return sorted(p for p in routes_dir.glob("*.py") if p.name != "__init__.py")

    # Default: only the RES-BE-015 sweep scope.
    return [routes_dir / name for name in TARGET_ROUTES if (routes_dir / name).is_file()]


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit `.execute()` callsites in routes/ that lack _run_with_budget."
    )
    parser.add_argument("--file", help="Path to a single file (overrides default scope).")
    parser.add_argument(
        "--all-routes",
        action="store_true",
        help="Audit every routes/*.py (default: only RES-BE-015 scope).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object per line for machine consumers / CI annotations.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the human-readable summary; useful with --json.",
    )
    args = parser.parse_args(argv)

    files = _select_files(args)
    violations = audit_paths(files)

    # Stable, deterministic order.
    violations.sort(key=lambda v: (v.file, v.line, v.col, v.kind))

    if args.json:
        for v in violations:
            print(json.dumps(asdict(v), ensure_ascii=False))

    if not args.quiet:
        per_file: dict[str, int] = {}
        for v in violations:
            per_file[v.file] = per_file.get(v.file, 0) + 1
        if not args.json:
            for v in violations:
                print(v.format_human())
        if per_file:
            print()
            print(f"== Audit summary ({len(files)} files scanned) ==")
            for f in sorted(per_file):
                rel = os.path.relpath(f)
                print(f"  {rel}: {per_file[f]} violation(s)")
            print(f"  total: {sum(per_file.values())}")
        else:
            scope = "all routes" if args.all_routes else "RES-BE-015 scope"
            print(f"OK: zero violations across {len(files)} files ({scope}).")

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
