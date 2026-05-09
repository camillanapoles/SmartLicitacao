"""Tests for ``backend/scripts/audit_response_model_coverage.py``.

The audit script is the data source for the future CI gate (AC3 of
PARITY-BE-FE-001) so the unit tests focus on three properties:

1. **Detection** — the AST walker correctly counts ``@router.<verb>(...)``
   decorators with and without ``response_model=``.
2. **Reproducibility** — the JSON output uses repository-relative paths
   so the baseline file stays stable across CI checkouts and worktrees.
3. **Gate semantics** — ``--check-against`` flips to exit code 1 only on
   genuine regressions (decreased typed-route count, lowered global
   coverage, or new untyped routes in a new file). Same-or-better
   never trips the gate.

The tests construct synthetic route modules in a tmp directory rather
than importing the real backend routes — keeps the tests hermetic and
independent of in-flight backfills.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# The audit script lives at backend/scripts/. Tests run with backend/
# on sys.path (via conftest), so we add scripts/ explicitly here.
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import audit_response_model_coverage as audit  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


SAMPLE_TYPED = '''\
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class FooResponse(BaseModel):
    ok: bool


@router.get("/foo", response_model=FooResponse)
async def get_foo() -> FooResponse:
    return FooResponse(ok=True)


@router.post("/bar", response_model=FooResponse)
async def post_bar() -> FooResponse:
    return FooResponse(ok=True)
'''


SAMPLE_MIXED = '''\
from fastapi import APIRouter

router = APIRouter()


@router.get("/typed", response_model=dict)
async def typed_one():
    return {}


@router.get("/untyped")
async def untyped_one():
    return {}


@router.post("/also-untyped")
async def untyped_two():
    return {}
'''


SAMPLE_HELPER = '''\
"""Pure helper module — no @router.* decorators."""

CONSTANT = 42


def helper(x: int) -> int:
    return x + 1
'''


SAMPLE_NAMED_ROUTER = '''\
from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/named", response_model=dict)
async def named():
    return {}


@api_router.delete("/named-untyped")
async def named_untyped():
    return {}
'''


@pytest.fixture
def routes_dir(tmp_path: Path) -> Path:
    """Build a synthetic backend/routes/ directory."""
    d = tmp_path / "routes"
    d.mkdir()
    (d / "all_typed.py").write_text(SAMPLE_TYPED)
    (d / "mixed.py").write_text(SAMPLE_MIXED)
    (d / "helper.py").write_text(SAMPLE_HELPER)
    (d / "named.py").write_text(SAMPLE_NAMED_ROUTER)
    return d


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def test_audit_file_counts_typed_routes(tmp_path: Path) -> None:
    p = tmp_path / "x.py"
    p.write_text(SAMPLE_TYPED)
    report = audit.audit_file(p)
    assert report.router_count == 2
    assert report.response_model_count == 2
    assert report.coverage_pct == 100.0
    assert report.missing_paths == []


def test_audit_file_counts_mixed(tmp_path: Path) -> None:
    p = tmp_path / "x.py"
    p.write_text(SAMPLE_MIXED)
    report = audit.audit_file(p)
    assert report.router_count == 3
    assert report.response_model_count == 1
    assert report.coverage_pct == pytest.approx(33.33, abs=0.01)
    assert report.missing_paths == ["/untyped", "/also-untyped"]


def test_audit_file_helper_excluded(tmp_path: Path) -> None:
    p = tmp_path / "helper.py"
    p.write_text(SAMPLE_HELPER)
    report = audit.audit_file(p)
    assert report.router_count == 0
    # helper coverage is "100% vacuously" — the aggregator skips it.
    assert report.coverage_pct == 100.0


def test_audit_recognizes_named_router(tmp_path: Path) -> None:
    """Names ending in ``_router`` (e.g. ``api_router``) are accepted."""
    p = tmp_path / "named.py"
    p.write_text(SAMPLE_NAMED_ROUTER)
    report = audit.audit_file(p)
    assert report.router_count == 2
    assert report.response_model_count == 1


def test_audit_skips_unrelated_decorators(tmp_path: Path) -> None:
    p = tmp_path / "x.py"
    p.write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n\n"
        "@property\n"
        "def foo(self): return 1\n\n"
        "@router.get('/x', response_model=dict)\n"
        "async def get_x(): return {}\n"
    )
    report = audit.audit_file(p)
    assert report.router_count == 1


def test_audit_skips_websocket(tmp_path: Path) -> None:
    """``@router.websocket(...)`` is not counted (no response_model in OpenAPI)."""
    p = tmp_path / "x.py"
    p.write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n\n"
        "@router.websocket('/ws')\n"
        "async def ws(): pass\n\n"
        "@router.get('/x', response_model=dict)\n"
        "async def get_x(): return {}\n"
    )
    report = audit.audit_file(p)
    assert report.router_count == 1


def test_audit_response_model_none_counts_as_typed(tmp_path: Path) -> None:
    """``response_model=None`` is the documented escape hatch (story AC2);
    the kwarg presence — not its value — is what the audit checks for.
    """
    p = tmp_path / "x.py"
    p.write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n\n"
        "@router.get('/raw', response_model=None)\n"
        "async def raw(): return b'...'\n"
    )
    report = audit.audit_file(p)
    assert report.router_count == 1
    assert report.response_model_count == 1


def test_audit_skips_broken_files(tmp_path: Path) -> None:
    """A SyntaxError must not abort the audit."""
    p = tmp_path / "broken.py"
    p.write_text("def (): not python\n")
    report = audit.audit_file(p)
    assert report.router_count == 0  # graceful empty


# ---------------------------------------------------------------------------
# Aggregation + JSON shape
# ---------------------------------------------------------------------------


def test_audit_routes_dir_uses_relative_paths(routes_dir: Path) -> None:
    reports = audit.audit_routes_dir(routes_dir)
    files = {r.file for r in reports}
    # Always rendered as backend/routes/<name>.py for reproducibility.
    assert files == {
        "backend/routes/all_typed.py",
        "backend/routes/mixed.py",
        "backend/routes/helper.py",
        "backend/routes/named.py",
    }


def test_aggregate_excludes_helpers(routes_dir: Path) -> None:
    reports = audit.audit_routes_dir(routes_dir)
    summary = audit.aggregate(reports)

    assert summary["summary"]["files_with_routes"] == 3
    # all_typed (2) + mixed (3) + named (2) = 7
    assert summary["summary"]["total_routes"] == 7
    # all_typed (2) + mixed (1) + named (1) = 4
    assert summary["summary"]["total_with_response_model"] == 4
    assert summary["summary"]["coverage_pct"] == pytest.approx(57.14, abs=0.01)
    assert "backend/routes/helper.py" in summary["summary"]["helper_files_excluded"]


def test_render_table_includes_coverage(routes_dir: Path) -> None:
    summary = audit.aggregate(audit.audit_routes_dir(routes_dir))
    out = audit.render_table(summary)
    assert "response_model coverage" in out
    assert "57.14" in out
    assert "/untyped" in out
    assert "/also-untyped" in out


def test_main_writes_json_with_sorted_keys(
    routes_dir: Path, tmp_path: Path
) -> None:
    """JSON baseline must be deterministic — sort_keys=True keeps diffs minimal."""
    out = tmp_path / "baseline.json"
    rc = audit.main(["--routes-dir", str(routes_dir), "--json", str(out)])
    assert rc == 0
    raw = out.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    # sort_keys=True means the literal output is the canonical re-dump.
    canonical = json.dumps(parsed, indent=2, sort_keys=True) + "\n"
    assert raw == canonical


# ---------------------------------------------------------------------------
# Gate semantics (--check-against)
# ---------------------------------------------------------------------------


def test_check_against_self_passes(routes_dir: Path, tmp_path: Path) -> None:
    """Re-running the audit against its own snapshot is a no-op (exit 0)."""
    baseline = tmp_path / "baseline.json"
    audit.main(["--routes-dir", str(routes_dir), "--json", str(baseline)])
    rc = audit.main(
        ["--routes-dir", str(routes_dir), "--check-against", str(baseline)]
    )
    assert rc == 0


def test_check_against_detects_regression(
    routes_dir: Path, tmp_path: Path
) -> None:
    """Removing ``response_model=`` from an existing route must trip the gate."""
    baseline = tmp_path / "baseline.json"
    audit.main(["--routes-dir", str(routes_dir), "--json", str(baseline)])

    # Regression: drop response_model from the all-typed file.
    (routes_dir / "all_typed.py").write_text(
        SAMPLE_TYPED.replace(", response_model=FooResponse", "")
    )
    rc = audit.main(
        ["--routes-dir", str(routes_dir), "--check-against", str(baseline)]
    )
    assert rc == 1


def test_check_against_detects_new_untyped_file(
    routes_dir: Path, tmp_path: Path
) -> None:
    """Adding a new file with untyped routes must trip the gate."""
    baseline = tmp_path / "baseline.json"
    audit.main(["--routes-dir", str(routes_dir), "--json", str(baseline)])

    (routes_dir / "new_untyped.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n\n"
        "@router.get('/new')\n"
        "async def new(): return {}\n"
    )
    rc = audit.main(
        ["--routes-dir", str(routes_dir), "--check-against", str(baseline)]
    )
    assert rc == 1


def test_check_against_allows_improvement(
    routes_dir: Path, tmp_path: Path
) -> None:
    """Adding response_model to a previously-untyped route must NOT trip."""
    baseline = tmp_path / "baseline.json"
    audit.main(["--routes-dir", str(routes_dir), "--json", str(baseline)])

    # Improvement: type up the previously-untyped routes in mixed.py.
    (routes_dir / "mixed.py").write_text(
        SAMPLE_MIXED.replace(
            "@router.get(\"/untyped\")",
            "@router.get(\"/untyped\", response_model=dict)",
        ).replace(
            "@router.post(\"/also-untyped\")",
            "@router.post(\"/also-untyped\", response_model=dict)",
        )
    )
    rc = audit.main(
        ["--routes-dir", str(routes_dir), "--check-against", str(baseline)]
    )
    assert rc == 0


# ---------------------------------------------------------------------------
# Real repository invariant — sanity check, not a coverage assertion.
# ---------------------------------------------------------------------------


def test_real_admin_routes_are_fully_typed_pass1() -> None:
    """PARITY-BE-FE-001 Pass 1 lives-or-dies on these three files.

    If a future PR drops response_model from an admin route the test
    fails immediately, before the coverage gate even runs.
    """
    backend_routes = Path(__file__).resolve().parents[2] / "routes"
    pass1_files = {"admin_trace.py", "admin_cron.py", "admin_llm_cost.py"}
    for name in pass1_files:
        report = audit.audit_file(backend_routes / name)
        assert report.router_count > 0, f"{name} should have routes"
        assert report.coverage_pct == 100.0, (
            f"{name} regressed: {report.coverage_pct}%, missing={report.missing_paths}"
        )
