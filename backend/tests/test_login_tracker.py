"""Tests for login_tracker — Redis write-behind login activity tracking.

LIFECYCLE-002 (#1427):
- Daily dedup via Redis SETNX
- Redis write-behind flush to PostgreSQL every 5min
- Graceful degradation when Redis is unavailable
"""

import json
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_fallback_buffer():
    """Clear the in-memory fallback buffer and reset cooldown before each test."""
    import login_tracker as lt
    lt._fallback_buffer.clear()
    lt._last_fallback_flush = 0.0
    yield


@pytest.fixture
def mock_redis():
    """Mock Redis client with common async methods."""
    redis = AsyncMock()
    redis.setnx = AsyncMock(return_value=1)  # 1 = key was set (new login day)
    redis.expire = AsyncMock(return_value=True)
    redis.set = AsyncMock(return_value=True)
    redis.lpush = AsyncMock(return_value=1)
    redis.lrange = AsyncMock(return_value=[])
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def mock_redis_pool(mock_redis):
    """Patch _get_redis to return the mock Redis."""
    with patch("login_tracker._get_redis", AsyncMock(return_value=mock_redis)) as mock_fn:
        yield mock_fn


@pytest.fixture
def mock_redis_unavailable():
    """Patch _get_redis to return None (Redis unavailable)."""
    with patch("login_tracker._get_redis", AsyncMock(return_value=None)) as mock_fn:
        yield mock_fn


@pytest.fixture
def mock_supabase():
    """Mock supabase_client.get_supabase and sb_execute for flush tests."""
    sb = MagicMock()
    sb.table.return_value = sb
    sb.rpc.return_value = sb
    sb.select.return_value = sb
    sb.eq.return_value = sb
    sb.single.return_value = sb
    sb.update.return_value = sb

    with patch("supabase_client.get_supabase", return_value=sb):
        with patch("supabase_client.sb_execute", AsyncMock(return_value=MagicMock())) as mock_exec:
            yield mock_exec


# ═══════════════════════════════════════════════════════════════════════════════
# record_login — Redis path
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecordLoginWithRedis:
    """record_login with Redis available."""

    @pytest.mark.asyncio
    async def test_records_new_login_day(self, mock_redis, mock_redis_pool):
        """SETNX returns 1: first login today -> record activity + queue flush."""
        from login_tracker import record_login

        await record_login("user-123")

        # SETNX called with correct activity key
        key = mock_redis.setnx.call_args[0][0]
        assert "smartlic:login:activity:" in key
        assert "user-123" in key
        assert _today_str() in key

        # Expire set on activity key
        mock_redis.expire.assert_called()

        # Last login time recorded via SET
        mock_redis.set.assert_called_once()

        # Flush queue entry pushed
        mock_redis.lpush.assert_called_once()
        payload_key = mock_redis.lpush.call_args[0][0]
        assert "smartlic:login:flush:pending" in payload_key
        payload = json.loads(mock_redis.lpush.call_args[0][1])
        assert payload["user_id"] == "user-123"
        assert payload["login_date"] == _today_str()

    @pytest.mark.asyncio
    async def test_skips_duplicate_login_day(self, mock_redis, mock_redis_pool):
        """SETNX returns 0: already logged in today -> skip."""
        mock_redis.setnx.return_value = 0  # Already exists

        from login_tracker import record_login

        await record_login("user-123")

        mock_redis.set.assert_not_called()
        mock_redis.lpush.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_empty_user_id(self, mock_redis, mock_redis_pool):
        """Empty user_id should be a no-op."""
        from login_tracker import record_login

        await record_login("")
        await record_login(None)

        mock_redis.setnx.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_provided_date(self, mock_redis, mock_redis_pool):
        """Custom date override works."""
        from login_tracker import record_login

        custom_date = date(2026, 6, 1)
        await record_login("user-123", login_date=custom_date)

        key = mock_redis.setnx.call_args[0][0]
        assert "2026-06-01" in key

    @pytest.mark.asyncio
    async def test_handles_redis_error_gracefully(self, mock_redis, mock_redis_pool):
        """Redis error should fall back to in-memory buffer."""
        mock_redis.setnx.side_effect = Exception("Redis connection lost")

        from login_tracker import record_login, _fallback_buffer

        await record_login("user-123")

        assert ("user-123", _today_str()) in _fallback_buffer


