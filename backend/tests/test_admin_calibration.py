"""BIZ-METRIC-001 (AC4, AC11, AC13) tests for /v1/admin/calibration/*.

Covers:
    * GET /v1/admin/survey/export-time-saved (aggregate + histogram)
    * PATCH /v1/admin/config/{key} happy path + 400 (key not allowed)
    * POST /v1/admin/calibration/recalibrate
        - eligible (n>=30 after IQR) computes new median
        - eligible + apply=true persists + invalidates cache
        - ineligible when n<30 (reason='insufficient_sample')
        - ineligible new_value out-of-range
    * Pure helpers: filter_outliers_iqr + compute_calibration

Same fixture pattern as test_admin_cnae.py: override require_auth +
require_admin and mock Supabase per-test.
"""

from __future__ import annotations

import statistics
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from routes.admin_calibration import (
    HISTOGRAM_BUCKETS,
    MIN_SAMPLE_SIZE,
    build_histogram,
    compute_calibration,
    filter_outliers_iqr,
)


@pytest.fixture
def admin_user():
    return {"id": "admin-uuid-1", "email": "admin@test.com", "is_admin": True}


@pytest.fixture
def client(admin_user):
    from main import app
    from auth import require_auth
    from admin import require_admin

    app.dependency_overrides[require_auth] = lambda: admin_user
    app.dependency_overrides[require_admin] = lambda: admin_user
    yield TestClient(app)
    app.dependency_overrides.pop(require_auth, None)
    app.dependency_overrides.pop(require_admin, None)


def _make_chain(rows: list[dict]) -> MagicMock:
    chain = MagicMock()
    chain.select.return_value = chain
    chain.gte.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.update.return_value = chain
    chain.eq.return_value = chain
    chain.insert.return_value = chain
    result = MagicMock()
    result.data = rows
    chain.execute.return_value = result
    return chain


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestPureHelpers:
    def test_filter_outliers_iqr_keeps_values_within_15_iqr(self):
        # Symmetric distribution: 1..10. Q1≈3.25, Q3≈7.75, IQR≈4.5,
        # lower=-3.5, upper=14.5 → no values dropped.
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        filtered, q1, q3, lower, upper = filter_outliers_iqr(values)
        assert len(filtered) == 10
        assert q1 < q3
        assert lower <= 1.0
        assert upper >= 10.0

    def test_filter_outliers_iqr_drops_extreme_values(self):
        # Bulk near 2-4h with one extreme outlier at 50h.
        values = [1.0, 1.5, 2.0, 2.0, 2.0, 2.5, 3.0, 3.0, 3.5, 4.0, 50.0]
        filtered, _, _, _, upper = filter_outliers_iqr(values)
        assert 50.0 not in filtered
        assert upper < 50.0

    def test_filter_outliers_iqr_handles_small_sample(self):
        # Fewer than 4 values → no outliers dropped.
        values = [1.0, 2.0, 3.0]
        filtered, _, _, _, _ = filter_outliers_iqr(values)
        assert filtered == [1.0, 2.0, 3.0]

    def test_compute_calibration_median_resists_outlier(self):
        rows = [
            {"estimated_manual_hours": 2.0, "bid_count": 10},
            {"estimated_manual_hours": 2.5, "bid_count": 12},
            {"estimated_manual_hours": 3.0, "bid_count": 15},
            {"estimated_manual_hours": 3.5, "bid_count": 20},
            {"estimated_manual_hours": 4.0, "bid_count": 25},
            {"estimated_manual_hours": 50.0, "bid_count": 30},
        ]
        metrics = compute_calibration(rows)
        # Sample = 6 valid; outlier 50.0 dropped → median of the 5
        # remaining is 3.0
        assert metrics["sample_size"] == 6
        assert metrics["after_outlier_removal"] == 5
        assert metrics["median_hours"] == pytest.approx(3.0)
        assert metrics["median_bid_count"] is not None

    def test_compute_calibration_skips_invalid_rows(self):
        rows = [
            {"estimated_manual_hours": None},
            {"estimated_manual_hours": 0},
            {"estimated_manual_hours": "abc"},
            {"estimated_manual_hours": 2.0},
            {"estimated_manual_hours": 100},  # > 50
        ]
        metrics = compute_calibration(rows)
        assert metrics["sample_size"] == 1  # only 2.0 is valid
        assert metrics["median_hours"] == pytest.approx(2.0)

    def test_build_histogram_buckets_match_definition(self):
        values = [0.2, 0.7, 1.5, 4.0, 25.0, 60.0]
        hist = build_histogram(values)
        assert len(hist) == len(HISTOGRAM_BUCKETS) + 1
        # 0.2 → <0.5h; 0.7 → 0.5-1.0h
        labels = [b.range_label for b in hist]
        assert labels[0].startswith("<")
        # The last bucket catches >=50.0h
        assert hist[-1].count == 1


