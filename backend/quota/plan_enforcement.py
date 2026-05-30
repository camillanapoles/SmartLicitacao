"""Plan enforcement, quota checking, and session management.

TD-007: Extracted from quota.py as part of DEBT-07 module split.
Contains check_quota, require_active_plan, and search session helpers.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from log_sanitizer import mask_user_id
from quota.quota_core import (
    PLAN_CAPABILITIES,
    PLAN_NAMES,
    QuotaInfo,
    TrialPhaseInfo,
    _cache_plan_status,
    _get_cached_plan_status,
    get_plan_capabilities,
)
from quota.quota_atomic import (
    SUBSCRIPTION_GRACE_DAYS,
    get_monthly_quota_used,
    get_quota_reset_date,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Profile-Based Plan Fallback (prevents "fail to free" anti-pattern)
# ============================================================================

def get_plan_from_profile(user_id: str, sb=None) -> Optional[str]:
    """Get user's plan from profiles.plan_type (reliable fallback).

    This is the safety net: profiles.plan_type is updated synchronously
    during plan activation (_activate_plan) and by admin actions, so it
    reflects the user's LAST KNOWN paid plan even when user_subscriptions
    has transient issues (billing gaps, Stripe webhook delays, DB errors).

    Returns valid plan_id or None if lookup fails.
    """
    try:
        if sb is None:
            from supabase_client import get_supabase
            sb = get_supabase()

        result = (
            sb.table("profiles")
            .select("plan_type")
            .eq("id", user_id)
            .single()
            .execute()
        )

        if not result.data:
            return None

        plan_type = result.data.get("plan_type", "free_trial")

        # Map legacy profile values to current plan IDs
        PLAN_TYPE_MAP = {
            "master": "sala_guerra",
            "premium": "maquina",
            "basic": "consultor_agil",
            "free": "free_trial",
        }
        mapped = PLAN_TYPE_MAP.get(plan_type, plan_type)

        plan_caps = get_plan_capabilities()
        if mapped in plan_caps:
            return mapped

        logger.warning(
            f"Unknown plan_type '{plan_type}' in profile for user {mask_user_id(user_id)}, "
            f"mapped to '{mapped}' which is not in plan capabilities"
        )
        return None

    except Exception as e:
        logger.warning(f"Failed to get plan from profile for user {mask_user_id(user_id)}: {e}")
        return None


# ============================================================================
# Main Quota Check
# ============================================================================

def check_quota(user_id: str) -> QuotaInfo:
    """
    Check user's plan and quota status.

    Returns complete quota info including capabilities and usage.

    RESILIENCE: Uses a multi-layer lookup to prevent paid users from
    being downgraded to free_trial due to transient errors:
      1. Active subscription in user_subscriptions (primary)
      2. Recently-expired subscription within grace period (billing gap)
      3. profiles.plan_type (last known plan - reliable fallback)
      4. free_trial (absolute last resort - only for truly new users)

    STORY-291 AC3/AC4: When Supabase CB is open, uses in-memory plan cache
    as fallback. If cache miss, allows search (fail-open) with logging.
    """
    from supabase_client import get_supabase, supabase_cb, CircuitBreakerOpenError
    sb = get_supabase()

    plan_id = None
    expires_at_dt: Optional[datetime] = None
    subscription_found = False
    cb_open = False

    # --- Layer 0 (STORY-291): Check if CB is open — use cache fallback ---
    if supabase_cb.state == "OPEN":
        cb_open = True
        cached_plan = _get_cached_plan_status(user_id)
        if cached_plan:
            logger.info(
                f"STORY-291 CB OPEN: Using cached plan '{cached_plan}' for user {mask_user_id(user_id)}"
            )
            plan_id = cached_plan
            subscription_found = True
        else:
            logger.warning(
                f"STORY-291 CB OPEN + CACHE MISS for user {mask_user_id(user_id)}: "
                f"Allowing search (fail-open). Will reconcile later."
            )
            plan_id = "free_trial"  # CRIT-SEC: Conservative fail-open (was smartlic_pro)
            subscription_found = True

    # --- Layer 1: Active subscription ---
    if not subscription_found:
        try:
            result = supabase_cb.call_sync(
                sb.table("user_subscriptions")
                .select("id, plan_id, expires_at")
                .eq("user_id", user_id)
                .eq("is_active", True)
                .order("created_at", desc=True)
                .limit(1)
                .execute
            )

            if result.data and len(result.data) > 0:
                sub = result.data[0]
                plan_id = sub.get("plan_id", None)
                expires_at_str = sub.get("expires_at")
                expires_at_dt = (
                    datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                    if expires_at_str
                    else None
                )
                subscription_found = True

        except CircuitBreakerOpenError:
            cb_open = True
            logger.warning(f"STORY-291 CB OPEN during subscription check for user {mask_user_id(user_id)}")
        except Exception as e:
            logger.error(f"Error fetching active subscription for user {mask_user_id(user_id)}: {e}")

    # --- Layer 2: Recently-expired subscription (grace period for billing gaps) ---
    if not subscription_found and not cb_open:
        try:
            grace_cutoff = (datetime.now(timezone.utc) - timedelta(days=SUBSCRIPTION_GRACE_DAYS)).isoformat()
            result = supabase_cb.call_sync(
                sb.table("user_subscriptions")
                .select("id, plan_id, expires_at")
                .eq("user_id", user_id)
                .gte("expires_at", grace_cutoff)
                .order("expires_at", desc=True)
                .limit(1)
                .execute
            )

            if result.data and len(result.data) > 0:
                sub = result.data[0]
                plan_id = sub.get("plan_id", None)
                expires_at_str = sub.get("expires_at")
                expires_at_dt = (
                    datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                    if expires_at_str
                    else None
                )
                subscription_found = True
                logger.info(
                    f"Using grace-period subscription for user {mask_user_id(user_id)}: "
                    f"plan={plan_id}, expires_at={expires_at_str}"
                )
        except CircuitBreakerOpenError:
            cb_open = True
            logger.warning(f"STORY-291 CB OPEN during grace-period check for user {mask_user_id(user_id)}")
        except Exception as e:
            logger.warning(f"Error fetching grace-period subscription for user {mask_user_id(user_id)}: {e}")

    # --- Layer 2.5 (STORY-291): CB opened mid-flow — check cache ---
    if cb_open and not subscription_found:
        cached_plan = _get_cached_plan_status(user_id)
        if cached_plan:
            logger.info(f"STORY-291 CB OPEN mid-flow: Using cached plan '{cached_plan}' for {mask_user_id(user_id)}")
            plan_id = cached_plan
            subscription_found = True
        else:
            logger.warning(
                f"STORY-291 CB OPEN + CACHE MISS for user {mask_user_id(user_id)}: fail-open"
            )
            plan_id = "smartlic_pro"
            subscription_found = True

    # --- Layer 3: Profile-based fallback (last known plan) ---
    if not subscription_found or not plan_id:
        profile_plan = get_plan_from_profile(user_id, sb)
        if profile_plan and profile_plan != "free_trial":
            logger.warning(
                f"FALLBACK ACTIVATED for user {mask_user_id(user_id)}: "
                f"no active subscription found, using profiles.plan_type='{profile_plan}'. "
                f"This may indicate a Stripe billing gap or webhook failure."
            )
            plan_id = profile_plan
            expires_at_dt = None
        elif not plan_id:
            plan_id = "free_trial"
            expires_at_dt = None

    # STORY-291 AC3: Cache plan status for future CB-open fallback
    if plan_id and not cb_open:
        _cache_plan_status(user_id, plan_id)

    # STORY-203 SYS-M04: Get plan capabilities from database-driven cache
    plan_caps = get_plan_capabilities()
    caps = plan_caps.get(plan_id, plan_caps.get("free_trial", PLAN_CAPABILITIES["free_trial"]))
    plan_name = PLAN_NAMES.get(plan_id, "FREE Trial")

    # Check expiry — ONLY for free_trial (trial expiry) vs paid (billing grace)
    if expires_at_dt and datetime.now(timezone.utc) > expires_at_dt:
        if plan_id == "free_trial":
            # P0 zero-churn: 48h grace period for trial users (was: block immediately)
            _TRIAL_GRACE_HOURS = int(os.getenv("TRIAL_GRACE_HOURS", "48"))
            _TRIAL_GRACE_MAX_SEARCHES = int(os.getenv("TRIAL_GRACE_MAX_SEARCHES", "3"))
            trial_grace_end = expires_at_dt + timedelta(hours=_TRIAL_GRACE_HOURS)
            now_utc = datetime.now(timezone.utc)

            if now_utc > trial_grace_end:
                return QuotaInfo(
                    allowed=False,
                    plan_id=plan_id,
                    plan_name=plan_name,
                    capabilities=caps,
                    quota_used=0,
                    quota_remaining=0,
                    quota_reset_date=get_quota_reset_date(),
                    trial_expires_at=expires_at_dt,
                    error_message="Seu trial expirou. Veja o valor que você analisou e continue tendo vantagem.",
                )

            grace_used = get_monthly_quota_used(user_id)
            if grace_used >= _TRIAL_GRACE_MAX_SEARCHES:
                return QuotaInfo(
                    allowed=False,
                    plan_id=plan_id,
                    plan_name=plan_name,
                    capabilities=caps,
                    quota_used=grace_used,
                    quota_remaining=0,
                    quota_reset_date=get_quota_reset_date(),
                    trial_expires_at=expires_at_dt,
                    error_message=(
                        f"Você usou suas {_TRIAL_GRACE_MAX_SEARCHES} buscas do período de "
                        f"cortesia. Assine o SmartLic Pro para continuar."
                    ),
                )

            logger.info(
                f"User {mask_user_id(user_id)} in trial grace period "
                f"(expired={expires_at_dt.isoformat()}, "
                f"grace_until={trial_grace_end.isoformat()}, "
                f"grace_searches={grace_used}/{_TRIAL_GRACE_MAX_SEARCHES})"
            )
        else:
            grace_end = expires_at_dt + timedelta(days=SUBSCRIPTION_GRACE_DAYS)
            if datetime.now(timezone.utc) > grace_end:
                return QuotaInfo(
                    allowed=False,
                    plan_id=plan_id,
                    plan_name=plan_name,
                    capabilities=caps,
                    quota_used=0,
                    quota_remaining=0,
                    quota_reset_date=get_quota_reset_date(),
                    trial_expires_at=expires_at_dt,
                    error_message=(
                        f"Sua assinatura {plan_name} expirou. "
                        f"Renove para continuar com acesso completo."
                    ),
                )
            logger.info(
                f"User {mask_user_id(user_id)} in billing grace period "
                f"(plan={plan_id}, expired={expires_at_dt.isoformat()}, "
                f"grace_until={grace_end.isoformat()})"
            )

    # Check monthly quota
    quota_used = get_monthly_quota_used(user_id)
    quota_limit = caps["max_requests_per_month"]
    quota_remaining = max(0, quota_limit - quota_used)

    if quota_used >= quota_limit:
        reset_date = get_quota_reset_date()
        return QuotaInfo(
            allowed=False,
            plan_id=plan_id,
            plan_name=plan_name,
            capabilities=caps,
            quota_used=quota_used,
            quota_remaining=0,
            quota_reset_date=reset_date,
            trial_expires_at=expires_at_dt,
            error_message=f"Você atingiu {quota_limit} análises este mês. Seu limite renova em {reset_date.strftime('%d/%m/%Y')}.",
        )

    # STORY-309 AC5: Dunning degradation — restrict access based on days since first failure
    subscription_status_for_dunning = None
    try:
        if not cb_open:
            status_result = supabase_cb.call_sync(
                sb.table("profiles")
                .select("subscription_status")
                .eq("id", user_id)
                .single()
                .execute
            )
            if status_result.data:
                subscription_status_for_dunning = status_result.data.get("subscription_status")
    except Exception:
        pass  # Non-fatal — degrade gracefully

    if subscription_status_for_dunning == "past_due":
        from services.dunning import get_days_since_failure, get_dunning_phase
        days = get_days_since_failure(user_id)
        phase = get_dunning_phase(days)

        if phase == "blocked":
            return QuotaInfo(
                allowed=False,
                plan_id=plan_id,
                plan_name=plan_name,
                capabilities=caps,
                quota_used=0,
                quota_remaining=0,
                quota_reset_date=get_quota_reset_date(),
                trial_expires_at=None,
                error_message="Seu pagamento falhou há mais de 21 dias. Atualize seu método de pagamento para continuar.",
                dunning_phase=phase,
                days_since_failure=days,
            )
        elif phase == "grace_period":
            return QuotaInfo(
                allowed=False,
                plan_id=plan_id,
                plan_name=plan_name,
                capabilities=caps,
                quota_used=0,
                quota_remaining=0,
                quota_reset_date=get_quota_reset_date(),
                trial_expires_at=None,
                error_message="Seu pagamento está pendente. Acesso somente leitura até a regularização.",
                dunning_phase=phase,
                days_since_failure=days,
            )

    # All checks passed
    return QuotaInfo(
        allowed=True,
        plan_id=plan_id,
        plan_name=plan_name,
        capabilities=caps,
        quota_used=quota_used,
        quota_remaining=quota_remaining,
        quota_reset_date=get_quota_reset_date(),
        trial_expires_at=expires_at_dt,
        error_message=None,
    )


# ============================================================================
# STORY-320: Trial Phase (Paywall Suave)
# ============================================================================

def get_trial_phase(user_id: str) -> TrialPhaseInfo:
    """Determine trial phase for soft paywall (STORY-320 AC1).

    - full_access (days 1 to TRIAL_PAYWALL_DAY): all features unrestricted
    - limited_access (day TRIAL_PAYWALL_DAY+1 to end): soft paywall active
    - not_trial: paid user or no trial

    Uses check_quota() to get trial_expires_at, then calculates current day.
    """
    from config import (
        TRIAL_PAYWALL_ENABLED,
        TRIAL_PAYWALL_DAY,
        TRIAL_DURATION_DAYS,
    )

    if not TRIAL_PAYWALL_ENABLED:
        return TrialPhaseInfo(phase="full_access", day=0, days_remaining=999)

    try:
        quota_info = check_quota(user_id)
    except Exception as e:
        logger.warning(f"STORY-320: Failed to check quota for trial phase: {e}")
        return TrialPhaseInfo(phase="full_access", day=0, days_remaining=999)

    if quota_info.plan_id != "free_trial":
        return TrialPhaseInfo(phase="not_trial", day=0, days_remaining=999)

    if not quota_info.trial_expires_at:
        return TrialPhaseInfo(phase="full_access", day=0, days_remaining=999)

    now = datetime.now(timezone.utc)

    trial_start = quota_info.trial_expires_at - timedelta(days=TRIAL_DURATION_DAYS)
    elapsed = now - trial_start
    current_day = max(1, elapsed.days + 1)

    diff = quota_info.trial_expires_at - now
    days_remaining = max(0, diff.days + (1 if diff.seconds > 0 else 0))

    if current_day > TRIAL_PAYWALL_DAY:
        phase = "limited_access"
    else:
        phase = "full_access"

    return TrialPhaseInfo(phase=phase, day=current_day, days_remaining=days_remaining)


# ============================================================================
# Exception Types
# ============================================================================

class QuotaExceededError(Exception):
    """Raised when user has no remaining search credits."""
    pass


# require_active_plan, _require_active_plan_dep, get_active_plan_dependency
# moved to quota.plan_auth (TD-007 DEBT-07 split — AC3 LOC constraint)
from quota.plan_auth import (
    require_active_plan,
    _require_active_plan_dep,
    get_active_plan_dependency,
    requires_subcontract_intel,
    get_subcontract_intel_dependency,
    requires_workspace_basic,
    get_workspace_basic_dependency,
)


def _ensure_profile_exists(user_id: str, sb) -> bool:
    """Ensure user profile exists in the profiles table.

    Creates a minimal profile if one doesn't exist (handles cases where
    the trigger on auth.users didn't fire or failed).

    Returns True if profile exists or was created, False on error.
    """
    try:
        result = sb.table("profiles").select("id").eq("id", user_id).execute()
        if result.data and len(result.data) > 0:
            return True

        try:
            user_data = sb.auth.admin.get_user_by_id(user_id)
            email = user_data.user.email if user_data and user_data.user else f"{user_id[:8]}@placeholder.local"
        except Exception as e:
            logger.warning(f"Could not fetch user email for profile creation: {e}")
            email = f"{user_id[:8]}@placeholder.local"

        sb.table("profiles").insert({
            "id": user_id,
            "email": email,
            "plan_type": "free_trial",
        }).execute()
        logger.info(f"Created missing profile for user {mask_user_id(user_id)}")
        return True
    except Exception as e:
        logger.error(f"Failed to ensure profile exists for user {mask_user_id(user_id)}: {e}")
        return False


# ============================================================================
# Shared Fallback Builders (AC7: eliminate duplication across routes)
# ============================================================================

def create_fallback_quota_info(user_id: str) -> "QuotaInfo":
    """Create QuotaInfo from profile's plan_type when subscription check fails."""
    fallback_plan = get_plan_from_profile(user_id) or "free_trial"
    fallback_caps = PLAN_CAPABILITIES.get(fallback_plan, PLAN_CAPABILITIES["free_trial"])
    fallback_name = PLAN_NAMES.get(fallback_plan, "FREE Trial") if fallback_plan != "free_trial" else "FREE Trial"
    if fallback_plan != "free_trial":
        logger.warning(
            f"PLAN FALLBACK for user {mask_user_id(user_id)}: "
            f"subscription check failed, using profiles.plan_type='{fallback_plan}'"
        )
    return QuotaInfo(
        allowed=True,
        plan_id=fallback_plan,
        plan_name=fallback_name,
        capabilities=fallback_caps,
        quota_used=0,
        quota_remaining=999999,
        quota_reset_date=datetime.now(timezone.utc),
        trial_expires_at=None,
        error_message=None,
    )


def create_legacy_quota_info() -> "QuotaInfo":
    """Create QuotaInfo for legacy mode (ENABLE_NEW_PRICING=false)."""
    return QuotaInfo(
        allowed=True,
        plan_id="legacy",
        plan_name="Legacy",
        capabilities=PLAN_CAPABILITIES["free_trial"],
        quota_used=0,
        quota_remaining=999999,
        quota_reset_date=datetime.now(timezone.utc),
        trial_expires_at=None,
        error_message=None,
    )



# register_search_session, update_search_session_status, save_search_session
# moved to quota.session_tracker (TD-007 DEBT-07 split — AC3 LOC constraint)
from quota.session_tracker import (
    register_search_session,
    update_search_session_status,
    save_search_session,
)
