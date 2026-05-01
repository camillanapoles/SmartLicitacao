"""
Email confirmation recovery endpoints.

GTM-FIX-009: Fix email confirmation dead end.
CONV-INST-003: DB-backed resend cooldown (persists across Railway redeploys).

Endpoints:
- POST /auth/resend-confirmation — Resend signup confirmation email (60s rate limit)
- GET  /auth/status              — Check if email has been confirmed
"""

import datetime
import logging
import time
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr

from rate_limiter import require_rate_limit, SIGNUP_RATE_LIMIT_PER_10MIN

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth-email"])

# In-memory fallback: used when Supabase is unavailable (fail-open strategy).
# Primary cooldown storage is user_email_actions table (CONV-INST-003).
_resend_timestamps: Dict[str, float] = {}
RESEND_COOLDOWN = 60  # seconds


class ResendRequest(BaseModel):
    email: EmailStr


class ResendResponse(BaseModel):
    success: bool
    message: str


class AuthStatusResponse(BaseModel):
    confirmed: bool
    user_id: str | None = None


def _check_resend_cooldown_db(email_lower: str, supabase) -> int | None:
    """Check resend cooldown from DB. Returns remaining seconds or None if allowed.

    Fails open (returns None / allows) if DB query fails.
    """
    try:
        result = (
            supabase.table("user_email_actions")
            .select("created_at")
            .eq("email", email_lower)
            .eq("action_type", "resend")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = getattr(result, "data", []) or []
        if not rows:
            return None
        last_sent_str = rows[0]["created_at"]
        # Parse ISO timestamp from Supabase (UTC)
        last_sent = datetime.datetime.fromisoformat(last_sent_str.replace("Z", "+00:00"))
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        elapsed = (now_utc - last_sent).total_seconds()
        if elapsed < RESEND_COOLDOWN:
            return int(RESEND_COOLDOWN - elapsed)
        return None
    except Exception as e:
        logger.warning(f"DB cooldown check failed, falling back to in-memory: {type(e).__name__}")
        return None


def _record_resend_db(email_lower: str, supabase) -> bool:
    """Record a resend action in DB. Returns True on success."""
    try:
        supabase.table("user_email_actions").insert(
            {"email": email_lower, "action_type": "resend"}
        ).execute()
        return True
    except Exception as e:
        logger.warning(f"DB resend record failed: {type(e).__name__}")
        return False


def _record_confirm_db(email_lower: str, supabase) -> bool:
    """Record an email confirmation in DB (idempotent). Returns True if first confirm."""
    try:
        # Check if already confirmed
        result = (
            supabase.table("user_email_actions")
            .select("id")
            .eq("email", email_lower)
            .eq("action_type", "confirm")
            .limit(1)
            .execute()
        )
        rows = getattr(result, "data", []) or []
        if rows:
            return False  # Already recorded — idempotent
        supabase.table("user_email_actions").insert(
            {"email": email_lower, "action_type": "confirm"}
        ).execute()
        return True
    except Exception as e:
        logger.warning(f"DB confirm record failed: {type(e).__name__}")
        return False


@router.post("/validate-signup-email")
async def validate_signup_email(
    request: ResendRequest,
    _rl=Depends(require_rate_limit(SIGNUP_RATE_LIMIT_PER_10MIN, 600)),
):
    """STORY-258 AC3: Backend disposable email validation (defense-in-depth).

    MED-SEC-001: Rate limited to 3 req/10min per IP to prevent trial multi-account abuse.
    Returns 422 if email domain is disposable.
    """
    from utils.disposable_emails import is_disposable_email
    from audit import log_audit_event

    email_lower = request.email.lower().strip()

    if is_disposable_email(email_lower):
        # AC14: Log to audit
        try:
            log_audit_event(
                event_type="signup_disposable_blocked",
                details={"email_domain": email_lower.split("@")[1]},
                level="WARNING",
            )
        except Exception:
            logger.warning(f"AUDIT: Disposable email signup attempt: {email_lower.split('@')[1]}")

        raise HTTPException(
            status_code=422,
            detail="Este provedor de email não é aceito. Use um email corporativo ou pessoal (Gmail, Outlook, etc.)",
        )

    return {"valid": True}


@router.post("/resend-confirmation", response_model=ResendResponse)
async def resend_confirmation(
    request: ResendRequest,
    _rl=Depends(require_rate_limit(SIGNUP_RATE_LIMIT_PER_10MIN, 600)),
):
    """Resend signup confirmation email with 60s rate limiting.

    CONV-INST-003: Cooldown persisted in Supabase user_email_actions table.
    In-memory _resend_timestamps used as fallback when DB is unavailable.
    MED-SEC-001: Rate limited to 3 req/10min per IP to prevent trial multi-account abuse.
    """
    email_lower = request.email.lower().strip()
    now = time.time()

    # Primary: DB-backed cooldown
    try:
        from supabase_client import get_supabase
        supabase = get_supabase()

        remaining = _check_resend_cooldown_db(email_lower, supabase)
        if remaining is not None:
            raise HTTPException(
                status_code=429,
                detail=f"Aguarde {remaining}s antes de reenviar."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"DB cooldown check unavailable, using in-memory fallback: {type(e).__name__}")
        # Fallback to in-memory cooldown
        last_sent = _resend_timestamps.get(email_lower)
        if last_sent and (now - last_sent) < RESEND_COOLDOWN:
            remaining_fallback = int(RESEND_COOLDOWN - (now - last_sent))
            raise HTTPException(
                status_code=429,
                detail=f"Aguarde {remaining_fallback}s antes de reenviar."
            )

    try:
        from supabase_client import get_supabase
        supabase = get_supabase()
        supabase.auth.resend({"type": "signup", "email": email_lower})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resend confirmation: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Erro ao reenviar email.")

    # Record in DB (primary); fall back to in-memory if DB fails
    try:
        from supabase_client import get_supabase
        supabase = get_supabase()
        if not _record_resend_db(email_lower, supabase):
            _resend_timestamps[email_lower] = now
    except Exception:
        _resend_timestamps[email_lower] = now

    logger.info(f"Confirmation email resent for {email_lower[:4]}***")

    return ResendResponse(
        success=True,
        message="Email reenviado! Verifique sua caixa de entrada."
    )


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(email: str = Query(..., description="Email to check")):
    """Check if a signup email has been confirmed.

    AC8: Returns { confirmed: boolean, user_id?: string }.
    AC7/AC9: Frontend polls this every 5s for auto-redirect.
    CONV-INST-003 AC6: Emits Mixpanel email_verification_completed server-side
    on first confirmation (idempotent via user_email_actions table).
    """
    email_lower = email.lower().strip()

    try:
        from supabase_client import get_supabase
        supabase = get_supabase()

        # Use admin API to list users filtered by email
        response = supabase.auth.admin.list_users()

        for user in response:
            user_email = getattr(user, "email", None)
            if user_email and user_email.lower() == email_lower:
                confirmed_at = getattr(user, "email_confirmed_at", None)
                if confirmed_at:
                    # CONV-INST-003 AC6: Emit server-side analytics on first confirmation.
                    # Idempotent: _record_confirm_db returns False if already recorded.
                    try:
                        from supabase_client import get_supabase as _get_sb
                        sb = _get_sb()
                        is_first_confirm = _record_confirm_db(email_lower, sb)
                        if is_first_confirm:
                            from analytics_events import track_event
                            user_id = getattr(user, "id", None)
                            track_event(
                                "email_verification_completed",
                                {
                                    "user_id": str(user_id) if user_id else "unknown",
                                    "email_domain": email_lower.split("@")[1],
                                    "source": "server_side",
                                },
                            )
                    except Exception as e:
                        logger.debug(
                            f"Server-side email_verification_completed emit failed: {type(e).__name__}"
                        )

                    # CRIT-SEC: Do NOT expose user_id — prevents enumeration
                    return AuthStatusResponse(
                        confirmed=True,
                    )
                return AuthStatusResponse(confirmed=False)

        return AuthStatusResponse(confirmed=False)

    except Exception as e:
        logger.error(f"Failed to check auth status: {type(e).__name__}")
        return AuthStatusResponse(confirmed=False)
