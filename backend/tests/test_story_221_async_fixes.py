"""
STORY-221: Async Blocking Issues - Test Suite

Tests covering:
- AC15: _check_user_roles uses asyncio.sleep (not time.sleep)
- AC16: Stripe webhook uses per-request client (no global stripe.api_key)
- AC17: validate_env_vars raises RuntimeError in production for missing vars
- Bonus: No asyncio.run() in production code
- Bonus: Lifespan context manager validation

All tests ensure proper async/await patterns and environment validation.
"""

import asyncio
import inspect
import os
import pathlib
from unittest.mock import AsyncMock, patch

import pytest


# =============================================================================
# AC15: _check_user_roles uses asyncio.sleep, not time.sleep
# =============================================================================


@pytest.mark.asyncio
async def test_check_user_roles_is_async():
    """AC15: _check_user_roles must be an async function."""
    from authorization import _check_user_roles

    assert asyncio.iscoroutinefunction(
        _check_user_roles
    ), "_check_user_roles must be async"


def test_check_user_roles_no_time_sleep_import():
    """AC15: authorization.py must not import or use time.sleep."""
    import authorization

    source = inspect.getsource(authorization)

    # Check no time.sleep calls
    assert (
        "time.sleep" not in source
    ), "authorization.py should not contain time.sleep"

    # Check no time module import
    assert "import time" not in source, "authorization.py should not import time"


@pytest.mark.asyncio
async def test_check_user_roles_uses_asyncio_sleep_on_retry():
    """AC15: _check_user_roles uses asyncio.sleep for retry delays.

    BTS-012 (#971 AC5) RCA — TWO compounding bugs in the original test:

    1) **Mock side_effect exhaustion** — the retry path runs
       ``2 attempts × 2 fallback queries`` (the ``is_admin`` column fallback
       at authorization.py:78-85). Providing only 2 side_effects exhausts the
       iterator mid-retry, raising ``StopIteration`` inside
       ``asyncio.to_thread``, which asyncio cannot propagate into a Future
       ("StopIteration interacts badly with generators"). Fix: 4 exceptions.

    2) **Read circuit-breaker pollution from sibling tests** — ``read_cb`` is
       a module-level singleton in ``supabase_client``. Earlier tests in the
       suite (e.g. retry / pool-exhaustion suites) leave a non-zero
       ``_consecutive_failures`` streak. This test then adds 4 more failures,
       crossing the streak threshold (``_CB_READ_STREAK``) and tripping the
       breaker mid-flight. ``sb_execute`` then raises
       ``CircuitBreakerOpenError``, which ``_check_user_roles`` short-circuits
       at line 103-109 → returns ``(False, False)`` **without** reaching
       ``await asyncio.sleep(0.3)`` → assertion fails with
       "Expected 'sleep' to be called once. Called 0 times."

       ``read_cb.reset()`` does NOT zero ``_consecutive_failures`` (only
       state/window/trial counters). We force-clear it here defensively so
       the test is robust against polluters. A separate story will fix
       ``SupabaseCircuitBreaker.reset()`` itself to also clear the streak.
    """
    # Defensive isolation against sibling-test CB pollution (see RCA #2).
    from supabase_client import read_cb
    read_cb.reset()
    read_cb._consecutive_failures = 0  # reset() does not clear this — see RCA

    with patch("supabase_client.get_supabase") as mock_sb:
        # Force retry path: 2 attempts x 2 fallback queries each = 4 failures
        mock_sb.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.side_effect = [
            Exception("attempt 0 / is_admin path"),
            Exception("attempt 0 / plan_type fallback"),
            Exception("attempt 1 / is_admin path"),
            Exception("attempt 1 / plan_type fallback"),
        ]

        with patch("authorization.asyncio.sleep", new_callable=AsyncMock) as mock_async_sleep:
            from authorization import _check_user_roles

            result = await _check_user_roles("user-123")

            # asyncio.sleep should have been called once (0.3s retry delay
            # between attempt 0 and attempt 1).
            mock_async_sleep.assert_called_once_with(0.3)

            # Result should be (False, False) after exhausting retries
            assert result == (False, False)


# =============================================================================
# AC16: Stripe webhook uses per-request client, not global stripe.api_key
# =============================================================================


def test_stripe_webhook_no_global_api_key():
    """AC16: webhooks/stripe.py must not set stripe.api_key globally."""
    import webhooks.stripe as stripe_webhook

    source = inspect.getsource(stripe_webhook)
    lines = source.split("\n")

    for line in lines:
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("#"):
            continue
        # Check for global stripe.api_key assignment
        assert (
            "stripe.api_key =" not in stripped
        ), f"Found global stripe.api_key assignment: {line}"


def test_billing_uses_per_request_api_key():
    """AC16: services/billing.py must pass api_key= to Stripe calls."""
    import services.billing as billing

    source = inspect.getsource(billing.update_stripe_subscription_billing_period)

    # Must pass api_key parameter to Stripe API calls
    assert (
        "api_key=stripe_key" in source or "api_key=" in source
    ), "Must pass api_key= to Stripe API calls"

    # Must NOT set global stripe.api_key
    assert "stripe.api_key = " not in source, "Must not set global stripe.api_key"


# =============================================================================
# AC17: validate_env_vars raises RuntimeError in production for missing vars
# =============================================================================


