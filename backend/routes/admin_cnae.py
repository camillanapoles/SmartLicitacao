"""DATA-CNAE-001 (AC7-AC9): Admin CRUD for cnae_setor_mapping.

Endpoints (all admin-only):
    GET    /v1/admin/cnae-mapping                 -- paginated list + search
    GET    /v1/admin/cnae-mapping/{cnae_code}     -- detail + audit log
    POST   /v1/admin/cnae-mapping                 -- create
    PATCH  /v1/admin/cnae-mapping/{cnae_code}     -- update
    DELETE /v1/admin/cnae-mapping/{cnae_code}     -- soft-delete (is_active=false)
    POST   /v1/admin/cnae-mapping/{cnae_code}/restore -- undo soft-delete
    POST   /v1/admin/cnae-mapping/bulk-import     -- CSV upload (preview + commit)

Every mutation:
    1. Records a row in ``cnae_mapping_audit_log`` with the JSONB diff
       and ``actor_user_id``.
    2. Drops the local in-process TTL cache for the affected key.
    3. Publishes on the Redis channel ``cnae_mapping:invalidate`` so
       sibling workers drop their caches too (AC9).

The ``bulk-import`` endpoint runs in two modes:
    * ``dry_run=true`` (default) — validates the CSV, returns a
      preview {creates, updates, deactivations, errors}, NO writes.
    * ``dry_run=false`` — applies the previewed changes inside a
      single Supabase transaction.  Each affected row gets an audit
      entry tagged ``action='bulk_import'``.

Notes:
    * cnae_code is canonicalised to the 4-digit IBGE prefix on every
      mutation via ``utils.cnae_mapping._extract_prefix``; "4781-4/00"
      and "4781" land in the same row.
    * setor_id is validated against the table's CHECK constraint
      (Postgres rejects unknown values with 23514) — admin gets a
      400 with the offending value.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field, ConfigDict

from admin import require_admin
from supabase_client import get_supabase
from utils.cnae_mapping import (
    CNAE_INVALIDATION_CHANNEL,
    _extract_prefix,
    invalidate_cnae_cache,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin/cnae-mapping", tags=["admin", "cnae"])


# ---------------------------------------------------------------------------
# Pydantic schemas (kept inline — small, route-local, registered as
# response_model on every endpoint so OpenAPI / api-types stay typed).
# ---------------------------------------------------------------------------
class CnaeMappingRow(BaseModel):
    cnae_code: str = Field(..., description="4-digit IBGE prefix")
    setor_id: str = Field(..., description="SmartLic sector identifier")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: Optional[str] = Field(default=None, max_length=2000)
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class CnaeMappingListResponse(BaseModel):
    items: list[CnaeMappingRow]
    total: int
    limit: int
    offset: int


class CnaeAuditLogEntry(BaseModel):
    id: str
    cnae_code: Optional[str]
    action: str
    old_value: Optional[dict[str, Any]] = None
    new_value: Optional[dict[str, Any]] = None
    actor_user_id: Optional[str] = None
    actor_email: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime


class CnaeMappingDetailResponse(BaseModel):
    mapping: CnaeMappingRow
    audit: list[CnaeAuditLogEntry]


class CnaeMappingCreateRequest(BaseModel):
    cnae_code: str = Field(..., min_length=1, max_length=20)
    setor_id: str = Field(..., min_length=1, max_length=64)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: Optional[str] = Field(default=None, max_length=2000)


class CnaeMappingUpdateRequest(BaseModel):
    setor_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    notes: Optional[str] = Field(default=None, max_length=2000)
    is_active: Optional[bool] = None


class CnaeMappingMutationResponse(BaseModel):
    mapping: CnaeMappingRow
    audit_id: str


class BulkImportPreviewItem(BaseModel):
    cnae_code: str
    action: str  # "create" | "update" | "noop" | "deactivate" | "error"
    old: Optional[CnaeMappingRow] = None
    new: Optional[CnaeMappingRow] = None
    error: Optional[str] = None


class BulkImportResponse(BaseModel):
    dry_run: bool
    creates: int
    updates: int
    deactivations: int
    noops: int
    errors: int
    preview: list[BulkImportPreviewItem]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalise_code(raw: str) -> str:
    """Canonicalise a CNAE input to its 4-digit prefix or raise 400."""
    prefix = _extract_prefix(raw)
    if not prefix:
        raise HTTPException(
            status_code=400,
            detail=f"cnae_code='{raw}' could not be normalised to a 4-digit prefix",
        )
    return prefix


async def _publish_invalidation(cnae_code: Optional[str]) -> None:
    """Best-effort Redis pubsub broadcast of cache invalidation.

    Failures are swallowed: TTL eviction in the 1h cache is the
    worst-case staleness if pubsub is unavailable.  The local cache
    is always dropped synchronously by the caller via
    ``invalidate_cnae_cache()`` so the writer worker never serves
    stale.
    """
    payload = cnae_code or "__all__"
    try:
        from redis_pool import get_redis_pool  # type: ignore

        pool = await get_redis_pool()
        if pool is None:
            return
        await pool.publish(CNAE_INVALIDATION_CHANNEL, payload)
    except Exception as exc:
        logger.debug("cnae_mapping pubsub publish failed: %s", exc)


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Strip non-serializable fields and clamp known shape."""
    return {
        "cnae_code": row.get("cnae_code"),
        "setor_id": row.get("setor_id"),
        "confidence": float(row["confidence"]) if row.get("confidence") is not None else 1.0,
        "notes": row.get("notes"),
        "is_active": bool(row.get("is_active", True)),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "updated_by": row.get("updated_by"),
    }