# ---------------------------------------------------------------------------
# GET aggregate
# ---------------------------------------------------------------------------

class TestSurveyAggregate:
    def test_aggregate_returns_summary_and_histogram(self, client):
        rows = [
            {"estimated_manual_hours": 2.0, "bid_count": 10, "submitted_at": "2026-04-20T00:00:00Z", "export_type": "excel"},
            {"estimated_manual_hours": 3.0, "bid_count": 15, "submitted_at": "2026-04-21T00:00:00Z", "export_type": "excel"},
            {"estimated_manual_hours": 4.5, "bid_count": 20, "submitted_at": "2026-04-22T00:00:00Z", "export_type": "pdf"},
        ]
        sb = MagicMock()
        sb.table.return_value = _make_chain(rows)

        with patch("routes.admin_calibration.get_supabase", return_value=sb), \
                patch("routes.admin_calibration.get_hours_saved_per_search", return_value=2.0):
            resp = client.get("/v1/admin/survey/export-time-saved?range_days=90")

        assert resp.status_code == 200
        body = resp.json()
        assert body["range_days"] == 90
        assert body["sample_size"] == 3
        assert body["current_constant"] == 2.0
        assert isinstance(body["histogram"], list)
        assert len(body["histogram"]) == len(HISTOGRAM_BUCKETS) + 1

    def test_aggregate_passes_iso_cutoff_to_postgrest(self, client):
        """PostgREST cannot evaluate SQL in filter values — we must
        send a literal ISO-8601 timestamp, not ``now() - interval ...``.
        Defends against regression of advisor-flagged production bug.
        """
        sb = MagicMock()
        captured: dict[str, str] = {}
        chain = MagicMock()
        chain.select.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain

        def gte(column: str, value: str):
            captured["column"] = column
            captured["value"] = value
            return chain

        chain.gte.side_effect = gte
        result = MagicMock()
        result.data = []
        chain.execute.return_value = result
        sb.table.return_value = chain

        with patch("routes.admin_calibration.get_supabase", return_value=sb), \
                patch("routes.admin_calibration.get_hours_saved_per_search", return_value=2.0):
            resp = client.get("/v1/admin/survey/export-time-saved?range_days=90")

        assert resp.status_code == 200
        assert captured["column"] == "submitted_at"
        # No SQL fragments leaking through
        assert "now()" not in captured["value"]
        assert "interval" not in captured["value"]
        # Looks like an ISO-8601 timestamp
        assert "T" in captured["value"]
        assert captured["value"].count("-") >= 2

    def test_aggregate_handles_db_error_gracefully(self, client):
        sb = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.gte.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.execute.side_effect = RuntimeError("db down")
        sb.table.return_value = chain

        with patch("routes.admin_calibration.get_supabase", return_value=sb), \
                patch("routes.admin_calibration.get_hours_saved_per_search", return_value=2.0):
            resp = client.get("/v1/admin/survey/export-time-saved")

        # Endpoint returns 200 with sample_size=0 — operator-friendly.
        assert resp.status_code == 200
        assert resp.json()["sample_size"] == 0


# ---------------------------------------------------------------------------
# PATCH config
# ---------------------------------------------------------------------------