def test_validate_env_vars_raises_in_production_without_required():
    """AC17: Missing critical env vars in production raises RuntimeError."""
    # Clear environment and set to production
    env_backup = {
        "SUPABASE_URL": os.environ.get("SUPABASE_URL"),
        "SUPABASE_SERVICE_ROLE_KEY": os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
        "SUPABASE_JWT_SECRET": os.environ.get("SUPABASE_JWT_SECRET"),
    }

    try:
        # Set production environment
        os.environ["ENVIRONMENT"] = "production"

        # Remove critical env vars
        for key in ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"]:
            os.environ.pop(key, None)

        # Re-import config to trigger validation
        import importlib

        import config

        importlib.reload(config)

        # Should raise RuntimeError with FATAL message
        with pytest.raises(RuntimeError, match="FATAL"):
            config.validate_env_vars()

    finally:
        # Restore environment
        for key, value in env_backup.items():
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)


def test_validate_env_vars_warns_in_dev_without_required():
    """AC17: Missing critical env vars in dev only warns, does not raise."""
    # Clear environment and set to development
    env_backup = {
        "ENVIRONMENT": os.environ.get("ENVIRONMENT"),
        "SUPABASE_URL": os.environ.get("SUPABASE_URL"),
        "SUPABASE_SERVICE_ROLE_KEY": os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
        "SUPABASE_JWT_SECRET": os.environ.get("SUPABASE_JWT_SECRET"),
    }

    try:
        # Set development environment
        os.environ["ENVIRONMENT"] = "development"

        # Remove critical env vars
        for key in ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"]:
            os.environ.pop(key, None)

        # Re-import config
        import importlib

        import config

        importlib.reload(config)

        # Should NOT raise - just warn
        config.validate_env_vars()  # No exception expected

    finally:
        # Restore environment
        for key, value in env_backup.items():
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)


# =============================================================================
# Bonus: No asyncio.run() in production code (AC4/AC5)
# =============================================================================


def test_no_asyncio_run_in_production_code():
    """Ensure no asyncio.run() calls in production code.

    STORY-CIG-BE-asyncio-run-production-scan Phase 1: use AST-based detection
    (ignores docstrings/comments/strings automatically) and skip (a) files
    under backend/scripts/ (CLI tools) and (b) AST nodes inside
    ``if __name__ == "__main__":`` blocks (module-level CLI entry points).
    """
    import ast as _ast

    backend_dir = pathlib.Path(__file__).parent.parent
    violations = []

    def _is_asyncio_run_call(node):
        if not isinstance(node, _ast.Call):
            return False
        func = node.func
        if isinstance(func, _ast.Attribute) and func.attr == "run":
            value = func.value
            if isinstance(value, _ast.Name) and value.id in {"asyncio", "_asyncio"}:
                return True
        return False

    def _is_main_guard(node):
        if not isinstance(node, _ast.If):
            return False
        test = node.test
        if not isinstance(test, _ast.Compare):
            return False
        left = test.left
        if not (isinstance(left, _ast.Name) and left.id == "__name__"):
            return False
        for comp in test.comparators:
            value = getattr(comp, "value", None)
            if value == "__main__":
                return True
        return False

    for py_file in backend_dir.glob("**/*.py"):
        if "tests" in py_file.parts or py_file.name.startswith("test_"):
            continue
        if "__pycache__" in str(py_file) or "venv" in str(py_file):
            continue

        # Phase 1 (a): CLI scripts are legitimate asyncio.run() hosts.
        relative = py_file.relative_to(backend_dir)
        if relative.parts and relative.parts[0] == "scripts":
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = _ast.parse(content, filename=str(py_file))
        except (OSError, SyntaxError):
            continue

        # Phase 1 (b): collect line ranges of ``if __name__ == "__main__":`` blocks.
        main_ranges = []
        for node in _ast.walk(tree):
            if _is_main_guard(node):
                end_line = getattr(node, "end_lineno", node.lineno)
                main_ranges.append((node.lineno, end_line))

        def _in_main_block(lineno, ranges=main_ranges):
            return any(start <= lineno <= end for start, end in ranges)

        for node in _ast.walk(tree):
            if _is_asyncio_run_call(node) and not _in_main_block(node.lineno):
                violations.append(f"{py_file.name}:{node.lineno}: asyncio.run(...)")

    assert not violations, (
        "Found asyncio.run() in production code:\n" + "\n".join(violations)
    )


# =============================================================================
# Bonus: Lifespan context manager validation (AC9)
# =============================================================================


def test_app_uses_lifespan():
    """AC9: FastAPI app must use lifespan context manager."""
    from main import app

    assert (
        app.router.lifespan_context is not None
    ), "App must use lifespan context manager"


# =============================================================================
# Integration test: Full async flow validation
# =============================================================================


@pytest.mark.asyncio
async def test_async_flow_integration():
    """Integration test: Validate async patterns work end-to-end."""
    with patch("supabase_client.get_supabase") as mock_sb:
        # Mock successful response
        mock_sb.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "is_admin": False,
            "plan_type": "free_trial",
        }

        from authorization import _check_user_roles

        # Should complete without blocking
        result = await _check_user_roles("user-123")

        # Verify it's actually async and returns expected result
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result == (False, False)
