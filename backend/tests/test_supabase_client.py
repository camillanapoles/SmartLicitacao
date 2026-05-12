"""Tests for supabase_client.py — circuit breaker, client management, sb_execute.

Wave 0 Safety Net: Covers SupabaseCircuitBreaker state transitions,
sliding window, cooldown, trial calls, _is_schema_error, sb_execute.
"""

import pytest
import time
import threading
import sys
import os
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from supabase_client import (
    SupabaseCircuitBreaker,
    CircuitBreakerOpenError,
    _is_schema_error,
)


# ──────────────────────────────────────────────────────────────────────
# SupabaseCircuitBreaker — State Transitions
# ──────────────────────────────────────────────────────────────────────

class TestCircuitBreakerStates:
    """Tests for CB state machine transitions."""

    @pytest.mark.timeout(30)
    def test_initial_state_closed(self):
        cb = SupabaseCircuitBreaker()
        assert cb.state == "CLOSED"

    @pytest.mark.timeout(30)
    def test_closed_to_open_on_failures(self):
        """50% failure rate in 10-window should open the CB."""
        cb = SupabaseCircuitBreaker(window_size=10, failure_rate_threshold=0.5)
        # Fill window with 10 failures
        for _ in range(10):
            cb._record_failure()
        assert cb.state == "OPEN"

    @pytest.mark.timeout(30)
    def test_mixed_results_below_threshold(self):
        """40% failure rate should not open CB (threshold=50%)."""
        cb = SupabaseCircuitBreaker(window_size=10, failure_rate_threshold=0.5)
        for _ in range(6):
            cb._record_success()
        for _ in range(4):
            cb._record_failure()
        assert cb.state == "CLOSED"

    @pytest.mark.timeout(30)
    def test_open_to_half_open_after_cooldown(self):
        """After cooldown expires, OPEN -> HALF_OPEN."""
        cb = SupabaseCircuitBreaker(
            window_size=4, failure_rate_threshold=0.5, cooldown_seconds=0.1
        )
        for _ in range(4):
            cb._record_failure()
        assert cb.state == "OPEN"
        time.sleep(0.15)
        assert cb.state == "HALF_OPEN"

    @pytest.mark.timeout(30)
    def test_half_open_to_closed_after_trial_successes(self):
        """3 trial successes in HALF_OPEN -> CLOSED."""
        cb = SupabaseCircuitBreaker(
            window_size=4, failure_rate_threshold=0.5,
            cooldown_seconds=0.05, trial_calls_max=3,
        )
        for _ in range(4):
            cb._record_failure()
        assert cb.state == "OPEN"
        time.sleep(0.1)
        assert cb.state == "HALF_OPEN"

        cb._record_success()
        cb._record_success()
        assert cb.state == "HALF_OPEN"  # Not yet
        cb._record_success()
        assert cb.state == "CLOSED"

    @pytest.mark.timeout(30)
    def test_half_open_to_open_on_failure(self):
        """A failure in HALF_OPEN -> OPEN."""
        cb = SupabaseCircuitBreaker(
            window_size=4, failure_rate_threshold=0.5,
            cooldown_seconds=0.05, trial_calls_max=3,
        )
        for _ in range(4):
            cb._record_failure()
        time.sleep(0.1)
        assert cb.state == "HALF_OPEN"
        cb._record_failure()
        assert cb.state == "OPEN"

    @pytest.mark.timeout(30)
    def test_reset(self):
        cb = SupabaseCircuitBreaker(window_size=4, failure_rate_threshold=0.5)
        for _ in range(4):
            cb._record_failure()
        assert cb.state == "OPEN"
        cb.reset()
        assert cb.state == "CLOSED"


# ──────────────────────────────────────────────────────────────────────
# SupabaseCircuitBreaker — call_sync
# ──────────────────────────────────────────────────────────────────────

