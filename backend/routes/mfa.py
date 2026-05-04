"""MFA (Multi-Factor Authentication) routes for SmartLic.

STORY-317: TOTP MFA with recovery codes.
- GET /v1/mfa/status — MFA status for current user
- POST /v1/mfa/recovery-codes — Generate recovery codes after MFA enrollment
- POST /v1/mfa/verify-recovery — Verify a recovery code (brute force protected)
- POST /v1/mfa/regenerate-recovery — Regenerate recovery codes (requires aal2)

Issue #639: Primary TOTP enrollment + verification (B2G compliance).
- POST /v1/mfa/enroll — Enrol a TOTP factor; returns QR + secret + backup codes
- POST /v1/mfa/verify-totp — Verify TOTP code, complete enrollment, elevate to aal2
"""

import asyncio
import logging
import secrets
from datetime import datetime, timezone, timedelta

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth import require_auth
from authorization import check_user_roles
from log_sanitizer import mask_ip_address, mask_user_id
from rate_limiter import require_rate_limit
from schemas.user import (
    MFAEnrollResponse,
    MFAVerifyRequest,
    MFAVerifyResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mfa", tags=["MFA"])

# Constants
RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_LENGTH = 8  # 8 hex chars = 4 bytes = 2^32 possibilities
MAX_FAILED_ATTEMPTS_PER_HOUR = 3


def _safe_log_value(value: object, max_len: int = 200) -> str:
    """Strip CRLF/control chars and truncate before logging.

    Defends against log-injection (CodeQL py/log-injection) when interpolating
    user-controlled or user-derived values (user_id, factor_id, exception types)
    into log statements. Output is always a plain str — never raw secrets.
    """
    if value is None:
        return ""
    text = str(value).replace("\r", "").replace("\n", "")
    return text[:max_len]


# ─── Schemas ───────────────────────────────────────────────────────────────────

class MfaStatusResponse(BaseModel):
    mfa_enabled: bool
    factors: list[dict] = Field(default_factory=list)
    aal_level: str = "aal1"
    mfa_required: bool = False


class RecoveryCodesResponse(BaseModel):
    codes: list[str]
    message: str = "Salve estes códigos em local seguro. Cada código só pode ser usado uma vez."


class VerifyRecoveryRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=20)


class VerifyRecoveryResponse(BaseModel):
    success: bool
    remaining_codes: int = 0
    message: str = ""


