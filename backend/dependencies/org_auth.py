"""RBAC-ORG-001: FastAPI dependency for organization role enforcement."""

import asyncio
from enum import Enum

from fastapi import Depends, HTTPException

from auth import require_auth
from pipeline.budget import _run_with_budget
from supabase_client import get_supabase


class OrgRole(str, Enum):
    OWNER = "owner"
    MEMBER = "member"
    VIEWER = "viewer"


_ROLE_RANK: dict[str, int] = {
    OrgRole.OWNER: 3,
    OrgRole.MEMBER: 2,
    OrgRole.VIEWER: 1,
}


def require_org_role(min_role: OrgRole):
    """Factory: returns a FastAPI dependency that enforces org role.

    Injects ``org_id`` from the path parameter automatically.
    Raises HTTP 403 if the caller is not a member or rank < min_role.
    """

    async def dependency(
        org_id: str,
        user: dict = Depends(require_auth),
    ) -> OrgRole:
        user_id = user["id"]

        def _query():
            return (
                get_supabase()
                .table("organization_members")
                .select("role")
                .eq("org_id", org_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )

        result = await _run_with_budget(
            asyncio.to_thread(_query),
            budget=10.0,
            phase="route",
            source="org_auth.require_org_role",
        )

        if not result.data:
            raise HTTPException(
                status_code=403,
                detail="Acesso negado: usuario nao e membro desta organizacao",
            )

        role_str = result.data[0]["role"]
        try:
            role = OrgRole(role_str)
        except ValueError:
            raise HTTPException(status_code=403, detail="Acesso negado: role invalido")

        if _ROLE_RANK[role] < _ROLE_RANK[min_role]:
            raise HTTPException(
                status_code=403,
                detail=f"Acesso negado: requer role {min_role.value}",
            )

        return role

    return dependency