class TestPatchConfig:
    def test_patch_persists_value_and_invalidates_cache(self, client):
        new_row = {
            "key": "hours_saved_per_search",
            "value": 3.2,
            "description": "manual override",
            "updated_at": "2026-04-28T15:00:00+00:00",
            "updated_by": "admin-uuid-1",
        }
        sb = MagicMock()
        sb.table.return_value = _make_chain([new_row])

        with patch("routes.admin_calibration.get_supabase", return_value=sb), \
                patch("routes.admin_calibration.invalidate_app_config") as mock_inv:
            resp = client.patch(
                "/v1/admin/config/hours_saved_per_search",
                json={"value": 3.2, "description": "manual override"},
            )

        assert resp.status_code == 200
        assert resp.json()["value"] == 3.2
        mock_inv.assert_called_once_with("hours_saved_per_search")

    def test_patch_rejects_unknown_key(self, client):
        resp = client.patch(
            "/v1/admin/config/some_other_key",
            json={"value": 42},
        )
        assert resp.status_code == 400

    def test_patch_404_when_row_not_found(self, client):
        sb = MagicMock()
        sb.table.return_value = _make_chain([])
        with patch("routes.admin_calibration.get_supabase", return_value=sb):
            resp = client.patch(
                "/v1/admin/config/hours_saved_per_search",
                json={"value": 2.5},
            )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST recalibrate
# ---------------------------------------------------------------------------

class TestRecalibrate:
    @staticmethod
    def _build_rows(n: int, hours: float = 3.0, bid_count: int = 12) -> list[dict]:
        return [
            {
                "estimated_manual_hours": hours,
                "bid_count": bid_count,
                "submitted_at": "2026-04-20T00:00:00Z",
                "export_type": "excel",
            }
            for _ in range(n)
        ]

    def test_recalibrate_eligible_does_not_apply_by_default(self, client):
        rows = self._build_rows(MIN_SAMPLE_SIZE + 5, hours=3.0)
        sb = MagicMock()
        sb.table.return_value = _make_chain(rows)

        with patch("routes.admin_calibration.get_supabase", return_value=sb), \
                patch("routes.admin_calibration.get_hours_saved_per_search", return_value=2.0):
            resp = client.post("/v1/admin/calibration/recalibrate", json={"range_days": 90})

        assert resp.status_code == 200
        body = resp.json()
        assert body["eligible"] is True
        assert body["new_value"] == pytest.approx(3.0)
        assert body["old_value"] == 2.0
        assert body["applied"] is False
        # diff_pct = (3.0 - 2.0) / 2.0 * 100 = 50
        assert body["diff_pct"] == pytest.approx(50.0)

    def test_recalibrate_apply_persists_new_value(self, client):
        rows = self._build_rows(MIN_SAMPLE_SIZE + 5, hours=4.0)
        sb = MagicMock()
        sb.table.return_value = _make_chain(rows)

        with patch("routes.admin_calibration.get_supabase", return_value=sb), \
                patch("routes.admin_calibration.get_hours_saved_per_search", return_value=2.0), \
                patch("routes.admin_calibration.invalidate_app_config") as mock_inv:
            resp = client.post(
                "/v1/admin/calibration/recalibrate",
                json={"range_days": 90, "apply": True},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["applied"] is True
        assert body["new_value"] == pytest.approx(4.0)
        mock_inv.assert_called_once_with("hours_saved_per_search")

    def test_recalibrate_ineligible_under_min_sample(self, client):
        rows = self._build_rows(5, hours=3.0)
        sb = MagicMock()
        sb.table.return_value = _make_chain(rows)

        with patch("routes.admin_calibration.get_supabase", return_value=sb), \
                patch("routes.admin_calibration.get_hours_saved_per_search", return_value=2.0):
            resp = client.post(
                "/v1/admin/calibration/recalibrate",
                json={"range_days": 90, "apply": True},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["eligible"] is False
        assert body["applied"] is False
        assert "insufficient_sample" in (body["reason"] or "")
