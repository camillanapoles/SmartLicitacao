"""Admin response schemas."""

from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class TraceMallocEntry(BaseModel):
    """Single tracemalloc allocation entry."""
    filename: str
    lineno: int
    size_kb: float
    count: int


class MemorySnapshot(BaseModel):
    """Response for GET /admin/memory-snapshot (SEN-BE-010 AC0)."""
    rss_bytes: Optional[int] = None
    rss_mb: Optional[float] = None
    tracemalloc_enabled: bool = False
    tracemalloc_top_25: List[TraceMallocEntry] = []
    asyncio_tasks_pending: int = 0
    gc_objects_count: int = 0
    redis_pool_size: Optional[int] = None


class AdminUsersListResponse(BaseModel):
    """Response for GET /admin/users."""
    users: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int


class AdminCreateUserResponse(BaseModel):
    """Response for POST /admin/users."""
    user_id: str
    email: str
    plan_id: Optional[str] = None


class AdminDeleteUserResponse(BaseModel):
    """Response for DELETE /admin/users/{user_id}."""
    deleted: bool
    user_id: str


class AdminUpdateUserResponse(BaseModel):
    """Response for PUT /admin/users/{user_id}."""
    updated: bool
    user_id: str


class AdminResetPasswordResponse(BaseModel):
    """Response for POST /admin/users/{user_id}/reset-password."""
    success: bool
    user_id: str


class AdminAssignPlanResponse(BaseModel):
    """Response for POST /admin/users/{user_id}/assign-plan."""
    assigned: bool
    user_id: str
    plan_id: str


class AdminUpdateCreditsResponse(BaseModel):
    """Response for PUT /admin/users/{user_id}/credits."""
    success: bool
    user_id: str
    credits: int
    previous_credits: Optional[int] = None
    subscription_created: Optional[bool] = None


# ---------------------------------------------------------------------------
# PARITY-BE-FE-001 (Pass 1): admin_trace.py / admin_cron.py / admin_llm_cost.py
# ---------------------------------------------------------------------------


class AdminJobTriggerResponse(BaseModel):
    """Response for POST /v1/admin/trigger-{contracts,bids}-backfill.

    Routes return ``status`` in {"enqueued", "skipped", "error"} plus an
    optional ``job_id`` (when ARQ accepts the job) and ``timeout_s``.
    ``detail`` carries the operator-facing reason string when non-OK.
    """
    status: str
    job_id: Optional[str] = None
    timeout_s: Optional[int] = None
    detail: Optional[str] = None


class AdminClearCheckpointsResponse(BaseModel):
    """Response for POST /v1/admin/clear-contracts-checkpoints."""
    status: str
    checkpoints_deleted: Optional[int] = None
    detail: Optional[str] = None


class AdminProgressTraceState(BaseModel):
    """``progress`` field of the search-trace response when a tracker
    is still in memory. ``mode`` is ``"redis"`` or ``"in-memory"``.
    """
    uf_count: Optional[int] = None
    ufs_completed: Optional[int] = None
    is_complete: Optional[bool] = None
    created_at: Optional[float] = None
    mode: Optional[str] = None
    error: Optional[str] = None


class AdminJobTraceState(BaseModel):
    """``jobs`` field of the search-trace response.

    Values are short status strings (``"completed"`` / ``"not_found"``)
    so the model accepts them as ``Optional[str]``. ``error`` is present
    when the lookup itself raised.
    """
    llm_summary: Optional[str] = None
    excel_generation: Optional[str] = None
    error: Optional[str] = None


class AdminCacheTraceState(BaseModel):
    """``cache`` field of the search-trace response."""
    is_revalidating: Optional[bool] = None
    redis: Optional[str] = None
    error: Optional[str] = None


class AdminSearchTraceResponse(BaseModel):
    """Response for GET /v1/admin/search-trace/{search_id}.

    Each sub-section is independently nullable: a transient Redis or ARQ
    failure sets the corresponding key to a small ``{"error": "..."}``
    payload instead of failing the whole response.
    """
    search_id: str
    queried_at: str
    progress: Optional[AdminProgressTraceState] = None
    cache: Optional[AdminCacheTraceState] = None
    jobs: Optional[AdminJobTraceState] = None


class AdminCircuitBreakerResetResponse(BaseModel):
    """Response for POST /v1/admin/cb/reset (STORY-416 AC5)."""
    status: str
    previous_states: Dict[str, Any]
    reset_by: Optional[str] = None


class AdminSchemaContractStatusResponse(BaseModel):
    """Response for GET /v1/admin/schema-contract-status (STORY-414 AC4)."""
    passed: Optional[bool] = None
    missing: List[str] = []
    strict_mode: bool = False
    checked_at: float = 0.0
    stale: bool = True


# --- admin_cron.py ---------------------------------------------------------


class CronJobHealthRow(BaseModel):
    """One row of ``public.get_cron_health()`` (STORY-1.1)."""
    jobname: Optional[str] = None
    schedule: Optional[str] = None
    active: Optional[bool] = None
    last_status: Optional[str] = None
    last_run_at: Optional[str] = None
    runs_24h: int = 0
    failures_24h: int = 0
    latency_avg_ms: Optional[int] = None
    last_return_message: Optional[str] = None


class AdminCronStatusResponse(BaseModel):
    """Response for GET /v1/admin/cron-status (STORY-1.1).

    On transient backend failure (Supabase CB open, RPC error) the route
    returns ``status="error"`` with ``jobs=[]`` so dashboards degrade
    gracefully instead of 500-ing.
    """
    status: str
    queried_at: str
    count: int
    jobs: List[CronJobHealthRow]
    detail: Optional[str] = None


# --- admin_llm_cost.py -----------------------------------------------------


class AdminLlmCostResponse(BaseModel):
    """Response for GET /v1/admin/llm-cost (STORY-2.11).

    Mirrors ``llm_budget.get_cost_snapshot()``. ``month`` is the Redis
    key shape (e.g. ``"llm_cost_month_2026_04"``); ``exceeded`` flips
    to ``True`` when the hard-reject is active.
    """
    month_to_date_usd: float = 0.0
    budget_usd: float = 0.0
    pct_used: float = 0.0
    projected_end_of_month_usd: float = 0.0
    month: str
    exceeded: bool = False


# --- LIFECYCLE-003 (#1428): User Segments ------------------------------------


class UserLifecycleTransition(BaseModel):
    """A single lifecycle transition event."""
    user_id: str
    previous_lifecycle: Optional[str] = None
    new_lifecycle: str
    changed_at: str


class PowerUserDetail(BaseModel):
    """Power user detail row for the segments dashboard."""
    user_id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    company: Optional[str] = None
    logins_14d: int = 0
    pipeline_count: int = 0
    alert_count: int = 0
    lifecycle: str


class UserSegmentsResponse(BaseModel):
    """Response for GET /admin/users/segments (LIFECYCLE-003)."""
    count_by_state: dict
    total_users: int
    transitions_last_week: list
    power_users: list
    queried_at: str
