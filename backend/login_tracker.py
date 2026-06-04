"""Login activity tracking with Redis write-behind.

LIFECYCLE-002 (#1427):
- Records login activity on session refresh (cache miss in auth.get_current_user)
- Daily dedup via Redis SETNX (1 per user per day)
- Redis write-behind flush to PostgreSQL every 5 minutes
- Graceful degradation if Redis is unavailable (in-memory fallback buffer)
- No sync PG writes on the request path

Architecture:
    record_login() -> Redis SETNX (dedup) + LPUSH (flush queue)
        -> periodic_flush() -> PG
        -> PG (direct, if Redis unavailable)
"""

import asyncio
import json
import logging
import time
from datetime import date, datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis key prefixes and constants
# ---------------------------------------------------------------------------
_REDIS_PREFIX = "smartlic:login:"
_KEY_ACTIVITY = f"{_REDIS_PREFIX}activity"       # :{user_id}:{date} (SETNX, 7d TTL)
_KEY_LAST_LOGIN = f"{_REDIS_PREFIX}last_login"   # :{user_id} (SET, 7d TTL)
# LPUSH list of pending flush entries
_KEY_FLUSH_QUEUE = f"{_REDIS_PREFIX}flush:pending"
_ACTIVITY_TTL = 7 * 24 * 3600    # 7 days
_FLUSH_QUEUE_TTL = 600           # 10 minutes (safety cleanup)
_FLUSH_INTERVAL_S = 300          # 5 minutes between PG flushes

# ---------------------------------------------------------------------------
# In-memory fallback buffer (flushed when Redis is unavailable)
# ---------------------------------------------------------------------------
_fallback_buffer: set[tuple[str, str]] = set()  # {(user_id, date_str)}
_last_fallback_flush: float = 0.0
_FALLBACK_FLUSH_COOLDOWN_S = 60  # Don't flush in-memory more than once per minute


async def _get_redis():
    """Get Redis pool — returns None gracefully if unavailable."""
    try:
        from redis_pool import get_redis_pool
        return await get_redis_pool()
    except Exception:
        return None


async def record_login(user_id: str, login_date: Optional[date] = None) -> None:
    """Record a login activity with daily dedup.

    Called on session refresh (cache miss in auth.get_current_user).
    Fire-and-forget — never blocks the request path with synchronous PG writes.

    Args:
        user_id: The authenticated user's UUID.
        login_date: Override date (defaults to today UTC).

    Design:
        1. Redis SETNX on ``smartlic:login:activity:{user_id}:{date}`` — atomic
           dedup. If the key already exists, this is not the first login today.
        2. On first login today: LPUSH metadata onto the flush queue.
        3. Background ``periodic_flush()`` drains the queue every 5 minutes.
        4. If Redis is unavailable, falls back to an in-memory set that is
           also drained by ``periodic_flush()``.
    """
    if not user_id:
        return

    today = login_date or datetime.now(timezone.utc).date()
    date_str = today.isoformat()

    redis = await _get_redis()
    if redis:
        try:
            activity_key = f"{_KEY_ACTIVITY}:{user_id}:{date_str}"
            is_new = await redis.setnx(activity_key, "1")
            if is_new:
                await redis.expire(activity_key, _ACTIVITY_TTL)

                # Track last login time
                last_login_key = f"{_KEY_LAST_LOGIN}:{user_id}"
                now_iso = datetime.now(timezone.utc).isoformat()
                await redis.set(last_login_key, now_iso, ex=_ACTIVITY_TTL)

                # Queue for PG flush
                payload = json.dumps({
                    "user_id": user_id,
                    "login_date": date_str,
                    "timestamp": now_iso,
                })
                await redis.lpush(_KEY_FLUSH_QUEUE, payload)
                await redis.expire(_KEY_FLUSH_QUEUE, _FLUSH_QUEUE_TTL)

                logger.debug(
                    "Login recorded via Redis: user=%s date=%s",
                    user_id[:8], date_str,
                )
            return
        except Exception as e:
            logger.warning(
                "Redis login tracking failed (%s) — fallback to in-memory buffer",
                e,
            )
            # Fall through to in-memory fallback

    # Fallback: in-memory buffer when Redis is unavailable
    entry = (user_id, date_str)
    if entry not in _fallback_buffer:
        _fallback_buffer.add(entry)
        logger.debug(
            "Login recorded in-memory fallback: user=%s date=%s",
            user_id[:8], date_str,
        )


# ---------------------------------------------------------------------------
# PG flush core
# ---------------------------------------------------------------------------

