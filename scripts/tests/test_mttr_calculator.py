"""Tests for scripts/mttr_calculator.py (OPS-MTTR-001 / issue #970)."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure scripts/ is importable when running pytest from any cwd.
SCRIPTS_DIR = Path(__file__).parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import mttr_calculator as mc  # noqa: E402


def test_parse_log_lines_extracts_status_and_path():
    lines = [
        "2026-05-09T19:55:00 GET /buscar 500 100ms",
        "2026-05-09T19:58:00 GET /buscar 200 80ms",
        "noise that should be ignored",
        "2026-05-09T20:00:00 POST /v1/sessions/abc12345 201 12ms",
    ]
    events = mc.parse_log_lines(lines)
    assert len(events) == 3
    paths = [path for _, path, _ in events]
    statuses = [status for _, _, status in events]
    assert "/buscar" in paths
    # uuid-ish segment normalized to :id placeholder
    assert "/v1/sessions/:id" in paths
    assert 500 in statuses and 200 in statuses and 201 in statuses


def test_compute_mttr_finds_5xx_to_2xx_transition():
    lines = mc.SAMPLE_LOG.splitlines()
    events = mc.parse_log_lines(lines)
    # Anchor "now" inside the sample window so 7d rolling captures all.
    now = datetime(2026, 5, 9, 21, 0, 0, tzinfo=timezone.utc)
    summary = mc.compute_mttr(events, window_days=7, now=now)

    assert "/buscar" in summary
    # /buscar has two recoveries: ~3min (19:55→19:58) and 45min (10:00→10:45 on 2026-05-08)
    assert summary["/buscar"]["incidents"] == 2
    # /health/ready has one 5min recovery
    assert "/health/ready" in summary
    assert summary["/health/ready"]["incidents"] == 1
    assert 290 <= summary["/health/ready"]["mttr_seconds"] <= 310


def test_render_markdown_flags_slo_breach():
    summary = {
        "/buscar": {"incidents": 1, "mttr_seconds": 45 * 60, "max_seconds": 45 * 60},
        "/health/ready": {"incidents": 1, "mttr_seconds": 5 * 60, "max_seconds": 5 * 60},
    }
    report, breach = mc.render_markdown(summary, window_days=7)
    assert breach is True
    assert "BREACH" in report
    assert "PASS" in report  # /health/ready under 30min SLO
    assert "/buscar" in report


def test_render_markdown_no_data():
    report, breach = mc.render_markdown({}, window_days=7)
    assert breach is False
    assert "No 5xx" in report


def test_normalize_path_collapses_numeric_and_uuid():
    assert mc.normalize_path("/api/users/12345") == "/api/users/:id"
    assert mc.normalize_path("/api/orders/abc12345?x=1") == "/api/orders/:id"
    assert mc.normalize_path("/buscar") == "/buscar"
    assert mc.normalize_path("/") == "/"


def test_main_sample_runs_clean(capsys):
    rc = mc.main(["--sample"])
    captured = capsys.readouterr()
    # Sample yields /buscar mean 24min (under 30) and /health/ready 5min → both PASS.
    assert rc == 0
    assert "MTTR Report" in captured.out
    assert "/buscar" in captured.out
    assert "PASS" in captured.out
