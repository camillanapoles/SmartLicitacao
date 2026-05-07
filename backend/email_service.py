"""
Transactional Email Service — STORY-225

Provides send_email() function with:
- Resend SDK integration
- Retry logic (3 retries, exponential backoff)
- Fire-and-forget async sending (never blocks caller)
- Structured logging

Usage:
    from email_service import send_email, EmailTemplate

    send_email(
        to="user@example.com",
        subject="Bem-vindo ao SmartLic!",
        html=render_welcome_template(name="João", plan="Consultor Ágil"),
        tags=[{"name": "category", "value": "welcome"}],
    )

Config:
    RESEND_API_KEY: Required. Set in .env / Railway.
    EMAIL_FROM: Optional. Defaults to "SmartLic <noreply@smartlic.tech>"
    EMAIL_ENABLED: Optional. Set to "false" to disable sending (dev mode).
"""

import logging
import os
import time
import threading
from html import escape
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "SmartLic <noreply@smartlic.tech>")
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() in ("true", "1", "yes", "on")
INTEL_REPORT_EMAIL_FROM = "SmartLic <tiago@smartlic.tech>"
INTEL_REPORT_REPLY_TO = "tiago.sasaki@gmail.com"

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds
MAX_DELAY = 10.0  # seconds


def _is_configured() -> bool:
    """Check if email service is properly configured."""
    if not EMAIL_ENABLED:
        return False
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — email sending disabled")
        return False
    return True


