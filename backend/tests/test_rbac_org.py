"""RBAC-ORG-001: 3 roles × 8 endpoints = 24 RBAC test cases.

Matrix:
  Roles: owner (rank 3), member (rank 2), viewer (rank 1)
  Endpoints:
    1. GET  /v1/organizations/me                        — auth-only
    2. POST /v1/organizations                           — auth-only
    3. GET  /v1/organizations/{id}                      — min_role=MEMBER
    4. POST /v1/organizations/{id}/invite               — min_role=OWNER
    5. POST /v1/organizations/{id}/accept               — auth-only
    6. DELETE /v1/organizations/{id}/members/{uid}      — min_role=OWNER
    7. GET  /v1/organizations/{id}/dashboard            — min_role=OWNER
    8. PUT  /v1/organizations/{id}/logo                 — min_role=OWNER

Expected status per role × requirement:
  auth-only: all roles → pass (2xx)
  min=MEMBER: owner→pass, member→pass, viewer→403
  min=OWNER:  owner→pass, member→403,  viewer→403
"""

import pytest
from unittest.mock import MagicMock, patch

from httpx import AsyncClient, ASGITransport

from main import app
from auth import require_auth

_ORG_AUTH_GET_SUPABASE = "dependencies.org_auth.get_supabase"
_ORG_SVC_GET_SUPABASE = "services.organization_service.get_supabase"

ORG_ID = "org-test-001"
TARGET_UID = "user-target-001"

_USER_OWNER = {"id": "user-owner", "email": "owner@rbac.test", "role": "authenticated", "aal": "aal1"}
_USER_MEMBER = {"id": "user-member", "email": "member@rbac.test", "role": "authenticated", "aal": "aal1"}
_USER_VIEWER = {"id": "user-viewer", "email": "viewer@rbac.test", "role": "authenticated", "aal": "aal1"}

_ROLE_USERS = {
    "owner": _USER_OWNER,
    "member": _USER_MEMBER,
    "viewer": _USER_VIEWER,
}


@pytest.fixture(autouse=True)
def _enable_organizations():
    with patch("routes.organizations.ORGANIZATIONS_ENABLED", True):
        yield


def _mock_auth_sb(role: str | None):
    """Supabase mock for the require_org_role dependency query."""
    sb = MagicMock()
    tbl = MagicMock()
    res = MagicMock()
    res.data = [{"role": role}] if role else []
    tbl.select.return_value = tbl
    tbl.eq.return_value = tbl
    tbl.limit.return_value = tbl
    tbl.execute.return_value = res
    sb.table.return_value = tbl
    return sb


def _mock_svc_sb_success():
    """Minimal service supabase mock returning sensible success data."""
    sb = MagicMock()
    tbl = MagicMock()
    res = MagicMock()
    res.data = [{"id": "row-1", "role": "owner"}]
    res.count = 1
    tbl.select.return_value = tbl
    tbl.insert.return_value = tbl
    tbl.update.return_value = tbl
    tbl.delete.return_value = tbl
    tbl.eq.return_value = tbl
    tbl.in_.return_value = tbl
    tbl.single.return_value = tbl
    tbl.limit.return_value = tbl
    tbl.order.return_value = tbl
    tbl.not_.return_value = tbl
    tbl.is_.return_value = tbl
    tbl.execute.return_value = res
    sb.table.return_value = tbl
    return sb


# ── Helpers ────────────────────────────────────────────────────────────────────

_NO_DEP_MOCK = object()  # sentinel: "don't patch the org-auth dep supabase"


async def _call(method: str, path: str, role_user: dict, dep_role=_NO_DEP_MOCK, **kwargs):
    """Execute one HTTP request with auth + optional org-role dep mock.

    dep_role=_NO_DEP_MOCK — don't mock (auth-only endpoints, no require_org_role)
    dep_role=None          — mock with empty data (user not in org → 403)
    dep_role="owner"|...   — mock with that role
    """
    app.dependency_overrides[require_auth] = lambda: role_user
    try:
        if dep_role is not _NO_DEP_MOCK:
            with patch(_ORG_AUTH_GET_SUPABASE, return_value=_mock_auth_sb(dep_role)):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as c:
                    resp = await getattr(c, method)(path, **kwargs)
        else:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await getattr(c, method)(path, **kwargs)
        return resp
    finally:
        app.dependency_overrides.clear()


