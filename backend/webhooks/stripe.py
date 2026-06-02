"""
Stripe Webhook Dispatcher — Thin Router (DEBT-307 Decomposition)

Validates signature, checks idempotency, routes to handler modules.

Handler logic lives in webhooks/handlers/:
- checkout.py: checkout.session.completed, async_payment_succeeded/failed
- subscription.py: customer.subscription.updated/deleted
- invoice.py: invoice.payment_succeeded/failed, payment_action_required

CRITICAL FEATURES:
1. Signature validation (rejects unsigned/forged webhooks)
2. Idempotency (duplicate events ignored via DB check)
3. Timeout protection (SYS-024: 30s asyncio.wait_for)
4. Event logging (audit trail in stripe_webhook_events)
5. Stuck event recovery (>5min reprocessing)

BACKWARD COMPATIBILITY:
All handler functions are re-exported here so existing tests that patch
`webhooks.stripe._handle_*` or `webhooks.stripe.redis_cache` continue to work.
"""

import asyncio
import os
from datetime import datetime, timezone, timedelta

import stripe
from fastapi import APIRouter, Request, HTTPException

from supabase_client import get_supabase
from cache import redis_cache  # noqa: F401 — re-exported for test patches
from log_sanitizer import get_sanitized_logger
from quota import invalidate_plan_status_cache, clear_plan_capabilities_cache  # noqa: F401
from pipeline.budget import _run_with_budget

# Re-export handler functions for backward compatibility with test patches.
# Tests do: @patch('webhooks.stripe._handle_checkout_session_completed')
# This works because Python patches the NAME in THIS module's namespace.
from webhooks.handlers.checkout import (  # noqa: F401
    handle_checkout_session_completed as _handle_checkout_session_completed,
    handle_async_payment_succeeded as _handle_async_payment_succeeded,
    handle_async_payment_failed as _handle_async_payment_failed,
    handle_intel_report_payment_failed as _handle_intel_report_payment_failed,
    _send_async_payment_failed_email,
    _create_partner_referral_async,
    _create_post_purchase_sequence,
)
from webhooks.handlers.subscription import (  # noqa: F401
    handle_subscription_created as _handle_subscription_created,
    handle_subscription_updated as _handle_subscription_updated,
    handle_subscription_deleted as _handle_subscription_deleted,
    handle_subscription_trial_will_end as _handle_subscription_trial_will_end,
    _mark_partner_referral_churned,
    _send_cancellation_email,
)
from webhooks.handlers.invoice import (  # noqa: F401
    handle_invoice_payment_succeeded as _handle_invoice_payment_succeeded,
    handle_invoice_payment_failed as _handle_invoice_payment_failed,
    handle_payment_action_required as _handle_payment_action_required,
    _send_payment_confirmation_email,
    _send_payment_action_required_email,
    _send_payment_failed_email,
)
from webhooks.handlers._shared import resolve_user_id as _resolve_user_id  # noqa: F401
from webhooks.handlers.founding import (  # noqa: F401
    mark_founding_lead_abandoned as _handle_founding_checkout_expired_raw,
)
from webhooks.handlers.stripe_product_price import (  # noqa: F401
    handle_product_updated as _handle_product_updated,
    handle_price_created as _handle_price_created,
    handle_price_updated as _handle_price_updated,
    handle_price_deleted as _handle_price_deleted,
)

# REF-MON-002: eager import populates HANDLERS_REGISTRY via @webhook_handler
# decorators in webhooks.handlers._registry. The dispatcher uses this registry
# below in place of the legacy if-elif chain.
from webhooks.handlers import HANDLERS_REGISTRY  # noqa: F401

logger = get_sanitized_logger(__name__)
router = APIRouter()

# Stripe configuration
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# SYS-024: Timeout for webhook event processing (seconds)
WEBHOOK_DB_TIMEOUT_S = 30

# RES-BE: per-query budget for idempotency/status writes (fits within the 30s overall budget)
_WEBHOOK_IDEMPOTENCY_BUDGET_S = 5.0
_MAX_LOG_VALUE_LEN = 80

if not STRIPE_WEBHOOK_SECRET:
    logger.error(
        "STRIPE_WEBHOOK_SECRET not configured — webhook signature validation will fail. "
        "Set STRIPE_WEBHOOK_SECRET in .env (get from Stripe Dashboard > Developers > Webhooks > Signing secret)"
    )


