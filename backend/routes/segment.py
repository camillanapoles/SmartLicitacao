"""User segmentation endpoint (CONV-018).

Stores segmentation data (sector, UFs, objective type) in the user's
profile context_data for journey personalization.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require_auth
from schemas.user import ObjetivoTipo
from supabase_client import get_supabase, sb_execute

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/segment", tags=["segment"])


class SaveSegmentRequest(BaseModel):
    """Request body for POST /v1/segment/save (CONV-018)."""

    segmento_principal: int | None = Field(
        default=None,
        description="Primary business sector ID from sectors list",
    )
    objetivo_tipo: ObjetivoTipo | None = Field(
        default=None,
        description="User's primary objective: vencer_licitacao, subcontratar, monitorar",
    )


class SaveSegmentResponse(BaseModel):
    """Response for POST /v1/segment/save (CONV-018)."""

    status: str = Field(description="Operation status, always 'ok' on success")
    context_data: dict = Field(description="Full merged context_data after save")


@router.post("/save", response_model=SaveSegmentResponse)
async def save_segment(
    body: SaveSegmentRequest,
    user: dict = Depends(require_auth),
) -> SaveSegmentResponse:
    """Save user segmentation data to profile context_data (CONV-018).

    Merges the new fields into the existing ``context_data`` JSONB column
    on the ``profiles`` table without overwriting other fields.

    Returns the full updated context_data on success.
    """
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    sb = get_supabase()

    # 1. Fetch current context_data
    try:
        result = await sb_execute(
            sb.table("profiles")
            .select("context_data")
            .eq("id", user_id)
            .single(),
            category="read",
        )
    except Exception as exc:
        logger.warning(
            "CONV-018: failed to fetch context_data for user %s: %s",
            user_id[:8],
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="Erro ao acessar perfil do usuário.",
        )

    current_context = result.data.get("context_data", {}) if result.data else {}

    # 2. Merge new fields
    if body.segmento_principal is not None:
        current_context["segmento_principal"] = body.segmento_principal
    if body.objetivo_tipo is not None:
        current_context["objetivo_tipo"] = (
            body.objetivo_tipo.value
            if hasattr(body.objetivo_tipo, "value")
            else body.objetivo_tipo
        )

    # 3. Persist merged context
    try:
        await sb_execute(
            sb.table("profiles")
            .update({"context_data": current_context})
            .eq("id", user_id),
            category="write",
        )
    except Exception as exc:
        logger.warning(
            "CONV-018: failed to update context_data for user %s: %s",
            user_id[:8],
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="Erro ao salvar segmentação.",
        )

    return {"status": "ok", "context_data": current_context}