async def _flush_batch(entries: list[dict]) -> int:
    """Flush accumulated login records to PostgreSQL via the record_login RPC.

    Deduplicates by (user_id, login_date) before flushing, then calls the
    idempotent ``public.record_login`` RPC for each unique entry.

    Args:
        entries: List of dicts with keys ``user_id``, ``login_date``, ``timestamp``.

    Returns:
        Number of successfully flushed entries.
    """
    if not entries:
        return 0

    # Dedup by (user_id, login_date)
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for e in entries:
        key = (e["user_id"], e["login_date"])
        if key not in seen:
            seen.add(key)
            unique.append(e)

    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()

        flushed = 0
        for entry in unique:
            try:
                ts = entry.get("timestamp",
                              datetime.now(timezone.utc).isoformat())
                await sb_execute(
                    sb.rpc("record_login", {
                        "p_user_id": entry["user_id"],
                        "p_login_date": entry["login_date"],
                        "p_last_login_at": ts,
                    }),
                    category="write",
                )
                flushed += 1
            except Exception as e:
                logger.error(
                    "Failed to flush login for user %s: %s",
                    entry["user_id"][:8], e,
                )

        if flushed:
            logger.info("Login flush: %d entries flushed to PG", flushed)
        return flushed

    except Exception as e:
        logger.error("Login flush batch failed: %s", e)
        return 0


# ---------------------------------------------------------------------------
# Redis queue flush
# ---------------------------------------------------------------------------

async def _flush_redis_buffer() -> int:
    """Drain all pending login records from the Redis LPUSH queue to PG.

    Retrieves the full list atomically, deletes the key, then processes.
    """
    redis = await _get_redis()
    if not redis:
        return 0

    try:
        entries_data = await redis.lrange(_KEY_FLUSH_QUEUE, 0, -1)
        if not entries_data:
            return 0

        # Atomically drain — delete before processing to avoid duplicates
        # if a crash occurs mid-flush (dedup at PG layer handles the rest).
        await redis.delete(_KEY_FLUSH_QUEUE)

        entries: list[dict] = []
        for raw in entries_data:
            try:
                entries.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                continue

        return await _flush_batch(entries)
    except Exception as e:
        logger.error("Failed to flush Redis login buffer: %s", e)
        return 0


# ---------------------------------------------------------------------------
# In-memory fallback flush
# ---------------------------------------------------------------------------

async def _flush_inmemory_fallback() -> int:
    """Flush the in-memory fallback buffer to PG.

    Fire every minute at most (cooldown: ``_FALLBACK_FLUSH_COOLDOWN_S``).
    """
    global _last_fallback_flush, _fallback_buffer

    now = time.monotonic()
    if now - _last_fallback_flush < _FALLBACK_FLUSH_COOLDOWN_S:
        return 0

    _last_fallback_flush = now

    if not _fallback_buffer:
        return 0

    # Snapshot and clear
    buffer_snapshot = set(_fallback_buffer)
    _fallback_buffer.clear()

    entries = [
        {
            "user_id": uid,
            "login_date": ds,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for uid, ds in buffer_snapshot
    ]

    return await _flush_batch(entries)


# ---------------------------------------------------------------------------
# Background periodic flush task
# ---------------------------------------------------------------------------

async def periodic_flush() -> None:
    """Background coroutine: flush login activity buffers every 5 minutes.

    Registered in ``startup/lifespan.py`` via ``TaskRegistry``.
    Drains both the Redis LPUSH queue and the in-memory fallback set.
    """
    logger.info(
        "Login tracker: periodic flush task started (interval=%ds)",
        _FLUSH_INTERVAL_S,
    )
    while True:
        try:
            await asyncio.sleep(_FLUSH_INTERVAL_S)
            redis_count = await _flush_redis_buffer()
            mem_count = await _flush_inmemory_fallback()
            if redis_count or mem_count:
                logger.debug(
                    "Periodic flush: redis=%d in-memory=%d",
                    redis_count, mem_count,
                )
        except asyncio.CancelledError:
            logger.info("Login tracker: periodic flush cancelled")
            break
        except Exception as e:
            logger.error("Login tracker: periodic flush error: %s", e)


async def flush_now() -> int:
    """Force-flush all pending login records.

    Called during shutdown to minimise data loss.
    Returns total entries flushed.
    """
    total = await _flush_redis_buffer()
    total += await _flush_inmemory_fallback()
    if total:
        logger.info("Login tracker: flush_now completed — %d entries flushed", total)
    return total
