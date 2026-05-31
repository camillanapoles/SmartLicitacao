"""FastAPI plan-auth dependencies for quota enforcement.

TD-007: Extracted from plan_enforcement.py as part of DEBT-07 module split.
Contains require_active_plan, _require_active_plan_dep, get_active_plan_dependency.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from analytics_events import track_funnel_event
from log_sanitizer import mask_user_id

logger = logging.getLogger(__name__)


async def require_active_plan(user: dict) -> dict:
    """FastAPI dependency: ensures user has an active plan (valid trial OR paid subscription).

    STORY-265 AC7: Encapsulates verification of active plan status.
    STORY-265 AC8: Returns HTTP 403 with structured body on expired trial/plan.
    STORY-265 AC9: Read-only endpoints (GET /pipeline, GET /sessions, GET /me)
                   should NOT use this dependency.
    STORY-291 AC4: When Supabase CB is open, allows user through (fail-open).
    STORY-309 AC5: Returns HTTP 402 when user is in dunning grace_period or blocked phase.
    """
    from fastapi import HTTPException
    from authorization import has_master_access
    from supabase_client import CircuitBreakerOpenError
    from quota.plan_enforcement import check_quota

    user_id = user["id"]

    try:
        if await has_master_access(user_id):
            return user
    except CircuitBreakerOpenError:
        logger.warning(
            f"STORY-291 CB OPEN: Bypassing master check for user {mask_user_id(user_id)} (fail-open)"
        )
        return user
    except Exception:
        pass

    try:
        quota_info = await asyncio.to_thread(check_quota, user_id)
    except CircuitBreakerOpenError:
        logger.warning(
            f"STORY-291 CB OPEN: Bypassing plan check for user {mask_user_id(user_id)} (fail-open)"
        )
        return user

    # STORY-309 AC5: Dunning phase enforcement
    _dunning_phase = getattr(quota_info, "dunning_phase", "healthy")
    _days_since_failure = getattr(quota_info, "days_since_failure", None)
    if _dunning_phase == "blocked":
        logger.info(
            "dunning_blocked",
            extra={
                "user_id": mask_user_id(user_id),
                "dunning_phase": "blocked",
                "days_since_failure": _days_since_failure,
                "plan_id": quota_info.plan_id,
            },
        )
        track_funnel_event(
            "paywall_hit",
            user_id=user_id,
            properties={
                "reason": "dunning_blocked",
                "plan_id": quota_info.plan_id,
                "days_since_failure": _days_since_failure,
            },
        )
        raise HTTPException(
            status_code=402,
            detail={
                "error": "dunning_blocked",
                "message": getattr(quota_info, "error_message", "") or "Atualize seu método de pagamento para continuar.",
                "upgrade_url": "/planos",
                "dunning_phase": "blocked",
                "days_since_failure": _days_since_failure,
            },
        )
    elif _dunning_phase == "grace_period":
        logger.info(
            "dunning_grace_period_blocked",
            extra={
                "user_id": mask_user_id(user_id),
                "dunning_phase": "grace_period",
                "days_since_failure": _days_since_failure,
                "plan_id": quota_info.plan_id,
            },
        )
        track_funnel_event(
            "paywall_hit",
            user_id=user_id,
            properties={
                "reason": "dunning_grace_period",
                "plan_id": quota_info.plan_id,
                "days_since_failure": _days_since_failure,
            },
        )
        raise HTTPException(
            status_code=402,
            detail={
                "error": "dunning_grace_period",
                "message": getattr(quota_info, "error_message", "") or "Seu pagamento está pendente. Acesso somente leitura.",
                "upgrade_url": "/planos",
                "dunning_phase": "grace_period",
                "days_since_failure": _days_since_failure,
            },
        )

    if not quota_info.allowed:
        is_trial = quota_info.plan_id == "free_trial"
        error_type = "trial_expired" if is_trial else "plan_expired"

        days_overdue = 0
        if quota_info.trial_expires_at:
            delta = datetime.now(timezone.utc) - quota_info.trial_expires_at
            days_overdue = max(0, delta.days)

        logger.info(
            "trial_blocked",
            extra={
                "user_id": mask_user_id(user_id),
                "error_type": error_type,
                "plan_id": quota_info.plan_id,
                "expired_at": quota_info.trial_expires_at.isoformat() if quota_info.trial_expires_at else None,
                "days_overdue": days_overdue,
            },
        )
        track_funnel_event(
            "paywall_hit",
            user_id=user_id,
            properties={
                "reason": error_type,
                "plan_id": quota_info.plan_id,
                "trial_days_past": days_overdue if is_trial else None,
                "expired_at": quota_info.trial_expires_at.isoformat() if quota_info.trial_expires_at else None,
            },
        )

        raise HTTPException(
            status_code=403,
            detail={
                "error": error_type,
                "message": quota_info.error_message or "Seu acesso expirou. Reative para continuar analisando oportunidades.",
                "upgrade_url": "/planos",
            },
        )

    return user


async def _require_active_plan_dep(user: dict = None) -> dict:
    """Internal: chains require_auth + require_active_plan for use as Depends()."""
    return await require_active_plan(user)


def get_active_plan_dependency():
    """Create a FastAPI dependency that chains require_auth → require_active_plan.

    STORY-265 AC7: Use this on endpoints that must block expired trials.
    STORY-265 AC9: Do NOT use on read-only endpoints.

    Returns:
        A FastAPI Depends-compatible callable.
    """
    from fastapi import Depends
    from auth import require_auth

    async def _dep(user: dict = Depends(require_auth)):
        return await require_active_plan(user)

    return _dep


# ============================================================================
# SUBINTEL-030 (EPIC-SUBINTEL #1224): Subcontracting Intelligence gate
# ============================================================================

_SUBCONTRACT_INTEL_UPSELL = {
    "message": "Inteligência de Cadeia de Fornecimento disponível no plano SmartLic Insight.",
    "error_code": "subcontract_intel_not_available",
    "upgrade_cta": "Conhecer o SmartLic Insight",
    "suggested_plan": "smartlic_insight",
}


async def requires_subcontract_intel(user: dict) -> dict:
    """FastAPI dependency: gate for the Subcontracting Intelligence vertical.

    SUBINTEL-030 — strictly additive, two-stage gate consumed by every
    ``/v1/subcontract/*`` endpoint (SUBINTEL-010+):

      1. Global feature flag ``SUBCONTRACT_INTEL_ENABLED``. When OFF the whole
         vertical is inert — the endpoint behaves as if it does not exist
         (HTTP 404), so production is unaffected until the flag is flipped.
      2. Plan capability ``allow_subcontract_intel``. Only plans that opt in
         (the SmartLic Insight tier — SUBINTEL-031) pass; everyone else gets
         an upsell HTTP 403. Master/admin always bypass.

    Default state (flag off, capability ``False`` on every existing plan) is
    behaviourally identical to this dependency not existing — no regression.

    Security posture: this is a paid premium gate, so it FAILS CLOSED on
    transient backend errors (unlike ``require_active_plan`` which is
    intentionally fail-open). ``check_quota`` itself already degrades to
    ``free_trial`` on DB errors, whose capability is ``False`` → 403.
    """
    from fastapi import HTTPException
    from authorization import has_master_access
    from config.features import get_feature_flag
    from quota.plan_enforcement import check_quota
    from supabase_client import CircuitBreakerOpenError

    user_id = user["id"]

    # Stage 1: global kill-switch. Off ⇒ route is inert (404), as if unmounted.
    if not get_feature_flag("SUBCONTRACT_INTEL_ENABLED"):
        raise HTTPException(status_code=404, detail="Not Found")

    # Master/admin always bypass the capability gate (mirrors require_active_plan).
    try:
        if await has_master_access(user_id):
            return user
    except Exception:
        # Fail-closed: do NOT grant access on a failed master check. Fall
        # through to the capability check below.
        pass

    try:
        quota_info = await asyncio.to_thread(check_quota, user_id)
    except CircuitBreakerOpenError:
        # Premium gate must not open on transient DB unavailability.
        raise HTTPException(status_code=403, detail=_SUBCONTRACT_INTEL_UPSELL)

    caps = getattr(quota_info, "capabilities", None) or {}
    if not caps.get("allow_subcontract_intel", False):
        track_funnel_event(
            "paywall_hit",
            user_id=user_id,
            properties={
                "reason": "subcontract_intel_not_available",
                "plan_id": getattr(quota_info, "plan_id", None),
            },
        )
        raise HTTPException(status_code=403, detail=_SUBCONTRACT_INTEL_UPSELL)

    return user


def get_subcontract_intel_dependency():
    """FastAPI Depends factory chaining require_auth → requires_subcontract_intel.

    Endpoints in the future ``/v1/subcontract/*`` router (SUBINTEL-010+) use
    this so the gate is enforced consistently across the vertical.
    """
    from fastapi import Depends
    from auth import require_auth

    async def _dep(user: dict = Depends(require_auth)):
        return await requires_subcontract_intel(user)

    return _dep


# ============================================================================
# COMPINT-000 (EPIC-COMPINT #1261): Competitive Intelligence gate
# ============================================================================

_COMPETITIVE_INTEL_UPSELL = {
    "message": "Inteligência Concorrencial disponível no plano SmartLic Command.",
    "error_code": "competitive_intel_not_available",
    "upgrade_cta": "Conhecer o SmartLic Command",
    "suggested_plan": "smartlic_command",
}


async def requires_competitive_intel(user: dict) -> dict:
    """FastAPI dependency: gate for the Competitive Intelligence vertical.

    COMPINT-000 — strictly additive, two-stage gate consumed by every
    ``/v1/competitive-intel/*`` endpoint:

      1. Global feature flag ``COMPETITIVE_INTEL_ENABLED``. When OFF the whole
         vertical is inert — the endpoint behaves as if it does not exist
         (HTTP 404), so production is unaffected until the flag is flipped.
      2. Plan capability ``allow_competitive_intel``. Only plans that opt in
         pass; everyone else gets an upsell HTTP 403. Master/admin always
         bypass.

    Default state (flag off, capability ``False`` on every existing plan) is
    behaviourally identical to this dependency not existing — no regression.

    Security posture: this is a paid premium gate, so it FAILS CLOSED on
    transient backend errors (unlike ``require_active_plan`` which is
    intentionally fail-open). ``check_quota`` itself already degrades to
    ``free_trial`` on DB errors, whose capability is ``False`` → 403.
    """
    from fastapi import HTTPException
    from authorization import has_master_access
    from config.features import get_feature_flag
    from quota.plan_enforcement import check_quota
    from supabase_client import CircuitBreakerOpenError

    user_id = user["id"]

    # Stage 1: global kill-switch. Off => route is inert (404), as if unmounted.
    if not get_feature_flag("COMPETITIVE_INTEL_ENABLED"):
        raise HTTPException(status_code=404, detail="Not Found")

    # Master/admin always bypass the capability gate (mirrors require_active_plan).
    try:
        if await has_master_access(user_id):
            return user
    except Exception:
        # Fail-closed: do NOT grant access on a failed master check. Fall
        # through to the capability check below.
        pass

    try:
        quota_info = await asyncio.to_thread(check_quota, user_id)
    except CircuitBreakerOpenError:
        # Premium gate must not open on transient DB unavailability.
        raise HTTPException(status_code=403, detail=_COMPETITIVE_INTEL_UPSELL)

    caps = getattr(quota_info, "capabilities", None) or {}
    if not caps.get("allow_competitive_intel", False):
        track_funnel_event(
            "paywall_hit",
            user_id=user_id,
            properties={
                "reason": "competitive_intel_not_available",
                "plan_id": getattr(quota_info, "plan_id", None),
            },
        )
        raise HTTPException(status_code=403, detail=_COMPETITIVE_INTEL_UPSELL)

    return user


def get_competitive_intel_dependency():
    """FastAPI Depends factory chaining require_auth -> requires_competitive_intel.

    Endpoints in the future ``/v1/competitive-intel/*`` router use this so the
    gate is enforced consistently across the vertical.
    """
    from fastapi import Depends
    from auth import require_auth

    async def _dep(user: dict = Depends(require_auth)):
        return await requires_competitive_intel(user)

    return _dep


# ============================================================================
# B2GOPS-000 (EPIC-B2GOPS #1262): B2G Operations gate
# ============================================================================

_B2G_OPS_UPSELL = {
    "message": "Sistema Operacional B2G disponível no plano SmartLic Command.",
    "error_code": "b2g_ops_not_available",
    "upgrade_cta": "Conhecer o SmartLic Command",
    "suggested_plan": "smartlic_command",
}


async def requires_workspace_basic(user: dict) -> dict:
    """FastAPI dependency: gate for the B2G Operations vertical.

    B2GOPS-000 — strictly additive, two-stage gate consumed by every
    B2GOPS endpoint:

      1. Global feature flag ``B2G_OPS_ENABLED``. When OFF the whole
         vertical is inert — the endpoint behaves as if it does not exist
         (HTTP 404), so production is unaffected until the flag is flipped.
      2. Plan capability ``allow_workspace_basic``. Only plans that opt in
         pass; everyone else gets an upsell HTTP 403. Master/admin always bypass.

    Default state (flag off, capability ``False`` on every existing plan) is
    behaviourally identical to this dependency not existing — no regression.

    Security posture: this is a paid premium gate, so it FAILS CLOSED on
    transient backend errors.
    """
    from fastapi import HTTPException
    from authorization import has_master_access
    from config.features import get_feature_flag
    from quota.plan_enforcement import check_quota
    from supabase_client import CircuitBreakerOpenError

    user_id = user["id"]

    # Stage 1: global kill-switch. Off ⇒ route is inert (404), as if unmounted.
    if not get_feature_flag("B2G_OPS_ENABLED"):
        raise HTTPException(status_code=404, detail="Not Found")

    # Master/admin always bypass the capability gate.
    try:
        if await has_master_access(user_id):
            return user
    except Exception:
        pass

    try:
        quota_info = await asyncio.to_thread(check_quota, user_id)
    except CircuitBreakerOpenError:
        raise HTTPException(status_code=403, detail=_B2G_OPS_UPSELL)

    caps = getattr(quota_info, "capabilities", None) or {}
    if not caps.get("allow_workspace_basic", False):
        track_funnel_event(
            "paywall_hit",
            user_id=user_id,
            properties={
                "reason": "b2g_ops_not_available",
                "plan_id": getattr(quota_info, "plan_id", None),
            },
        )
        raise HTTPException(status_code=403, detail=_B2G_OPS_UPSELL)

    return user


def get_workspace_basic_dependency():
    """FastAPI Depends factory chaining require_auth → requires_workspace_basic.

    B2GOPS endpoints use this so the gate is enforced consistently across the
    B2G Operations vertical.
    """
    from fastapi import Depends
    from auth import require_auth

    async def _dep(user: dict = Depends(require_auth)):
        return await requires_workspace_basic(user)

    return _dep