class TestCircuitBreakerCallSync:
    """Tests for synchronous call execution with CB."""

    @pytest.mark.timeout(30)
    def test_call_sync_success(self):
        cb = SupabaseCircuitBreaker()
        result = cb.call_sync(lambda: 42)
        assert result == 42

    @pytest.mark.timeout(30)
    def test_call_sync_failure_recorded(self):
        cb = SupabaseCircuitBreaker()
        with pytest.raises(ValueError):
            cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("test")))

    @pytest.mark.timeout(30)
    def test_call_sync_open_raises(self):
        cb = SupabaseCircuitBreaker(window_size=2, failure_rate_threshold=0.5)
        for _ in range(2):
            cb._record_failure()
        with pytest.raises(CircuitBreakerOpenError):
            cb.call_sync(lambda: 42)


# ──────────────────────────────────────────────────────────────────────
# SupabaseCircuitBreaker — call_async
# ──────────────────────────────────────────────────────────────────────

class TestCircuitBreakerCallAsync:
    """Tests for async call execution with CB."""

    @pytest.mark.timeout(30)
    @pytest.mark.asyncio
    async def test_call_async_success(self):
        cb = SupabaseCircuitBreaker()

        async def ok():
            return 42

        result = await cb.call_async(ok())
        assert result == 42

    @pytest.mark.timeout(30)
    @pytest.mark.asyncio
    async def test_call_async_failure(self):
        cb = SupabaseCircuitBreaker()

        async def fail():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await cb.call_async(fail())

    @pytest.mark.timeout(30)
    @pytest.mark.asyncio
    async def test_call_async_open_raises(self):
        cb = SupabaseCircuitBreaker(window_size=2, failure_rate_threshold=0.5)
        for _ in range(2):
            cb._record_failure()

        async def ok():
            return 42

        with pytest.raises(CircuitBreakerOpenError):
            await cb.call_async(ok())


# ──────────────────────────────────────────────────────────────────────
# Sliding Window Behavior
# ──────────────────────────────────────────────────────────────────────

class TestSlidingWindow:
    """Tests for the sliding window failure counting."""

    @pytest.mark.timeout(30)
    def test_window_evicts_old_entries(self):
        """When window is full, oldest entry is evicted."""
        cb = SupabaseCircuitBreaker(window_size=4, failure_rate_threshold=0.5)
        # 4 failures -> open
        for _ in range(4):
            cb._record_failure()
        assert cb.state == "OPEN"

        # Reset and verify clean state
        cb.reset()
        # 3 successes + 1 failure = 25% failure rate in 4-window -> stays CLOSED
        for _ in range(3):
            cb._record_success()
        cb._record_failure()
        assert cb.state == "CLOSED"  # 1/4 = 25% < 50%

    @pytest.mark.timeout(30)
    def test_window_requires_full_before_opening(self):
        """CB needs a full window before calculating failure rate."""
        cb = SupabaseCircuitBreaker(window_size=10, failure_rate_threshold=0.5)
        for _ in range(5):
            cb._record_failure()
        # Only 5 entries in 10-window -> shouldn't open
        assert cb.state == "CLOSED"


# ──────────────────────────────────────────────────────────────────────
# Exclude Predicates (CRIT-040)
# ──────────────────────────────────────────────────────────────────────

class TestExcludePredicates:
    """Tests for exclude predicates preventing certain errors from counting."""

    @pytest.mark.timeout(30)
    def test_excluded_error_not_counted(self):
        def is_schema(e):
            return "schema" in str(e)

        cb = SupabaseCircuitBreaker(
            window_size=4, failure_rate_threshold=0.5,
            exclude_predicates=[is_schema],
        )
        for _ in range(10):
            cb._record_failure(Exception("schema error PGRST205"))
        # Excluded errors should not count -> CB stays closed
        assert cb.state == "CLOSED"

    @pytest.mark.timeout(30)
    def test_non_excluded_error_counted(self):
        def is_schema(e):
            return "schema" in str(e)

        cb = SupabaseCircuitBreaker(
            window_size=4, failure_rate_threshold=0.5,
            exclude_predicates=[is_schema],
        )
        for _ in range(4):
            cb._record_failure(Exception("connection timeout"))
        assert cb.state == "OPEN"


# ──────────────────────────────────────────────────────────────────────
# _is_schema_error
# ──────────────────────────────────────────────────────────────────────

