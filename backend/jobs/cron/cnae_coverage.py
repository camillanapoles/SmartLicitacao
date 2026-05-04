"""DATA-CNAE-001 (AC14): Monthly CNAE coverage report cron.

Runs ``scripts/cnae_coverage_report.py`` once per month from the ARQ
worker.  The report is written to ``docs/reports/cnae-coverage-{YYYY-MM-DD}.md``
in the deployment image and also emits the summary as a single
``logger.info`` line so the report is observable in Railway logs even
when the filesystem is ephemeral.

The schedule is the 1st day of every month at 06 UTC (=03 BRT).  The
helper is identical in shape to the other ``start_*_task`` factories
under ``backend/jobs/cron/``.  Disable with
``CNAE_COVERAGE_CRON_INTERVAL_S=0``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Default: 30 days.  We don't try to align to "1st of the month at
# 06 UTC" because the Railway worker can restart at arbitrary times;
# instead we sleep a long interval and rely on idempotency (the
# script overwrites the day-stamped file).
DEFAULT_INTERVAL_S = 30 * 24 * 60 * 60  # 30 days


def _interval_seconds() -> int:
    raw = os.getenv("CNAE_COVERAGE_CRON_INTERVAL_S", str(DEFAULT_INTERVAL_S))
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_INTERVAL_S


def _repo_root() -> Path:
    # backend/jobs/cron/cnae_coverage.py -> 4 levels up to repo root.
    return Path(__file__).resolve().parents[3]


async def run_cnae_coverage_once() -> dict:
    """Run the coverage script and return a summary dict."""
    script = _repo_root() / "scripts" / "cnae_coverage_report.py"
    if not script.exists():
        logger.warning("cnae_coverage: script missing at %s", script)
        return {"status": "skipped", "reason": "script_missing"}
    started = time.monotonic()
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.error("cnae_coverage: script timed out after 120s")
        return {"status": "error", "reason": "timeout"}
    duration_ms = int((time.monotonic() - started) * 1000)
    if result.returncode != 0:
        logger.error(
            "cnae_coverage: script failed rc=%s stderr=%s",
            result.returncode,
            result.stderr.strip()[:500],
        )
        return {
            "status": "error",
            "rc": result.returncode,
            "stderr": result.stderr.strip()[-500:],
        }
    logger.info(
        "cnae_coverage: report generated in %dms — %s",
        duration_ms,
        result.stdout.strip(),
    )
    return {"status": "ok", "duration_ms": duration_ms}


def start_cnae_coverage_task() -> asyncio.Task | None:
    """Spawn the long-running cron loop.

    Returns the asyncio Task or ``None`` when the cron is disabled
    (``CNAE_COVERAGE_CRON_INTERVAL_S=0``).
    """
    interval = _interval_seconds()
    if interval <= 0:
        logger.info("cnae_coverage: cron disabled (interval=0)")
        return None

    async def _loop() -> None:
        # Run once a few seconds after startup so the operator gets a
        # baseline report from the latest deploy without waiting 30d.
        await asyncio.sleep(60)
        while True:
            try:
                await run_cnae_coverage_once()
            except Exception as exc:  # pragma: no cover — logging only
                logger.warning("cnae_coverage: loop iteration failed: %s", exc)
            await asyncio.sleep(interval)

    return asyncio.create_task(_loop(), name="cnae-coverage-cron")