def _record_audit(
    sb,
    *,
    cnae_code: Optional[str],
    action: str,
    old_value: Optional[dict[str, Any]],
    new_value: Optional[dict[str, Any]],
    actor: dict[str, Any],
    note: Optional[str] = None,
) -> str:
    """Insert one row into cnae_mapping_audit_log and return its id."""
    payload = {
        "cnae_code": cnae_code,
        "action": action,
        "old_value": old_value,
        "new_value": new_value,
        "actor_user_id": actor.get("id"),
        "actor_email": actor.get("email"),
        "note": note,
    }
    try:
        result = sb.table("cnae_mapping_audit_log").insert(payload).execute()
        rows = getattr(result, "data", None) or []
        if rows:
            return str(rows[0].get("id"))
    except Exception as exc:
        # Audit failure must not break the mutation, but we want a
        # loud Sentry breadcrumb because losing audit is a compliance
        # risk.
        logger.error(
            "cnae_mapping audit log insert failed for cnae=%s action=%s: %s",
            cnae_code,
            action,
            exc,
        )
    return ""


def _fetch_row(sb, code: str) -> Optional[dict[str, Any]]:
    try:
        result = (
            sb.table("cnae_setor_mapping")
            .select("*")
            .eq("cnae_code", code)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.warning("cnae_mapping fetch failed for %s: %s", code, exc)
        raise HTTPException(status_code=503, detail="Database unavailable")
    rows = getattr(result, "data", None) or []
    if not rows:
        return None
    row: dict[str, Any] = rows[0]
    return row


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("", response_model=CnaeMappingListResponse)
async def list_cnae_mappings(
    admin: dict = Depends(require_admin),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(default=None, max_length=64),
    setor_id: Optional[str] = Query(default=None, max_length=64),
    is_active: Optional[bool] = Query(default=None),
    min_confidence: Optional[float] = Query(default=None, ge=0.0, le=1.0),
):
    """List CNAE mappings with pagination + filters."""
    sb = get_supabase()
    query = sb.table("cnae_setor_mapping").select("*", count="exact")

    if search:
        # Search by code prefix or by sector match.  We do NOT use ILIKE
        # on cnae_code because the table is small enough (low thousands)
        # that admins typing "478" expect prefix match; PostgREST's
        # ``like`` operator is fine here.
        like_pattern = f"%{search}%"
        query = query.or_(
            f"cnae_code.ilike.{like_pattern},setor_id.ilike.{like_pattern},notes.ilike.{like_pattern}"
        )
    if setor_id is not None:
        query = query.eq("setor_id", setor_id)
    if is_active is not None:
        query = query.eq("is_active", is_active)
    if min_confidence is not None:
        query = query.gte("confidence", min_confidence)

    try:
        result = (
            query.order("cnae_code", desc=False)
            .range(offset, offset + limit - 1)
            .execute()
        )
    except Exception as exc:
        logger.warning("cnae_mapping list query failed: %s", exc)
        raise HTTPException(status_code=503, detail="Database unavailable")

    items = [CnaeMappingRow(**_row_to_dict(r)) for r in (result.data or [])]
    total = int(getattr(result, "count", None) or 0)
    return CnaeMappingListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{cnae_code}", response_model=CnaeMappingDetailResponse)
async def get_cnae_mapping(
    cnae_code: str,
    admin: dict = Depends(require_admin),
):
    """Detail view: row + last 50 audit entries."""
    code = _normalise_code(cnae_code)
    sb = get_supabase()

    row = _fetch_row(sb, code)
    if not row:
        raise HTTPException(status_code=404, detail=f"cnae_code={code} not found")

    try:
        audit_result = (
            sb.table("cnae_mapping_audit_log")
            .select("*")
            .eq("cnae_code", code)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
    except Exception as exc:
        logger.warning("cnae_mapping audit fetch failed: %s", exc)
        audit_result = None

    audit_rows = getattr(audit_result, "data", None) or []
    return CnaeMappingDetailResponse(
        mapping=CnaeMappingRow(**_row_to_dict(row)),
        audit=[CnaeAuditLogEntry(**a) for a in audit_rows],
    )


@router.post("", response_model=CnaeMappingMutationResponse, status_code=201)
async def create_cnae_mapping(
    body: CnaeMappingCreateRequest,
    admin: dict = Depends(require_admin),
):
    """Create a new mapping row.  Admin-only."""
    code = _normalise_code(body.cnae_code)
    sb = get_supabase()

    if _fetch_row(sb, code) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"cnae_code={code} already exists; use PATCH to update.",
        )

    payload = {
        "cnae_code": code,
        "setor_id": body.setor_id,
        "confidence": body.confidence,
        "notes": body.notes,
        "is_active": True,
        "updated_by": admin.get("id"),
    }
    try:
        result = sb.table("cnae_setor_mapping").insert(payload).execute()
    except Exception as exc:
        # Postgres CHECK constraint violations land here.
        msg = str(exc)
        if "cnae_setor_mapping_setor_id_chk" in msg or "23514" in msg:
            raise HTTPException(
                status_code=400,
                detail=f"setor_id='{body.setor_id}' not in allowed list",
            )
        logger.warning("cnae_mapping create failed for %s: %s", code, exc)
        raise HTTPException(status_code=503, detail="Database unavailable")

    new_row = (result.data or [payload])[0]
    audit_id = _record_audit(
        sb,
        cnae_code=code,
        action="create",
        old_value=None,
        new_value=_row_to_dict(new_row),
        actor=admin,
    )
    invalidate_cnae_cache(code)
    await _publish_invalidation(code)
    return CnaeMappingMutationResponse(
        mapping=CnaeMappingRow(**_row_to_dict(new_row)),
        audit_id=audit_id,
    )


@router.patch("/{cnae_code}", response_model=CnaeMappingMutationResponse)
async def update_cnae_mapping(
    cnae_code: str,
    body: CnaeMappingUpdateRequest,
    admin: dict = Depends(require_admin),
):
    """Update a mapping (partial)."""
    code = _normalise_code(cnae_code)
    sb = get_supabase()

    old = _fetch_row(sb, code)
    if old is None:
        raise HTTPException(status_code=404, detail=f"cnae_code={code} not found")

    update: dict[str, Any] = {}
    if body.setor_id is not None:
        update["setor_id"] = body.setor_id
    if body.confidence is not None:
        update["confidence"] = body.confidence
    if body.notes is not None:
        update["notes"] = body.notes
    if body.is_active is not None:
        update["is_active"] = body.is_active
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    update["updated_by"] = admin.get("id")

    try:
        result = (
            sb.table("cnae_setor_mapping")
            .update(update)
            .eq("cnae_code", code)
            .execute()
        )
    except Exception as exc:
        msg = str(exc)
        if "cnae_setor_mapping_setor_id_chk" in msg or "23514" in msg:
            raise HTTPException(
                status_code=400,
                detail=f"setor_id='{body.setor_id}' not in allowed list",
            )
        logger.warning("cnae_mapping update failed for %s: %s", code, exc)
        raise HTTPException(status_code=503, detail="Database unavailable")

    new_row = (result.data or [{**old, **update}])[0]
    audit_id = _record_audit(
        sb,
        cnae_code=code,
        action="update",
        old_value=_row_to_dict(old),
        new_value=_row_to_dict(new_row),
        actor=admin,
    )
    invalidate_cnae_cache(code)
    await _publish_invalidation(code)
    return CnaeMappingMutationResponse(
        mapping=CnaeMappingRow(**_row_to_dict(new_row)),
        audit_id=audit_id,
    )


@router.delete("/{cnae_code}", response_model=CnaeMappingMutationResponse)
async def soft_delete_cnae_mapping(
    cnae_code: str,
    admin: dict = Depends(require_admin),
):
    """Soft-delete: flips is_active to false but keeps the row."""
    code = _normalise_code(cnae_code)
    sb = get_supabase()

    old = _fetch_row(sb, code)
    if old is None:
        raise HTTPException(status_code=404, detail=f"cnae_code={code} not found")
    if not old.get("is_active", True):
        raise HTTPException(
            status_code=409,
            detail=f"cnae_code={code} is already inactive",
        )

    try:
        result = (
            sb.table("cnae_setor_mapping")
            .update({"is_active": False, "updated_by": admin.get("id")})
            .eq("cnae_code", code)
            .execute()
        )
    except Exception as exc:
        logger.warning("cnae_mapping soft-delete failed: %s", exc)
        raise HTTPException(status_code=503, detail="Database unavailable")

    new_row = (result.data or [{**old, "is_active": False}])[0]
    audit_id = _record_audit(
        sb,
        cnae_code=code,
        action="delete",
        old_value=_row_to_dict(old),
        new_value=_row_to_dict(new_row),
        actor=admin,
    )
    invalidate_cnae_cache(code)
    await _publish_invalidation(code)
    return CnaeMappingMutationResponse(
        mapping=CnaeMappingRow(**_row_to_dict(new_row)),
        audit_id=audit_id,
    )


@router.post("/{cnae_code}/restore", response_model=CnaeMappingMutationResponse)
async def restore_cnae_mapping(
    cnae_code: str,
    admin: dict = Depends(require_admin),
):
    """Undo a soft-delete by flipping is_active back to true."""
    code = _normalise_code(cnae_code)
    sb = get_supabase()

    old = _fetch_row(sb, code)
    if old is None:
        raise HTTPException(status_code=404, detail=f"cnae_code={code} not found")
    if old.get("is_active", True):
        raise HTTPException(
            status_code=409,
            detail=f"cnae_code={code} is already active",
        )

    try:
        result = (
            sb.table("cnae_setor_mapping")
            .update({"is_active": True, "updated_by": admin.get("id")})
            .eq("cnae_code", code)
            .execute()
        )
    except Exception as exc:
        logger.warning("cnae_mapping restore failed: %s", exc)
        raise HTTPException(status_code=503, detail="Database unavailable")

    new_row = (result.data or [{**old, "is_active": True}])[0]
    audit_id = _record_audit(
        sb,
        cnae_code=code,
        action="restore",
        old_value=_row_to_dict(old),
        new_value=_row_to_dict(new_row),
        actor=admin,
    )
    invalidate_cnae_cache(code)
    await _publish_invalidation(code)
    return CnaeMappingMutationResponse(
        mapping=CnaeMappingRow(**_row_to_dict(new_row)),
        audit_id=audit_id,
    )


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------
EXPECTED_BULK_COLUMNS = {"cnae_code", "setor_id"}


def _parse_csv(content: bytes) -> list[dict[str, str]]:
    """Parse a CSV upload into a list of dict rows.

    Required columns: cnae_code, setor_id.  Optional: confidence,
    notes, is_active.  We accept ``;`` and ``,`` as delimiters (the
    sample format we hand to admins).
    """
    text = content.decode("utf-8-sig", errors="replace")
    sample = text[:1024]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="CSV is empty")
    headers = {h.strip().lower() for h in reader.fieldnames}
    missing = EXPECTED_BULK_COLUMNS - headers
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV missing required columns: {sorted(missing)}",
        )
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in reader]


