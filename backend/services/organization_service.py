"""Organization service for multi-user consultancy management.

STORY-322: Plano Consultoria — multi-user organization support.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from supabase_client import get_supabase

logger = logging.getLogger(__name__)


async def create_organization(owner_id: str, name: str) -> dict:
    """Create a new organization and add the owner as a member.

    1. Insert into organizations (owner_id, name)
    2. Insert owner into organization_members (role='owner', accepted_at=NOW())
    3. Return the created organization
    """
    sb = get_supabase()

    # Insert org
    org_result = sb.table("organizations").insert({
        "owner_id": owner_id,
        "name": name,
    }).execute()

    if not org_result.data:
        raise ValueError("Failed to create organization")

    org = org_result.data[0]

    # Add owner as member (accepted immediately)
    now = datetime.now(timezone.utc).isoformat()
    sb.table("organization_members").insert({
        "org_id": org["id"],
        "user_id": owner_id,
        "role": "owner",
        "accepted_at": now,
    }).execute()

    logger.info(f"Organization created: org_id={org['id']}, owner_id={owner_id[:8]}***")
    return org


async def get_organization(org_id: str, user_id: str) -> Optional[dict]:
    """Get organization details. User must be a member."""
    sb = get_supabase()

    # Verify membership
    member = (
        sb.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not member.data:
        return None

    org = sb.table("organizations").select("*").eq("id", org_id).single().execute()
    if not org.data:
        return None

    # Get members list
    members = (
        sb.table("organization_members")
        .select("user_id, role, invited_at, accepted_at")
        .eq("org_id", org_id)
        .execute()
    )

    result = org.data
    result["members"] = members.data or []
    result["user_role"] = member.data[0]["role"]
    return result


async def invite_member(org_id: str, inviter_id: str, email: str) -> dict:
    """Invite a member to the organization by email.

    1. Verify inviter is owner/admin
    2. Check max_members limit
    3. Find user by email in profiles
    4. Insert into organization_members (accepted_at=NULL = pending)
    """
    sb = get_supabase()

    # Check inviter role
    inviter = (
        sb.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", inviter_id)
        .limit(1)
        .execute()
    )
    if not inviter.data or inviter.data[0]["role"] != "owner":
        raise PermissionError("Apenas owner pode convidar membros")

    # Check member count vs max
    org = (
        sb.table("organizations")
        .select("max_members")
        .eq("id", org_id)
        .single()
        .execute()
    )
    if not org.data:
        raise ValueError("Organization not found")

    current_members = (
        sb.table("organization_members")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .execute()
    )
    if current_members.count and current_members.count >= org.data["max_members"]:
        raise ValueError(f"Limite de membros atingido ({org.data['max_members']})")

    # Find user by email
    user_result = (
        sb.table("profiles")
        .select("id")
        .eq("email", email)
        .limit(1)
        .execute()
    )
    if not user_result.data:
        raise ValueError(f"Nenhum usuario encontrado com o email {email}")

    target_user_id = user_result.data[0]["id"]

    # Check if already member
    existing = (
        sb.table("organization_members")
        .select("id")
        .eq("org_id", org_id)
        .eq("user_id", target_user_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise ValueError("Usuario ja e membro da organizacao")

    # Insert invite (accepted_at=NULL means pending)
    invite_result = sb.table("organization_members").insert({
        "org_id": org_id,
        "user_id": target_user_id,
        "role": "member",
    }).execute()

    logger.info(f"Member invited: org_id={org_id}, email={email}")
    return invite_result.data[0] if invite_result.data else {}


async def accept_invite(org_id: str, user_id: str) -> dict:
    """Accept a pending invitation."""
    sb = get_supabase()

    # Find pending invite
    invite = (
        sb.table("organization_members")
        .select("id, accepted_at")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not invite.data:
        raise ValueError("Convite nao encontrado")
    if invite.data[0].get("accepted_at"):
        raise ValueError("Convite ja aceito")

    # Accept
    now = datetime.now(timezone.utc).isoformat()
    sb.table("organization_members").update({"accepted_at": now}).eq("id", invite.data[0]["id"]).execute()

    logger.info(f"Invite accepted: org_id={org_id}, user_id={user_id[:8]}***")
    return {"accepted": True}


async def remove_member(org_id: str, remover_id: str, target_user_id: str) -> dict:
    """Remove a member from the organization.

    Remover must be owner/admin. Cannot remove the owner.
    """
    sb = get_supabase()

    # Check remover role
    remover = (
        sb.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", remover_id)
        .limit(1)
        .execute()
    )
    if not remover.data or remover.data[0]["role"] != "owner":
        raise PermissionError("Apenas owner pode remover membros")

    # Check target role (cannot remove owner)
    target = (
        sb.table("organization_members")
        .select("id, role")
        .eq("org_id", org_id)
        .eq("user_id", target_user_id)
        .limit(1)
        .execute()
    )
    if not target.data:
        raise ValueError("Membro nao encontrado")
    if target.data[0]["role"] == "owner":
        raise PermissionError("Nao e possivel remover o owner da organizacao")

    # Delete
    sb.table("organization_members").delete().eq("id", target.data[0]["id"]).execute()

    logger.info(f"Member removed: org_id={org_id}, target_user_id={target_user_id[:8]}***")
    return {"removed": True}


async def get_org_dashboard(org_id: str, user_id: str) -> dict:
    """Get consolidated dashboard stats for the organization.

    Only owner/admin can see org-wide stats.
    """
    sb = get_supabase()

    # Verify role
    member = (
        sb.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not member.data or member.data[0]["role"] != "owner":
        raise PermissionError("Apenas owner pode ver o dashboard")

    # Get all member IDs
    members = (
        sb.table("organization_members")
        .select("user_id")
        .eq("org_id", org_id)
        .execute()
    )
    member_ids = [m["user_id"] for m in (members.data or [])]

    if not member_ids:
        return {"total_searches": 0, "total_opportunities": 0, "total_value": 0, "member_count": 0}

    # Aggregate search sessions
    sessions = (
        sb.table("search_sessions")
        .select("total_results, total_value")
        .in_("user_id", member_ids)
        .execute()
    )

    total_searches = len(sessions.data) if sessions.data else 0
    total_opportunities = sum(s.get("total_results", 0) or 0 for s in (sessions.data or []))
    total_value = sum(float(s.get("total_value", 0) or 0) for s in (sessions.data or []))

    return {
        "total_searches": total_searches,
        "total_opportunities": total_opportunities,
        "total_value": total_value,
        "member_count": len(member_ids),
    }


async def update_org_logo(org_id: str, user_id: str, logo_url: str) -> dict:
    """Update organization logo URL. Only owner/admin."""
    sb = get_supabase()

    # Check role
    member = (
        sb.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not member.data or member.data[0]["role"] != "owner":
        raise PermissionError("Apenas owner pode alterar o logo")

    sb.table("organizations").update({"logo_url": logo_url}).eq("id", org_id).execute()

    logger.info(f"Logo updated: org_id={org_id}")
    return {"updated": True}


async def get_user_org(user_id: str) -> Optional[dict]:
    """Get the organization a user belongs to, if any."""
    sb = get_supabase()

    member = (
        sb.table("organization_members")
        .select("org_id, role, accepted_at")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not member.data:
        return None

    org_id = member.data[0]["org_id"]
    org = (
        sb.table("organizations")
        .select("id, name, logo_url, max_members, plan_type")
        .eq("id", org_id)
        .single()
        .execute()
    )

    if not org.data:
        return None

    result = org.data
    result["user_role"] = member.data[0]["role"]
    result["accepted"] = member.data[0].get("accepted_at") is not None
    return result
