"""BIZ-METRIC-001 (AC3, AC13): tests for /v1/survey/export-time-saved.

Covers:
    * 201 happy path persists row with correct user_id binding
    * 422 validation failures (invalid export_type, hours out-of-range)
    * 401 contract when require_auth fails (not exercised here — covered
      indirectly via the dependency override pattern below)
    * 503 when Supabase insert blows up
    * Empty insert response treated as 503

Same pattern as test_admin_cnae.py: override ``require_auth`` via
``app.dependency_overrides`` and patch ``get_supabase`` per-test.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def authed_user():
    return {
        "id": "user-uuid-survey-1",
        "email": "user@test.com",
        "role": "authenticated",
    }


@pytest.fixture
def client(authed_user):
    from main import app
    from auth import require_auth

    app.dependency_overrides[require_auth] = lambda: authed_user
    yield TestClient(app)
    app.dependency_overrides.pop(require_auth, None)


def _ok_insert_chain(returned_row: dict) -> MagicMock:
    chain = MagicMock()
    chain.insert.return_value = chain
    result = MagicMock()
    result.data = [returned_row]
    chain.execute.return_value = result
    return chain


class TestSubmitSurvey:
    def test_submit_persists_row_with_user_id(self, client, authed_user):
        returned = {
            "id": "row-uuid-1",
            "submitted_at": "2026-04-28T15:00:00+00:00",
        }
        sb = MagicMock()
        sb.table.return_value = _ok_insert_chain(returned)

        with patch("routes.survey.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/survey/export-time-saved",
                json={
                    "export_type": "excel",
                    "estimated_manual_hours": 4.5,
                    "search_id": "search-abc",
                    "bid_count": 12,
                    "free_text": "  manual search on PNCP  ",
                },
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "row-uuid-1"
        assert body["submitted_at"].startswith("2026-04-28")

        # Verify the inserted payload
        sb.table.assert_called_once_with("export_time_saved_survey")
        insert_call = sb.table.return_value.insert.call_args
        assert insert_call is not None
        payload = insert_call.args[0]
        assert payload["user_id"] == authed_user["id"]
        assert payload["export_type"] == "excel"
        assert payload["estimated_manual_hours"] == 4.5
        assert payload["bid_count"] == 12
        # free_text trimmed
        assert payload["free_text"] == "manual search on PNCP"

    def test_submit_rejects_invalid_export_type(self, client):
        resp = client.post(
            "/v1/survey/export-time-saved",
            json={"export_type": "csv", "estimated_manual_hours": 2.0},
        )
        assert resp.status_code == 422

    def test_submit_rejects_hours_out_of_range_low(self, client):
        resp = client.post(
            "/v1/survey/export-time-saved",
            json={"export_type": "excel", "estimated_manual_hours": 0.05},
        )
        assert resp.status_code == 422

    def test_submit_rejects_hours_out_of_range_high(self, client):
        resp = client.post(
            "/v1/survey/export-time-saved",
            json={"export_type": "excel", "estimated_manual_hours": 100.0},
        )
        assert resp.status_code == 422

    def test_submit_returns_503_on_db_error(self, client):
        sb = MagicMock()
        chain = MagicMock()
        chain.insert.return_value = chain
        chain.execute.side_effect = RuntimeError("db down")
        sb.table.return_value = chain

        with patch("routes.survey.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/survey/export-time-saved",
                json={"export_type": "pdf", "estimated_manual_hours": 3.0},
            )
        assert resp.status_code == 503

    def test_submit_returns_503_on_empty_insert_response(self, client):
        sb = MagicMock()
        chain = MagicMock()
        chain.insert.return_value = chain
        result = MagicMock()
        result.data = []
        chain.execute.return_value = result
        sb.table.return_value = chain

        with patch("routes.survey.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/survey/export-time-saved",
                json={"export_type": "sheets", "estimated_manual_hours": 1.5},
            )
        assert resp.status_code == 503

    def test_submit_strips_blank_free_text_to_none(self, client):
        returned = {
            "id": "row-uuid-2",
            "submitted_at": "2026-04-28T15:00:00+00:00",
        }
        sb = MagicMock()
        sb.table.return_value = _ok_insert_chain(returned)

        with patch("routes.survey.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/survey/export-time-saved",
                json={
                    "export_type": "excel",
                    "estimated_manual_hours": 2.0,
                    "free_text": "   ",
                },
            )
        assert resp.status_code == 201
        payload = sb.table.return_value.insert.call_args.args[0]
        assert payload["free_text"] is None
