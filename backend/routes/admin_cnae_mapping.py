"""DATA-CNAE-001: Admin CRUD endpoints for ``cnae_setor_mapping`` table.

Allows admins to add, update, and soft-delete CNAE -> sector mappings at
runtime without redeploys. The lookup function
``utils.cnae_mapping.lookup_cnae_setor`` reads from this table (with
hardcoded fallback) and is LRU-cached, so every mutation here calls
:func:`utils.cnae_mapping.invalidate_cnae_cache` to invalidate the cache.

Routes (all under ``/v1/admin``):

* ``GET    /v1/admin/cnae-mapping?setor=<id>``     list (filtered).
* ``POST   /v1/admin/cnae-mapping``                create entry.
* ``PATCH  /v1/admin/cnae-mapping/{cnae_code}``    update entry.
* ``DELETE /v1/admin/cnae-mapping/{cnae_code}``    soft delete.

All endpoints require ``profiles.is_admin = true`` via :func:`admin.require_admin`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from admin import require_admin
from supabase_client import get_supabase, sb_execute_direct
from utils.cnae_mapping import invalidate_cnae_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin", "cnae-mapping"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CnaeMappingCreate(BaseModel):
    cnae_code: str = Field(..., min_length=4, max_length=4, pattern=r"^\d{4}$")
    setor_id: str = Field(..., min_length=1, max_length=64)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    fallback_setor_id: Optional[str] = Field(default=None, max_length=64)
    notes: Optional[str] = Field(default=None, max_length=500)


class CnaeMappingUpdate(BaseModel):
    setor_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    fallback_setor_id: Optional[str] = Field(default=None, max_length=64)
    notes: Optional[str] = Field(default=None, max_length=500)


class CnaeMappingRow(BaseModel):
    cnae_code: str
    setor_id: str
    confidence: float
    fallback_setor_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


class CnaeMappingListResponse(BaseModel):
    count: int
    rows: list[CnaeMappingRow]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize(row: dict[str, Any]) -> CnaeMappingRow:
    return CnaeMappingRow(
        cnae_code=row["cnae_code"],
        setor_id=row["setor_id"],
        confidence=float(row.get("confidence") or 1.0),
        fallback_setor_id=row.get("fallback_setor_id"),
        notes=row.get("notes"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        updated_by=row.get("updated_by"),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/cnae-mapping", response_model=CnaeMappingListResponse)
async def list_cnae_mappings(
    setor: Optional[str] = Query(default=None, description="Filter by setor_id"),
    user: dict = Depends(require_admin),
) -> CnaeMappingListResponse:
    """List CNAE mappings, optionally filtered by ``setor``."""
    try:
        sb = get_supabase()
        query = sb.table("cnae_setor_mapping").select("*").order("cnae_code")
        if setor:
            query = query.eq("setor_id", setor)
        result = await sb_execute_direct(query)
        rows = getattr(result, "data", None) or []
        serialized = [_serialize(r) for r in rows if isinstance(r, dict)]
        return CnaeMappingListResponse(count=len(serialized), rows=serialized)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("list_cnae_mappings failed: %s", exc)
        raise HTTPException(status_code=500, detail="failed to list cnae mappings")


@router.post("/cnae-mapping", response_model=CnaeMappingRow, status_code=201)
async def create_cnae_mapping(
    payload: CnaeMappingCreate,
    user: dict = Depends(require_admin),
) -> CnaeMappingRow:
    """Create a new CNAE -> setor mapping."""
    try:
        sb = get_supabase()
        row = {
            "cnae_code": payload.cnae_code,
            "setor_id": payload.setor_id,
            "confidence": payload.confidence,
            "fallback_setor_id": payload.fallback_setor_id,
            "notes": payload.notes,
            "updated_by": user.get("id") or user.get("sub"),
        }
        # Drop None values so DB defaults / nullable columns are respected.
        row = {k: v for k, v in row.items() if v is not None}
        result = await sb_execute_direct(
            sb.table("cnae_setor_mapping").insert(row)
        )
        data = getattr(result, "data", None) or []
        if not data:
            raise HTTPException(status_code=409, detail="insert returned no row (conflict?)")
        invalidate_cnae_cache()
        return _serialize(data[0])
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("create_cnae_mapping failed: %s", exc)
        msg = str(exc).lower()
        if "duplicate" in msg or "unique" in msg or "23505" in msg:
            raise HTTPException(status_code=409, detail="cnae_code already exists")
        raise HTTPException(status_code=500, detail="failed to create cnae mapping")


@router.patch("/cnae-mapping/{cnae_code}", response_model=CnaeMappingRow)
async def update_cnae_mapping(
    cnae_code: str,
    payload: CnaeMappingUpdate,
    user: dict = Depends(require_admin),
) -> CnaeMappingRow:
    """Patch an existing mapping. Fields not present in the body are untouched."""
    updates: dict[str, Any] = {}
    if payload.setor_id is not None:
        updates["setor_id"] = payload.setor_id
    if payload.confidence is not None:
        updates["confidence"] = payload.confidence
    if payload.fallback_setor_id is not None:
        updates["fallback_setor_id"] = payload.fallback_setor_id
    if payload.notes is not None:
        updates["notes"] = payload.notes
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["updated_by"] = user.get("id") or user.get("sub")

    try:
        sb = get_supabase()
        result = await sb_execute_direct(
            sb.table("cnae_setor_mapping").update(updates).eq("cnae_code", cnae_code)
        )
        data = getattr(result, "data", None) or []
        if not data:
            raise HTTPException(status_code=404, detail="cnae_code not found")
        invalidate_cnae_cache()
        return _serialize(data[0])
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("update_cnae_mapping failed cnae=%s: %s", cnae_code, exc)
        raise HTTPException(status_code=500, detail="failed to update cnae mapping")


@router.delete("/cnae-mapping/{cnae_code}", response_model=CnaeMappingRow)
async def delete_cnae_mapping(
    cnae_code: str,
    user: dict = Depends(require_admin),
) -> CnaeMappingRow:
    """Soft delete: marks ``notes='deleted'`` so audit trail is preserved.

    The DB lookup in ``utils.cnae_mapping._db_lookup`` skips rows with
    ``notes = 'deleted'`` and the LRU cache is invalidated so the next
    request falls back to the hardcoded dict (if present there).
    """
    try:
        sb = get_supabase()
        updates = {
            "notes": "deleted",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": user.get("id") or user.get("sub"),
        }
        result = await sb_execute_direct(
            sb.table("cnae_setor_mapping").update(updates).eq("cnae_code", cnae_code)
        )
        data = getattr(result, "data", None) or []
        if not data:
            raise HTTPException(status_code=404, detail="cnae_code not found")
        invalidate_cnae_cache()
        return _serialize(data[0])
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("delete_cnae_mapping failed cnae=%s: %s", cnae_code, exc)
        raise HTTPException(status_code=500, detail="failed to delete cnae mapping")
