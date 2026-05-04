"""BIZ-METRIC-001: TTL-cached helpers for the ``app_config`` table.

The ``app_config`` table replaces hardcoded constants spread across the
backend. The first consumer is ``backend/routes/analytics.py::summary``,
which reads ``hours_saved_per_search`` from this helper instead of using
the previously hardcoded ``total_searches * 2``.

Design notes:
    * In-process TTL cache (default 5 min) keeps the analytics-summary
      hot path off the database. ``functools.lru_cache`` is *not* used
      because it has no time-based expiry and cannot be invalidated
      from the admin PATCH endpoint without resorting to private
      attributes.
    * Reads use the service-role Supabase client (RLS bypass).
    * Failures (DB unavailable, missing key, parse errors) fall back to
      the literal constant ``DEFAULT_HOURS_SAVED_PER_SEARCH`` so the
      personal dashboard never breaks because of a config issue.
    * ``invalidate_app_config(key)`` is called by the admin PATCH
      endpoint after a successful mutation so the next read picks up
      the new value immediately (worst case: another worker keeps
      the stale value until its own TTL expires — acceptable).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Per-search hours-saved fallback when the DB row is missing/unavailable.
#: Mirrors the seed value in
#: ``supabase/migrations/20260428100700_app_config_table.sql`` and
#: preserves the legacy hardcoded value (``total_searches * 2``).
DEFAULT_HOURS_SAVED_PER_SEARCH: float = 2.0

#: TTL for the in-process config cache, in seconds (5 minutes).
DEFAULT_TTL_SECONDS: int = 300

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

# (value, expires_at_monotonic)
_cache: dict[str, tuple[Any, float]] = {}
_cache_lock = threading.Lock()


def _now() -> float:
    return time.monotonic()


def _store(key: str, value: Any, ttl_seconds: int) -> None:
    with _cache_lock:
        _cache[key] = (value, _now() + ttl_seconds)


def _peek(key: str) -> Optional[Any]:
    """Return cached value if non-expired, else None."""
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at <= _now():
            _cache.pop(key, None)
            return None
        return value


def invalidate_app_config(key: Optional[str] = None) -> None:
    """Drop one (or all, if ``key`` is None) cache entries.

    Called by ``backend/routes/admin_calibration.py`` after a PATCH so
    callers in the same process see the new value on the next read.
    """
    with _cache_lock:
        if key is None:
            _cache.clear()
        else:
            _cache.pop(key, None)


def clear_cache() -> None:
    """Test convenience — drop all entries."""
    invalidate_app_config(None)


# ---------------------------------------------------------------------------
# DB read
# ---------------------------------------------------------------------------

def _fetch_value_from_db(key: str) -> Optional[Any]:
    """Fetch ``app_config.value`` for *key* via service-role client.

    Returns the parsed JSONB payload (Python object) or None if the row
    does not exist / DB is unavailable. Errors are swallowed and logged
    at WARNING — analytics summary stays available with the fallback
    constant.
    """
    try:
        from supabase_client import get_supabase  # local import: avoid circulars at module load

        sb = get_supabase()
        result = (
            sb.table("app_config")
            .select("value")
            .eq("key", key)
            .limit(1)
            .execute()
        )
        rows = getattr(result, "data", None) or []
        if not rows:
            return None
        return rows[0].get("value")
    except Exception as exc:
        logger.warning("app_config fetch failed for key=%s: %s", key, exc)
        return None


# ---------------------------------------------------------------------------
# Public reads
# ---------------------------------------------------------------------------

def get_config_value(
    key: str,
    *,
    default: Any = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> Any:
    """Read ``app_config.value`` for *key* with TTL cache + safe fallback.

    Args:
        key: The config row identifier (e.g. ``hours_saved_per_search``).
        default: Returned if the DB row is missing or unreadable.
        ttl_seconds: How long to cache successful reads.

    Returns:
        The parsed JSONB payload, or ``default`` on miss/error. Successful
        reads are cached. Misses are NOT cached (so a freshly-seeded row
        becomes visible on the next call).
    """
    cached = _peek(key)
    if cached is not None:
        return cached

    value = _fetch_value_from_db(key)
    if value is None:
        return default

    _store(key, value, ttl_seconds)
    return value


def get_hours_saved_per_search(*, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> float:
    """Convenience reader for the ``hours_saved_per_search`` constant.

    Always returns a positive ``float``. Coerces JSON numbers/strings to
    float; falls back to ``DEFAULT_HOURS_SAVED_PER_SEARCH`` on any
    parse failure or missing row.
    """
    raw = get_config_value(
        "hours_saved_per_search",
        default=DEFAULT_HOURS_SAVED_PER_SEARCH,
        ttl_seconds=ttl_seconds,
    )
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning(
            "app_config.hours_saved_per_search has non-numeric value %r; "
            "falling back to %.2f",
            raw,
            DEFAULT_HOURS_SAVED_PER_SEARCH,
        )
        return DEFAULT_HOURS_SAVED_PER_SEARCH

    if value <= 0 or value > 50:
        logger.warning(
            "app_config.hours_saved_per_search out of sane range (got %.4f); "
            "falling back to %.2f",
            value,
            DEFAULT_HOURS_SAVED_PER_SEARCH,
        )
        return DEFAULT_HOURS_SAVED_PER_SEARCH

    return value


__all__ = [
    "DEFAULT_HOURS_SAVED_PER_SEARCH",
    "DEFAULT_TTL_SECONDS",
    "clear_cache",
    "get_config_value",
    "get_hours_saved_per_search",
    "invalidate_app_config",
]
