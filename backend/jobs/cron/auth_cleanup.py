"""jobs.cron.auth_cleanup — MFA-EXT-001 AC7.

Two daily cleanups:

1. Reset stale ``auth_attempts`` rows: if ``last_failure_at`` is older
   than 24h and ``consecutive_failures > 0``, set the counter back to 0.
   This is the safety net for the per-attempt runtime check (the
   ``/auth/login-attempt`` endpoint also performs the 24h idle reset
   inline, so the cron only catches users who never come back to retry).

2. Clear expired ``profiles.force_mfa_enrollment_until``: if the
   timestamp is in the past AND the user is still without MFA, clear
   the column so the next request to a protected endpoint produces a
   fresh evaluation. Without this, a user who blew through the 7-day
   bruteforce window would stay hard-blocked forever — defeating the
   "force MFA enrollment" intent (it's a *deadline*, not a permanent
   ban).

Schedule: every 24 h, kicked off at startup like sibling crons.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# 24h interval, like other daily housekeeping crons.
AUTH_CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60

# Counter is reset if no new failure in the last 24h.
ATTEMPT_IDLE_HOURS = 24


def _is_cb_or_connection_error(exc: BaseException) -> bool:
    """Best-effort detection of a circuit-breaker / Supabase connection
    error so we can downgrade to a warning instead of a Sentry-grade error.

    Mirrors jobs.cron.canary._is_cb_or_connection_error to avoid a hard
    import dependency between crons.
    """
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return (
        "circuitbreaker" in name
        or "circuit" in msg
        or "connectionerror" in name
        or "timeout" in name
    )


async def reset_stale_auth_attempts() -> dict:
    """Reset ``consecutive_failures = 0`` for rows idle > 24h.

    Returns a small dict for logging / tests.
    """
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=ATTEMPT_IDLE_HOURS)
        ).isoformat()
        result = await sb_execute(
            sb.table("auth_attempts")
            .update({"consecutive_failures": 0})
            .gt("consecutive_failures", 0)
            .lt("last_failure_at", cutoff),
            category="write",
        )
        reset_count = len(result.data) if result and result.data else 0
        logger.info("MFA-EXT-001: reset %d stale auth_attempts (24h idle)", reset_count)
        return {"reset": reset_count}
    except Exception as e:
        if _is_cb_or_connection_error(e):
            logger.warning("MFA-EXT-001: auth_attempts reset skipped (Supabase unavailable): %s", e)
        else:
            logger.error("MFA-EXT-001: auth_attempts reset error: %s", e, exc_info=True)
        return {"reset": 0, "error": str(e)}


async def clear_expired_force_mfa() -> dict:
    """Clear ``profiles.force_mfa_enrollment_until`` for rows past the deadline.

    Only clears rows where the deadline is in the past. Users who enrolled
    MFA mid-window keep their column populated until cleanup runs — that's
    fine because ``require_mfa`` short-circuits on aal2 / verified factor
    well before consulting the column.
    """
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()
        now_iso = datetime.now(timezone.utc).isoformat()
        result = await sb_execute(
            sb.table("profiles")
            .update({"force_mfa_enrollment_until": None})
            .lt("force_mfa_enrollment_until", now_iso),
            category="write",
        )
        cleared = len(result.data) if result and result.data else 0
        logger.info("MFA-EXT-001: cleared %d expired force_mfa_enrollment_until", cleared)
        return {"cleared": cleared}
    except Exception as e:
        if _is_cb_or_connection_error(e):
            logger.warning("MFA-EXT-001: force_mfa cleanup skipped (Supabase unavailable): %s", e)
        else:
            logger.error("MFA-EXT-001: force_mfa cleanup error: %s", e, exc_info=True)
        return {"cleared": 0, "error": str(e)}


async def run_auth_cleanup_once() -> dict:
    """Run both cleanup steps once. Used by the loop and by tests."""
    attempts = await reset_stale_auth_attempts()
    force = await clear_expired_force_mfa()
    return {"attempts": attempts, "force_mfa": force}


async def _auth_cleanup_loop() -> None:
    """Background loop — runs once at startup, then every 24h."""
    try:
        result = await run_auth_cleanup_once()
        logger.info("MFA-EXT-001 auth cleanup (startup): %s", result)
    except Exception as e:
        if _is_cb_or_connection_error(e):
            logger.warning("MFA-EXT-001 startup auth cleanup skipped: %s", e)
        else:
            logger.error("MFA-EXT-001 startup auth cleanup error: %s", e, exc_info=True)

    while True:
        try:
            await asyncio.sleep(AUTH_CLEANUP_INTERVAL_SECONDS)
            result = await run_auth_cleanup_once()
            logger.info("MFA-EXT-001 auth cleanup cycle: %s", result)
        except asyncio.CancelledError:
            logger.info("MFA-EXT-001: auth cleanup task cancelled")
            break
        except Exception as e:
            if _is_cb_or_connection_error(e):
                logger.warning("MFA-EXT-001 auth cleanup cycle skipped: %s", e)
            else:
                logger.error("MFA-EXT-001 auth cleanup cycle error: %s", e, exc_info=True)
            await asyncio.sleep(300)


async def start_auth_cleanup_task() -> asyncio.Task:
    """Lifespan hook: kick off the auth cleanup background loop."""
    task = asyncio.create_task(_auth_cleanup_loop(), name="auth_cleanup")
    logger.info("MFA-EXT-001: auth cleanup background task started (interval: 24h)")
    return task
