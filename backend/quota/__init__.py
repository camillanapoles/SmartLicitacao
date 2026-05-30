"""Quota management package — facade re-export for backwards compatibility.

TD-007: quota.py (1660 LOC) split into:
  - quota_core.py      — plan definitions, capabilities, types
  - quota_atomic.py    — atomic DB quota operations
  - plan_enforcement.py — check_quota, require_active_plan, sessions

All original symbols re-exported here so that `from quota import X` continues
to work without any changes in callers (AC2 — zero broken imports).
"""

# quota_core: plan definitions, capabilities, status cache, types
from quota.quota_core import (
    PLAN_CAPABILITIES,
    PLAN_CAPABILITIES_CACHE_TTL,
    PLAN_NAMES,
    PLAN_PRICES,
    PLAN_STATUS_CACHE_MAXSIZE,
    PLAN_STATUS_CACHE_TTL,
    UPGRADE_SUGGESTIONS,
    PlanCapabilities,
    PlanPriority,
    QuotaInfo,
    TrialPhaseInfo,
    _cache_plan_status,
    _coerce_capabilities_row,
    _FALLBACK_PLAN_CAPABILITIES,
    _get_cached_plan_status,
    _load_plan_capabilities_from_db,
    _plan_status_cache,
    _plan_status_cache_lock,
    _UNKNOWN_PLAN_DEFAULTS,
    clear_plan_capabilities_cache,
    get_plan_capabilities,
    invalidate_plan_status_cache,
)

# quota_atomic: atomic DB operations
from quota.quota_atomic import (
    SUBSCRIPTION_GRACE_DAYS,
    check_and_increment_org_quota_atomic,
    check_and_increment_quota_atomic,
    get_current_month_key,
    get_monthly_quota_used,
    get_quota_reset_date,
    get_user_org_plan,
    increment_monthly_quota,
)

# plan_enforcement: check_quota, require_active_plan, sessions
from quota.plan_enforcement import (
    QuotaExceededError,
    _ensure_profile_exists,
    _require_active_plan_dep,
    check_quota,
    create_fallback_quota_info,
    create_legacy_quota_info,
    get_active_plan_dependency,
    get_plan_from_profile,
    get_subcontract_intel_dependency,
    get_workspace_basic_dependency,
    get_trial_phase,
    register_search_session,
    require_active_plan,
    requires_subcontract_intel,
    requires_workspace_basic,
    save_search_session,
    update_search_session_status,
)

# plan_auth: re-export via plan_enforcement facade (already re-exported above)
# session_tracker: re-export via plan_enforcement facade (already re-exported above)

__all__ = [
    # quota_core
    "PLAN_CAPABILITIES",
    "PLAN_CAPABILITIES_CACHE_TTL",
    "PLAN_NAMES",
    "PLAN_PRICES",
    "PLAN_STATUS_CACHE_MAXSIZE",
    "PLAN_STATUS_CACHE_TTL",
    "UPGRADE_SUGGESTIONS",
    "PlanCapabilities",
    "PlanPriority",
    "QuotaInfo",
    "TrialPhaseInfo",
    "_cache_plan_status",
    "_coerce_capabilities_row",
    "_FALLBACK_PLAN_CAPABILITIES",
    "_get_cached_plan_status",
    "_load_plan_capabilities_from_db",
    "_plan_status_cache",
    "_plan_status_cache_lock",
    "_UNKNOWN_PLAN_DEFAULTS",
    "clear_plan_capabilities_cache",
    "get_plan_capabilities",
    "invalidate_plan_status_cache",
    # quota_atomic
    "SUBSCRIPTION_GRACE_DAYS",
    "check_and_increment_org_quota_atomic",
    "check_and_increment_quota_atomic",
    "get_current_month_key",
    "get_monthly_quota_used",
    "get_quota_reset_date",
    "get_user_org_plan",
    "increment_monthly_quota",
    # plan_enforcement
    "QuotaExceededError",
    "_ensure_profile_exists",
    "_require_active_plan_dep",
    "check_quota",
    "create_fallback_quota_info",
    "create_legacy_quota_info",
    "get_active_plan_dependency",
    "get_plan_from_profile",
    "get_subcontract_intel_dependency",
    "get_workspace_basic_dependency",
    "get_trial_phase",
    "register_search_session",
    "require_active_plan",
    "requires_subcontract_intel",
    "requires_workspace_basic",
    "save_search_session",
    "update_search_session_status",
]
