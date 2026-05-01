"""MON-FN-005: Boot-time assertions for required production environment variables.

Fail-fast in production — any required env var missing raises RuntimeError
before FastAPI begins accepting traffic.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Extensible allow-list — add vars here as instrumentation hardens over time.
REQUIRED_ENV_VARS_PRODUCTION: dict[str, str] = {
    "MIXPANEL_TOKEN": "Funnel analytics token (Mixpanel project settings)",
    # "STRIPE_WEBHOOK_SECRET": "Webhook signature validation",
    # "RESEND_WEBHOOK_SECRET": "Resend webhook HMAC",
    # "SENTRY_DSN": "Error tracking",
    # "SUPABASE_SERVICE_ROLE_KEY": "Server-side DB access",
}

# Escape hatch — set to 'true' to bypass assertions without redeploying code.
# Audit: any bypass is logged at CRITICAL level.
_BYPASS_VAR = "BYPASS_REQUIRED_ENV_ASSERTIONS"


def assert_required_env_vars() -> None:
    """Boot assertion: fail if required env vars are missing in production.

    In non-production environments, logs a WARNING and returns silently so
    local dev / CI never break on missing vars.

    Raises:
        RuntimeError: if any required var is missing/empty in production.
    """
    env = os.getenv("ENVIRONMENT", "development").lower()

    if env != "production":
        logger.info("MON-FN-005: Env-var assertion skipped (ENVIRONMENT=%s)", env)
        return

    if os.getenv(_BYPASS_VAR, "").lower() in ("true", "1", "yes"):
        logger.critical(
            "MON-FN-005: BYPASS_REQUIRED_ENV_ASSERTIONS=true — "
            "skipping production env-var assertions. Audit this immediately."
        )
        return

    missing = [
        f"  - {name}: {desc}"
        for name, desc in REQUIRED_ENV_VARS_PRODUCTION.items()
        if not os.getenv(name, "").strip()
    ]

    if missing:
        msg = (
            "FATAL: Required environment variables missing in production:\n"
            + "\n".join(missing)
            + "\n\nFix: railway variables --service bidiq-backend set <VAR>=<value>"
        )
        logger.critical(msg)
        raise RuntimeError(msg)

    logger.info(
        "MON-FN-005: Env-var assertion passed (%d required vars present)",
        len(REQUIRED_ENV_VARS_PRODUCTION),
    )


def assert_mixpanel_reachable() -> None:
    """Boot assertion: force eager Mixpanel init and emit a smoke event.

    Only runs in production. Forces the normally-lazy _get_mixpanel() call
    so init failures surface at boot rather than silently at first track_event.

    Raises:
        RuntimeError: if Mixpanel client fails to initialize in production.
    """
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env != "production":
        return

    from analytics_events import _get_mixpanel

    mp = _get_mixpanel()
    if mp is None:
        raise RuntimeError(
            "MON-FN-005: Mixpanel client failed to initialize in production. "
            "Check MIXPANEL_TOKEN and that mixpanel-python is installed."
        )

    # Smoke event — fire-and-forget, does NOT block boot on network error.
    try:
        mp.track("system", "backend_boot", {
            "environment": env,
            "release": os.getenv("SENTRY_RELEASE", "unknown"),
        })
        logger.info("MON-FN-005: Mixpanel smoke event 'backend_boot' sent")
    except Exception as exc:
        logger.warning("MON-FN-005: Mixpanel smoke event failed (non-fatal): %s", exc)
