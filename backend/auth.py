"""Authentication middleware for FastAPI using Supabase JWT.

Security hardened in Issue #168:
- JWT errors sanitized (no token content in logs)
- Auth events logged with proper masking

Performance optimization:
- Token validation cache (60s TTL) to reduce Supabase Auth API calls
- Eliminates intermittent auth failures from remote validation timeouts

CRITICAL FIX (2026-02-11): Use local JWT validation instead of Supabase API
- Fixes: token_verification success=False AuthApiError
- Source: https://github.com/orgs/supabase/discussions/20763
- Much faster (no API call) and more reliable

STORY-203 SYS-M02: Use hashlib.sha256 for deterministic cache keys
- Python's hash() is not deterministic across process restarts
- hashlib.sha256() provides collision-resistant, deterministic hashing

STORY-227 Track 1: ES256+JWKS support
- Supabase rotated JWT signing from HS256 to ES256 (Feb 2026)
- Supports JWKS endpoint for dynamic public key fetching (5-min cache)
- Supports PEM public key via SUPABASE_JWT_SECRET env var
- Backward compatible: accepts both HS256 and ES256 during transition
- Key detection order: JWKS endpoint > PEM key > HS256 symmetric secret
"""

import json
import time
import os
import hashlib
import jwt
from collections import OrderedDict
from jwt import PyJWKClient
from typing import Any, Optional, Tuple

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from log_sanitizer import log_auth_event, get_sanitized_logger

logger = get_sanitized_logger(__name__)

security = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# DEBT-014 SYS-010 + SYS-018: Bounded LRU auth cache with Redis L2
# ---------------------------------------------------------------------------
# L1 (in-memory): OrderedDict with LRU eviction, 60s TTL, max 1000 entries
# L2 (Redis): shared between Gunicorn workers, 5min TTL
# Fallback: if Redis unavailable, L1 still works (per-worker only)
#
# Key: SHA256 hash of FULL token (STORY-210 AC3)
# Value: (user_data, timestamp)
# ---------------------------------------------------------------------------
_token_cache: OrderedDict[str, Tuple[dict, float]] = OrderedDict()
CACHE_TTL = 60  # L1 in-memory TTL (seconds)
REDIS_CACHE_TTL = 300  # L2 Redis TTL (5 minutes, shared between workers)
MAX_CACHE_ENTRIES = 1000  # Max L1 entries (LRU eviction when exceeded)
_REDIS_KEY_PREFIX = "smartlic:auth:"


def _cache_store_memory(token_hash: str, user_data: dict) -> None:
    """Store in L1 with LRU eviction."""
    _token_cache[token_hash] = (user_data, time.time())
    _token_cache.move_to_end(token_hash)
    # Evict oldest entries if over limit
    while len(_token_cache) > MAX_CACHE_ENTRIES:
        _token_cache.popitem(last=False)
        try:
            from metrics import AUTH_CACHE_EVICTIONS
            AUTH_CACHE_EVICTIONS.inc()
        except Exception:
            pass
    try:
        from metrics import AUTH_CACHE_SIZE
        AUTH_CACHE_SIZE.set(len(_token_cache))
    except Exception:
        pass


async def _redis_cache_get(token_hash: str) -> Optional[dict]:
    """Try to get user data from Redis L2 cache."""
    try:
        from redis_pool import get_redis_pool
        redis = await get_redis_pool()
        if redis:
            data = await redis.get(f"{_REDIS_KEY_PREFIX}{token_hash}")
            if data:
                return json.loads(data)
    except Exception:
        pass
    return None


async def _redis_cache_set(token_hash: str, user_data: dict) -> None:
    """Store user data in Redis L2 cache with TTL (fire-and-forget)."""
    try:
        from redis_pool import get_redis_pool
        redis = await get_redis_pool()
        if redis:
            await redis.setex(
                f"{_REDIS_KEY_PREFIX}{token_hash}",
                REDIS_CACHE_TTL,
                json.dumps(user_data),
            )
    except Exception:
        pass

# ---------------------------------------------------------------------------
# JWKS client — lazily initialized on first use to avoid startup failures
# when SUPABASE_URL is not yet configured or network is unavailable.
# ---------------------------------------------------------------------------
_jwks_client: Optional[PyJWKClient] = None
_jwks_init_attempted: bool = False