def _safe_log_value(value) -> str:
    """Return a bounded, non-sensitive value for webhook logs."""
    if value is None:
        return "unknown"
    safe = "".join(ch for ch in str(value) if ch.isalnum() or ch in "._:-")
    if not safe:
        return "unknown"
    if len(safe) > _MAX_LOG_VALUE_LEN:
        return f"{safe[:_MAX_LOG_VALUE_LEN]}..."
    return safe


def _validate_event_envelope(event) -> None:
    """
    Validate the Stripe event fields used before any database operation.

    Stripe verifies authenticity in construct_event(), but tests and future
    SDK changes can still hand us malformed envelopes. Fail closed before
    idempotency writes so bad events are not persisted or routed.
    """
    event_id = getattr(event, "id", None)
    event_type = getattr(event, "type", None)
    data = getattr(event, "data", None)
    data_object = getattr(data, "object", None)

    if not isinstance(event_id, str) or not event_id.startswith("evt_"):
        raise ValueError("missing_or_invalid_event_id")
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("missing_or_invalid_event_type")
    if data is None or data_object is None:
        raise ValueError("missing_event_data_object")


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events with idempotency and signature validation.

    Security:
    - Verifies Stripe signature to prevent fake webhooks
    - Rejects unsigned/invalid requests with HTTP 400

    Idempotency:
    - Checks stripe_webhook_events table for duplicate event IDs
    - Returns "already_processed" for duplicate webhooks

    Processing:
    - Routes to handler in webhooks/handlers/ based on event.type
    - Wraps in asyncio.wait_for() with 30s timeout (SYS-024)
    - Marks event status in stripe_webhook_events for audit trail

    Args:
        request: FastAPI Request object with Stripe event payload

    Returns:
        dict: {"status": "success"} or {"status": "already_processed"}

    Raises:
        HTTPException 400: Invalid payload or signature verification failed
        HTTPException 500: Database error during processing
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        logger.warning("Webhook rejected: Missing stripe-signature header")
        raise HTTPException(status_code=400, detail="Assinatura de webhook inválida")

    # CRITICAL: Verify signature (prevents fake webhooks)
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.warning(
            "Stripe webhook rejected: invalid payload "
            f"reason={_safe_log_value(e.__class__.__name__)}"
        )
        raise HTTPException(status_code=400, detail="Dados de webhook inválidos")
    except stripe.error.SignatureVerificationError as e:
        logger.warning(
            "Stripe webhook rejected: signature verification failed "
            f"reason={_safe_log_value(e.__class__.__name__)}"
        )
        raise HTTPException(status_code=400, detail="Assinatura de webhook inválida")

    try:
        _validate_event_envelope(event)
    except ValueError as e:
        logger.warning(
            "Stripe webhook rejected: malformed event envelope "
            f"reason={_safe_log_value(e)}, "
            f"event_id={_safe_log_value(getattr(event, 'id', None))}, "
            f"type={_safe_log_value(getattr(event, 'type', None))}"
        )
        raise HTTPException(status_code=400, detail="Dados de webhook inválidos")

    logger.info(
        "Received Stripe webhook: "
        f"event_id={_safe_log_value(event.id)}, type={_safe_log_value(event.type)}"
    )

    sb = get_supabase()

    try:
        # STORY-307 AC1: Atomic idempotency — INSERT ON CONFLICT DO NOTHING
        now = datetime.now(timezone.utc)
        _event_id = event.id
        _event_type = event.type
        _now_iso = now.isoformat()

        def _sync_claim():
            return sb.table("stripe_webhook_events").upsert(
                {
                    "id": _event_id,
                    "type": _event_type,
                    "status": "processing",
                    "received_at": _now_iso,
                },
                on_conflict="id",
                ignore_duplicates=True,
            ).execute()

        claim_result = await _run_with_budget(
            asyncio.to_thread(_sync_claim),
            budget=_WEBHOOK_IDEMPOTENCY_BUDGET_S,
            phase="route",
            source="webhook.stripe.idempotency_claim",
        )

        # If upsert returned no data, the event already exists
        if not claim_result.data:
            # AC6: Check if event is stuck in 'processing' for >5 minutes
            def _sync_stuck_check():
                return (
                    sb.table("stripe_webhook_events")
                    .select("id, status, received_at")
                    .eq("id", _event_id)
                    .limit(1)
                    .execute()
                )

            stuck_check = await _run_with_budget(
                asyncio.to_thread(_sync_stuck_check),
                budget=_WEBHOOK_IDEMPOTENCY_BUDGET_S,
                phase="route",
                source="webhook.stripe.stuck_check",
            )
            if stuck_check.data:
                existing = stuck_check.data[0]
                if existing.get("status") == "processing" and existing.get("received_at"):
                    received_at = datetime.fromisoformat(
                        existing["received_at"].replace("Z", "+00:00")
                    )
                    if (now - received_at) > timedelta(minutes=5):
                        # AC7: Log WARNING and allow reprocessing
                        logger.warning(
                            "Stripe webhook stuck in processing for >5min — reprocessing: "
                            f"event_id={_safe_log_value(event.id)}"
                        )
                        await _run_with_budget(
                            asyncio.to_thread(lambda: sb.table("stripe_webhook_events").update({
                                "status": "processing",
                                "received_at": _now_iso,
                            }).eq("id", _event_id).execute()),
                            budget=_WEBHOOK_IDEMPOTENCY_BUDGET_S,
                            phase="route",
                            source="webhook.stripe.stuck_reset",
                        )
                    else:
                        logger.info(
                            f"Webhook already processing: event_id={_safe_log_value(event.id)}"
                        )
                        return {"status": "already_processed", "event_id": event.id}
                else:
                    logger.info(
                        f"Webhook already processed: event_id={_safe_log_value(event.id)}"
                    )
                    return {"status": "already_processed", "event_id": event.id}

        # SYS-024: Wrap event routing in asyncio.wait_for() to prevent DB hangs.
        #
        # REF-MON-002: Registry lookup replaces the legacy if-elif chain. The
        # adapter classes in webhooks/handlers/_registry.py delegate to the
        # same module-level _handle_* names re-exported above, so test patches
        # of the form @patch('webhooks.stripe._handle_*') continue to work.
        async def _process_event():
            """Route event to appropriate handler via HANDLERS_REGISTRY."""
            handler = HANDLERS_REGISTRY.get(event.type)
            if handler is None:
                logger.info(f"Unhandled event type: {event.type}")
                return
            # NOTE: invoke process() directly (not handle()) — the dispatcher
            # above has already claimed stripe_webhook_events for this
            # event.id, so calling handle() would double-claim and skip the
            # processing. handle() is for callers outside this dispatcher.
            await handler.process(sb, event)

        try:
            await asyncio.wait_for(_process_event(), timeout=WEBHOOK_DB_TIMEOUT_S)
        except asyncio.TimeoutError:
            logger.error(
                f"Webhook processing timed out after {WEBHOOK_DB_TIMEOUT_S}s: "
                f"event_id={_safe_log_value(event.id)}, type={_safe_log_value(event.type)}"
            )
            try:
                _timeout_at = datetime.now(timezone.utc).isoformat()
                _timeout_msg = f"Processing timed out after {WEBHOOK_DB_TIMEOUT_S}s"
                await _run_with_budget(
                    asyncio.to_thread(lambda: sb.table("stripe_webhook_events").update({
                        "status": "timeout",
                        "processed_at": _timeout_at,
                        "payload": {"error": _timeout_msg},
                    }).eq("id", _event_id).execute()),
                    budget=_WEBHOOK_IDEMPOTENCY_BUDGET_S,
                    phase="route",
                    source="webhook.stripe.mark_timeout",
                )
            except Exception:
                pass
            raise HTTPException(status_code=504, detail="Webhook processing timed out")

        # AC2: Mark event as completed after successful processing
        _completed_at = datetime.now(timezone.utc).isoformat()
        _event_payload = event.data.object
        await _run_with_budget(
            asyncio.to_thread(lambda: sb.table("stripe_webhook_events").update({
                "status": "completed",
                "processed_at": _completed_at,
                "payload": _event_payload,
            }).eq("id", _event_id).execute()),
            budget=_WEBHOOK_IDEMPOTENCY_BUDGET_S,
            phase="route",
            source="webhook.stripe.mark_completed",
        )

        logger.info(
            f"Webhook processed successfully: event_id={_safe_log_value(event.id)}"
        )
        return {"status": "success", "event_id": event.id}

    except HTTPException:
        raise
    except Exception as e:
        # AC3: Mark event as failed on processing error
        try:
            _failed_at = datetime.now(timezone.utc).isoformat()
            _err_str = str(e)
            await _run_with_budget(
                asyncio.to_thread(lambda: sb.table("stripe_webhook_events").update({
                    "status": "failed",
                    "processed_at": _failed_at,
                    "payload": {"error": _err_str},
                }).eq("id", _event_id).execute()),
                budget=_WEBHOOK_IDEMPOTENCY_BUDGET_S,
                phase="route",
                source="webhook.stripe.mark_failed",
            )
        except Exception as update_err:
            logger.error(f"Failed to mark webhook as failed: {update_err}")
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")