def send_email(
    to: str,
    subject: str,
    html: str,
    tags: Optional[list[dict[str, str]]] = None,
    reply_to: Optional[str] = None,
    headers: Optional[dict[str, str]] = None,
    from_email: Optional[str] = None,
) -> Optional[str]:
    """
    Send a transactional email via Resend.

    AC3: Core send function with retry logic.
    AC4: Max 3 retries with exponential backoff.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html: HTML body content.
        tags: Optional Resend tags for tracking.
        reply_to: Optional reply-to address.
        headers: Optional extra headers dict.
        from_email: Optional sender override (defaults to EMAIL_FROM env var).

    Returns:
        Email ID string on success, None on failure.
        Never raises — logs errors instead.
    """
    if not _is_configured():
        logger.debug(f"Email not sent (disabled/unconfigured): to={to}, subject={subject}")
        return None

    import resend
    resend.api_key = RESEND_API_KEY

    params: dict = {
        "from": from_email or EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if tags:
        params["tags"] = tags
    if reply_to:
        params["reply_to"] = reply_to
    if headers:
        params["headers"] = headers

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            result = resend.Emails.send(params)
            email_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
            logger.info(f"Email sent: to={to}, subject={subject}, id={email_id}")
            return email_id
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                logger.warning(
                    f"Email send failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"Email send failed after {MAX_RETRIES} attempts: to={to}, "
                    f"subject={subject}, error={last_error}"
                )

    return None


def send_batch_email(
    messages: list[dict],
    idempotency_key: str | None = None,
) -> list[dict] | None:
    """
    Send a batch of emails via Resend Batch API.

    STORY-278 AC4: Batch sending for daily digest.
    Max 100 emails per call (Resend limit).

    Args:
        messages: List of email dicts, each with keys: to, subject, html, tags (optional).
        idempotency_key: Optional key to prevent duplicate sends on retry.

    Returns:
        List of send results on success, None on failure.
        Never raises — logs errors instead.
    """
    if not _is_configured():
        logger.debug(f"Batch email not sent (disabled/unconfigured): count={len(messages)}")
        return None

    if not messages:
        return []

    import resend
    resend.api_key = RESEND_API_KEY

    # Build batch params
    batch_params = []
    for msg in messages:
        param: dict = {
            "from": EMAIL_FROM,
            "to": [msg["to"]] if isinstance(msg["to"], str) else msg["to"],
            "subject": msg["subject"],
            "html": msg["html"],
        }
        if msg.get("tags"):
            param["tags"] = msg["tags"]
        batch_params.append(param)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            headers = {}
            if idempotency_key:
                headers["Idempotency-Key"] = f"{idempotency_key}-{attempt}"
            result = resend.Batch.send(batch_params)
            result_list = result if isinstance(result, list) else [result]
            logger.info(f"Batch email sent: count={len(messages)}, results={len(result_list)}")
            return result_list
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                logger.warning(
                    f"Batch email send failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"Batch email send failed after {MAX_RETRIES} attempts: "
                    f"count={len(messages)}, error={last_error}"
                )

    return None


def send_email_async(
    to: str,
    subject: str,
    html: str,
    tags: Optional[list[dict[str, str]]] = None,
    reply_to: Optional[str] = None,
    headers: Optional[dict[str, str]] = None,
    from_email: Optional[str] = None,
) -> None:
    """
    Fire-and-forget email send in a background thread.

    AC22: Email send failure does not crash the triggering operation.
    Use this for non-critical emails (welcome, notifications) where
    we don't need to wait for the result.

    Args:
        Same as send_email().
    """
    def _send():
        try:
            send_email(
                to=to,
                subject=subject,
                html=html,
                tags=tags,
                reply_to=reply_to,
                headers=headers,
                from_email=from_email,
            )
        except Exception as e:
            # Belt-and-suspenders: send_email already catches, but just in case
            logger.error(f"Async email send unexpected error: {e}")

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()


# ---------------------------------------------------------------------------
# Founders email constants (personal tone — from Tiago directly)
# ---------------------------------------------------------------------------
FOUNDERS_EMAIL_FROM = "Tiago do SmartLic <tiago@smartlic.tech>"
FOUNDERS_EMAIL_REPLY_TO = "tiago.sasaki@gmail.com"


def send_founders_welcome_email(user_email: str, user_name: str) -> Optional[str]:
    """Send founders welcome email with idempotency gate via founding_leads.

    Checks founding_leads.welcome_sent_at before sending to prevent double-sends.
    On success, sets welcome_sent_at so subsequent calls are no-ops.

    Args:
        user_email: Recipient email address (matched against founding_leads.email).
        user_name: Display name for the personal greeting.

    Returns:
        Resend email ID string on success, None if not sent (already sent or error).
    """
    from templates.emails.founders_welcome import (
        render_founders_welcome_email,
        FOUNDERS_WELCOME_SUBJECT,
    )

    if not _is_configured():
        logger.debug(
            "Founders welcome email not sent (disabled/unconfigured): to=%s", user_email
        )
        return None

    # --- Idempotency check: skip if welcome_sent_at already set ---
    lead_id: Optional[str] = None
    try:
        from supabase_client import get_supabase

        db = get_supabase()
        result = (
            db.table("founding_leads")
            .select("id, welcome_sent_at")
            .eq("email", user_email)
            .eq("checkout_status", "completed")
            .limit(1)
            .execute()
        )
        rows = getattr(result, "data", None) or []
        if not rows:
            logger.warning(
                "send_founders_welcome_email: no completed founding_lead for email=%s — skipping",
                user_email,
            )
            return None
        row = rows[0]
        if row.get("welcome_sent_at"):
            logger.info(
                "send_founders_welcome_email: already sent (welcome_sent_at=%s) for email=%s",
                row["welcome_sent_at"],
                user_email,
            )
            return None
        lead_id = row.get("id")
    except Exception as exc:
        logger.error(
            "send_founders_welcome_email: idempotency DB check failed for email=%s: %s",
            user_email,
            exc,
        )
        return None

    # --- Send email ---
    html = render_founders_welcome_email(user_name=user_name)

    email_id = send_email(
        to=user_email,
        subject=FOUNDERS_WELCOME_SUBJECT,
        html=html,
        from_email=FOUNDERS_EMAIL_FROM,
        reply_to=FOUNDERS_EMAIL_REPLY_TO,
        tags=[{"name": "category", "value": "founders_welcome"}],
    )

    # --- Mark welcome as sent (idempotency record) ---
    if email_id and lead_id:
        try:
            from datetime import datetime, timezone

            db.table("founding_leads").update(
                {"welcome_sent_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", lead_id).execute()
        except Exception as exc:
            logger.error(
                "send_founders_welcome_email: failed to set welcome_sent_at for lead_id=%s: %s",
                lead_id,
                exc,
            )

    return email_id


def send_intel_report_ready(
    user_email: str,
    name: str,
    pdf_url: str,
    product_name: str,
    purchase_id: str,
) -> Optional[str]:
    """Send the Intel Report ready transactional email.

    This path waits for Resend's response so the ARQ job can report delivery
    failures in logs/tests without requiring a real email service.
    """
    from templates.emails.base import FRONTEND_URL, email_base

    template_path = Path(__file__).parent / "templates" / "emails" / "intel_report_ready.html"
    body_html = template_path.read_text(encoding="utf-8").format(
        name=escape(name or user_email.split("@")[0]),
        product_name=escape(product_name),
        pdf_url=escape(pdf_url, quote=True),
        trial_url=escape(
            f"{FRONTEND_URL}/signup?utm_source=intel_report&utm_medium=email"
            f"&purchase_id={purchase_id}",
            quote=True,
        ),
    )
    html = email_base(
        title="Seu Raio-X do Concorrente está pronto — SmartLic",
        body_html=body_html,
        is_transactional=True,
    )

    return send_email(
        to=user_email,
        subject="Seu Raio-X do Concorrente está pronto — SmartLic",
        html=html,
        reply_to=INTEL_REPORT_REPLY_TO,
        from_email=INTEL_REPORT_EMAIL_FROM,
        tags=[
            {"name": "category", "value": "intel_report"},
            {"name": "status", "value": "ready"},
            {"name": "purchase_id", "value": purchase_id[:32]},
        ],
    )