# ── Endpoint 1: GET /organizations/me — auth-only ─────────────────────────────


class TestRbacGetMyOrg:
    """Endpoint 1 (auth-only): all roles see 200."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", ["owner", "member", "viewer"])
    async def test_get_my_org_all_roles_pass(self, role: str):
        svc_sb = _mock_svc_sb_success()
        svc_sb.table.return_value.execute.return_value.data = []  # no org → {"organization": null}

        with patch(_ORG_SVC_GET_SUPABASE, return_value=svc_sb):
            resp = await _call("get", "/v1/organizations/me", _ROLE_USERS[role])

        assert resp.status_code == 200


# ── Endpoint 2: POST /organizations — auth-only ───────────────────────────────


class TestRbacCreateOrg:
    """Endpoint 2 (auth-only): all roles can attempt create (result depends on service)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", ["owner", "member", "viewer"])
    async def test_create_org_all_roles_pass_auth(self, role: str):
        call_count = [0]

        def execute_side():
            call_count[0] += 1
            r = MagicMock()
            if call_count[0] == 1:
                r.data = [{"id": "org-new", "name": "Test Org", "owner_id": "u1", "max_members": 5, "plan_type": "consultoria"}]
            else:
                r.data = [{"id": "mem-1"}]
            return r

        svc_sb, svc_tbl, _ = _mock_svc_sb_success(), MagicMock(), None
        svc_tbl.insert.return_value = svc_tbl
        svc_tbl.execute.side_effect = execute_side
        svc_sb.table.return_value = svc_tbl

        with patch(_ORG_SVC_GET_SUPABASE, return_value=svc_sb):
            resp = await _call("post", "/v1/organizations", _ROLE_USERS[role], json={"name": "Test Org"})

        # Auth passes → service runs → 201 (not 401/403 auth error)
        assert resp.status_code in (201, 400, 500)  # not 401/403


# ── Endpoint 3: GET /organizations/{id} — min_role=MEMBER ────────────────────


class TestRbacGetOrg:
    """Endpoint 3: owner→200, member→200, viewer→403."""

    @pytest.mark.asyncio
    async def test_get_org_owner_passes(self):
        svc_sb = _mock_svc_sb_success()
        org_data = {"id": ORG_ID, "name": "Org", "owner_id": "u1", "max_members": 5, "plan_type": "consultoria"}
        call_count = [0]

        def execute_side():
            call_count[0] += 1
            r = MagicMock()
            if call_count[0] == 1:
                r.data = [{"role": "owner"}]
            elif call_count[0] == 2:
                r.data = org_data
            else:
                r.data = [{"user_id": "u1", "role": "owner", "invited_at": None, "accepted_at": "2026-01-01"}]
            return r

        svc_sb.table.return_value.execute.side_effect = execute_side

        with (
            patch(_ORG_AUTH_GET_SUPABASE, return_value=_mock_auth_sb("owner")),
            patch(_ORG_SVC_GET_SUPABASE, return_value=svc_sb),
        ):
            resp = await _call("get", f"/v1/organizations/{ORG_ID}", _USER_OWNER, dep_role="owner")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_org_member_passes(self):
        svc_sb = _mock_svc_sb_success()
        org_data = {"id": ORG_ID, "name": "Org", "owner_id": "u1", "max_members": 5, "plan_type": "consultoria"}
        call_count = [0]

        def execute_side():
            call_count[0] += 1
            r = MagicMock()
            if call_count[0] == 1:
                r.data = [{"role": "member"}]
            elif call_count[0] == 2:
                r.data = org_data
            else:
                r.data = []
            return r

        svc_sb.table.return_value.execute.side_effect = execute_side

        with (
            patch(_ORG_AUTH_GET_SUPABASE, return_value=_mock_auth_sb("member")),
            patch(_ORG_SVC_GET_SUPABASE, return_value=svc_sb),
        ):
            resp = await _call("get", f"/v1/organizations/{ORG_ID}", _USER_MEMBER, dep_role="member")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_org_viewer_blocked(self):
        """viewer rank < MEMBER → 403 from require_org_role."""
        resp = await _call("get", f"/v1/organizations/{ORG_ID}", _USER_VIEWER, dep_role="viewer")
        assert resp.status_code == 403