# ═══════════════════════════════════════════════════════════════════════════════
# record_login — Redis unavailable path
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecordLoginRedisUnavailable:
    """record_login when Redis is unavailable (graceful degradation)."""

    @pytest.mark.asyncio
    async def test_falls_back_to_inmemory_buffer(self, mock_redis_unavailable):
        """Redis unavailable: store in in-memory fallback set."""
        from login_tracker import record_login, _fallback_buffer

        await record_login("user-123")

        assert len(_fallback_buffer) == 1
        assert ("user-123", _today_str()) in _fallback_buffer

    @pytest.mark.asyncio
    async def test_deduplicates_in_inmemory_buffer(self, mock_redis_unavailable):
        """Same user+date should not create duplicate buffer entries."""
        from login_tracker import record_login, _fallback_buffer

        await record_login("user-123")
        await record_login("user-123")

        assert len(_fallback_buffer) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# _flush_batch — PG flush core
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlushBatch:
    """_flush_batch core logic."""

    @pytest.mark.asyncio
    async def test_flushes_unique_entries(self, mock_supabase):
        """Unique entries are flushed via record_login RPC."""
        from login_tracker import _flush_batch

        entries = [
            {"user_id": "user-1", "login_date": "2026-06-01", "timestamp": "2026-06-01T10:00:00"},
            {"user_id": "user-2", "login_date": "2026-06-01", "timestamp": "2026-06-01T10:00:00"},
        ]

        count = await _flush_batch(entries)
        assert count == 2

    @pytest.mark.asyncio
    async def test_deduplicates_by_user_and_date(self, mock_supabase):
        """Duplicate (user_id, login_date) pairs are flushed once."""
        from login_tracker import _flush_batch

        entries = [
            {"user_id": "user-1", "login_date": "2026-06-01", "timestamp": "2026-06-01T10:00:00"},
            {"user_id": "user-1", "login_date": "2026-06-01", "timestamp": "2026-06-01T12:00:00"},
            {"user_id": "user-2", "login_date": "2026-06-01", "timestamp": "2026-06-01T10:00:00"},
        ]

        count = await _flush_batch(entries)
        assert count == 2  # user-1 counted once, user-2 once

    @pytest.mark.asyncio
    async def test_handles_empty_entries(self, mock_supabase):
        """Empty list returns 0 without calling Supabase."""
        from login_tracker import _flush_batch

        count = await _flush_batch([])
        assert count == 0
        mock_supabase.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_rpc_failure_gracefully(self, mock_supabase):
        """RPC failure should not crash the batch — logs and continues."""
        from login_tracker import _flush_batch

        mock_supabase.side_effect = Exception("DB error")

        entries = [
            {"user_id": "user-1", "login_date": "2026-06-01", "timestamp": "2026-06-01T10:00:00"},
        ]
        count = await _flush_batch(entries)
        assert count == 0  # Failed, but no exception raised


