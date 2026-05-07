"""TD-TEST-004: Unit tests for backend/health.py core module.

Covers functions NOT already tested in test_health_canary.py,
test_health_wedge_risk.py, or test_health_ready.py:
  - HealthStatus enum values
  - SourceHealthResult dataclass and to_dict()
  - SystemHealth dataclass and to_dict()
  - initialize_health_tracking() / get_uptime_seconds()
  - get_health_status() integration (mocking check_all_sources_health)
  - get_system_health() component checks (Redis, Supabase, circuit breakers)
  - ConnectError path in check_source_health()
"""

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. HealthStatus enum
# ---------------------------------------------------------------------------

class TestHealthStatusEnum:
    """Verify enum string values used in JSON responses."""

    def test_healthy_value(self):
        from health import HealthStatus
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.HEALTHY.value == "healthy"

    def test_degraded_value(self):
        from health import HealthStatus
        assert HealthStatus.DEGRADED == "degraded"

    def test_unhealthy_value(self):
        from health import HealthStatus
        assert HealthStatus.UNHEALTHY == "unhealthy"

    def test_enum_is_str_subclass(self):
        from health import HealthStatus
        assert isinstance(HealthStatus.HEALTHY, str)


# ---------------------------------------------------------------------------
# 2. SourceHealthResult dataclass / to_dict()
# ---------------------------------------------------------------------------

class TestSourceHealthResult:
    """to_dict() must produce the exact keys consumed by frontend/monitoring."""

    def test_to_dict_has_required_keys(self):
        from health import SourceHealthResult, HealthStatus
        r = SourceHealthResult(
            source_code="PNCP",
            status=HealthStatus.HEALTHY,
            response_time_ms=42,
        )
        d = r.to_dict()
        for key in ("source", "status", "response_time_ms", "error", "last_checked"):
            assert key in d, f"Missing key: {key}"

    def test_to_dict_status_is_string(self):
        from health import SourceHealthResult, HealthStatus
        r = SourceHealthResult(source_code="Portal", status=HealthStatus.DEGRADED)
        d = r.to_dict()
        assert isinstance(d["status"], str)
        assert d["status"] == "degraded"

    def test_to_dict_error_none_when_healthy(self):
        from health import SourceHealthResult, HealthStatus
        r = SourceHealthResult(source_code="PNCP", status=HealthStatus.HEALTHY)
        assert r.to_dict()["error"] is None

    def test_to_dict_error_populated_when_provided(self):
        from health import SourceHealthResult, HealthStatus
        r = SourceHealthResult(
            source_code="PNCP",
            status=HealthStatus.UNHEALTHY,
            error="Connection refused",
        )
        assert r.to_dict()["error"] == "Connection refused"

    def test_to_dict_last_checked_is_iso_string(self):
        from health import SourceHealthResult, HealthStatus
        r = SourceHealthResult(source_code="PNCP", status=HealthStatus.HEALTHY)
        d = r.to_dict()
        # Must be parseable as timezone-aware datetime
        ts = datetime.fromisoformat(d["last_checked"])
        assert ts.tzinfo is not None


# ---------------------------------------------------------------------------
# 3. SystemHealth dataclass / to_dict()
# ---------------------------------------------------------------------------

class TestSystemHealth:
    """to_dict() structure is the contract for the /sources/health payload."""

    def _make_system_health(self, status="healthy"):
        from health import SystemHealth, HealthStatus, SourceHealthResult
        return SystemHealth(
            status=HealthStatus(status),
            version="0.3.0",
            timestamp=datetime.now(timezone.utc),
            sources={
                "PNCP": SourceHealthResult(
                    source_code="PNCP",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=55,
                )
            },
            uptime_seconds=123.4,
            environment="test",
        )

    def test_to_dict_top_level_keys(self):
        h = self._make_system_health()
        d = h.to_dict()
        required = (
            "status", "version", "timestamp",
            "environment", "uptime_seconds", "sources",
        )
        for key in required:
            assert key in d, f"Missing top-level key: {key}"

    def test_to_dict_sources_nested_correctly(self):
        h = self._make_system_health()
        d = h.to_dict()
        assert "PNCP" in d["sources"]
        pncp = d["sources"]["PNCP"]
        assert pncp["status"] == "healthy"

    def test_to_dict_status_is_string(self):
        h = self._make_system_health("degraded")
        assert h.to_dict()["status"] == "degraded"

    def test_to_dict_version_preserved(self):
        h = self._make_system_health()
        assert h.to_dict()["version"] == "0.3.0"