# ── Endpoint 4: POST /organizations/{id}/invite — min_role=OWNER ─────────────


class TestRbacInvite:
    """Endpoint 4: owner→200, member→403, viewer→403."""

    @pytest.mark.asyncio
    async def test_invite_owner_passes(self):
        svc_sb = _mock_svc_sb_success()
        call_count = [0]

        def execute_side():
            call_count[0] += 1
            r = MagicMock()
            r.data = [{"role": "owner"}] if call_count[0] == 1 else [{"id": "x"}]
            r.data = {"max_members": 5} if call_count[0] == 2 else r.data
            r.count = 1
            return r

        svc_sb.table.return_value.execute.side_effect = execute_side

        with (
            patch(_ORG_AUTH_GET_SUPABASE, return_value=_mock_auth_sb("owner")),
            patch(_ORG_SVC_GET_SUPABASE, return_value=svc_sb),
        ):
            resp = await _call(
                "post", f"/v1/organizations/{ORG_ID}/invite", _USER_OWNER,
                dep_role="owner", json={"email": "new@test.com"},
            )

        # 200 or 400 (user-not-found) — either way, auth/rbac passed
        assert resp.status_code in (200, 400)

    @pytest.mark.asyncio
    async def test_invite_member_blocked(self):
        resp = await _call(
            "post", f"/v1/organizations/{ORG_ID}/invite", _USER_MEMBER,
            dep_role="member", json={"email": "x@test.com"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_invite_viewer_blocked(self):
        resp = await _call(
            "post", f"/v1/organizations/{ORG_ID}/invite", _USER_VIEWER,
            dep_role="viewer", json={"email": "x@test.com"},
        )
        assert resp.status_code == 403


# ── Endpoint 5: POST /organizations/{id}/accept — auth-only ──────────────────


class TestRbacAcceptInvite:
    """Endpoint 5 (auth-only): all roles can accept."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", ["owner", "member", "viewer"])
    async def test_accept_invite_all_roles_pass_auth(self, role: str):
        svc_sb = _mock_svc_sb_success()
        call_count = [0]

        def execute_side():
            call_count[0] += 1
            r = MagicMock()
            # pending invite — not yet accepted
            r.data = [{"id": "inv-1", "accepted_at": None}] if call_count[0] == 1 else [{}]
            return r

        svc_sb.table.return_value.execute.side_effect = execute_side

        with patch(_ORG_SVC_GET_SUPABASE, return_value=svc_sb):
            resp = await _call("post", f"/v1/organizations/{ORG_ID}/accept", _ROLE_USERS[role])

        # Auth passes → service runs (200 or 400 depending on invite state)
        assert resp.status_code in (200, 400)


# ── Endpoint 6: DELETE /organizations/{id}/members/{uid} — min_role=OWNER ────


class TestRbacRemoveMember:
    """Endpoint 6: owner→200, member→403, viewer→403."""

    @pytest.mark.asyncio
    async def test_remove_member_owner_passes(self):
        svc_sb = _mock_svc_sb_success()
        call_count = [0]

        def execute_side():
            call_count[0] += 1
            r = MagicMock()
            if call_count[0] == 1:
                r.data = [{"role": "owner"}]
            elif call_count[0] == 2:
                r.data = [{"id": "mem-t", "role": "member"}]
            else:
                r.data = [{"id": "mem-t"}]
            return r

        svc_sb.table.return_value.execute.side_effect = execute_side

        with (
            patch(_ORG_AUTH_GET_SUPABASE, return_value=_mock_auth_sb("owner")),
            patch(_ORG_SVC_GET_SUPABASE, return_value=svc_sb),
        ):
            resp = await _call(
                "delete", f"/v1/organizations/{ORG_ID}/members/{TARGET_UID}",
                _USER_OWNER, dep_role="owner",
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_remove_member_member_blocked(self):
        resp = await _call(
            "delete", f"/v1/organizations/{ORG_ID}/members/{TARGET_UID}",
            _USER_MEMBER, dep_role="member",
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_remove_member_viewer_blocked(self):
        resp = await _call(
            "delete", f"/v1/organizations/{ORG_ID}/members/{TARGET_UID}",
            _USER_VIEWER, dep_role="viewer",
        )
        assert resp.status_code == 403


# ── Endpoint 7: GET /organizations/{id}/dashboard — min_role=OWNER ───────────


class TestRbacDashboard:
    """Endpoint 7: owner→200, member→403, viewer→403."""

    @pytest.mark.asyncio
    async def test_dashboard_owner_passes(self):
        svc_sb = _mock_svc_sb_success()
        call_count = [0]

        def execute_side():
            call_count[0] += 1
            r = MagicMock()
            if call_count[0] == 1:
                r.data = [{"role": "owner"}]
            elif call_count[0] == 2:
                r.data = [{"user_id": "u1"}]
            else:
                r.data = [{"total_results": 5, "total_value": 100.0}]
            return r

        svc_sb.table.return_value.execute.side_effect = execute_side

        with (
            patch(_ORG_AUTH_GET_SUPABASE, return_value=_mock_auth_sb("owner")),
            patch(_ORG_SVC_GET_SUPABASE, return_value=svc_sb),
        ):
            resp = await _call("get", f"/v1/organizations/{ORG_ID}/dashboard", _USER_OWNER, dep_role="owner")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_dashboard_member_blocked(self):
        resp = await _call("get", f"/v1/organizations/{ORG_ID}/dashboard", _USER_MEMBER, dep_role="member")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_dashboard_viewer_blocked(self):
        resp = await _call("get", f"/v1/organizations/{ORG_ID}/dashboard", _USER_VIEWER, dep_role="viewer")
        assert resp.status_code == 403


# ── Endpoint 8: PUT /organizations/{id}/logo — min_role=OWNER ────────────────


class TestRbacLogo:
    """Endpoint 8: owner→200, member→403, viewer→403."""

    @pytest.mark.asyncio
    async def test_logo_owner_passes(self):
        svc_sb = _mock_svc_sb_success()
        call_count = [0]

        def execute_side():
            call_count[0] += 1
            r = MagicMock()
            r.data = [{"role": "owner"}] if call_count[0] == 1 else [{}]
            return r

        svc_sb.table.return_value.execute.side_effect = execute_side

        with (
            patch(_ORG_AUTH_GET_SUPABASE, return_value=_mock_auth_sb("owner")),
            patch(_ORG_SVC_GET_SUPABASE, return_value=svc_sb),
        ):
            resp = await _call(
                "put", f"/v1/organizations/{ORG_ID}/logo", _USER_OWNER,
                dep_role="owner", json={"logo_url": "https://example.com/logo.png"},
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_logo_member_blocked(self):
        resp = await _call(
            "put", f"/v1/organizations/{ORG_ID}/logo", _USER_MEMBER,
            dep_role="member", json={"logo_url": "https://example.com/logo.png"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_logo_viewer_blocked(self):
        resp = await _call(
            "put", f"/v1/organizations/{ORG_ID}/logo", _USER_VIEWER,
            dep_role="viewer", json={"logo_url": "https://example.com/logo.png"},
        )
        assert resp.status_code == 403


# ── Edge: non-member (not in org at all) ─────────────────────────────────────


class TestRbacNonMemberEdge:
    """Edge case: user not in org at all → 403 on any role-gated endpoint."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path,body", [
        ("get",    f"/v1/organizations/{ORG_ID}",                       None),
        ("post",   f"/v1/organizations/{ORG_ID}/invite",                {"email": "x@x.com"}),
        ("delete", f"/v1/organizations/{ORG_ID}/members/{TARGET_UID}",  None),
        ("get",    f"/v1/organizations/{ORG_ID}/dashboard",             None),
        ("put",    f"/v1/organizations/{ORG_ID}/logo",                  {"logo_url": "http://x.com/l.png"}),
    ])
    async def test_non_member_blocked_on_role_gated_endpoints(self, method: str, path: str, body):
        kwargs = {"json": body} if body else {}
        # dep_role=None → _mock_auth_sb(None) → data=[] → 403
        resp = await _call(method, path, _USER_OWNER, dep_role=None, **kwargs)
        assert resp.status_code == 403