# ═══════════════════════════════════════════════════════════════════════════════
# _flush_redis_buffer — Redis queue flush
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlushRedisBuffer:
    """_flush_redis_buffer — drain Redis LPUSH queue to PG."""

    @pytest.mark.asyncio
    async def test_drains_queue(self, mock_redis, mock_redis_pool):
        """Drains Redis queue and calls _flush_batch."""
        from login_tracker import _flush_redis_buffer

        mock_redis.lrange.return_value = [
            json.dumps({"user_id": "user-1", "login_date": "2026-06-01", "timestamp": "2026-06-01T10:00:00"}),
            json.dumps({"user_id": "user-2", "login_date": "2026-06-01", "timestamp": "2026-06-01T10:00:00"}),
        ]

        with patch("login_tracker._flush_batch", AsyncMock(return_value=2)) as mock_flush:
            count = await _flush_redis_buffer()

            assert count == 2
            mock_flush.assert_called_once()
            mock_redis.delete.assert_called_once_with("smartlic:login:flush:pending")

    @pytest.mark.asyncio
    async def test_noop_when_queue_empty(self, mock_redis, mock_redis_pool):
        """Empty queue returns 0 without calling flush or delete."""
        from login_tracker import _flush_redis_buffer

        mock_redis.lrange.return_value = []

        with patch("login_tracker._flush_batch", AsyncMock()) as mock_flush:
            count = await _flush_redis_buffer()

            assert count == 0
            mock_flush.assert_not_called()
            mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_noop_when_redis_unavailable(self, mock_redis_unavailable):
        """Redis unavailable: returns 0."""
        from login_tracker import _flush_redis_buffer

        count = await _flush_redis_buffer()
        assert count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# _flush_inmemory_fallback — in-memory buffer flush
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlushInmemoryFallback:
    """_flush_inmemory_fallback — drain in-memory fallback buffer to PG."""

    @pytest.mark.asyncio
    async def test_flushes_buffer(self):
        """In-memory buffer entries are flushed."""
        from login_tracker import _flush_inmemory_fallback, _fallback_buffer

        _fallback_buffer.add(("user-1", "2026-06-01"))
        _fallback_buffer.add(("user-2", "2026-06-01"))

        with patch("login_tracker._flush_batch", AsyncMock(return_value=2)) as mock_flush:
            count = await _flush_inmemory_fallback()

            assert count == 2
            mock_flush.assert_called_once()
            assert len(_fallback_buffer) == 0  # Buffer cleared

    @pytest.mark.asyncio
    async def test_respects_cooldown(self):
        """Should not flush more than once per minute."""
        from login_tracker import _flush_inmemory_fallback, _fallback_buffer

        import login_tracker as lt
        lt._last_fallback_flush = 999999999.0

        _fallback_buffer.add(("user-1", "2026-06-01"))

        with patch("login_tracker._flush_batch", AsyncMock()) as mock_flush:
            count = await _flush_inmemory_fallback()
            assert count == 0
            mock_flush.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: auth.get_current_user triggers record_login
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthIntegration:
    """get_current_user cache miss triggers record_login.

    Verifies by checking the in-memory fallback buffer after a cache miss
    (Redis not configured in test env -> falls through to in-memory buffer).
    """

    _ENV = {
        "SUPABASE_JWT_SECRET": "test-secret-key-at-least-32-chars-long!",
        "SUPABASE_URL": "https://test.supabase.co",
    }

    @pytest.mark.asyncio
    @patch.dict("os.environ", _ENV)
    async def test_cache_miss_calls_record_login(self):
        """Cache miss -> JWT validated -> record_login called (buffer has entry)."""
        from auth import get_current_user
        from login_tracker import _fallback_buffer

        mock_jwt_decode = MagicMock(return_value={
            "sub": "user-123-uuid",
            "email": "test@example.com",
            "role": "authenticated",
            "aud": "authenticated",
        })

        with (
            patch("auth.jwt.decode", mock_jwt_decode),
            patch("auth._get_jwt_key_and_algorithms", return_value=("test-secret", ["HS256"])),
            patch("auth._redis_cache_get", AsyncMock(return_value=None)),
            patch("auth._redis_cache_set", AsyncMock()),
        ):
            _fallback_buffer.clear()

            credentials = MagicMock()
            credentials.credentials = "valid.jwt.token"

            result = await get_current_user(credentials=credentials)

            assert result is not None
            assert result["id"] == "user-123-uuid"

            # record_login was called -> in-memory fallback buffer has entry
            assert len(_fallback_buffer) == 1
            entry = next(iter(_fallback_buffer))
            assert entry[0] == "user-123-uuid"
            assert entry[1] == datetime.now(timezone.utc).date().isoformat()

    @pytest.mark.asyncio
    @patch.dict("os.environ", _ENV)
    async def test_cache_hit_does_not_call_record_login(self):
        """Cache HIT -> record_login NOT called (buffer is empty)."""
        from auth import get_current_user
        from login_tracker import _fallback_buffer

        with (
            patch("auth._redis_cache_get", AsyncMock(return_value={
                "id": "user-123-uuid",
                "email": "test@example.com",
                "role": "authenticated",
            })),
            patch("auth._redis_cache_set", AsyncMock()),
        ):
            _fallback_buffer.clear()

            credentials = MagicMock()
            credentials.credentials = "valid.jwt.token"

            result = await get_current_user(credentials=credentials)

            assert result is not None

            # Cache HIT -> record_login NOT called -> buffer is empty
            assert len(_fallback_buffer) == 0

    @pytest.mark.asyncio
    @patch.dict("os.environ", _ENV)
    async def test_record_login_failure_does_not_block_auth(self):
        """record_login exception should not prevent auth success."""
        from auth import get_current_user
        from login_tracker import _fallback_buffer

        mock_jwt_decode = MagicMock(return_value={
            "sub": "user-456-uuid",
            "email": "other@example.com",
            "role": "authenticated",
            "aud": "authenticated",
        })

        with (
            patch("auth.jwt.decode", mock_jwt_decode),
            patch("auth._get_jwt_key_and_algorithms", return_value=("test-secret", ["HS256"])),
            patch("auth._redis_cache_get", AsyncMock(return_value=None)),
            patch("auth._redis_cache_set", AsyncMock()),
        ):
            _fallback_buffer.clear()

            credentials = MagicMock()
            credentials.credentials = "valid.jwt.token2"

            result = await get_current_user(credentials=credentials)

            # Auth still succeeds even if record_login internally errors
            assert result is not None
            assert result["id"] == "user-456-uuid"


# ═══════════════════════════════════════════════════════════════════════════════
# flush_now — force flush
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlushNow:
    """flush_now force-flush on shutdown."""

    @pytest.mark.asyncio
    async def test_flushes_both_buffers(self, mock_redis, mock_redis_pool):
        """flush_now drains Redis queue and in-memory buffer."""
        from login_tracker import flush_now, _fallback_buffer

        mock_redis.lrange.return_value = [
            json.dumps({"user_id": "user-1", "login_date": "2026-06-01", "timestamp": "2026-06-01T10:00:00"}),
        ]

        _fallback_buffer.add(("user-2", "2026-06-01"))

        with patch("login_tracker._flush_batch", AsyncMock(return_value=1)) as mock_flush:
            total = await flush_now()

            assert total >= 2
            assert mock_flush.call_count >= 1
