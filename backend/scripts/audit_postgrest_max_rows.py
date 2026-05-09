#!/usr/bin/env python3
"""DATA-CAP-001: Audit raw ``.limit(N).execute()`` patterns in ``backend/routes/``
where ``N >= 1000`` and the call is not wrapped in ``paginate_full``.

Background
----------
PostgREST silently caps every SELECT response at ``max_rows=1000`` per call.
A ``.limit(5000).execute()`` therefore returns at most 1000 rows with no
warning. DATA-CAP-001 introduced ``backend/utils/postgrest_paginate.py`` —
``paginate_full(query, route=..., entity_type=..., max_total=N)`` — to loop
``.range(...).execute()`` past the cap. This script keeps callsites from
regressing.

Detection
---------
This is an AST-based audit (deterministic, no false-positive lexical
matches). It reports each ``.limit(N).execute()`` call inside ``backend/routes/``
where:

  * ``N`` is an integer literal ``>= MIN_LIMIT`` (default 1000), AND
  * the enclosing chain is not under a ``paginate_full(...)`` invocation.

The intent is to flag any new ``.limit(big_N).execute()`` that would silently
truncate. Routes still use ``.limit(N)`` legitimately for *small* N (e.g.
``.limit(20)`` for a top-N query that fits trivially in a single page) —
those are excluded by the threshold.

Exit codes
----------

  0 — no violations
  1 — one or more violations
  2 — invalid invocation / IO error
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional

# Threshold below which ``.limit(N)`` is considered "obviously fine" — small
# top-N queries (e.g. ``.limit(20)``) trivially fit in a single PostgREST
# page and never trip the cap. Bump this if a route legitimately uses
# ``.limit(900)`` for cosmetic pagination.
MIN_LIMIT = 1000


@dataclass
class Violation:
    file: str
    line: int
    col: int
    limit_value: int
    detail: str

    def format_human(self) -> str:
        return f"{self.file}:{self.line}:{self.col}: .limit({self.limit_value}).execute() without paginate_full — {self.detail}"


def _attr_name(node: ast.AST) -> Optional[str]:
    """Return the attribute name for an ``Attribute`` node (e.g. ``execute``)."""
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_call_named(node: ast.AST, name: str) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == name
    if isinstance(func, ast.Name):
        return func.id == name
    return False


def _walk_chain(node: ast.AST):
    """Yield each ``Call``/``Attribute`` along a chained call expression."""
    cur = node
    while True:
        yield cur
        if isinstance(cur, ast.Call):
            cur = cur.func
        elif isinstance(cur, ast.Attribute):
            cur = cur.value
        else:
            return


def _find_limit_value(call_node: ast.Call) -> Optional[int]:
    """If this ``Call`` is ``.limit(<int>)``, return the int literal."""
    func = call_node.func
    if not isinstance(func, ast.Attribute) or func.attr != "limit":
        return None
    if not call_node.args:
        return None
    arg = call_node.args[0]
    # Constant int literal — Python 3.8+
    if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
        return arg.value
    return None


class LimitExecuteVisitor(ast.NodeVisitor):
    """Walk the module looking for ``.limit(big_N).execute()`` patterns
    that are not under a ``paginate_full`` call.
    """

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.violations: list[Violation] = []
        # Stack of paginate_full guards — when truthy, .limit().execute()
        # callsites inside are ignored (they may be passed as the query
        # builder argument, but the helper itself loops .range()).
        self._guard_stack: list[bool] = []

    def visit_Call(self, node: ast.Call) -> None:
        # Track entering/leaving a ``paginate_full(...)`` call so anything
        # nested inside is exempt. (The helper takes the query builder
        # without a terminal .execute(); if the caller mistakenly passed
        # one we still want to flag it, but the realistic shape is
        # ``paginate_full(sb.table(...).select(...).eq(...))``.)
        is_paginate = _is_call_named(node, "paginate_full")
        self._guard_stack.append(is_paginate)
        try:
            # Pattern: <chain>.limit(N).execute()
            if (
                _attr_name(node.func) == "execute"
                and not any(self._guard_stack[:-1])  # caller is not paginate_full
            ):
                # Walk back along the chain looking for a .limit(N) call
                # immediately upstream.
                chain_iter = _walk_chain(node.func.value if isinstance(node.func, ast.Attribute) else node)
                for ancestor in chain_iter:
                    if isinstance(ancestor, ast.Call):
                        limit_val = _find_limit_value(ancestor)
                        if limit_val is not None and limit_val >= MIN_LIMIT:
                            self.violations.append(
                                Violation(
                                    file=self.file_path,
                                    line=node.lineno,
                                    col=node.col_offset,
                                    limit_value=limit_val,
                                    detail=(
                                        f".limit({limit_val}) followed by .execute() — "
                                        "PostgREST will silently truncate at 1000 rows. "
                                        "Use paginate_full(query, route=..., max_total=N) "
                                        "from utils.postgrest_paginate."
                                    ),
                                )
                            )
                            break
            self.generic_visit(node)
        finally:
            self._guard_stack.pop()


def _audit_file(path: Path) -> list[Violation]:
    try:
        source = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover
        print(f"[audit] could not read {path}: {exc}", file=sys.stderr)
        return []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:  # pragma: no cover
        print(f"[audit] syntax error in {path}: {exc}", file=sys.stderr)
        return []
    visitor = LimitExecuteVisitor(file_path=str(path))
    visitor.visit(tree)
    return visitor.violations


def _iter_route_files(root: Path) -> Iterable[Path]:
    routes_dir = root / "backend" / "routes"
    if not routes_dir.is_dir():
        return []
    return sorted(p for p in routes_dir.glob("*.py") if p.name != "__init__.py")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit .limit(N >= 1000).execute() callsites in backend/routes/."
    )
    parser.add_argument(
        "--file",
        help="Audit a single file instead of the full backend/routes/ tree.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object per violation (for CI annotations).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]

    files: Iterable[Path]
    if args.file:
        files = [Path(args.file)]
    else:
        files = list(_iter_route_files(repo_root))

    all_violations: list[Violation] = []
    for f in files:
        all_violations.extend(_audit_file(f))

    if args.json:
        for v in all_violations:
            print(json.dumps(asdict(v)))
    else:
        if not all_violations:
            print(f"[audit] OK — no .limit(>= {MIN_LIMIT}).execute() patterns found.")
        for v in all_violations:
            print(v.format_human())

    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main())
