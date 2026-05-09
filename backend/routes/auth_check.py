"""STORY-258 AC11-AC12, AC15: Pre-signup validation endpoints.

Endpoints:
- GET /auth/check-email — Validate email (disposable check, no enumeration leak)
- GET /auth/check-phone — Validate phone uniqueness (boolean only)

MED-SEC-001: Rate-limited via FlexibleRateLimiter (Redis + in-memory fallback).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Query

from rate_limiter import require_rate_limit, SIGNUP_RATE_LIMIT_PER_10MIN
from schemas.parity import CheckEmailResponse, CheckPhoneResponse
from utils.disposable_emails import is_disposable_email, is_corporate_email
from utils.phone_normalizer import normalize_phone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth-check"])


# ---------------------------------------------------------------------------
# GET /auth/check-email
# ---------------------------------------------------------------------------

@router.get("/check-email", response_model=CheckEmailResponse)
async def check_email(
    request: Request,
    email: str = Query(..., min_length=5, max_length=320),
    _rl=Depends(require_rate_limit(SIGNUP_RATE_LIMIT_PER_10MIN, 600)),
):
    """AC15: Pre-signup email validation.

    Returns { available: bool, disposable: bool, corporate: bool }.

    Security:
    - Does NOT reveal if email already exists (always available=true for disposable).
    - MED-SEC-001: Rate limited 3 req/10min per IP (Redis + fallback).
    """

    email_lower = email.strip().lower()
    disposable = is_disposable_email(email_lower)
    corporate = is_corporate_email(email_lower)

    if disposable:
        # AC15: Don't reveal that email was blocked — return available=true
        # to prevent enumeration (blocked vs already-exists is indistinguishable)
        client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
        logger.info(f"AUDIT: Disposable email check — domain blocked (ip={client_ip})")
        return {
            "available": True,
            "disposable": True,
            "corporate": False,
        }

    return {
        "available": True,
        "disposable": False,
        "corporate": corporate,
    }


# ---------------------------------------------------------------------------
# GET /auth/check-phone
# ---------------------------------------------------------------------------

async def _check_fingerprint_abuse(phone: str, company: str | None, request: Request):
    """AC13: Log warning if same phone+company combination exists with different email."""
    if not phone or not company:
        return
    try:
        from supabase_client import get_supabase, sb_execute
        db = get_supabase()
        result = await sb_execute(db.table("profiles").select("id, email").eq("phone_whatsapp", phone).eq("company", company))
        if result.data:
            logger.warning(
                f"AUDIT: Potential duplicate account detected — "
                f"phone={phone[:4]}****, company={company}, "
                f"existing_accounts={len(result.data)}, ip={request.client.host if request.client else 'unknown'}"
            )
    except Exception as e:
        logger.debug(f"Fingerprint check failed (non-blocking): {e}")


@router.get("/check-phone", response_model=CheckPhoneResponse)
async def check_phone(
    request: Request,
    phone: str = Query(..., min_length=8, max_length=20),
    company: str | None = Query(default=None, max_length=200),
    _rl=Depends(require_rate_limit(SIGNUP_RATE_LIMIT_PER_10MIN, 600)),
):
    """AC11-AC12: Pre-signup phone uniqueness check.

    Returns { available: bool } only — no data leakage.
    AC13: Optional company param triggers fingerprint abuse detection (non-blocking).
    MED-SEC-001: Rate limited 3 req/10min per IP (Redis + fallback).
    """

    normalized = normalize_phone(phone)
    if not normalized:
        return {"available": True}  # Invalid format — don't block, let form validation handle

    try:
        from supabase_client import get_supabase, sb_execute
        db = get_supabase()

        result = await sb_execute(
            db.table("profiles")
            .select("id")
            .eq("phone_whatsapp", normalized)
            .limit(1)
        )

        available = not bool(result.data)

        # AC13: Non-blocking fingerprint abuse detection when company is provided
        if available and company:
            await _check_fingerprint_abuse(normalized, company, request)

        return {"available": available}

    except Exception as e:
        logger.warning(f"Phone check failed (returning available=true): {e}")
        # Fail open — don't block signup on DB errors
        return {"available": True}