# ---------------------------------------------------------------------------
# 4. Uptime tracking
# ---------------------------------------------------------------------------

class TestUptimeTracking:
    """initialize_health_tracking() / get_uptime_seconds() round-trip."""

    def test_uptime_none_before_init(self):
        from health import get_uptime_seconds
        import health as health_module
        original = health_module._start_time
        try:
            health_module._start_time = None
            result = get_uptime_seconds()
            assert result is None
        finally:
            health_module._start_time = original

    def test_uptime_positive_after_init(self):
        from health import initialize_health_tracking, get_uptime_seconds
        import health as health_module
        original = health_module._start_time
        try:
            initialize_health_tracking()
            uptime = get_uptime_seconds()
            assert uptime is not None
            assert uptime >= 0.0
        finally:
            health_module._start_time = original

    def test_uptime_increases_over_time(self):
        from health import initialize_health_tracking, get_uptime_seconds
        import health as health_module
        original = health_module._start_time
        try:
            initialize_health_tracking()
            u1 = get_uptime_seconds()
            time.sleep(0.05)
            u2 = get_uptime_seconds()
            assert u2 > u1
        finally:
            health_module._start_time = original


# ---------------------------------------------------------------------------
# 5. check_source_health() — ConnectError/generic-exception paths
# ---------------------------------------------------------------------------

