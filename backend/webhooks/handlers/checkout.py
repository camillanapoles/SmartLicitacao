"""
Checkout session webhook handlers.

Events:
- checkout.session.completed
- checkout.session.async_payment_succeeded (Boleto/PIX — STORY-280)
- checkout.session.async_payment_failed (Boleto/PIX — STORY-280)
- payment_intent.payment_failed (Intel Report one-time payment failure — #630)
"""

import asyncio

import stripe
from datetime import datetime, timezone, timedelta

from log_sanitizer import get_sanitized_logger
from pipeline.budget import _run_with_budget
from webhooks.handlers._shared import resolve_user_id, invalidate_user_caches

# RES-BE: per-query budget (fits within the 30s overall webhook timeout)
_WEBHOOK_QUERY_BUDGET_S = 5.0

logger = get_sanitized_logger(__name__)


# ============================================================================
# Intel Report one-time payment handlers (#630)
# ============================================================================

async def handle_intel_report_checkout_completed(sb, session_data: dict) -> None:
    """Handle checkout.session.completed for Intel Report one-time payments (#630).

    Idempotency is guaranteed at the dispatcher level (stripe_webhook_events table),
    so this handler does NOT implement its own dedup — the dispatcher will call this
    at most once per event_id.

    Inserts a row in intel_report_purchases with status='pending' and enqueues
    the generate_intel_report ARQ job (issue #631).
    """
    metadata = session_data.get("metadata") or {}
    product_type = metadata.get("product_type")
    entity_key = metadata.get("entity_key")
    user_id = metadata.get("user_id")
    payment_intent = session_data.get("payment_intent")
    session_id = session_data.get("id")

    if not user_id or not product_type or not entity_key:
        logger.warning(
            f"Intel Report checkout missing required metadata: "
            f"user_id={user_id}, product_type={product_type}, entity_key={entity_key}"
        )
        return

    logger.info(
        f"Intel Report checkout completed: user_id={user_id[:8]}, "
        f"product_type={product_type}, entity_key={entity_key!r}, "
        f"session_id={session_id}"
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    purchase_row = {
        "user_id": user_id,
        "product_type": product_type,
        "entity_key": entity_key,
        "status": "pending",
        "stripe_checkout_session_id": session_id,
        "stripe_payment_intent_id": payment_intent,
        "created_at": now_iso,
    }

    insert_result = await _run_with_budget(
        asyncio.to_thread(lambda: sb.table("intel_report_purchases").insert(purchase_row).execute()),
        budget=_WEBHOOK_QUERY_BUDGET_S,
        phase="route",
        source="webhook.intel_report.insert_purchase",
    )

    purchase_id = None
    if insert_result.data:
        purchase_id = insert_result.data[0].get("id")
        logger.info(f"Intel Report purchase created: purchase_id={purchase_id}")

    # Enqueue generation job (issue #631 implements the actual job)
    # Best-effort: if ARQ is unavailable the purchase row is still persisted.
    if purchase_id:
        try:
            from job_queue import get_arq_pool
            pool = await get_arq_pool()
            if pool:
                await pool.enqueue_job("generate_intel_report", purchase_id)
                logger.info(f"generate_intel_report job enqueued for purchase_id={purchase_id}")
        except Exception as arq_err:
            logger.warning(
                f"Could not enqueue generate_intel_report (non-fatal, will retry on webhook replay): {arq_err}"
            )

        # CONV-011b-1: Create post-purchase sequence if product_sku is present in metadata
        product_sku = metadata.get("product_sku")
        if product_sku:
            await _create_post_purchase_sequence(sb, purchase_id, product_sku, user_id)


async def handle_intel_report_async_payment_succeeded(sb, session_data: dict) -> None:
    """Handle checkout.session.async_payment_succeeded for Intel Report (Boleto/PIX — #630).

    Same logic as handle_intel_report_checkout_completed: inserts purchase and
    enqueues generation. This event fires when an async payment method (boleto/pix)
    is confirmed after the checkout session was created.
    """
    # Reuse the same logic as the synchronous path
    await handle_intel_report_checkout_completed(sb, session_data)


async def handle_intel_report_payment_failed(sb, event: stripe.Event) -> None:
    """Handle payment_intent.payment_failed for Intel Report purchases (#630).

    Updates the purchase status to 'failed' for the matching payment_intent.
    The PaymentIntent object does not have session metadata, so we look up the
    purchase row by stripe_payment_intent_id.
    """
    payment_intent_obj = event.data.object
    payment_intent_id = getattr(payment_intent_obj, "id", None) or (
        payment_intent_obj.get("id") if hasattr(payment_intent_obj, "get") else None
    )

    if not payment_intent_id:
        logger.warning("payment_intent.payment_failed: missing payment_intent id")
        return

    logger.warning(f"Intel Report payment failed: payment_intent_id={payment_intent_id}")

    await _run_with_budget(
        asyncio.to_thread(lambda: sb.table("intel_report_purchases").update({
            "status": "failed",
        }).eq("stripe_payment_intent_id", payment_intent_id).eq("status", "pending").execute()),
        budget=_WEBHOOK_QUERY_BUDGET_S,
        phase="route",
        source="webhook.intel_report.mark_failed",
    )


async def handle_checkout_session_completed(sb, event: stripe.Event) -> None:
    """
    Handle checkout.session.completed event.

    STORY-280 AC2: For async payment methods (Boleto/PIX), payment_status is "unpaid"
    at checkout completion. We must NOT activate — wait for async_payment_succeeded.

    For card payments (synchronous), payment_status is "paid" — activate immediately.

    #630: Intel Report one-time payments (mode=payment + metadata.product_type) are
    dispatched to handle_intel_report_checkout_completed BEFORE the subscription checks.
    """
    session_data = event.data.object
    metadata = session_data.get("metadata") or {}

    # #630: Intel Report one-time payment — dispatch before subscription logic
    if session_data.get("mode") == "payment" and metadata.get("product_type"):
        await handle_intel_report_checkout_completed(sb, session_data)
        return

    # FOUND-CRIT-006: founding mode=payment one-time checkout — routed entirely
    # through mark_founding_lead_completed (which handles entitlement + invite).
    # These sessions have no plan_id/subscription in metadata, so they must be
    # dispatched early and returned before the subscription-activation path.
    if session_data.get("mode") == "payment" and metadata.get("source") == "founding":
        logger.info(
            "checkout.session.completed: founding mode=payment — "
            "routing to mark_founding_lead_completed"
        )
        try:
            from webhooks.handlers.founding import mark_founding_lead_completed
            mark_founding_lead_completed(sb, session_data)
        except Exception as e:
            logger.error(f"founding mode=payment handler failed (non-fatal): {e}")
        return

    # CONV-011b-1: Digital product one-time payment (mode=payment + product_sku in metadata)
    if session_data.get("mode") == "payment" and metadata.get("product_sku"):
        product_sku = metadata["product_sku"]
        digital_user_id = metadata.get("user_id")
        if not digital_user_id:
            logger.warning(
                f"Digital product checkout missing user_id in metadata: product_sku={product_sku}"
            )
            return

        logger.info(
            f"Digital product checkout completed: user_id={digital_user_id[:8]}, "
            f"product_sku={product_sku}, session_id={session_data.get('id')}"
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        purchase_row = {
            "user_id": digital_user_id,
            "product_type": "digital_product",
            "entity_key": product_sku,
            "status": "completed",
            "stripe_checkout_session_id": session_data.get("id"),
            "stripe_payment_intent_id": session_data.get("payment_intent"),
            "created_at": now_iso,
        }

        insert_result = await _run_with_budget(
            asyncio.to_thread(lambda: sb.table("intel_report_purchases").insert(purchase_row).execute()),
            budget=_WEBHOOK_QUERY_BUDGET_S,
            phase="route",
            source="webhook.digital_product.insert_purchase",
        )

        digital_purchase_id = None
        if insert_result.data:
            digital_purchase_id = insert_result.data[0].get("id")
            logger.info(f"Digital product purchase created: purchase_id={digital_purchase_id}")

        if digital_purchase_id:
            await _create_post_purchase_sequence(sb, digital_purchase_id, product_sku, digital_user_id)

        return

    user_id = resolve_user_id(sb, session_data)
    plan_id = metadata.get("plan_id")
    billing_period = metadata.get("billing_period", "monthly")
    stripe_subscription_id = session_data.get("subscription")
    stripe_customer_id = session_data.get("customer")
    payment_status = session_data.get("payment_status", "paid")

    # STORY-BIZ-001: keep founding_leads in sync regardless of regular-checkout path.
    # Note: founding mode=subscription sessions (legacy) still go through this path.
    try:
        from webhooks.handlers.founding import mark_founding_lead_completed
        mark_founding_lead_completed(sb, session_data)
    except Exception as e:
        logger.debug(f"Founding lead update skipped (non-fatal): {e}")

    if not user_id or not plan_id:
        logger.warning(
            f"Checkout session missing user_id or plan_id: "
            f"user_id={user_id}, metadata={metadata}"
        )
        return

    # STORY-280 AC2: Boleto/PIX -> payment_status="unpaid" at checkout.session.completed
    if payment_status == "unpaid":
        logger.info(
            f"Checkout completed with async payment (Boleto/PIX): user_id={user_id}, "
            f"plan_id={plan_id}, payment_status=unpaid — awaiting async_payment_succeeded"
        )

        def _sync_insert_pending():
            return sb.table("user_subscriptions").insert({
                "user_id": user_id,
                "plan_id": plan_id,
                "billing_period": billing_period,
                "credits_remaining": 0,
                "expires_at": None,
                "stripe_subscription_id": stripe_subscription_id,
                "stripe_customer_id": stripe_customer_id,
                "is_active": False,
                "subscription_status": "pending_payment",
            }).execute()

        await _run_with_budget(
            asyncio.to_thread(_sync_insert_pending),
            budget=_WEBHOOK_QUERY_BUDGET_S,
            phase="route",
            source="webhook.checkout_completed.insert_pending",
        )
        return

    # Card payment (synchronous) — activate immediately
    logger.info(
        f"Checkout completed: user_id={user_id}, plan_id={plan_id}, "
        f"billing_period={billing_period}, stripe_sub={stripe_subscription_id}"
    )

    # Look up plan for duration_days and max_searches
    def _sync_get_plan():
        return sb.table("plans").select("duration_days, max_searches").eq("id", plan_id).single().execute()

    plan_result = await _run_with_budget(
        asyncio.to_thread(_sync_get_plan),
        budget=_WEBHOOK_QUERY_BUDGET_S,
        phase="route",
        source="webhook.checkout_completed.get_plan",
    )
    duration_days = 30
    max_searches = 1000
    if plan_result.data:
        duration_days = plan_result.data.get("duration_days", 30) or 30
        max_searches = plan_result.data.get("max_searches", 1000) or 1000

    expires_at = (datetime.now(timezone.utc) + timedelta(days=duration_days)).isoformat()

    # Deactivate existing active subscriptions for this user
    await _run_with_budget(
        asyncio.to_thread(lambda: sb.table("user_subscriptions").update(
            {"is_active": False}
        ).eq("user_id", user_id).eq("is_active", True).execute()),
        budget=_WEBHOOK_QUERY_BUDGET_S,
        phase="route",
        source="webhook.checkout_completed.deactivate_existing",
    )

    # Create new active subscription
    _new_sub = {
        "user_id": user_id,
        "plan_id": plan_id,
        "billing_period": billing_period,
        "credits_remaining": max_searches,
        "expires_at": expires_at,
        "stripe_subscription_id": stripe_subscription_id,
        "stripe_customer_id": stripe_customer_id,
        "is_active": True,
        "subscription_status": "active",
    }
    await _run_with_budget(
        asyncio.to_thread(lambda: sb.table("user_subscriptions").insert(_new_sub).execute()),
        budget=_WEBHOOK_QUERY_BUDGET_S,
        phase="route",
        source="webhook.checkout_completed.insert_active",
    )

    # Sync profiles.plan_type AND subscription_status (keeps fallback current — CRITICAL)
    await _run_with_budget(
        asyncio.to_thread(lambda: sb.table("profiles").update({
            "plan_type": plan_id,
            "subscription_status": "active",
        }).eq("id", user_id).execute()),
        budget=_WEBHOOK_QUERY_BUDGET_S,
        phase="route",
        source="webhook.checkout_completed.sync_profile",
    )

    await invalidate_user_caches(user_id, "Checkout activation complete")

    # STORY-323 AC6: Create partner referral on conversion
    _create_partner_referral_async(user_id, plan_result, session_data)

    # Zero-churn P1 §8.1: Send welcome email after activation
    _send_welcome_email(sb, user_id, plan_id)

    # Zero-churn P1: Track subscription activation in funnel
    try:
        from analytics_events import track_funnel_event
        track_funnel_event("subscription_activated", user_id, {
            "plan_id": plan_id,
            "billing_period": billing_period,
            "payment_method": "card",
        })
    except Exception:
        pass


async def handle_async_payment_succeeded(sb, event: stripe.Event) -> None:
    """
    Handle checkout.session.async_payment_succeeded event (STORY-280 AC2).

    Fired when a Boleto/PIX async payment is confirmed after checkout.
    Activates the pending subscription created by handle_checkout_session_completed.

    #630: Intel Report async payments (boleto/pix) dispatched to
    handle_intel_report_async_payment_succeeded before subscription logic.
    """
    session_data = event.data.object
    metadata = session_data.get("metadata") or {}

    # #630: Intel Report async payment (boleto/pix confirmed)
    if session_data.get("mode") == "payment" and metadata.get("product_type"):
        await handle_intel_report_async_payment_succeeded(sb, session_data)
        return

    user_id = resolve_user_id(sb, session_data)
    plan_id = metadata.get("plan_id")
    billing_period = metadata.get("billing_period", "monthly")
    stripe_subscription_id = session_data.get("subscription")
    stripe_customer_id = session_data.get("customer")

    if not user_id or not plan_id:
        logger.warning(
            f"Async payment succeeded missing user_id or plan_id: "
            f"user_id={user_id}, metadata={metadata}"
        )
        return

    logger.info(
        f"Async payment succeeded (Boleto/PIX): user_id={user_id}, plan_id={plan_id}, "
        f"stripe_sub={stripe_subscription_id}"
    )

    # Look up plan for duration_days and max_searches
    def _sync_get_plan_async():
        return sb.table("plans").select("duration_days, max_searches").eq("id", plan_id).single().execute()

    plan_result = await _run_with_budget(
        asyncio.to_thread(_sync_get_plan_async),
        budget=_WEBHOOK_QUERY_BUDGET_S,
        phase="route",
        source="webhook.async_payment_succeeded.get_plan",
    )
    duration_days = 30
    max_searches = 1000
    if plan_result.data:
        duration_days = plan_result.data.get("duration_days", 30) or 30
        max_searches = plan_result.data.get("max_searches", 1000) or 1000

    expires_at = (datetime.now(timezone.utc) + timedelta(days=duration_days)).isoformat()

    # Deactivate existing active subscriptions for this user
    await _run_with_budget(
        asyncio.to_thread(lambda: sb.table("user_subscriptions").update(
            {"is_active": False}
        ).eq("user_id", user_id).eq("is_active", True).execute()),
        budget=_WEBHOOK_QUERY_BUDGET_S,
        phase="route",
        source="webhook.async_payment_succeeded.deactivate_existing",
    )

    # Find and activate the pending subscription (created at checkout.session.completed)
    def _sync_find_pending():
        return (
            sb.table("user_subscriptions")
            .select("id")
            .eq("stripe_subscription_id", stripe_subscription_id)
            .eq("subscription_status", "pending_payment")
            .limit(1)
            .execute()
        )

    pending_result = await _run_with_budget(
        asyncio.to_thread(_sync_find_pending),
        budget=_WEBHOOK_QUERY_BUDGET_S,
        phase="route",
        source="webhook.async_payment_succeeded.find_pending",
    )

    if pending_result.data:
        _pending_id = pending_result.data[0]["id"]
        await _run_with_budget(
            asyncio.to_thread(lambda: sb.table("user_subscriptions").update({
                "is_active": True,
                "subscription_status": "active",
                "credits_remaining": max_searches,
                "expires_at": expires_at,
            }).eq("id", _pending_id).execute()),
            budget=_WEBHOOK_QUERY_BUDGET_S,
            phase="route",
            source="webhook.async_payment_succeeded.activate_pending",
        )
    else:
        _new_sub_async = {
            "user_id": user_id,
            "plan_id": plan_id,
            "billing_period": billing_period,
            "credits_remaining": max_searches,
            "expires_at": expires_at,
            "stripe_subscription_id": stripe_subscription_id,
            "stripe_customer_id": stripe_customer_id,
            "is_active": True,
            "subscription_status": "active",
        }
        await _run_with_budget(
            asyncio.to_thread(lambda: sb.table("user_subscriptions").insert(_new_sub_async).execute()),
            budget=_WEBHOOK_QUERY_BUDGET_S,
            phase="route",
            source="webhook.async_payment_succeeded.insert_active",
        )

    # Sync profiles.plan_type AND subscription_status
    await _run_with_budget(
        asyncio.to_thread(lambda: sb.table("profiles").update({
            "plan_type": plan_id,
            "subscription_status": "active",
        }).eq("id", user_id).execute()),
        budget=_WEBHOOK_QUERY_BUDGET_S,
        phase="route",
        source="webhook.async_payment_succeeded.sync_profile",
    )

    await invalidate_user_caches(user_id, "Async payment activation complete")

    # Zero-churn P1 §8.1: Send welcome email after async payment activation
    _send_welcome_email(sb, user_id, plan_id)

    # Zero-churn P1: Track async payment activation in funnel
    try:
        from analytics_events import track_funnel_event
        track_funnel_event("subscription_activated", user_id, {
            "plan_id": plan_id,
            "billing_period": billing_period,
            "payment_method": "boleto_pix",
        })
    except Exception:
        pass


async def handle_async_payment_failed(sb, event: stripe.Event) -> None:
    """
    Handle checkout.session.async_payment_failed event (STORY-280 AC2).

    Fired when a Boleto/PIX payment fails (e.g., boleto expired without payment).
    """
    session_data = event.data.object
    user_id = resolve_user_id(sb, session_data)
    metadata = session_data.get("metadata") or {}
    plan_id = metadata.get("plan_id")
    stripe_subscription_id = session_data.get("subscription")

    if not user_id:
        logger.warning(f"Async payment failed missing user_id: metadata={metadata}")
        return

    logger.warning(
        f"Async payment failed (Boleto/PIX): user_id={user_id}, plan_id={plan_id}, "
        f"stripe_sub={stripe_subscription_id}"
    )

    # Clean up pending subscription row (mark as failed)
    if stripe_subscription_id:
        await _run_with_budget(
            asyncio.to_thread(lambda: sb.table("user_subscriptions").update({
                "subscription_status": "payment_failed",
            }).eq("stripe_subscription_id", stripe_subscription_id).eq(
                "subscription_status", "pending_payment"
            ).execute()),
            budget=_WEBHOOK_QUERY_BUDGET_S,
            phase="route",
            source="webhook.async_payment_failed.mark_failed",
        )

    # Send notification email
    _send_async_payment_failed_email(sb, user_id, plan_id)


# ============================================================================
# Post-purchase sequence (CONV-011b-1)
# ============================================================================

_DIGITAL_STEPS_DEFINITIONS = [
    {"step": "delivery", "offset_hours": 0, "template_id": None, "sent_at": None, "opened_at": None},
    {"step": "followup", "offset_hours": 48, "template_id": None, "sent_at": None, "opened_at": None},
    {"step": "reengagement", "offset_hours": 168, "template_id": None, "sent_at": None, "opened_at": None},
]


async def _create_post_purchase_sequence(sb, purchase_id: str, product_sku: str, user_id: str) -> None:
    """Create a post_purchase_sequences row and schedule ARQ email jobs.

    CONV-011b-1: Foundation for the 3-step email sequence (delivery 0h,
    followup 48h, reengagement 7d). Webhook calls this after creating a
    purchase record, so the sequence row and ARQ schedule fan out atomically.

    Idempotent: skips if a sequence for this purchase_id already exists.
    Never raises — failures are logged as warnings.
    """
    try:
        # Check for existing sequence (idempotency)
        def _sync_check_existing():
            return (
                sb.table("post_purchase_sequences")
                .select("id")
                .eq("purchase_id", purchase_id)
                .limit(1)
                .execute()
            )

        existing = await _run_with_budget(
            asyncio.to_thread(_sync_check_existing),
            budget=_WEBHOOK_QUERY_BUDGET_S,
            phase="route",
            source="webhook.post_purchase.check_existing",
        )
        if existing and existing.data:
            logger.info(
                f"Post-purchase sequence already exists for purchase_id={purchase_id}, skipping"
            )
            return

        # Populate template_ids based on product_sku
        steps = []
        for s in _DIGITAL_STEPS_DEFINITIONS:
            step_def = dict(s)
            step_def["template_id"] = f"{product_sku}_{step_def['step']}"
            steps.append(step_def)

        now_iso = datetime.now(timezone.utc).isoformat()

        def _sync_insert_sequence():
            return sb.table("post_purchase_sequences").insert({
                "purchase_id": purchase_id,
                "product_sku": product_sku,
                "user_id": user_id,
                "status": "active",
                "sequence_steps": steps,
                "current_step": 0,
                "created_at": now_iso,
                "updated_at": now_iso,
            }).execute()

        insert_result = await _run_with_budget(
            asyncio.to_thread(_sync_insert_sequence),
            budget=_WEBHOOK_QUERY_BUDGET_S,
            phase="route",
            source="webhook.post_purchase.insert_sequence",
        )

        if not insert_result.data:
            logger.warning(
                f"Post-purchase sequence insert returned no data for purchase_id={purchase_id}"
            )
            return

        sequence_id = insert_result.data[0]["id"]
        logger.info(
            f"Post-purchase sequence created: sequence_id={sequence_id}, "
            f"purchase_id={purchase_id}, product_sku={product_sku}"
        )

        # Schedule ARQ jobs for each step (best-effort)
        try:
            from job_queue import get_arq_pool
            pool = await get_arq_pool()
            if pool:
                await pool.enqueue_job(
                    "send_post_purchase_step",
                    sequence_id=sequence_id,
                    step_index=0,
                )
                logger.info(
                    f"send_post_purchase_step[0] enqueued for sequence_id={sequence_id}"
                )
                if len(steps) > 1:
                    await pool.enqueue_job(
                        "send_post_purchase_step",
                        sequence_id=sequence_id,
                        step_index=1,
                        _defer_by=timedelta(hours=steps[1]["offset_hours"]),
                    )
                    logger.info(
                        f"send_post_purchase_step[1] enqueued (+{steps[1]['offset_hours']}h) "
                        f"for sequence_id={sequence_id}"
                    )
                if len(steps) > 2:
                    await pool.enqueue_job(
                        "send_post_purchase_step",
                        sequence_id=sequence_id,
                        step_index=2,
                        _defer_by=timedelta(hours=steps[2]["offset_hours"]),
                    )
                    logger.info(
                        f"send_post_purchase_step[2] enqueued (+{steps[2]['offset_hours']}h) "
                        f"for sequence_id={sequence_id}"
                    )
        except Exception as arq_err:
            logger.warning(
                f"Could not enqueue post-purchase ARQ jobs (non-fatal): {arq_err}"
            )

    except Exception as e:
        logger.warning(
            f"Failed to create post-purchase sequence for purchase_id={purchase_id}: {e}"
        )


# ============================================================================
# Helpers (fire-and-forget)
# ============================================================================

def _send_async_payment_failed_email(sb, user_id: str, plan_id: str | None) -> None:
    """Send async payment failed email (STORY-280 AC2). Never raises."""
    try:
        from email_service import send_email_async
        from templates.emails.boleto_reminder import render_boleto_expired_email
        from quota import PLAN_NAMES

        profile = sb.table("profiles").select("email, full_name").eq("id", user_id).single().execute()
        if not profile.data or not profile.data.get("email"):
            return

        email = profile.data["email"]
        name = profile.data.get("full_name") or email.split("@")[0]
        plan_name = PLAN_NAMES.get(plan_id, plan_id) if plan_id else "SmartLic Pro"

        html = render_boleto_expired_email(
            user_name=name,
            plan_name=plan_name,
        )
        send_email_async(
            to=email,
            subject="Boleto expirado — Gere um novo para ativar seu plano",
            html=html,
            tags=[{"name": "category", "value": "boleto_expired"}],
        )
        logger.info(f"Boleto expired email queued for user_id={user_id}")
    except Exception as e:
        logger.warning(f"Failed to send boleto expired email: {e}")


def _send_welcome_email(sb, user_id: str, plan_id: str | None) -> None:
    """Send welcome email after subscription activation (Zero-churn P1 §8.1). Never raises."""
    try:
        from email_service import send_email_async
        from templates.emails.welcome_subscriber import render_welcome_subscriber_email
        from quota import PLAN_NAMES

        profile = sb.table("profiles").select("email, full_name").eq("id", user_id).single().execute()
        if not profile.data or not profile.data.get("email"):
            return

        email = profile.data["email"]
        name = profile.data.get("full_name") or email.split("@")[0]
        plan_name = PLAN_NAMES.get(plan_id, "SmartLic Pro") if plan_id else "SmartLic Pro"

        html = render_welcome_subscriber_email(
            user_name=name,
            plan_name=plan_name,
        )
        send_email_async(
            to=email,
            subject=f"Sua assinatura {plan_name} esta ativa!",
            html=html,
            tags=[{"name": "category", "value": "welcome_subscriber"}],
        )
        logger.info(f"Welcome subscriber email queued for user_id={user_id}")
    except Exception as e:
        logger.warning(f"Failed to send welcome email: {e}")


def _create_partner_referral_async(
    user_id: str, plan_result, session_data: dict
) -> None:
    """STORY-323 AC6: Create partner referral on checkout completion. Never raises."""
    try:
        import asyncio
        from services.partner_service import create_partner_referral

        price_brl = 0.0
        if plan_result and plan_result.data:
            price_brl = float(plan_result.data.get("price_brl", 0) or 0)

        discount = session_data.get("total_details", {}).get("breakdown", {}).get("discounts", [])
        stripe_coupon_id = None
        if discount and isinstance(discount, list) and len(discount) > 0:
            stripe_coupon_id = discount[0].get("discount", {}).get("coupon", {}).get("id")

        if not stripe_coupon_id:
            session_discount = session_data.get("discount")
            if session_discount and isinstance(session_discount, dict):
                stripe_coupon_id = session_discount.get("coupon", {}).get("id")

        loop = asyncio.get_event_loop()
        loop.create_task(
            create_partner_referral(user_id, price_brl, stripe_coupon_id)
        )
    except Exception as e:
        logger.warning(f"STORY-323: Failed to create partner referral for {user_id[:8]}: {e}")
