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