class TestCheckSourceHealthConnectError:
    """ConnectError from httpx must map to UNHEALTHY (not DEGRADED)."""

    @pytest.mark.asyncio
    async def test_connect_error_returns_unhealthy(self):
        import httpx
        from health import check_source_health, HealthStatus

        with patch("health.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            result = await check_source_health("PNCP")

        assert result.status == HealthStatus.UNHEALTHY
        assert "Connection error" in result.error

    @pytest.mark.asyncio
    async def test_generic_exception_returns_unhealthy(self):
        from health import check_source_health, HealthStatus

        with patch("health.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(
                side_effect=RuntimeError("unexpected")
            )
            result = await check_source_health("PNCP")

        assert result.status == HealthStatus.UNHEALTHY
        assert "Error" in result.error


# ---------------------------------------------------------------------------
# 6. get_health_status() integration
# ---------------------------------------------------------------------------

class TestGetHealthStatus:
    """Integration test for get_health_status() — mock the network layer."""

    @pytest.mark.asyncio
    async def test_returns_system_health_instance(self):
        from health import (
            get_health_status,
            SystemHealth,
            HealthStatus,
            SourceHealthResult,
        )

        healthy_sources = {
            "PNCP": SourceHealthResult(
                "PNCP", HealthStatus.HEALTHY, response_time_ms=30
            ),
        }

        with patch(
            "health.check_all_sources_health",
            new_callable=AsyncMock,
            return_value=healthy_sources,
        ):
            result = await get_health_status(include_sources=True)

        assert isinstance(result, SystemHealth)
        assert result.status == HealthStatus.HEALTHY
        assert "PNCP" in result.sources

    @pytest.mark.asyncio
    async def test_without_sources_returns_healthy(self):
        from health import get_health_status, HealthStatus

        result = await get_health_status(include_sources=False)
        assert result.status == HealthStatus.HEALTHY
        assert result.sources == {}

    @pytest.mark.asyncio
    async def test_degraded_source_propagates_to_overall_status(self):
        from health import get_health_status, HealthStatus, SourceHealthResult

        degraded_sources = {
            "PNCP": SourceHealthResult(
                "PNCP", HealthStatus.HEALTHY, response_time_ms=30
            ),
            "Portal": SourceHealthResult(
                "Portal", HealthStatus.UNHEALTHY, error="timeout"
            ),
        }

        with patch(
            "health.check_all_sources_health",
            new_callable=AsyncMock,
            return_value=degraded_sources,
        ):
            result = await get_health_status(include_sources=True)

        assert result.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_to_dict_has_required_keys(self):
        from health import get_health_status, HealthStatus, SourceHealthResult

        sources = {
            "PNCP": SourceHealthResult(
                "PNCP", HealthStatus.HEALTHY, response_time_ms=50
            ),
        }
        with patch(
            "health.check_all_sources_health",
            new_callable=AsyncMock,
            return_value=sources,
        ):
            result = await get_health_status(include_sources=True)

        d = result.to_dict()
        for key in ("status", "version", "timestamp", "sources"):
            assert key in d, f"Missing key in to_dict(): {key}"


# ---------------------------------------------------------------------------
# 7. get_system_health() — component checks
# ---------------------------------------------------------------------------

def _make_mock_cb(is_degraded=False):
    """Build a mock circuit breaker."""
    mock_cb = MagicMock()
    mock_cb.is_degraded = is_degraded
    mock_cb.try_recover = AsyncMock()
    return mock_cb


def _base_patches(redis_side_effect=None, redis_result=None):
    """Return common patch contexts for get_system_health tests."""
    if redis_side_effect:
        redis_patch = patch(
            "redis_pool.get_redis_pool",
            new_callable=AsyncMock,
            side_effect=redis_side_effect,
        )
    else:
        redis_patch = patch(
            "redis_pool.get_redis_pool",
            new_callable=AsyncMock,
            return_value=redis_result,
        )
    mock_sb = MagicMock()
    mock_resp = MagicMock()
    mock_resp.data = [{"id": "x"}]
    sb_patch = patch("supabase_client.get_supabase", return_value=mock_sb)
    sb_exec_patch = patch(
        "supabase_client.sb_execute",
        new_callable=AsyncMock,
        return_value=mock_resp,
    )
    worker_patch = patch(
        "job_queue.is_queue_available",
        new_callable=AsyncMock,
        return_value=True,
    )
    slo_patch = patch(
        "slo.get_slo_compliance_summary",
        return_value={"compliance": "ok"},
    )
    return redis_patch, sb_patch, sb_exec_patch, worker_patch, slo_patch


class TestGetSystemHealth:
    """get_system_health() aggregates Redis, Supabase, and circuit breaker."""

    @pytest.mark.asyncio
    async def test_healthy_when_all_up(self):
        from health import get_system_health

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_cb = _make_mock_cb(is_degraded=False)

        (
            redis_p, sb_p, sb_exec_p, worker_p, slo_p
        ) = _base_patches(redis_result=mock_redis)

        with (
            redis_p,
            sb_p,
            sb_exec_p,
            worker_p,
            slo_p,
            patch("pncp_client.get_circuit_breaker", return_value=mock_cb),
            patch(
                "health.check_openai_health",
                new_callable=AsyncMock,
                return_value={"status": "ok", "latency_ms": 42.0, "cached": False},
            ),
        ):
            result = await get_system_health()

        assert result["status"] == "healthy"
        assert result["components"]["redis"]["status"] == "up"
        assert result["components"]["supabase"]["status"] == "up"

    @pytest.mark.asyncio
    async def test_unhealthy_when_redis_down(self):
        from health import get_system_health

        mock_cb = _make_mock_cb(is_degraded=False)
        (
            redis_p, sb_p, sb_exec_p, worker_p, slo_p
        ) = _base_patches(redis_side_effect=ConnectionError("Redis down"))

        with (
            redis_p,
            sb_p,
            sb_exec_p,
            worker_p,
            slo_p,
            patch("pncp_client.get_circuit_breaker", return_value=mock_cb),
        ):
            result = await get_system_health()

        assert result["status"] == "unhealthy"
        assert result["components"]["redis"]["status"] == "down"

    @pytest.mark.asyncio
    async def test_response_has_required_top_level_keys(self):
        from health import get_system_health

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_cb = _make_mock_cb(is_degraded=False)

        (
            redis_p, sb_p, sb_exec_p, worker_p, slo_p
        ) = _base_patches(redis_result=mock_redis)

        with (
            redis_p,
            sb_p,
            sb_exec_p,
            worker_p,
            slo_p,
            patch("pncp_client.get_circuit_breaker", return_value=mock_cb),
            patch(
                "health.check_openai_health",
                new_callable=AsyncMock,
                return_value={"status": "ok", "latency_ms": 42.0, "cached": False},
            ),
        ):
            result = await get_system_health()

        for key in ("status", "components", "timestamp", "version"):
            assert key in result, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_degraded_when_source_circuit_open(self):
        from health import get_system_health

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_cb = _make_mock_cb(is_degraded=True)  # circuit open

        (
            redis_p, sb_p, sb_exec_p, worker_p, slo_p
        ) = _base_patches(redis_result=mock_redis)

        with (
            redis_p,
            sb_p,
            sb_exec_p,
            worker_p,
            slo_p,
            patch("pncp_client.get_circuit_breaker", return_value=mock_cb),
        ):
            result = await get_system_health()

        assert result["status"] == "degraded"
