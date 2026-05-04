"""BIZ-METRIC-001 (AC3): user-facing post-export survey endpoints.

Surfaces a single endpoint:
    POST /v1/survey/export-time-saved   -- submit a survey response

Inserts a row into ``export_time_saved_survey`` (RLS: user_id =
auth.uid()) using the service-role client. Strict input validation:
    * ``estimated_manual_hours`` must be in [0.1, 50] (matches DB CHECK)
    * ``export_type`` must be in {excel, pdf, sheets}
    * ``free_text`` capped at 2000 chars (matches DB CHECK)

Admin endpoints (list/aggregate) live in
``backend/routes/admin_calibration.py``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from auth import require_auth
from pipeline.budget import _run_with_budget
from supabase_client import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/survey", tags=["survey"])


# ---------------------------------------------------------------------------
# Pydantic schemas (route-local — kept inline like admin_cnae.py)
# ---------------------------------------------------------------------------

VALID_EXPORT_TYPES = {"excel", "pdf", "sheets"}


class ExportTimeSavedSurveyRequest(BaseModel):
    """Body for POST /v1/survey/export-time-saved."""

    export_type: str = Field(
        ...,
        description="excel | pdf | sheets",
        max_length=16,
    )
    estimated_manual_hours: float = Field(
        ...,
        ge=0.1,
        le=50.0,
        description="User-reported manual-equivalent hours (range [0.1, 50])",
    )
    search_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Search session id this export came from",
    )
    export_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Export job/download identifier",
    )
    bid_count: Optional[int] = Field(
        default=None,
        ge=0,
        le=100_000,
        description="Number of bids included in the export",
    )
    free_text: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional free-text answer ('how would you have done this before?')",
    )

    model_config = ConfigDict(extra="ignore")

    @field_validator("export_type")
    @classmethod
    def _validate_export_type(cls, value: str) -> str:
        if value not in VALID_EXPORT_TYPES:
            raise ValueError(
                f"export_type must be one of {sorted(VALID_EXPORT_TYPES)}, got '{value}'"
            )
        return value

    @field_validator("free_text")
    @classmethod
    def _strip_free_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ExportTimeSavedSurveyResponse(BaseModel):
    """Body for POST /v1/survey/export-time-saved (201)."""

    id: str
    submitted_at: str


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/export-time-saved",
    response_model=ExportTimeSavedSurveyResponse,
    status_code=201,
)
async def submit_export_time_saved_survey(
    body: ExportTimeSavedSurveyRequest,
    user: dict = Depends(require_auth),
) -> ExportTimeSavedSurveyResponse:
    """Persist one row in ``export_time_saved_survey``.

    Auth required. The row is owned by ``user.id`` (RLS: users only ever
    see their own submissions). Returns 503 if the database is
    unavailable so the frontend can retry on next export.
    """
    user_id = user.get("id")
    if not user_id:
        # require_auth guarantees this, but stay defensive.
        raise HTTPException(status_code=401, detail="Authentication required")

    payload = {
        "user_id": user_id,
        "search_id": body.search_id,
        "export_id": body.export_id,
        "export_type": body.export_type,
        "bid_count": body.bid_count,
        "estimated_manual_hours": float(body.estimated_manual_hours),
        "free_text": body.free_text,
    }

    sb = get_supabase()

    def _sync_insert():
        return (
            sb.table("export_time_saved_survey")
            .insert(payload)
            .execute()
        )

    try:
        result = await _run_with_budget(
            asyncio.to_thread(_sync_insert),
            budget=3.0,
            phase="route",
            source="survey.submit_export_time_saved_survey",
        )
    except asyncio.TimeoutError:
        logger.warning(
            "BIZ-METRIC-001: export_time_saved_survey insert exceeded 3s budget for user=%s",
            user_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Não foi possível registrar a resposta. Tente novamente.",
        )
    except Exception as exc:
        logger.warning(
            "BIZ-METRIC-001: export_time_saved_survey insert failed for user=%s: %s",
            user_id,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="Não foi possível registrar a resposta. Tente novamente.",
        )

    rows = getattr(result, "data", None) or []
    if not rows:
        # Insert succeeded but no row returned — extremely rare, treat as 503.
        raise HTTPException(
            status_code=503,
            detail="Resposta registrada mas sem confirmação do servidor.",
        )

    row = rows[0]
    return ExportTimeSavedSurveyResponse(
        id=str(row["id"]),
        submitted_at=str(row["submitted_at"]),
    )