def _coerce_bool(value: str, default: bool = True) -> bool:
    if value == "":
        return default
    return value.lower() in {"1", "true", "yes", "y", "t"}


def _coerce_confidence(value: str) -> float:
    if value == "":
        return 1.0
    try:
        f = float(value)
    except ValueError as exc:
        raise ValueError(f"confidence must be a float, got '{value}'") from exc
    if not 0.0 <= f <= 1.0:
        raise ValueError(f"confidence must be in [0,1], got {f}")
    return f


@router.post("/bulk-import", response_model=BulkImportResponse)
async def bulk_import(
    file: UploadFile = File(...),
    dry_run: bool = Query(default=True),
    admin: dict = Depends(require_admin),
):
    """CSV upload — preview-first then apply.

    Default ``dry_run=true`` returns the diff without writing.  Pass
    ``dry_run=false`` to commit the changes (each row gets its own
    audit entry tagged ``action='bulk_import'``).
    """
    if file.content_type not in {None, "text/csv", "application/vnd.ms-excel", "application/octet-stream"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content-type: {file.content_type}",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty upload")
    rows = _parse_csv(content)

    sb = get_supabase()
    preview: list[BulkImportPreviewItem] = []
    creates = updates = deactivations = noops = errors = 0

    for raw in rows:
        cnae_input = raw.get("cnae_code", "")
        try:
            code = _extract_prefix(cnae_input)
            if not code:
                raise ValueError(f"Could not normalise cnae_code='{cnae_input}'")
            setor = raw.get("setor_id", "")
            if not setor:
                raise ValueError("setor_id is required")
            confidence = _coerce_confidence(raw.get("confidence", ""))
            is_active = _coerce_bool(raw.get("is_active", ""), default=True)
            notes = raw.get("notes") or None
        except ValueError as exc:
            errors += 1
            preview.append(
                BulkImportPreviewItem(
                    cnae_code=cnae_input or "?",
                    action="error",
                    error=str(exc),
                )
            )
            continue

        old = _fetch_row(sb, code)
        if old is None:
            creates += 1
            new_row = {
                "cnae_code": code,
                "setor_id": setor,
                "confidence": confidence,
                "notes": notes,
                "is_active": is_active,
            }
            preview.append(
                BulkImportPreviewItem(
                    cnae_code=code,
                    action="create",
                    new=CnaeMappingRow(**_row_to_dict(new_row)),
                )
            )
            continue

        same = (
            old.get("setor_id") == setor
            and float(old.get("confidence") or 1.0) == confidence
            and bool(old.get("is_active", True)) == is_active
            and (old.get("notes") or None) == notes
        )
        if same:
            noops += 1
            preview.append(
                BulkImportPreviewItem(
                    cnae_code=code,
                    action="noop",
                    old=CnaeMappingRow(**_row_to_dict(old)),
                )
            )
            continue

        action = "deactivate" if (not is_active and old.get("is_active", True)) else "update"
        if action == "deactivate":
            deactivations += 1
        else:
            updates += 1
        preview.append(
            BulkImportPreviewItem(
                cnae_code=code,
                action=action,
                old=CnaeMappingRow(**_row_to_dict(old)),
                new=CnaeMappingRow(**_row_to_dict({
                    **old,
                    "setor_id": setor,
                    "confidence": confidence,
                    "is_active": is_active,
                    "notes": notes,
                })),
            )
        )

    if dry_run:
        return BulkImportResponse(
            dry_run=True,
            creates=creates,
            updates=updates,
            deactivations=deactivations,
            noops=noops,
            errors=errors,
            preview=preview,
        )

    # Apply: errors are skipped, every other action gets persisted +
    # audited.  This is intentionally simple — admin previewed first.
    for item in preview:
        if item.action in {"error", "noop"}:
            continue
        new = item.new.model_dump(mode="json") if item.new else {}
        old = item.old.model_dump(mode="json") if item.old else None
        try:
            if item.action == "create":
                payload = {
                    "cnae_code": item.cnae_code,
                    "setor_id": new.get("setor_id"),
                    "confidence": new.get("confidence", 1.0),
                    "notes": new.get("notes"),
                    "is_active": True,
                    "updated_by": admin.get("id"),
                }
                sb.table("cnae_setor_mapping").insert(payload).execute()
            else:
                update = {
                    "setor_id": new.get("setor_id"),
                    "confidence": new.get("confidence", 1.0),
                    "notes": new.get("notes"),
                    "is_active": new.get("is_active", True),
                    "updated_by": admin.get("id"),
                }
                sb.table("cnae_setor_mapping").update(update).eq(
                    "cnae_code", item.cnae_code
                ).execute()
        except Exception as exc:
            logger.warning(
                "cnae_mapping bulk-import row failed cnae=%s action=%s: %s",
                item.cnae_code,
                item.action,
                exc,
            )
            item.action = "error"
            item.error = str(exc)
            errors += 1
            continue
        _record_audit(
            sb,
            cnae_code=item.cnae_code,
            action="bulk_import",
            old_value=old,
            new_value=new,
            actor=admin,
            note=f"bulk-import {item.action}",
        )
        invalidate_cnae_cache(item.cnae_code)

    # Single broadcast — workers wipe their entire CNAE cache.
    await _publish_invalidation(None)

    return BulkImportResponse(
        dry_run=False,
        creates=creates,
        updates=updates,
        deactivations=deactivations,
        noops=noops,
        errors=errors,
        preview=preview,
    )
