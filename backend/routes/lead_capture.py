"""A2: Lead capture endpoint for calculadora/CNPJ/alertas.

Public (no auth) endpoint that stores email + context for lead nurturing.
"""

import asyncio
import logging
from datetime import datetime, timezone

from pipeline.budget import _run_with_budget

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lead-capture", tags=["lead-capture"])


class LeadCaptureRequest(BaseModel):
    email: str
    source: str  # 'calculadora' | 'cnpj' | 'alertas'
    setor: Optional[str] = None
    uf: Optional[str] = None
    captured_at: Optional[str] = None


class LeadCaptureResponse(BaseModel):
    success: bool


@router.post("", response_model=LeadCaptureResponse)
async def capture_lead(req: LeadCaptureRequest):
    """Store a lead capture (public, no auth, rate-limited by global middleware)."""
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=400, detail="Email inválido")

    try:
        from supabase_client import get_supabase
        sb = get_supabase()
        lead_row = {
            "email": req.email.lower().strip(),
            "source": req.source,
            "setor": req.setor,
            "uf": req.uf.upper() if req.uf else None,
            "captured_at": req.captured_at or datetime.now(timezone.utc).isoformat(),
        }

        def _sync_upsert():
            return sb.table("leads").upsert(lead_row, on_conflict="email,source").execute()

        await _run_with_budget(
            asyncio.to_thread(_sync_upsert),
            budget=5.0,
            phase="route",
            source="lead_capture.capture_lead",
        )
    except Exception as e:
        # Fail-open: don't block UX if DB is down
        logger.warning("Failed to store lead: %s", e)

    return LeadCaptureResponse(success=True)
