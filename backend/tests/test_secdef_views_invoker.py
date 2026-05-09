"""
SEC-VIEW-001: Static SQL analysis tests for the SECURITY INVOKER downgrade
of 3 public views flagged by the Supabase Database Linter.

Tests verify the migration SQL structure (UP + DOWN) — full RLS regression
against a live database is captured in `scripts/manual_test_secdef_views.sql`
and validated post-deploy via the Supabase advisor.

Memory `feedback_test_regex_invariant_semantic`: assertions check semantic
invariants (presence of ALTER VIEW SET, correct GRANT/REVOKE pattern per
view) rather than exact line text — resistant to whitespace/cosmetic edits.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
UP_FILE = MIGRATIONS_DIR / "20260509120000_sec_view_001_invoker_downgrade.sql"
DOWN_FILE = MIGRATIONS_DIR / "20260509120000_sec_view_001_invoker_downgrade.down.sql"

VIEWS = (
    "ingestion_orphan_checkpoints",
    "pncp_raw_bids_bloat_stats",
    "cron_job_health",
)


@pytest.fixture(scope="module")
def up_sql() -> str:
    assert UP_FILE.exists(), f"UP migration missing: {UP_FILE}"
    return UP_FILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def down_sql() -> str:
    assert DOWN_FILE.exists(), f"DOWN migration missing: {DOWN_FILE}"
    return DOWN_FILE.read_text(encoding="utf-8")


def _normalize(sql: str) -> str:
    """Collapse whitespace for tolerant matching."""
    return re.sub(r"\s+", " ", sql).strip()


# ──────────────────────────────────────────────────────────────────────
# AC1: UP migration — ALTER VIEW ... SET (security_invoker = true)
# ──────────────────────────────────────────────────────────────────────


class TestUpMigrationInvokerDowngrade:
    """Each of the 3 views must be downgraded to SECURITY INVOKER."""

    @pytest.mark.parametrize("view", VIEWS)
    def test_view_set_security_invoker_true(self, up_sql: str, view: str) -> None:
        normalized = _normalize(up_sql)
        # Tolerant pattern: optional whitespace around `=`.
        pattern = rf"ALTER VIEW public\.{re.escape(view)} SET \( ?security_invoker ?= ?true ?\)"
        assert re.search(pattern, normalized, re.IGNORECASE), (
            f"UP migration must contain `ALTER VIEW public.{view} SET (security_invoker = true)`"
        )

    def test_no_create_or_replace_view(self, up_sql: str) -> None:
        """Sanity: do not redefine the views — only ALTER their reloptions."""
        assert "CREATE OR REPLACE VIEW" not in up_sql.upper(), (
            "UP migration should ONLY ALTER existing views, not redefine them. "
            "Redefining loses the original column list / comments."
        )


# ──────────────────────────────────────────────────────────────────────
# AC2: GRANT alignment per view
# ──────────────────────────────────────────────────────────────────────


class TestGrantAlignment:
    """Per-view privilege posture after downgrade."""

    def test_bloat_stats_revoked_from_authenticated(self, up_sql: str) -> None:
        assert re.search(
            r"REVOKE\s+ALL\s+ON\s+public\.pncp_raw_bids_bloat_stats\s+FROM\s+authenticated",
            up_sql,
            re.IGNORECASE,
        ), "bloat_stats must REVOKE ALL FROM authenticated (admin diagnostic only)"

    def test_bloat_stats_revoked_from_anon(self, up_sql: str) -> None:
        assert re.search(
            r"REVOKE\s+ALL\s+ON\s+public\.pncp_raw_bids_bloat_stats\s+FROM\s+anon",
            up_sql,
            re.IGNORECASE,
        ), "bloat_stats must REVOKE ALL FROM anon"

    def test_bloat_stats_granted_to_service_role(self, up_sql: str) -> None:
        assert re.search(
            r"GRANT\s+SELECT\s+ON\s+public\.pncp_raw_bids_bloat_stats\s+TO\s+service_role",
            up_sql,
            re.IGNORECASE,
        ), "bloat_stats must remain readable by service_role"

    def test_cron_job_health_revoked_from_authenticated(self, up_sql: str) -> None:
        assert re.search(
            r"REVOKE\s+ALL\s+ON\s+public\.cron_job_health\s+FROM\s+authenticated",
            up_sql,
            re.IGNORECASE,
        ), "cron_job_health must REVOKE ALL FROM authenticated"

    def test_cron_job_health_revoked_from_anon(self, up_sql: str) -> None:
        assert re.search(
            r"REVOKE\s+ALL\s+ON\s+public\.cron_job_health\s+FROM\s+anon",
            up_sql,
            re.IGNORECASE,
        ), "cron_job_health must REVOKE ALL FROM anon"

    def test_cron_job_health_granted_to_service_role(self, up_sql: str) -> None:
        assert re.search(
            r"GRANT\s+SELECT\s+ON\s+public\.cron_job_health\s+TO\s+service_role",
            up_sql,
            re.IGNORECASE,
        ), "cron_job_health must remain readable by service_role"

    def test_orphan_checkpoints_keeps_authenticated_path(self, up_sql: str) -> None:
        """
        ingestion_orphan_checkpoints relies on RLS of underlying app tables.
        UP must NOT REVOKE FROM authenticated — RLS remains the gate.
        """
        # Look at all REVOKE statements in the migration
        revokes_against_view = re.findall(
            r"REVOKE\s+\w+\s+ON\s+public\.ingestion_orphan_checkpoints",
            up_sql,
            re.IGNORECASE,
        )
        assert not revokes_against_view, (
            "ingestion_orphan_checkpoints must keep its existing GRANT; RLS on "
            "ingestion_checkpoints/ingestion_runs is the access gate."
        )


# ──────────────────────────────────────────────────────────────────────
# AC1 (cont): DOWN migration restores prior posture
# ──────────────────────────────────────────────────────────────────────


class TestDownMigrationRollback:
    """DOWN migration must reverse the UP changes (STORY-6.2 mandatory)."""

    @pytest.mark.parametrize("view", VIEWS)
    def test_view_reverted_to_security_invoker_false(
        self, down_sql: str, view: str
    ) -> None:
        normalized = _normalize(down_sql)
        pattern = rf"ALTER VIEW public\.{re.escape(view)} SET \( ?security_invoker ?= ?false ?\)"
        assert re.search(pattern, normalized, re.IGNORECASE), (
            f"DOWN migration must contain `ALTER VIEW public.{view} SET (security_invoker = false)`"
        )

    def test_down_restores_bloat_stats_authenticated_grant(
        self, down_sql: str
    ) -> None:
        assert re.search(
            r"GRANT\s+SELECT\s+ON\s+public\.pncp_raw_bids_bloat_stats\s+TO\s+authenticated",
            down_sql,
            re.IGNORECASE,
        ), "DOWN must restore the original authenticated GRANT on bloat_stats"

    def test_down_restores_cron_job_health_authenticated_grant(
        self, down_sql: str
    ) -> None:
        # Original migration had no explicit GRANT, but rollback to "broader"
        # state is intentional (lets future advisor lint re-flag clearly).
        assert re.search(
            r"GRANT\s+SELECT\s+ON\s+public\.cron_job_health\s+TO\s+authenticated",
            down_sql,
            re.IGNORECASE,
        ), "DOWN must restore broader access on cron_job_health"


# ──────────────────────────────────────────────────────────────────────
# Sanity: pair of files exists with matching basename (STORY-6.2)
# ──────────────────────────────────────────────────────────────────────


class TestMigrationPairing:
    def test_up_and_down_files_exist(self) -> None:
        assert UP_FILE.exists(), f"UP file missing: {UP_FILE}"
        assert DOWN_FILE.exists(), f"DOWN file missing: {DOWN_FILE}"

    def test_paired_basename(self) -> None:
        """UP and DOWN must share the same timestamp+slug prefix."""
        up_stem = UP_FILE.name.replace(".sql", "")
        down_stem = DOWN_FILE.name.replace(".down.sql", "")
        assert up_stem == down_stem, (
            f"UP/DOWN basename mismatch: {up_stem!r} vs {down_stem!r}"
        )