class RegenerateRecoveryResponse(BaseModel):
    codes: list[str]
    message: str = "Novos códigos gerados. Os códigos anteriores foram invalidados."


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _generate_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    """Generate cryptographically secure recovery codes.

    Returns list of uppercase hex strings formatted as XXXX-XXXX.
    """
    codes = []
    for _ in range(count):
        raw = secrets.token_hex(RECOVERY_CODE_LENGTH // 2).upper()
        formatted = f"{raw[:4]}-{raw[4:]}"
        codes.append(formatted)
    return codes


def _hash_code(code: str) -> str:
    """Hash a recovery code with bcrypt."""
    clean = code.replace("-", "").upper()
    return bcrypt.hashpw(clean.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_code(code: str, code_hash: str) -> bool:
    """Verify a recovery code against its bcrypt hash."""
    clean = code.replace("-", "").upper()
    return bcrypt.checkpw(clean.encode("utf-8"), code_hash.encode("utf-8"))


async def _get_supabase():
    """Get Supabase client (lazy import to avoid circular deps)."""
    from supabase_client import get_supabase
    return get_supabase()


async def _check_brute_force(user_id: str) -> int:
    """Check failed recovery attempts in the last hour.

    Returns the number of failed attempts. Raises 429 if limit exceeded.
    """
    sb = await _get_supabase()
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    result = await asyncio.to_thread(
        sb.table("mfa_recovery_attempts")
        .select("id")
        .eq("user_id", user_id)
        .eq("success", False)
        .gte("attempted_at", one_hour_ago)
        .execute
    )

    failed_count = len(result.data) if result.data else 0

    if failed_count >= MAX_FAILED_ATTEMPTS_PER_HOUR:
        logger.warning(f"MFA recovery brute force limit hit for user {user_id[:8]}...")
        raise HTTPException(
            status_code=429,
            detail=f"Muitas tentativas. Tente novamente em 1 hora. ({failed_count}/{MAX_FAILED_ATTEMPTS_PER_HOUR})",
        )

    return failed_count


async def _record_attempt(user_id: str, success: bool) -> None:
    """Record a recovery code attempt for brute force tracking."""
    sb = await _get_supabase()
    await asyncio.to_thread(
        sb.table("mfa_recovery_attempts").insert({
            "user_id": user_id,
            "success": success,
        }).execute
    )


# ─── Routes ────────────────────────────────────────────────────────────────────

@router.get("/status", response_model=MfaStatusResponse)
async def get_mfa_status(user: dict = Depends(require_auth)):
    """AC4: Get MFA status for the current user.

    Returns whether MFA is enabled, enrolled factors, current AAL level,
    and whether MFA is required for this user's role.
    """
    user_id = user["id"]

    # Check if user is admin/master (MFA required for these roles)
    is_admin, is_master = await check_user_roles(user_id)
    mfa_required = is_admin or is_master

    # Get AAL from JWT claims (stored in user dict by auth.py)
    aal_level = user.get("aal", "aal1")

    # Get enrolled factors from Supabase auth.mfa_factors table
    factors = []
    try:
        sb = await _get_supabase()
        result = await asyncio.to_thread(
            sb.table("mfa_factors")
            .select("id, factor_type, friendly_name, status, created_at")
            .eq("user_id", user_id)
            .execute
        )

        if result.data:
            for f in result.data:
                factors.append({
                    "id": f["id"],
                    "type": f.get("factor_type", "totp"),
                    "friendly_name": f.get("friendly_name", ""),
                    "verified": f.get("status") == "verified",
                })
    except Exception as e:
        # If we can't read factors, use mfa_amr_claims or default
        logger.warning(f"Failed to read MFA factors for user {user_id[:8]}: {type(e).__name__}")

    mfa_enabled = any(f.get("verified") for f in factors)

    return MfaStatusResponse(
        mfa_enabled=mfa_enabled,
        factors=factors,
        aal_level=aal_level,
        mfa_required=mfa_required,
    )


@router.post("/recovery-codes", response_model=RecoveryCodesResponse)
async def generate_recovery_codes(user: dict = Depends(require_auth)):
    """AC5: Generate 10 recovery codes after MFA enrollment.

    This should be called immediately after successful MFA enrollment.
    Stores bcrypt-hashed codes in the database, returns plaintext once.
    """
    user_id = user["id"]
    sb = await _get_supabase()

    # Delete any existing codes for this user (fresh set on each enrollment)
    await asyncio.to_thread(
        sb.table("mfa_recovery_codes").delete().eq("user_id", user_id).execute
    )

    # Generate and store codes
    plaintext_codes = _generate_recovery_codes()

    rows = []
    for code in plaintext_codes:
        rows.append({
            "user_id": user_id,
            "code_hash": _hash_code(code),
        })

    await asyncio.to_thread(
        sb.table("mfa_recovery_codes").insert(rows).execute
    )

    logger.info(f"Generated {len(plaintext_codes)} recovery codes for user {user_id[:8]}...")

    return RecoveryCodesResponse(codes=plaintext_codes)


@router.post("/verify-recovery", response_model=VerifyRecoveryResponse)
async def verify_recovery_code(
    body: VerifyRecoveryRequest,
    user: dict = Depends(require_auth),
):
    """AC7: Verify a recovery code for MFA bypass.

    Brute force protection: max 3 failed attempts per hour.
    On success: marks code as used, returns remaining count.
    """
    user_id = user["id"]

    # AC7: Check brute force limit
    await _check_brute_force(user_id)

    sb = await _get_supabase()

    # Get unused codes for this user
    result = await asyncio.to_thread(
        sb.table("mfa_recovery_codes")
        .select("id, code_hash")
        .eq("user_id", user_id)
        .is_("used_at", "null")
        .execute
    )

    stored_codes = result.data or []

    # Try to match the provided code against stored hashes
    for stored in stored_codes:
        if _verify_code(body.code, stored["code_hash"]):
            # Mark as used
            await asyncio.to_thread(
                sb.table("mfa_recovery_codes").update({
                    "used_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", stored["id"]).execute
            )

            # Record successful attempt
            await _record_attempt(user_id, success=True)

            remaining = len(stored_codes) - 1
            logger.info(f"Recovery code verified for user {user_id[:8]}. Remaining: {remaining}")

            msg = "Código verificado com sucesso."
            if remaining <= 2:
                msg += f" Atenção: restam apenas {remaining} códigos. Regenere seus códigos."

            return VerifyRecoveryResponse(
                success=True,
                remaining_codes=remaining,
                message=msg,
            )

    # No match — record failed attempt
    await _record_attempt(user_id, success=False)

    _fail_query = (
        sb.table("mfa_recovery_attempts")
        .select("id")
        .eq("user_id", user_id)
        .eq("success", False)
        .gte("attempted_at", (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
    )
    _fail_result = await asyncio.to_thread(_fail_query.execute)
    failed_count = len(_fail_result.data or [])

    remaining_attempts = MAX_FAILED_ATTEMPTS_PER_HOUR - failed_count

    return VerifyRecoveryResponse(
        success=False,
        remaining_codes=0,
        message=f"Código inválido ou já utilizado. Tentativas restantes: {remaining_attempts}",
    )


# ─── Issue #639 — Primary TOTP enrollment + verification ──────────────────────

# Rate limit: max 5 attempts per 15 minutes on /verify-totp (brute-force guard)
_VERIFY_TOTP_MAX_ATTEMPTS = 5
_VERIFY_TOTP_WINDOW_SECONDS = 900  # 15 minutes


def _get_client_ip(request: Request) -> str:
    """Extract caller IP, respecting X-Forwarded-For (Railway proxy)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _get_user_access_token(request: Request) -> str:
    """Extract the Bearer token from the Authorization header.

    Required for user-scoped auth.mfa.* operations against Supabase GoTrue.
    Returns empty string when missing — caller should handle gracefully
    (typically only reached in unit tests where Supabase is mocked).
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


def _get_user_supabase_for_auth(access_token: str):
    """Build a user-scoped Supabase client with the user's session bound.

    `auth.mfa.enroll/challenge/verify` operate via GoTrue (not PostgREST),
    so we must call ``set_session`` after constructing the client.
    """
    from supabase_client import get_user_supabase

    client = get_user_supabase(access_token)
    try:
        # set_session requires a refresh_token argument; we don't have it
        # server-side, so pass an empty string. GoTrue accepts the access
        # token alone for the brief duration of this request.
        client.auth.set_session(access_token=access_token, refresh_token="")
    except Exception as e:  # noqa: BLE001
        logger.debug(
            "MFA: set_session raised %s (continuing — auth.mfa.* will pick up "
            "the Authorization header set by get_user_supabase)",
            type(e).__name__,
        )
    return client


def _extract_totp_payload(enroll_resp) -> tuple[str, str, str]:
    """Normalise the supabase-py enroll response into (factor_id, qr_uri, secret).

    The SDK returns either a dataclass-style object (``.id``, ``.totp.uri``) or
    a dict depending on version. We handle both shapes defensively.
    """
    def _attr_or_key(obj, key, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    factor_id = _attr_or_key(enroll_resp, "id", "")
    totp = _attr_or_key(enroll_resp, "totp")
    qr_uri = _attr_or_key(totp, "uri", "") or _attr_or_key(totp, "qr_code", "")
    secret = _attr_or_key(totp, "secret", "")

    return str(factor_id or ""), str(qr_uri or ""), str(secret or "")


def _extract_factor_id_from_challenge(challenge_resp) -> str:
    """Extract challenge id from supabase-py challenge response (object or dict)."""
    if challenge_resp is None:
        return ""
    if isinstance(challenge_resp, dict):
        return str(challenge_resp.get("id", ""))
    return str(getattr(challenge_resp, "id", ""))


async def _persist_backup_codes(user_id: str) -> list[str]:
    """Generate + persist a fresh batch of recovery codes (reuses existing infra).

    Replaces any existing codes (matches /recovery-codes endpoint semantics).
    Returns the plaintext codes — they MUST be shown to the user once and
    never logged.
    """
    sb = await _get_supabase()

    await asyncio.to_thread(
        sb.table("mfa_recovery_codes").delete().eq("user_id", user_id).execute
    )

    plaintext_codes = _generate_recovery_codes()
    rows = [{"user_id": user_id, "code_hash": _hash_code(code)} for code in plaintext_codes]
    await asyncio.to_thread(
        sb.table("mfa_recovery_codes").insert(rows).execute
    )

    return plaintext_codes


def _log_mfa_event(
    user_id: str,
    event: str,
    success: bool,
    ip: str,
    extra: str = "",
) -> None:
    """Structured log for MFA enroll/verify attempts (Issue #639 AC).

    PII is masked via log_sanitizer (mask_user_id, mask_ip_address). All
    user-derived values are additionally passed through ``_safe_log_value``
    to strip CRLF/control chars and prevent log-injection
    (CodeQL py/log-injection / py/clear-text-logging-sensitive-data).
    """
    safe_extra = _safe_log_value(extra)
    logger.info(
        "mfa_event user_id=%s event=%s success=%s ip=%s%s",
        _safe_log_value(mask_user_id(user_id)),
        _safe_log_value(event),
        success,
        _safe_log_value(mask_ip_address(ip)),
        f" {safe_extra}" if safe_extra else "",
    )


@router.post("/enroll", response_model=MFAEnrollResponse)
async def enroll_totp(
    request: Request,
    user: dict = Depends(require_auth),
):
    """Issue #639 AC1: Enrol a TOTP MFA factor for the current user.

    Returns the QR code URI (otpauth://...), the base32 secret, and 10 fresh
    one-time backup codes. The user adds the URI/secret to an authenticator
    app and then calls /verify-totp with a generated code to complete enrolment.

    Backup codes are returned ONCE — the client must persist them.
    """
    user_id = user["id"]
    ip = _get_client_ip(request)
    access_token = _get_user_access_token(request)

    if not access_token:
        _log_mfa_event(user_id, "mfa_enroll", success=False, ip=ip, extra="reason=missing_token")
        raise HTTPException(status_code=401, detail="Token de autenticação ausente.")

    try:
        sb_user = _get_user_supabase_for_auth(access_token)
        enroll_resp = await asyncio.to_thread(
            lambda: sb_user.auth.mfa.enroll({
                "factor_type": "totp",
                "friendly_name": "SmartLic",
            })
        )
    except Exception as e:  # noqa: BLE001 — Supabase SDK raises various types
        _log_mfa_event(
            user_id, "mfa_enroll", success=False, ip=ip,
            extra=f"reason=supabase_error type={type(e).__name__}",
        )
        logger.warning(
            "MFA enrol failed for user %s: %s",
            _safe_log_value(mask_user_id(user_id)),
            _safe_log_value(type(e).__name__),
        )
        raise HTTPException(
            status_code=502,
            detail="Não foi possível iniciar o cadastro de MFA. Tente novamente em instantes.",
        )

    factor_id, qr_uri, secret = _extract_totp_payload(enroll_resp)
    if not factor_id or not qr_uri or not secret:
        _log_mfa_event(
            user_id, "mfa_enroll", success=False, ip=ip, extra="reason=incomplete_response",
        )
        raise HTTPException(
            status_code=502,
            detail="Resposta de cadastro MFA incompleta. Tente novamente.",
        )

    # Generate and persist backup codes (reuses existing recovery-codes infra).
    try:
        backup_codes = await _persist_backup_codes(user_id)
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "MFA enrol: failed to persist backup codes for user %s: %s",
            _safe_log_value(mask_user_id(user_id)),
            _safe_log_value(type(e).__name__),
        )
        # Non-fatal: enrolment can proceed; user can call /v1/mfa/recovery-codes later.
        backup_codes = []

    _log_mfa_event(user_id, "mfa_enroll", success=True, ip=ip, extra=f"factor_id={factor_id[:8]}")

    return MFAEnrollResponse(
        factor_id=factor_id,
        qr_code_uri=qr_uri,
        secret=secret,
        backup_codes=backup_codes,
    )


@router.post(
    "/verify-totp",
    response_model=MFAVerifyResponse,
    dependencies=[Depends(require_rate_limit(_VERIFY_TOTP_MAX_ATTEMPTS, _VERIFY_TOTP_WINDOW_SECONDS))],
)
async def verify_totp(
    body: MFAVerifyRequest,
    request: Request,
    user: dict = Depends(require_auth),
):
    """Issue #639 AC2: Verify a TOTP code to complete enrolment + elevate to aal2.

    Looks up the user's most recent unverified factor, creates a Supabase
    challenge, then verifies the supplied code. On success the Supabase
    session is elevated to aal2 (subsequent requests carry that claim in
    the JWT, gating /admin and other sensitive routes).

    Rate limit: 5 attempts / 15 min via require_rate_limit (token bucket).
    """
    user_id = user["id"]
    ip = _get_client_ip(request)
    access_token = _get_user_access_token(request)

    if not access_token:
        _log_mfa_event(user_id, "mfa_verify", success=False, ip=ip, extra="reason=missing_token")
        raise HTTPException(status_code=401, detail="Token de autenticação ausente.")

    # Find the user's most recent unverified factor (the one they just enrolled).
    sb = await _get_supabase()
    try:
        result = await asyncio.to_thread(
            sb.table("mfa_factors")
            .select("id, status, created_at")
            .eq("user_id", user_id)
            .eq("factor_type", "totp")
            .order("created_at", desc=True)
            .execute
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "MFA verify: failed to read factors for user %s: %s",
            _safe_log_value(mask_user_id(user_id)),
            _safe_log_value(type(e).__name__),
        )
        raise HTTPException(status_code=502, detail="Erro ao consultar fator MFA.")

    factors = result.data or []
    # Prefer the most-recent unverified factor; fall back to verified for re-challenge.
    pending = next((f for f in factors if f.get("status") == "unverified"), None)
    target = pending or (factors[0] if factors else None)

    if not target:
        _log_mfa_event(
            user_id, "mfa_verify", success=False, ip=ip, extra="reason=no_factor",
        )
        raise HTTPException(
            status_code=400,
            detail="Nenhum fator MFA encontrado. Cadastre um TOTP primeiro via /v1/mfa/enroll.",
        )

    factor_id = target["id"]

    try:
        sb_user = _get_user_supabase_for_auth(access_token)
        challenge_resp = await asyncio.to_thread(
            lambda: sb_user.auth.mfa.challenge({"factor_id": factor_id})
        )
        challenge_id = _extract_factor_id_from_challenge(challenge_resp)
        if not challenge_id:
            raise RuntimeError("empty challenge_id from Supabase")

        await asyncio.to_thread(
            lambda: sb_user.auth.mfa.verify({
                "factor_id": factor_id,
                "challenge_id": challenge_id,
                "code": body.totp_code,
            })
        )
    except Exception as e:  # noqa: BLE001
        _log_mfa_event(
            user_id,
            "mfa_verify",
            success=False,
            ip=ip,
            extra=f"reason=verify_failed type={type(e).__name__}",
        )
        logger.warning(
            "MFA verify failed for user %s: %s",
            _safe_log_value(mask_user_id(user_id)),
            _safe_log_value(type(e).__name__),
        )
        raise HTTPException(
            status_code=400,
            detail="Código TOTP inválido ou expirado. Verifique o relógio do dispositivo e tente novamente.",
        )

    _log_mfa_event(user_id, "mfa_verify", success=True, ip=ip, extra=f"factor_id={factor_id[:8]}")

    return MFAVerifyResponse(
        success=True,
        aal_level="aal2",
        factor_id=factor_id,
        message="Verificação concluída. Sua sessão agora está em AAL2.",
    )


@router.post("/regenerate-recovery", response_model=RegenerateRecoveryResponse)
async def regenerate_recovery_codes(user: dict = Depends(require_auth)):
    """AC8: Regenerate recovery codes (requires aal2).

    Invalidates all existing codes and generates a fresh set.
    """
    user_id = user["id"]
    aal = user.get("aal", "aal1")

    # Require aal2 for regeneration (user must have verified MFA this session)
    if aal != "aal2":
        raise HTTPException(
            status_code=403,
            detail="Verificação MFA necessária para regenerar códigos. Faça login com seu código TOTP primeiro.",
        )

    sb = await _get_supabase()

    # Delete all existing codes
    await asyncio.to_thread(
        sb.table("mfa_recovery_codes").delete().eq("user_id", user_id).execute
    )

    # Generate fresh codes
    plaintext_codes = _generate_recovery_codes()

    rows = [{"user_id": user_id, "code_hash": _hash_code(code)} for code in plaintext_codes]
    await asyncio.to_thread(
        sb.table("mfa_recovery_codes").insert(rows).execute
    )

    logger.info(f"Regenerated recovery codes for user {user_id[:8]}...")

    return RegenerateRecoveryResponse(codes=plaintext_codes)