def _get_jwks_client() -> Optional[PyJWKClient]:
    """Return the cached PyJWKClient instance, creating it on first call.

    The client is only created if a JWKS URL can be determined from either:
      1. SUPABASE_JWKS_URL env var (explicit override), or
      2. SUPABASE_URL env var (auto-constructed).

    Returns None if neither is available or if initialization fails.
    The 5-minute cache is handled internally by PyJWKClient (lifespan=300).
    """
    global _jwks_client, _jwks_init_attempted

    if _jwks_client is not None:
        return _jwks_client

    # Only attempt init once to avoid repeated failures on every request
    if _jwks_init_attempted:
        return None
    _jwks_init_attempted = True

    jwks_url = os.getenv("SUPABASE_JWKS_URL")
    if not jwks_url:
        supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        if supabase_url:
            jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"

    if not jwks_url:
        logger.debug("No JWKS URL available — JWKS client not initialized")
        return None

    try:
        _jwks_client = PyJWKClient(
            jwks_url,
            cache_jwk_set=True,
            lifespan=300,  # AC3: 5-minute JWKS cache TTL
        )
        logger.info(f"JWKS client initialized: {jwks_url}")
        return _jwks_client
    except Exception as e:
        logger.warning(f"Failed to initialize JWKS client: {type(e).__name__}")
        return None


def _is_pem_key(secret: str) -> bool:
    """Check whether SUPABASE_JWT_SECRET contains a PEM-encoded public key."""
    return secret.strip().startswith("-----BEGIN")


