"""jobs.cron.send_lead_magnet — Lead magnet PDF delivery pipeline.

STORY-1169: Generates datalake-powered PDF and emails it to captured leads.

Two jobs:
  - send_lead_magnet_job: Immediate delivery for a single lead (enqueued after
    lead capture). Generated on-demand with personalized sector/UF data.
  - send_lead_magnet_batch_job: Catch-up batch that processes pending leads
    (email_sent_at IS NULL, email_status = 'pending'). Runs every 5 min.
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

LEAD_MAGNET_BATCH_INTERVAL_S = 300   # 5 min
LEAD_MAGNET_BATCH_MAX = 50           # Max leads per batch
LEAD_MAGNET_QUOTA_DAILY_MAX = 80     # Leave 20 for trial/transactional emails

# Redis rate-limit key
_QUOTA_KEY = "lead_magnet:daily_sent"
_QUOTA_TTL = 86400  # 24h


async def _check_daily_quota(redis) -> bool:
    """Check if we're under the daily Resend quota limit. Returns True if OK."""
    try:
        used = await redis.get(_QUOTA_KEY)
        used_int = int(used) if used else 0
        return used_int < LEAD_MAGNET_QUOTA_DAILY_MAX
    except Exception:
        return True  # Fail-open: if Redis is down, try anyway


async def _increment_quota(redis) -> None:
    """Increment daily sent counter."""
    try:
        await redis.incr(_QUOTA_KEY)
        await redis.expire(_QUOTA_KEY, _QUOTA_TTL)
    except Exception:
        pass


async def send_lead_magnet_job(ctx, email: str, setor: str | None = None,
                                uf: str | None = None) -> dict:
    """Immediate delivery job — enqueued right after lead capture.

    Generates a personalized PDF with datalake insights and emails it
    as an attachment. Updates the leads table on success/failure.
    """
    from email_service import send_email, EMAIL_ENABLED
    from templates.emails.lead_magnet_delivery import render_lead_magnet_email
    from services.lead_magnet_pdf import generate_lead_magnet_pdf
    from supabase_client import get_supabase
    from sectors import SECTORS

    if not EMAIL_ENABLED:
        logger.info(f"lead_magnet: email disabled, skipping {email}")
        return {"status": "disabled", "email": email}

    sb = get_supabase()
    result = {"status": "pending", "email": email}

    try:
        # Generate PDF
        pdf_bytes = await generate_lead_magnet_pdf(email, setor=setor, uf=uf)

        # Render email
        sector_name = None
        if setor:
            sector_cfg = SECTORS.get(setor, {})
            sector_name = sector_cfg.get("name", setor)

        subject, html = render_lead_magnet_email(setor=setor, sector_name=sector_name)

        # Send email with PDF attachment
        email_id = send_email(
            to=email,
            subject=subject,
            html=html,
            attachments=[{
                "filename": "guia-oportunidades-b2g-smartlic.pdf",
                "content": pdf_bytes,
                "content_type": "application/pdf",
            }],
            tags=[{"name": "category", "value": "lead_magnet"}],
        )

        if email_id:
            # Mark as sent
            def _mark_sent():
                return sb.table("leads").update({
                    "email_sent_at": datetime.now(timezone.utc).isoformat(),
                    "email_message_id": email_id,
                    "email_status": "sent",
                }).eq("email", email).is_("email_sent_at", "null").execute()

            await asyncio.to_thread(_mark_sent)
            result = {"status": "sent", "email": email, "message_id": email_id}
            logger.info(f"lead_magnet: sent to {email} (id={email_id})")
        else:
            # Email failed after retries
            def _mark_failed():
                return sb.table("leads").update({
                    "email_status": "failed",
                }).eq("email", email).is_("email_sent_at", "null").execute()

            await asyncio.to_thread(_mark_failed)
            result = {"status": "failed", "email": email}
            logger.warning(f"lead_magnet: send failed for {email}")

    except Exception:
        logger.exception(f"lead_magnet: unexpected error for {email}")
        try:
            def _mark_error():
                return sb.table("leads").update({
                    "email_status": "failed",
                }).eq("email", email).is_("email_sent_at", "null").execute()
            await asyncio.to_thread(_mark_error)
        except Exception:
            pass
        result = {"status": "error", "email": email}

    return result


async def send_lead_magnet_batch_job(ctx) -> dict:
    """Catch-up batch: process pending leads (runs every 5 min).

    Processes up to LEAD_MAGNET_BATCH_MAX leads with email_sent_at IS NULL
    and email_status = 'pending'. Ordered by captured_at (oldest first).
    """
    from email_service import EMAIL_ENABLED
    from supabase_client import get_supabase, sb_execute
    from redis_pool import get_redis_pool

    if not EMAIL_ENABLED:
        return {"status": "disabled", "processed": 0}

    redis = await get_redis_pool()
    if not await _check_daily_quota(redis):
        logger.warning("lead_magnet: daily quota exhausted, skipping batch")
        return {"status": "quota_exceeded", "processed": 0}

    sb = get_supabase()

    try:
        resp = await sb_execute(
            sb.table("leads")
            .select("email, setor, uf")
            .is_("email_sent_at", "null")
            .eq("email_status", "pending")
            .order("captured_at")
            .limit(LEAD_MAGNET_BATCH_MAX),
        )
        pending = resp.data or []
    except Exception:
        logger.exception("lead_magnet: failed to fetch pending leads")
        return {"status": "error", "processed": 0}

    if not pending:
        return {"status": "ok", "processed": 0}

    processed = 0
    for lead in pending:
        if not await _check_daily_quota(redis):
            logger.warning(f"lead_magnet: quota hit after {processed}/{len(pending)}")
            break

        email = lead.get("email")
        if not email:
            continue

        job_result = await send_lead_magnet_job(
            ctx,
            email=email,
            setor=lead.get("setor"),
            uf=lead.get("uf"),
        )
        if job_result.get("status") == "sent":
            await _increment_quota(redis)
            processed += 1

    logger.info(f"lead_magnet: batch processed {processed}/{len(pending)} pending leads")
    return {"status": "ok", "processed": processed, "total_pending": len(pending)}


async def start_lead_magnet_batch_task() -> asyncio.Task:
    """Start the periodic lead magnet batch delivery loop."""
    async def _loop():
        # Spread first run jitter to avoid thundering herd
        import random
        initial_jitter = random.uniform(30, 120)
        logger.info(f"lead_magnet: batch loop starting in {initial_jitter:.0f}s")
        await asyncio.sleep(initial_jitter)

        while True:
            try:
                from job_queue import get_arq_pool
                pool = get_arq_pool()
                if pool:
                    await pool.enqueue_job("send_lead_magnet_batch_job")
            except Exception:
                logger.warning("lead_magnet: batch enqueue failed", exc_info=True)
            await asyncio.sleep(LEAD_MAGNET_BATCH_INTERVAL_S)

    return asyncio.create_task(_loop())
