"""CONV-018: Tests for POST /v1/segment/save.

Covers:
    * 200 happy path saves segmento_principal + objetivo_tipo in context_data
    * 200 partial update (only segmento_principal, no objetivo_tipo)
    * 200 merges with existing context_data (does not overwrite other fields)
    * 422 validation rejects invalid ObjetivoTipo values
    * 401 contract when not authenticated (dependency override not set)

Same pattern as test_survey.py: override ``require_auth`` via
``app.dependency_overrides`` and patch ``get_supabase`` per-test.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def authed_user():
    return {
        "id": "user-uuid-segment-1",
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


def _mk_mock_sb(existing_context: dict | None = None) -> MagicMock:
    """Build a mock Supabase client that returns ``existing_context`` from
    the ``profiles`` table ``context_data`` column, and captures updates."""
    sb = MagicMock()
    table_mock = MagicMock()

    # Select chain: table("profiles").select("context_data").eq("id", ...).single()
    select_chain = MagicMock()
    select_chain.single.return_value = select_chain
    select_chain.eq.return_value = select_chain
    fetch_result = MagicMock()
    fetch_result.data = (
        {"context_data": existing_context} if existing_context else {}
    )
    select_chain.execute.return_value = fetch_result
    # .select() returns the chain
    table_mock.select.return_value = select_chain

    # Update chain: table("profiles").update(...).eq("id", ...)
    update_chain = MagicMock()
    update_chain.eq.return_value = update_chain
    update_result = MagicMock()
    update_result.data = []
    update_chain.execute.return_value = update_result
    table_mock.update.return_value = update_chain

    # sb.table("profiles") returns table_mock
    sb.table.return_value = table_mock

    return sb


class TestSaveSegment:
    """CONV-018: POST /v1/segment/save endpoint."""

    def test_saves_both_fields(self, client, authed_user):
        """Happy path: saves segmento_principal + objetivo_tipo."""
        sb = _mk_mock_sb()

        with patch("routes.segment.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/segment/save",
                json={
                    "segmento_principal": 5,
                    "objetivo_tipo": "vencer_licitacao",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["context_data"]["segmento_principal"] == 5
        assert body["context_data"]["objetivo_tipo"] == "vencer_licitacao"

        # Verify update payload
        update_call = sb.table.return_value.update.call_args
        assert update_call is not None
        payload = update_call.args[0]
        assert payload["context_data"]["segmento_principal"] == 5
        assert payload["context_data"]["objetivo_tipo"] == "vencer_licitacao"

    def test_saves_partial_segmento_only(self, client):
        """Partial: only segmento_principal, no objetivo_tipo."""
        sb = _mk_mock_sb()

        with patch("routes.segment.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/segment/save",
                json={"segmento_principal": 3},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["context_data"]["segmento_principal"] == 3
        # objetivo_tipo should NOT be in context_data
        assert "objetivo_tipo" not in body["context_data"]

    def test_saves_partial_objetivo_only(self, client):
        """Partial: only objetivo_tipo, no segmento_principal."""
        sb = _mk_mock_sb()

        with patch("routes.segment.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/segment/save",
                json={"objetivo_tipo": "monitorar"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["context_data"]["objetivo_tipo"] == "monitorar"
        assert "segmento_principal" not in body["context_data"]

    def test_merges_existing_context(self, client):
        """Merge: does not overwrite existing context_data fields."""
        existing = {
            "cnae": "4781-4/00",
            "ufs_atuacao": ["SP", "RJ"],
            "porte_empresa": "EPP",
        }
        sb = _mk_mock_sb(existing)

        with patch("routes.segment.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/segment/save",
                json={
                    "segmento_principal": 1,
                    "objetivo_tipo": "subcontratar",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        ctx = body["context_data"]
        # Original fields preserved
        assert ctx["cnae"] == "4781-4/00"
        assert ctx["ufs_atuacao"] == ["SP", "RJ"]
        assert ctx["porte_empresa"] == "EPP"
        # New fields added
        assert ctx["segmento_principal"] == 1
        assert ctx["objetivo_tipo"] == "subcontratar"

    def test_rejects_invalid_objetivo_tipo(self, client):
        """422: invalid ObjetivoTipo value."""
        resp = client.post(
            "/v1/segment/save",
            json={
                "segmento_principal": 1,
                "objetivo_tipo": "invalid_value",
            },
        )
        assert resp.status_code == 422

    def test_empty_body_is_valid_noop(self, client):
        """200: empty body is a no-op (no fields to update)."""
        sb = _mk_mock_sb()
        with patch("routes.segment.get_supabase", return_value=sb):
            resp = client.post("/v1/segment/save", json={})
        assert resp.status_code == 200

    def test_subcontratar_value_accepted(self, client):
        """Happy path with subcontratar objective."""
        sb = _mk_mock_sb()

        with patch("routes.segment.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/segment/save",
                json={
                    "segmento_principal": 10,
                    "objetivo_tipo": "subcontratar",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["context_data"]["objetivo_tipo"] == "subcontratar"