def _get_jwt_key_and_algorithms(token: str) -> Tuple[Any, list[str]]:
    """Determine the correct key and algorithm(s) for JWT verification.

    Strategy (AC4 — backward compatible during HS256→ES256 transition):
      1. JWKS endpoint (preferred): fetch signing key by token's ``kid`` header.
         Returns the EC public key with ``["ES256"]``.
      2. PEM public key: if SUPABASE_JWT_SECRET starts with ``-----BEGIN``,
         treat it as an EC/RSA PEM key. Returns the PEM string with
         ``["ES256"]`` (AC5).
      3. HS256 symmetric secret (legacy): plain string used directly with
         ``["HS256"]``.

    Returns:
        (key, algorithms): tuple of the verification key and list of
        algorithm strings to pass to ``jwt.decode``.

    Raises:
        HTTPException 401: if no JWT secret is configured at all.
    """
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")

    # --- Strategy 1: JWKS endpoint (dynamic key rotation support) ----------
    jwks = _get_jwks_client()
    if jwks is not None:
        try:
            signing_key = jwks.get_signing_key_from_jwt(token)
            logger.debug("Using JWKS-derived signing key (ES256)")
            return signing_key.key, ["ES256"]
        except jwt.exceptions.PyJWKClientError as e:
            # JWKS fetch/match failed — fall through to other strategies
            logger.debug(f"JWKS key lookup failed ({type(e).__name__}), trying fallbacks")
        except Exception as e:
            logger.debug(f"JWKS unexpected error ({type(e).__name__}), trying fallbacks")

    # --- Strategy 2: PEM public key in env var (AC5) -----------------------
    if jwt_secret and _is_pem_key(jwt_secret):
        logger.debug("Using PEM public key from SUPABASE_JWT_SECRET (ES256)")
        return jwt_secret, ["ES256"]

    # --- Strategy 3: HS256 symmetric secret (legacy) -----------------------
    if jwt_secret:
        logger.debug("Using symmetric secret from SUPABASE_JWT_SECRET (HS256)")
        return jwt_secret, ["HS256"]

    # No key available at all
    logger.error("SUPABASE_JWT_SECRET not configured and no JWKS URL available!")
    raise HTTPException(
        status_code=401,
        detail="Autenticação indisponível. Faça login novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def reset_jwks_client() -> None:
    """Reset the JWKS client so it will be re-initialized on next use.

    Useful for testing or when rotating JWKS endpoints at runtime.
    """
    global _jwks_client, _jwks_init_attempted
    _jwks_client = None
    _jwks_init_attempted = False
    logger.info("JWKS client reset — will re-initialize on next request")




async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    """Extract and verify user from Supabase JWT token.

    Supports ES256 (via JWKS or PEM key) and HS256 (symmetric secret) with
    automatic fallback between algorithms during the transition period (AC4).
    Key detection order: JWKS endpoint > PEM key > HS256 symmetric secret.

    Uses local cache (60s TTL) to reduce validation overhead by ~95% and
    eliminate intermittent validation failures from remote timeouts.

    Returns None if no token provided (allows anonymous access where needed).
    Raises HTTPException 401 if token is invalid.
    Raises HTTPException 401 if auth is not configured (no key available).
    """
    if credentials is None:
        return None

    token = credentials.credentials
    # STORY-210 AC3: Hash FULL token (SHA256) to prevent identity collision.
    # Collision probability < 2^-128.
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()

    # FAST PATH 1: Check L1 in-memory cache (no I/O)
    if token_hash in _token_cache:
        user_data, cached_at = _token_cache[token_hash]
        age = time.time() - cached_at
        if age < CACHE_TTL:
            _token_cache.move_to_end(token_hash)  # LRU refresh
            logger.debug(f"Auth cache L1 HIT (age={age:.1f}s, user={user_data['id'][:8]})")
            try:
                from metrics import AUTH_CACHE_HITS
                AUTH_CACHE_HITS.labels(level="memory").inc()
            except Exception:
                pass
            return user_data
        else:
            del _token_cache[token_hash]
            logger.debug(f"Auth cache L1 EXPIRED (age={age:.1f}s)")

    # FAST PATH 2: Check L2 Redis cache (shared between workers)
    redis_data = await _redis_cache_get(token_hash)
    if redis_data:
        logger.debug(f"Auth cache L2 HIT (redis, user={redis_data.get('id', '?')[:8]})")
        _cache_store_memory(token_hash, redis_data)  # Promote to L1
        try:
            from metrics import AUTH_CACHE_HITS
            AUTH_CACHE_HITS.labels(level="redis").inc()
        except Exception:
            pass
        return redis_data

    # SLOW PATH: Cache miss — validate locally with JWT
    logger.debug("Auth cache MISS - validating JWT locally")
    try:
        from metrics import AUTH_CACHE_MISSES
        AUTH_CACHE_MISSES.inc()
    except Exception:
        pass
    try:
        # Determine key and algorithm(s) based on configuration
        # (raises HTTPException 401 if completely unconfigured)
        key, algorithms = _get_jwt_key_and_algorithms(token)

        try:
            # STORY-210 AC7: Enable audience verification (removed verify_aud: False)
            payload = jwt.decode(
                token,
                key,
                algorithms=algorithms,
                audience="authenticated",  # Supabase default audience
            )
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            raise HTTPException(status_code=401, detail="Token expirado")
        except jwt.InvalidTokenError as e:
            # DEBT-SYS-015: HS256→ES256 transition complete — single-algorithm path only.
            logger.warning(f"Invalid JWT token: {type(e).__name__}")
            raise HTTPException(status_code=401, detail="Token invalido")

        # Extract user data from JWT claims
        user_id = payload.get("sub")
        email = payload.get("email")
        role = payload.get("role", "authenticated")

        if not user_id:
            raise HTTPException(status_code=401, detail="Token sem user ID")

        # STORY-317: Extract AAL (Authenticator Assurance Level) from JWT
        # aal1 = password only, aal2 = password + TOTP verified
        aal = payload.get("aal", "aal1")

        # Build user data from JWT claims (no API call needed!)
        user_data = {
            "id": user_id,
            "email": email or "unknown",
            "role": role,
            "aal": aal,
        }

        # Cache validated token in L1 + L2
        _cache_store_memory(token_hash, user_data)
        await _redis_cache_set(token_hash, user_data)
        logger.debug(f"Auth cache STORED (L1+L2) for user {user_data['id'][:8]}")
        logger.info(f"JWT validation SUCCESS for user {user_data['id'][:8]} ({email})")

        # LIFECYCLE-002 (#1427): Fire-and-forget login tracking on session refresh.
        # Recorded on cache miss (new/refreshed JWT), deduped per day via Redis.
        # Never blocks the request path — exception-safe, graceful degradation.
        try:
            from login_tracker import record_login
            await record_login(user_id)
        except Exception:
            pass

        return user_data

    except HTTPException:
        raise
    except Exception as e:
        # SECURITY: Sanitize error message to avoid token leakage (Issue #168)
        # Only log generic error type, never the actual exception details
        # which may contain token fragments
        log_auth_event(
            logger,
            event="token_verification",
            success=False,
            reason=type(e).__name__,  # Only log exception type, not message
        )
        raise HTTPException(status_code=401, detail="Token invalido ou expirado")


async def require_auth(
    user: Optional[dict] = Depends(get_current_user),
) -> dict:
    """Require authenticated user. Returns user dict or raises 401."""
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Autenticacao necessaria. Faca login para continuar.",
        )
    return user