class TestIsSchemaError:
    """Tests for schema error detection."""

    @pytest.mark.timeout(30)
    def test_pgrst205(self):
        assert _is_schema_error(Exception("PGRST205: relation not found")) is True

    @pytest.mark.timeout(30)
    def test_pgrst204(self):
        assert _is_schema_error(Exception("PGRST204: column not found")) is True

    @pytest.mark.timeout(30)
    def test_pg_42703(self):
        assert _is_schema_error(Exception("42703: undefined column")) is True

    @pytest.mark.timeout(30)
    def test_pg_42P01(self):
        assert _is_schema_error(Exception("42P01: undefined table")) is True

    @pytest.mark.timeout(30)
    def test_non_schema_error(self):
        assert _is_schema_error(Exception("connection refused")) is False

    @pytest.mark.timeout(30)
    def test_empty_message(self):
        assert _is_schema_error(Exception("")) is False


# ──────────────────────────────────────────────────────────────────────
# Thread Safety
# ──────────────────────────────────────────────────────────────────────

class TestThreadSafety:
    """Tests for concurrent access to the circuit breaker."""

    @pytest.mark.timeout(30)
    def test_concurrent_failures(self):
        cb = SupabaseCircuitBreaker(window_size=100, failure_rate_threshold=0.5)
        errors = []

        def record_many():
            try:
                for _ in range(50):
                    cb._record_failure()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        # Should be OPEN after 200 failures in a 100-window
        assert cb.state == "OPEN"

    @pytest.mark.timeout(30)
    def test_get_supabase_singleton_initialized_once_under_concurrency(self, monkeypatch):
        """Prove singleton + init-once invariants under thread contention.

        Fix (TEST-CI-002 TST-2): replaces the fragile ``sys.modules["supabase"]``
        replacement approach with ``mock.patch('supabase.create_client')`` which
        patches the attribute on the real module. Under extreme CI load with coverage
        instrumentation, the old approach could fail (~1/10k) when ``from supabase
        import create_client`` inside ``get_supabase()`` resolved to the real module
        instead of the test's fake module, or when the ``sys.modules`` entry was
        overwritten by coverage machinery.

        Invariants verified:
          1. create_client called exactly once (init-once)
          2. All 9 caller threads receive the same object (singleton)
          3. No thread errors under contention
          4. The module-level ``_supabase_client`` reference matches every result
        """
        import supabase_client

        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
        monkeypatch.setattr(supabase_client, "_supabase_client", None)
        monkeypatch.setattr(supabase_client, "_supabase_client_lock", threading.Lock())
        monkeypatch.setattr(supabase_client, "_configure_httpx_pool", lambda client: None)

        assert supabase_client._supabase_client is None, (
            f"Fixture pollution: _supabase_client should be None but is "
            f"{type(supabase_client._supabase_client).__name__}"
        )

        call_count = 0
        call_lock = threading.Lock()

        def create_client(url, key):
            nonlocal call_count
            with call_lock:
                call_count += 1
            time.sleep(0.05)
            return object()

        # Use mock.patch on the real supabase module's attribute instead of
        # replacing sys.modules["supabase"] — this is resilient to coverage
        # instrumentation re-importing modules during thread setup.
        with mock.patch("supabase.create_client", side_effect=create_client):
            results = []
            errors = []
            results_lock = threading.Lock()
            start_barrier = threading.Barrier(9)

            def get_client():
                try:
                    start_barrier.wait(timeout=10)
                    client = supabase_client.get_supabase()
                    with results_lock:
                        results.append(client)
                except Exception as exc:
                    with results_lock:
                        errors.append(exc)

            threads = [threading.Thread(target=get_client) for _ in range(9)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=15)

            assert all(not t.is_alive() for t in threads), "threads stuck"
            assert errors == [], f"unexpected errors: {errors}"
            assert len(results) == 9, f"expected 9 results, got {len(results)}"
            assert len({id(client) for client in results}) == 1, (
                "Singleton invariant broken: callers received different objects"
            )
            assert supabase_client._supabase_client is not None, (
                "Singleton was never created by any thread"
            )
            assert all(
                client is supabase_client._supabase_client for client in results
            ), "Not all results reference the module-level singleton"
            assert call_count == 1, (
                f"Expected create_client called once but got {call_count}"
            )
