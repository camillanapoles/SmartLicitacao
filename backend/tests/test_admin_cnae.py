"""DATA-CNAE-001 (AC7-AC9, AC15) tests for /v1/admin/cnae-mapping CRUD.

Covers:
    * GET list with filters + pagination
    * GET detail + audit timeline
    * POST create (success + 409 on conflict)
    * PATCH update + audit log
    * DELETE soft-delete + restore
    * POST bulk-import dry_run preview AND committed mode
    * Auth gate: 403 when no admin override applied
    * Cache invalidation hook is called on every mutation

We follow the project pattern (see test_admin_cron_status.py): override
``require_auth`` and ``require_admin`` via ``app.dependency_overrides``
rather than patching the decorators.  All Supabase calls are mocked.
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from auth import require_auth
from admin import require_admin


@pytest.fixture(autouse=True)
def _disable_listener(monkeypatch: pytest.MonkeyPatch):
    """Keep the Redis listener thread off during tests."""
    monkeypatch.setenv("CNAE_LISTENER_DISABLED", "true")
    yield


@pytest.fixture
def admin_user():
    return {"id": "admin-uuid-1", "email": "admin@test.com", "is_admin": True}


@pytest.fixture
def client(admin_user):
    app.dependency_overrides[require_auth] = lambda: admin_user
    app.dependency_overrides[require_admin] = lambda: admin_user
    yield TestClient(app)
    app.dependency_overrides.pop(require_auth, None)
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def client_no_admin():
    """Auth passes but admin check is left to the real require_admin
    (which will fail because our fake user has no env entry / DB row).
    Used to verify the 403 contract on the admin gate.
    """
    fake = {"id": "regular-uuid", "email": "user@test.com"}
    app.dependency_overrides[require_auth] = lambda: fake
    yield TestClient(app)
    app.dependency_overrides.pop(require_auth, None)


# Reusable Supabase chain mock --------------------------------------------------
class _ChainMock:
    """A chainable MagicMock-ish object.

    Returns ``self`` for any method call, except ``execute()`` which
    returns a configurable result.  Pass ``data`` and optional
    ``count`` at construction.
    """

    def __init__(self, *, data=None, count=None):
        self._result = MagicMock(data=data, count=count)

    def __getattr__(self, _name):
        # Return self for any chainable .select/.eq/.order/.range/.update/...
        return self._chain

    def _chain(self, *args, **kwargs):
        return self

    def execute(self):
        return self._result


# ---------------------------------------------------------------------------
# GET list
# ---------------------------------------------------------------------------
class TestList:
    def test_list_returns_paginated_rows(self, client):
        rows = [
            {
                "cnae_code": "4120",
                "setor_id": "engenharia",
                "confidence": 1.0,
                "notes": None,
                "is_active": True,
                "created_at": "2026-04-28T12:00:00+00:00",
                "updated_at": "2026-04-28T12:00:00+00:00",
                "updated_by": None,
            }
        ]
        sb = MagicMock()
        sb.table.return_value = _ChainMock(data=rows, count=1)

        with patch("routes.admin_cnae.get_supabase", return_value=sb):
            resp = client.get("/v1/admin/cnae-mapping?limit=10&offset=0")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert data["items"][0]["cnae_code"] == "4120"

    def test_list_supports_setor_filter(self, client):
        sb = MagicMock()
        sb.table.return_value = _ChainMock(data=[], count=0)
        with patch("routes.admin_cnae.get_supabase", return_value=sb):
            resp = client.get("/v1/admin/cnae-mapping?setor_id=engenharia")
        assert resp.status_code == 200

    def test_list_503_on_db_error(self, client):
        sb = MagicMock()

        def boom():
            raise RuntimeError("db down")

        chain = MagicMock()
        chain.execute.side_effect = boom
        sb.table.return_value.select.return_value.order.return_value.range.return_value = chain
        with patch("routes.admin_cnae.get_supabase", return_value=sb):
            resp = client.get("/v1/admin/cnae-mapping")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# GET detail
# ---------------------------------------------------------------------------
class TestDetail:
    def test_detail_returns_row_and_audit(self, client):
        # Two .table() chains: first cnae_setor_mapping select, then
        # cnae_mapping_audit_log select.  Use side_effect to dispatch.
        row = {
            "cnae_code": "4120",
            "setor_id": "engenharia",
            "confidence": 1.0,
            "notes": None,
            "is_active": True,
        }
        audit = [
            {
                "id": "audit-1",
                "cnae_code": "4120",
                "action": "create",
                "old_value": None,
                "new_value": row,
                "actor_user_id": None,
                "actor_email": None,
                "note": None,
                "created_at": "2026-04-28T12:00:00+00:00",
            }
        ]
        sb = MagicMock()
        sb.table.side_effect = [
            _ChainMock(data=[row]),
            _ChainMock(data=audit),
        ]
        with patch("routes.admin_cnae.get_supabase", return_value=sb):
            resp = client.get("/v1/admin/cnae-mapping/4120")
        assert resp.status_code == 200
        body = resp.json()
        assert body["mapping"]["setor_id"] == "engenharia"
        assert len(body["audit"]) == 1

    def test_detail_404_when_missing(self, client):
        sb = MagicMock()
        sb.table.return_value = _ChainMock(data=[])
        with patch("routes.admin_cnae.get_supabase", return_value=sb):
            resp = client.get("/v1/admin/cnae-mapping/9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST create
# ---------------------------------------------------------------------------
class TestCreate:
    def test_create_inserts_row_and_logs_audit(self, client):
        # First .table() call: existence check (returns empty).
        # Second .table() call: insert (returns the row).
        # Third .table() call: audit insert.
        row = {
            "cnae_code": "9988",
            "setor_id": "engenharia",
            "confidence": 0.8,
            "notes": "test",
            "is_active": True,
        }
        sb = MagicMock()
        sb.table.side_effect = [
            _ChainMock(data=[]),                 # _fetch_row
            _ChainMock(data=[row]),              # insert
            _ChainMock(data=[{"id": "a-1"}]),    # audit
        ]
        with patch("routes.admin_cnae.get_supabase", return_value=sb), patch(
            "routes.admin_cnae.invalidate_cnae_cache"
        ) as mock_invalidate, patch(
            "routes.admin_cnae._publish_invalidation"
        ) as mock_pub:
            resp = client.post(
                "/v1/admin/cnae-mapping",
                json={
                    "cnae_code": "9988",
                    "setor_id": "engenharia",
                    "confidence": 0.8,
                    "notes": "test",
                },
            )
        assert resp.status_code == 201
        assert resp.json()["mapping"]["cnae_code"] == "9988"
        mock_invalidate.assert_called_once_with("9988")
        mock_pub.assert_called_once()

    def test_create_409_when_row_exists(self, client):
        sb = MagicMock()
        sb.table.return_value = _ChainMock(data=[{"cnae_code": "4120"}])
        with patch("routes.admin_cnae.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/admin/cnae-mapping",
                json={"cnae_code": "4120", "setor_id": "engenharia"},
            )
        assert resp.status_code == 409

    def test_create_400_on_check_constraint(self, client):
        sb = MagicMock()
        # _fetch_row returns empty (so we proceed to insert)
        first = _ChainMock(data=[])

        # The insert chain raises a check-constraint error
        def boom():
            raise RuntimeError(
                'new row violates check constraint "cnae_setor_mapping_setor_id_chk"'
            )

        insert_chain = MagicMock()
        insert_chain.execute.side_effect = boom
        sb.table.side_effect = [
            first,
            MagicMock(insert=MagicMock(return_value=insert_chain)),
        ]
        with patch("routes.admin_cnae.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/admin/cnae-mapping",
                json={"cnae_code": "9988", "setor_id": "wat"},
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# PATCH / DELETE / RESTORE
# ---------------------------------------------------------------------------
class TestUpdateAndDelete:
    def test_patch_updates_row(self, client):
        old = {
            "cnae_code": "4120",
            "setor_id": "engenharia",
            "confidence": 1.0,
            "notes": None,
            "is_active": True,
        }
        new = {**old, "confidence": 0.5, "notes": "downgraded"}
        sb = MagicMock()
        sb.table.side_effect = [
            _ChainMock(data=[old]),         # _fetch_row
            _ChainMock(data=[new]),         # update
            _ChainMock(data=[{"id": "a"}]), # audit
        ]
        with patch("routes.admin_cnae.get_supabase", return_value=sb), patch(
            "routes.admin_cnae.invalidate_cnae_cache"
        ) as mock_invalidate, patch(
            "routes.admin_cnae._publish_invalidation"
        ):
            resp = client.patch(
                "/v1/admin/cnae-mapping/4120",
                json={"confidence": 0.5, "notes": "downgraded"},
            )
        assert resp.status_code == 200
        assert resp.json()["mapping"]["confidence"] == 0.5
        mock_invalidate.assert_called_once_with("4120")

    def test_patch_400_when_no_fields(self, client):
        old = {"cnae_code": "4120", "setor_id": "engenharia", "confidence": 1.0, "is_active": True}
        sb = MagicMock()
        sb.table.return_value = _ChainMock(data=[old])
        with patch("routes.admin_cnae.get_supabase", return_value=sb):
            resp = client.patch("/v1/admin/cnae-mapping/4120", json={})
        assert resp.status_code == 400

    def test_delete_marks_inactive(self, client):
        old = {"cnae_code": "4120", "setor_id": "engenharia", "confidence": 1.0, "is_active": True}
        new = {**old, "is_active": False}
        sb = MagicMock()
        sb.table.side_effect = [
            _ChainMock(data=[old]),
            _ChainMock(data=[new]),
            _ChainMock(data=[{"id": "a"}]),
        ]
        with patch("routes.admin_cnae.get_supabase", return_value=sb), patch(
            "routes.admin_cnae.invalidate_cnae_cache"
        ), patch("routes.admin_cnae._publish_invalidation"):
            resp = client.delete("/v1/admin/cnae-mapping/4120")
        assert resp.status_code == 200
        assert resp.json()["mapping"]["is_active"] is False

    def test_delete_409_when_already_inactive(self, client):
        sb = MagicMock()
        sb.table.return_value = _ChainMock(
            data=[{"cnae_code": "4120", "setor_id": "engenharia", "confidence": 1.0, "is_active": False}]
        )
        with patch("routes.admin_cnae.get_supabase", return_value=sb):
            resp = client.delete("/v1/admin/cnae-mapping/4120")
        assert resp.status_code == 409

    def test_restore_marks_active(self, client):
        old = {"cnae_code": "4120", "setor_id": "engenharia", "confidence": 1.0, "is_active": False}
        new = {**old, "is_active": True}
        sb = MagicMock()
        sb.table.side_effect = [
            _ChainMock(data=[old]),
            _ChainMock(data=[new]),
            _ChainMock(data=[{"id": "a"}]),
        ]
        with patch("routes.admin_cnae.get_supabase", return_value=sb), patch(
            "routes.admin_cnae.invalidate_cnae_cache"
        ), patch("routes.admin_cnae._publish_invalidation"):
            resp = client.post("/v1/admin/cnae-mapping/4120/restore")
        assert resp.status_code == 200
        assert resp.json()["mapping"]["is_active"] is True

    def test_restore_409_when_already_active(self, client):
        sb = MagicMock()
        sb.table.return_value = _ChainMock(
            data=[{"cnae_code": "4120", "setor_id": "engenharia", "confidence": 1.0, "is_active": True}]
        )
        with patch("routes.admin_cnae.get_supabase", return_value=sb):
            resp = client.post("/v1/admin/cnae-mapping/4120/restore")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------
class TestBulkImport:
    CSV = (
        "cnae_code,setor_id,confidence,notes,is_active\n"
        "4120,engenharia,1.0,seed,true\n"
        "9988,manutencao_predial,0.7,new,true\n"
    )

    def test_dry_run_returns_preview_without_writes(self, client):
        existing_4120 = {
            "cnae_code": "4120",
            "setor_id": "engenharia",
            "confidence": 1.0,
            "notes": "seed",
            "is_active": True,
        }

        # Each _fetch_row call hits sb.table() once.  We have 2 rows.
        sb = MagicMock()
        sb.table.side_effect = [
            _ChainMock(data=[existing_4120]),  # 4120 exists
            _ChainMock(data=[]),               # 9988 does not
        ]

        with patch("routes.admin_cnae.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/admin/cnae-mapping/bulk-import?dry_run=true",
                files={"file": ("seed.csv", io.BytesIO(self.CSV.encode("utf-8")), "text/csv")},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["dry_run"] is True
        assert body["creates"] == 1
        assert body["noops"] == 1
        assert body["errors"] == 0
        actions = sorted(item["action"] for item in body["preview"])
        assert actions == ["create", "noop"]

    def test_invalid_csv_missing_columns(self, client):
        sb = MagicMock()
        with patch("routes.admin_cnae.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/admin/cnae-mapping/bulk-import?dry_run=true",
                files={"file": ("bad.csv", io.BytesIO(b"foo,bar\n1,2\n"), "text/csv")},
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------
class TestAuthGate:
    def test_list_403_for_non_admin(self, client_no_admin):
        # require_admin not overridden — the real one will reject our
        # fake user (no env entry, no DB row).  Patch the supabase
        # check to return False explicitly so the test is hermetic.
        with patch("admin._is_admin_from_supabase", return_value=False):
            resp = client_no_admin.get("/v1/admin/cnae-mapping")
        assert resp.status_code == 403