async def _get_profile_mfa_state(user_id: str) -> dict:
    """MFA-EXT-001: Fetch the profile fields needed by require_mfa.

    Returns ``{plan_type, force_mfa_enrollment_until}`` as a dict. On any
    DB error returns an empty dict — caller treats missing fields as
    "no extra enforcement" so the existing admin/master path still gates.

    Uses ``sb_execute`` (asyncio.to_thread wrapper) to avoid blocking the
    event loop — the prod outage on 2026-04-27 was rooted in sync
    ``.execute()`` inside async handlers (memory
    project_backend_outage_2026_04_27).
    """
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()
        result = await sb_execute(
            sb.table("profiles")
            .select("plan_type, force_mfa_enrollment_until")
            .eq("id", user_id)
            .limit(1),
            category="read",
        )
        rows = result.data or []
        return rows[0] if rows else {}
    except Exception as e:
        logger.warning(
            "MFA-EXT-001: profile fetch failed for user %s: %s",
            user_id[:8],
            type(e).__name__,
        )
        return {}


async def _user_has_verified_mfa(user_id: str) -> bool:
    """MFA-EXT-001: Check whether the user has any verified MFA factor.

    Async-safe: uses sb_execute. Returns False on error (fail-open for
    non-admin paths, matching prior STORY-317 behavior).
    """
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()
        result = await sb_execute(
            sb.table("mfa_factors")
            .select("id")
            .eq("user_id", user_id)
            .eq("status", "verified")
            .limit(1),
            category="read",
        )
        return bool(result.data)
    except Exception as e:
        logger.warning(
            "MFA-EXT-001: factor check failed for user %s: %s",
            user_id[:8],
            type(e).__name__,
        )
        return False


def _force_until_active(force_until: Any) -> bool:
    """Return True iff force_mfa_enrollment_until is set and in the future.

    Accepts either an ISO string (Supabase return) or a datetime instance.
    Treats parse errors as "not active" (fail-open for the trigger; the
    admin/master path still gates).
    """
    if not force_until:
        return False
    try:
        from datetime import datetime, timezone
        if isinstance(force_until, str):
            iso = force_until.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
        elif isinstance(force_until, datetime):
            dt = force_until
        else:
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt > datetime.now(timezone.utc)
    except Exception:
        return False


