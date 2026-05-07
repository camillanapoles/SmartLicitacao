"""ARQ cron: auto-disable founding offer 1 day after deadline."""
import logging
from datetime import datetime, timezone

import sentry_sdk

logger = logging.getLogger(__name__)


async def founders_auto_disable_check(ctx: dict) -> None:
    """Disable founding offer 1 day after deadline_at to handle timezone edge cases."""
    from supabase_client import get_supabase

    sb = get_supabase()

    try:
        result = sb.table("founding_policy").select("deadline_at, active").eq("id", 1).single().execute()
        if not result.data:
            return

        policy = result.data
        if not policy.get("active", False):
            return  # Already disabled

        deadline_at = policy.get("deadline_at")
        if not deadline_at:
            return

        # Parse deadline (string or datetime)
        if isinstance(deadline_at, str):
            from dateutil import parser as dtparser
            deadline_dt = dtparser.parse(deadline_at)
        else:
            deadline_dt = deadline_at

        # Add 1 day margin for timezone edge cases
        from datetime import timedelta
        cutoff = deadline_dt + timedelta(days=1)

        now_utc = datetime.now(timezone.utc)
        cutoff_aware = cutoff.replace(tzinfo=timezone.utc) if cutoff.tzinfo is None else cutoff

        if now_utc > cutoff_aware:
            logger.warning("founders_auto_disable: deadline passed, disabling offer")
            sb.table("founding_policy").update({
                "active": False,
                "paused_reason": "auto_disabled: deadline passed"
            }).eq("id", 1).execute()

            sentry_sdk.capture_message(
                "founders_auto_disabled: offer auto-disabled after deadline",
                level="warning",
                extras={"deadline_at": str(deadline_at)},
            )
            logger.info("founders_auto_disable: offer disabled successfully")

    except Exception as e:
        logger.error(f"founders_auto_disable_check failed: {e}", exc_info=True)