async def require_mfa(
    user: dict = Depends(require_auth),
) -> dict:
    """STORY-317 + MFA-EXT-001: Require MFA (aal2) for sensitive endpoints.

    Enforcement triggers (any -> MFA mandatory):
      1. admin or master role (STORY-317)
      2. plan_type == 'consultoria' (MFA-EXT-001 AC1)
      3. force_mfa_enrollment_until > NOW() — set by bruteforce trigger
         or consultoria backfill (MFA-EXT-001 AC4-AC5)

    If aal2 is already on the JWT, pass through. Otherwise, if any
    enforcement trigger fires, raise 403 with X-MFA-Required +
    X-MFA-Reason headers (the banner reads X-MFA-Reason for variant text).

    Used on: /admin/*, /checkout, /billing-portal, /change-password
    """
    aal = user.get("aal", "aal1")
    user_id = user["id"]

    if aal == "aal2":
        return user

    # Probe extra enforcement state (plan + bruteforce window) BEFORE the
    # role check so we can build a single 403 with the right reason.
    profile = await _get_profile_mfa_state(user_id)
    plan_type = profile.get("plan_type")
    force_until = profile.get("force_mfa_enrollment_until")

    is_consultoria = plan_type == "consultoria"
    is_force_window = _force_until_active(force_until)

    # Existing admin/master check (kept as-is for STORY-317 compatibility)
    from authorization import check_user_roles
    is_admin, is_master = await check_user_roles(user_id)

    enforce_mfa = is_admin or is_master or is_consultoria or is_force_window

    if enforce_mfa:
        # Resolve a single reason for telemetry / banner variant. Order
        # mirrors STORY-317 precedence: admin > consultoria > bruteforce.
        if is_admin or is_master:
            reason = "admin"
            detail = "MFA obrigatório para sua conta. Configure a autenticação em dois fatores."
        elif is_consultoria:
            reason = "consultoria"
            detail = "Plano Consultoria requer MFA. Configure a autenticação em dois fatores."
        else:
            reason = "bruteforce"
            detail = "Detectamos tentativas suspeitas. MFA é obrigatório. Configure agora."

        # If user has a verified factor already, the issue is just step-up
        # (aal1 -> aal2 challenge, handled by Supabase Auth client-side).
        has_factor = await _user_has_verified_mfa(user_id)
        if has_factor:
            raise HTTPException(
                status_code=403,
                detail="Verificação MFA necessária. Use seu app autenticador.",
                headers={
                    "X-MFA-Required": "true",
                    "X-MFA-Reason": reason,
                },
            )
        # Otherwise: hard-block, banner will direct user to /conta/seguranca
        raise HTTPException(
            status_code=403,
            detail=detail,
            headers={
                "X-MFA-Required": "true",
                "X-MFA-Reason": reason,
            },
        )

    # No enforcement -> for regular users, fall back to STORY-317 behavior:
    # if they have a verified factor, they must step up to aal2.
    has_factor = await _user_has_verified_mfa(user_id)
    if has_factor:
        raise HTTPException(
            status_code=403,
            detail="Verificação MFA necessária. Use seu app autenticador.",
            headers={"X-MFA-Required": "true"},
        )

    return user


# MFA-ENFORCE-EXT-001: test-only bypass flag. Set by conftest fixture for
# legacy TestClient tests that override require_auth but do not mock the
# require_mfa probe chain. Production code MUST NOT set this flag.
_MFA_HIGH_IMPACT_TEST_BYPASS: bool = False


async def _require_mfa_or_passthrough(user: dict) -> dict:
    """MFA-ENFORCE-EXT-001 helper: runs require_mfa with test bypass support."""
    if _MFA_HIGH_IMPACT_TEST_BYPASS:
        return user
    return await require_mfa(user=user)


async def require_mfa_high_impact(
    user: dict = Depends(require_auth),
) -> dict:
    """MFA-ENFORCE-EXT-001 AC2+AC4: high-impact endpoint guard.

    Wrapper over `require_mfa` applied ONLY to endpoints listed in
    `docs/audits/2026-05-mfa-coverage.md` (billing portal, change-password,
    delete account, subscription cancel/update). Behaviour identical to
    `require_mfa` (same 403 + X-MFA-Required headers) PLUS emits a
    Mixpanel `mfa_challenge_satisfied` event when the request passes
    (i.e., user already has aal2 or no enforcement applies).

    The event lets us audit which high-impact actions were taken under
    a verified MFA session vs aal1 — separate from the existing
    enforcement-trigger telemetry.
    """
    user = await _require_mfa_or_passthrough(user)
    try:
        from analytics_events import track_event

        track_event(
            "mfa_challenge_satisfied",
            {
                "user_id": user.get("id", "unknown"),
                "aal": user.get("aal", "aal1"),
                "scope": "high_impact",
            },
        )
    except Exception:
        # Fire-and-forget — never fail the request if telemetry is down.
        pass
    return user


def clear_token_cache() -> int:
    """Clear all cached tokens. Useful for testing or security incidents.

    Returns:
        Number of cache entries cleared
    """
    global _token_cache
    count = len(_token_cache)
    _token_cache.clear()
    logger.info(f"Auth cache cleared - removed {count} entries")
    return count
