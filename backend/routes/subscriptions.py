"""Subscription management routes.

Handles billing period updates and subscription modifications.
GTM-002: Removed pro-rata calculations — Stripe handles proration automatically.
UX-308: Cancel flow with reason selection, retention offers, and post-cancel feedback.
"""

import logging
import os
from typing import Literal, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import stripe as stripe_lib

from auth import require_auth, require_mfa_high_impact
from services.billing import (
    update_stripe_subscription_billing_period,
    get_next_billing_date,
)
from log_sanitizer import mask_user_id, log_user_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


class UpdateBillingPeriodRequest(BaseModel):
    """Request to update subscription billing period."""
    new_billing_period: Literal["monthly", "semiannual", "annual"] = Field(
        ...,
        description="Target billing period"
    )


class UpdateBillingPeriodResponse(BaseModel):
    """Response for billing period update."""
    success: bool
    new_billing_period: str
    next_billing_date: str
    message: str


CANCEL_REASONS = {"too_expensive", "not_using", "missing_features", "found_alternative", "other"}


class CancelSubscriptionRequest(BaseModel):
    """Request body for subscription cancellation (UX-308)."""
    reason: Optional[str] = Field(
        None,
        description="Cancellation reason: too_expensive, not_using, missing_features, found_alternative, other"
    )


class CancelSubscriptionResponse(BaseModel):
    """Response for subscription cancellation."""
    success: bool
    ends_at: str
    message: str


class CancelFeedbackRequest(BaseModel):
    """Post-cancellation feedback (UX-308 AC6)."""
    feedback: str = Field(..., min_length=1, max_length=2000, description="Free-text cancellation feedback")


class CancelFeedbackResponse(BaseModel):
    """Response for cancellation feedback."""
    success: bool
    message: str


@router.post("/update-billing-period", response_model=UpdateBillingPeriodResponse)
async def update_billing_period(
    request: UpdateBillingPeriodRequest,
    user: dict = Depends(require_mfa_high_impact),
):
    """Update subscription billing period (monthly / semiannual / annual).

    GTM-002: Simplified flow — Stripe handles proration automatically.
    No deferral logic, no manual credit calculations.
    """
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    logger.info(
        f"Updating billing period for user {mask_user_id(user_id)} to {request.new_billing_period}"
    )

    sb = get_supabase()

    # Step 1: Fetch current active subscription
    try:
        result = await sb_execute(
            sb.table("user_subscriptions")
            .select("id, plan_id, billing_period, stripe_subscription_id, expires_at")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .order("created_at", desc=True)
            .limit(1)
        )

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Nenhuma assinatura ativa encontrada")

        subscription = result.data[0]
        current_billing_period = subscription["billing_period"]
        plan_id = subscription["plan_id"]
        stripe_subscription_id = subscription.get("stripe_subscription_id")

        if current_billing_period == request.new_billing_period:
            raise HTTPException(
                status_code=400,
                detail=f"Já está no período {request.new_billing_period}"
            )

        if not stripe_subscription_id:
            raise HTTPException(status_code=400, detail="Assinatura sem identificador de cobrança")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch subscription for user {mask_user_id(user_id)}: {e}")
        raise HTTPException(status_code=500, detail="Erro ao buscar assinatura ativa")

    # Step 2: Get plan Stripe price IDs
    try:
        plan_result = await sb_execute(
            sb.table("plans")
            .select("stripe_price_id_monthly, stripe_price_id_semiannual, stripe_price_id_annual")
            .eq("id", plan_id)
            .single()
        )

        if not plan_result.data:
            raise HTTPException(status_code=404, detail=f"Plano {plan_id} não encontrado")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch plan {plan_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro ao buscar informações do plano")

    # Step 3: Update Stripe subscription (Stripe handles proration)
    try:
        update_stripe_subscription_billing_period(
            stripe_subscription_id=stripe_subscription_id,
            new_billing_period=request.new_billing_period,
            stripe_price_id_monthly=plan_result.data.get("stripe_price_id_monthly", ""),
            stripe_price_id_semiannual=plan_result.data.get("stripe_price_id_semiannual", ""),
            stripe_price_id_annual=plan_result.data.get("stripe_price_id_annual", ""),
        )
        logger.info(f"Updated Stripe subscription for user {mask_user_id(user_id)}")
    except Exception as e:
        logger.error(f"Stripe update failed for user {mask_user_id(user_id)}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao atualizar assinatura. Tente novamente.")

    # Step 4: Update Supabase subscription
    try:
        await sb_execute(
            sb.table("user_subscriptions").update({
                "billing_period": request.new_billing_period,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", subscription["id"])
        )
    except Exception as e:
        logger.error(f"DB update failed for user {mask_user_id(user_id)}: {e}", exc_info=True)
        logger.critical(
            f"DATA INCONSISTENCY: Stripe updated but Supabase failed for user {mask_user_id(user_id)}"
        )
        raise HTTPException(status_code=500, detail="Erro ao atualizar no banco de dados")

    # Step 5: Invalidate feature cache
    try:
        from cache import redis_cache
        await redis_cache.delete(f"features:{user_id}")
    except Exception as e:
        logger.warning(f"Cache invalidation failed (non-critical): {e}")

    # Step 6: Get next billing date for response
    next_billing = get_next_billing_date(user_id)
    next_billing_str = next_billing.isoformat() if next_billing else ""

    return UpdateBillingPeriodResponse(
        success=True,
        new_billing_period=request.new_billing_period,
        next_billing_date=next_billing_str,
        message=f"Período de cobrança atualizado para {request.new_billing_period}.",
    )


@router.post("/cancel", response_model=CancelSubscriptionResponse)
async def cancel_subscription(
    request: Optional[CancelSubscriptionRequest] = None,
    user: dict = Depends(require_mfa_high_impact),
):
    """Cancel subscription at period end.

    GTM-FIX-006: User-initiated cancellation flow.
    UX-308: Accepts optional cancellation reason for retention analytics.
    Sets cancel_at_period_end=True in Stripe, updates status to 'canceling'.
    """
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    reason = request.reason if request else None
    if reason and reason not in CANCEL_REASONS:
        reason = "other"
    logger.info(f"Cancellation requested for user {mask_user_id(user_id)}, reason={reason}")

    sb = get_supabase()
    stripe_key = os.getenv("STRIPE_SECRET_KEY")

    if not stripe_key:
        logger.error("STRIPE_SECRET_KEY not configured")
        raise HTTPException(status_code=500, detail="Configuração de pagamento ausente")

    # Step 1: Fetch current active subscription
    try:
        result = await sb_execute(
            sb.table("user_subscriptions")
            .select("id, stripe_subscription_id, expires_at")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .order("created_at", desc=True)
            .limit(1)
        )

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Nenhuma assinatura ativa encontrada")

        subscription = result.data[0]
        stripe_subscription_id = subscription.get("stripe_subscription_id")

        if not stripe_subscription_id:
            raise HTTPException(status_code=400, detail="Assinatura sem identificador de cobrança")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch subscription for user {mask_user_id(user_id)}: {e}")
        raise HTTPException(status_code=500, detail="Erro ao buscar assinatura ativa")

    # Step 2: Cancel subscription at period end in Stripe
    try:
        stripe_subscription = stripe_lib.Subscription.modify(
            stripe_subscription_id,
            cancel_at_period_end=True,
            api_key=stripe_key,
        )

        # Get the period end timestamp and convert to ISO string
        current_period_end = stripe_subscription.current_period_end
        ends_at_iso = datetime.fromtimestamp(current_period_end, tz=timezone.utc).isoformat()

        logger.info(f"Stripe subscription {stripe_subscription_id} set to cancel at {ends_at_iso}")
    except stripe_lib.error.StripeError as e:
        logger.error(f"Stripe cancellation failed for user {mask_user_id(user_id)}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao cancelar assinatura. Tente novamente.")
    except Exception as e:
        logger.error(f"Unexpected error during Stripe cancellation for user {mask_user_id(user_id)}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao processar cancelamento")

    # Step 3: Update profiles table with canceling status and end date
    try:
        await sb_execute(
            sb.table("profiles").update({
                "subscription_status": "canceling",
                "subscription_end_date": ends_at_iso,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", user_id)
        )

        logger.info(f"Updated profiles for user {mask_user_id(user_id)} to canceling status")
    except Exception as e:
        logger.error(f"Failed to update profiles for user {mask_user_id(user_id)}: {e}", exc_info=True)
        logger.critical(
            f"DATA INCONSISTENCY: Stripe canceled but profiles update failed for user {mask_user_id(user_id)}"
        )
        raise HTTPException(status_code=500, detail="Erro ao atualizar status de cancelamento")

    # Step 4: Log the action (includes reason for UX-308 analytics)
    log_user_action(
        logger,
        "subscription-cancel-requested",
        user_id,
        details={
            "stripe_subscription_id": stripe_subscription_id,
            "ends_at": ends_at_iso,
            "reason": reason,
        }
    )

    return CancelSubscriptionResponse(
        success=True,
        ends_at=ends_at_iso,
        message=f"Sua assinatura foi cancelada e permanecerá ativa até {datetime.fromisoformat(ends_at_iso).strftime('%d/%m/%Y')}.",
    )


@router.post("/cancel-feedback", response_model=CancelFeedbackResponse)
async def submit_cancel_feedback(
    request: CancelFeedbackRequest,
    user: dict = Depends(require_auth),
):
    """Submit post-cancellation feedback (UX-308 AC6).

    Logs feedback as a user action for analytics. Fire-and-forget — never blocks UX.
    """
    user_id = user["id"]

    log_user_action(
        logger,
        "subscription-cancel-feedback",
        user_id,
        details={"feedback": request.feedback[:2000]},
    )

    logger.info(f"Cancel feedback received from user {mask_user_id(user_id)}")

    return CancelFeedbackResponse(
        success=True,
        message="Obrigado pelo feedback!",
    )


# ---------------------------------------------------------------------------
# Pro mensal -> Lifetime founder upgrade (#1011 / UPGRADE-PATH-013)
# ---------------------------------------------------------------------------


class UpgradeToLifetimePreviewResponse(BaseModel):
    """Pro-rata preview for the modal confirmation step.

    Stripe handles the actual proration when we cancel with ``prorate=True`` and
    create the new charge — these numbers are an *estimate* surfaced to the
    user so they understand what will happen. The webhook is the source of
    truth for the final charge.
    """

    eligible: bool
    reason: str
    lifetime_price_brl_cents: int = 99700
    seats_remaining: int = 0
    seats_total: int = 0
    # Estimated credit returned by canceling the active sub (cents).
    # Computed best-effort from current_period_end vs now; Stripe's actual
    # credit may differ by a few cents.
    estimated_credit_brl_cents: int = 0
    # Net charge expected at checkout (lifetime price - credit, floored at 0).
    net_charge_brl_cents: int = 99700
    has_active_subscription: bool = False
    is_already_founder: bool = False


class UpgradeToLifetimeRequest(BaseModel):
    """Empty body — auth identifies the user."""

    confirmed: bool = Field(
        default=True,
        description="Client must explicitly confirm to proceed (defense in depth).",
    )


class UpgradeToLifetimeResponse(BaseModel):
    checkout_url: str
    session_id: str
    estimated_credit_brl_cents: int = 0
    net_charge_brl_cents: int = 99700


def _check_founding_seats(sb) -> dict:
    """Wrap ``check_founding_availability()`` RPC for the upgrade flow.

    Fails closed: any error returns ``available=False`` so we never sell a
    seat that may already be gone (cap is 50 — race-guarded server-side).
    """
    try:
        res = sb.rpc("check_founding_availability").execute()
        rows = getattr(res, "data", None) or []
        if not rows:
            return {"available": False, "reason": "unavailable", "seats_total": 0, "seats_remaining": 0}
        row = rows[0] if isinstance(rows, list) else rows
        return {
            "available": bool(row.get("available")),
            "reason": str(row.get("reason") or "unavailable"),
            "seats_total": int(row.get("seats_total") or 0),
            "seats_remaining": int(row.get("seats_remaining") or 0),
            "price_brl_cents": int(row.get("price_brl_cents") or 99700),
        }
    except Exception as exc:
        logger.error(f"upgrade-to-lifetime: availability RPC failed: {exc}")
        return {"available": False, "reason": "unavailable", "seats_total": 0, "seats_remaining": 0}


def _fetch_active_subscription(sb, user_id: str) -> dict | None:
    """Return the user's active row from ``user_subscriptions`` or None."""
    try:
        res = (
            sb.table("user_subscriptions")
            .select("id, stripe_subscription_id, expires_at, plan_id")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        return rows[0] if rows else None
    except Exception as exc:
        logger.error(f"upgrade-to-lifetime: subscription lookup failed: {exc}")
        return None


def _fetch_profile_founder_flag(sb, user_id: str) -> bool:
    try:
        res = (
            sb.table("profiles")
            .select("is_founder")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        return bool(rows[0].get("is_founder")) if rows else False
    except Exception as exc:
        logger.warning(f"upgrade-to-lifetime: profile lookup failed: {exc}")
        return False


def _estimate_credit_cents(stripe_sub: object, lifetime_price_cents: int) -> int:
    """Best-effort proration estimate for the modal preview.

    Reads ``current_period_start/end`` from the Stripe subscription object
    plus the latest invoice ``amount_paid`` (cents). If anything is missing,
    returns 0 so the user sees the worst case (full lifetime price).
    Capped at ``lifetime_price_cents`` so the UI never shows negative net.
    """
    try:
        period_start = getattr(stripe_sub, "current_period_start", None)
        period_end = getattr(stripe_sub, "current_period_end", None)
        items = getattr(stripe_sub, "items", None)
        if not (period_start and period_end and items):
            return 0
        total_seconds = max(period_end - period_start, 1)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        unused_seconds = max(period_end - now_ts, 0)
        # Pull unit_amount from first item
        item_data = getattr(items, "data", None) or []
        if not item_data:
            return 0
        price = getattr(item_data[0], "price", None)
        unit_amount = int(getattr(price, "unit_amount", 0) or 0)
        if unit_amount <= 0:
            return 0
        estimated = int(unit_amount * (unused_seconds / total_seconds))
        return min(max(estimated, 0), lifetime_price_cents)
    except Exception as exc:
        logger.warning(f"upgrade-to-lifetime: credit estimate failed: {exc}")
        return 0


@router.get("/upgrade-to-lifetime/preview", response_model=UpgradeToLifetimePreviewResponse)
async def upgrade_to_lifetime_preview(user: dict = Depends(require_auth)):
    """Preview pro-rata math for the upgrade-to-lifetime modal (#1011).

    Returns ``eligible=False`` with a structured ``reason`` whenever the user
    is not allowed to upgrade (already founder, no active sub, cap reached,
    feature flag off). Front-end uses this to render the right copy without
    parsing free text.
    """
    from supabase_client import get_supabase
    from config.features import get_feature_flag
    from pipeline.budget import _run_with_budget
    import asyncio

    user_id = user["id"]
    sb = get_supabase()
    lifetime_price = 99700

    if not get_feature_flag("FOUNDERS_OFFER_ENABLED"):
        return UpgradeToLifetimePreviewResponse(
            eligible=False,
            reason="founders_offer_disabled",
            lifetime_price_brl_cents=lifetime_price,
            net_charge_brl_cents=lifetime_price,
        )

    # Founder check (idempotency)
    is_founder = await _run_with_budget(
        asyncio.to_thread(_fetch_profile_founder_flag, sb, user_id),
        budget=3.0,
        phase="route",
        source="subscriptions.upgrade_preview.profile",
    )
    if is_founder:
        return UpgradeToLifetimePreviewResponse(
            eligible=False,
            reason="already_founder",
            is_already_founder=True,
            lifetime_price_brl_cents=lifetime_price,
            net_charge_brl_cents=0,
        )

    # Cap check
    seats = await _run_with_budget(
        asyncio.to_thread(_check_founding_seats, sb),
        budget=3.0,
        phase="route",
        source="subscriptions.upgrade_preview.seats",
    )
    if not seats["available"]:
        return UpgradeToLifetimePreviewResponse(
            eligible=False,
            reason=seats["reason"],
            seats_total=seats.get("seats_total", 0),
            seats_remaining=seats.get("seats_remaining", 0),
            lifetime_price_brl_cents=lifetime_price,
            net_charge_brl_cents=lifetime_price,
        )

    # Active subscription
    sub = await _run_with_budget(
        asyncio.to_thread(_fetch_active_subscription, sb, user_id),
        budget=3.0,
        phase="route",
        source="subscriptions.upgrade_preview.subscription",
    )
    if not sub or not sub.get("stripe_subscription_id"):
        return UpgradeToLifetimePreviewResponse(
            eligible=False,
            reason="no_active_subscription",
            seats_total=seats.get("seats_total", 0),
            seats_remaining=seats.get("seats_remaining", 0),
            lifetime_price_brl_cents=lifetime_price,
            net_charge_brl_cents=lifetime_price,
        )

    # Estimate credit (best-effort — Stripe is final source of truth)
    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    estimated_credit = 0
    if stripe_key:
        try:
            stripe_sub = stripe_lib.Subscription.retrieve(
                sub["stripe_subscription_id"],
                expand=["items.data.price"],
                api_key=stripe_key,
            )
            estimated_credit = _estimate_credit_cents(stripe_sub, lifetime_price)
        except Exception as exc:
            logger.warning(f"upgrade-to-lifetime: Stripe retrieve failed: {exc}")

    net_charge = max(lifetime_price - estimated_credit, 0)

    return UpgradeToLifetimePreviewResponse(
        eligible=True,
        reason="ok",
        seats_total=seats.get("seats_total", 0),
        seats_remaining=seats.get("seats_remaining", 0),
        lifetime_price_brl_cents=lifetime_price,
        estimated_credit_brl_cents=estimated_credit,
        net_charge_brl_cents=net_charge,
        has_active_subscription=True,
    )


@router.post("/upgrade-to-lifetime", response_model=UpgradeToLifetimeResponse)
async def upgrade_to_lifetime(
    request: UpgradeToLifetimeRequest,
    user: dict = Depends(require_mfa_high_impact),
):
    """Upgrade Pro mensal -> Lifetime founder (#1011 / UPGRADE-PATH-013).

    Flow:
      1. Re-check founder cap via existing ``check_founding_availability()`` RPC
         (race-guarded, atomic). Reject 410 if cap reached.
      2. Reject 409 if ``profiles.is_founder`` is already TRUE (idempotent).
      3. Cancel the active Stripe subscription with ``prorate=True``. Stripe
         issues a credit balance to the customer automatically — no custom
         prorata math.
      4. Create a Stripe Checkout Session in ``mode='payment'`` for the
         R$997 one-time founder price (``FOUNDING_ONE_TIME_PRICE_ID``).
         Customer balance is consumed automatically by Stripe.
      5. Return checkout URL. The existing webhook handler
         (``webhooks/handlers/founding.py::_activate_lifetime_founder_entitlement``)
         flips ``is_founder=TRUE`` once payment completes — DO NOT duplicate.
      6. Audit log via ``audit_logger`` for billing.subscription_change.
    """
    from supabase_client import get_supabase
    from config.features import get_feature_flag
    from pipeline.budget import _run_with_budget
    from audit import audit_logger
    import asyncio

    if not request.confirmed:
        raise HTTPException(status_code=400, detail="Confirmação obrigatória.")

    user_id = user["id"]
    sb = get_supabase()
    lifetime_price = 99700

    if not get_feature_flag("FOUNDERS_OFFER_ENABLED"):
        raise HTTPException(
            status_code=410,
            detail={"message": "Oferta Fundadores encerrada.", "error_code": "founders_offer_disabled"},
        )

    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_key:
        logger.error("upgrade-to-lifetime: STRIPE_SECRET_KEY not configured")
        raise HTTPException(status_code=500, detail="Configuração de pagamento ausente.")

    founding_price_id = os.getenv("FOUNDING_ONE_TIME_PRICE_ID")
    if not founding_price_id:
        logger.error("upgrade-to-lifetime: FOUNDING_ONE_TIME_PRICE_ID not configured")
        raise HTTPException(status_code=500, detail="Preço fundador indisponível.")

    # Step 1 — idempotency check (already founder?)
    is_founder = await _run_with_budget(
        asyncio.to_thread(_fetch_profile_founder_flag, sb, user_id),
        budget=3.0,
        phase="route",
        source="subscriptions.upgrade.profile",
    )
    if is_founder:
        raise HTTPException(
            status_code=409,
            detail={"message": "Você já é fundador SmartLic.", "error_code": "already_founder"},
        )

    # Step 2 — cap re-check (race-guarded server-side)
    seats = await _run_with_budget(
        asyncio.to_thread(_check_founding_seats, sb),
        budget=3.0,
        phase="route",
        source="subscriptions.upgrade.seats",
    )
    if not seats["available"]:
        raise HTTPException(
            status_code=410,
            detail={
                "message": "Vagas Fundadores esgotadas.",
                "error_code": seats["reason"],
                "seats_total": seats.get("seats_total", 0),
                "seats_remaining": seats.get("seats_remaining", 0),
            },
        )

    # Step 3 — fetch active sub
    sub = await _run_with_budget(
        asyncio.to_thread(_fetch_active_subscription, sb, user_id),
        budget=5.0,
        phase="route",
        source="subscriptions.upgrade.fetch_sub",
    )
    if not sub or not sub.get("stripe_subscription_id"):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Nenhuma assinatura ativa para fazer upgrade.",
                "error_code": "no_active_subscription",
            },
        )
    stripe_subscription_id = sub["stripe_subscription_id"]

    # Step 4 — cancel sub with proration (Stripe credits the customer)
    estimated_credit = 0
    user_email = user.get("email") or ""
    try:
        # Retrieve to compute estimate + capture customer id
        stripe_sub = stripe_lib.Subscription.retrieve(
            stripe_subscription_id,
            expand=["items.data.price", "customer"],
            api_key=stripe_key,
        )
        estimated_credit = _estimate_credit_cents(stripe_sub, lifetime_price)
        stripe_customer_id = getattr(stripe_sub, "customer", None)
        if isinstance(stripe_customer_id, dict):
            stripe_customer_id = stripe_customer_id.get("id")
        elif hasattr(stripe_customer_id, "id"):
            stripe_customer_id = stripe_customer_id.id

        # Immediate cancel with proration -> credit balance.
        stripe_lib.Subscription.delete(
            stripe_subscription_id,
            prorate=True,
            api_key=stripe_key,
        )
        logger.info(
            f"upgrade-to-lifetime: cancelled sub {stripe_subscription_id} for "
            f"user {mask_user_id(user_id)}, estimated_credit_cents={estimated_credit}"
        )
    except stripe_lib.error.StripeError as exc:
        logger.error(
            f"upgrade-to-lifetime: Stripe cancel failed for user {mask_user_id(user_id)}: {exc}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=502,
            detail="Falha ao cancelar assinatura atual. Tente novamente em instantes.",
        )

    # Step 5 — create one-time checkout session.
    # If the cancel succeeded but checkout creation fails we surface 502 — the
    # user keeps the proration credit on file (Stripe handles it), so no
    # double-charge is possible. They can retry; the credit remains.
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    try:
        session_params = {
            "payment_method_types": ["card", "boleto"],
            "line_items": [{"price": founding_price_id, "quantity": 1}],
            "mode": "payment",
            "success_url": (
                f"{frontend_url}/conta/plano?upgrade=success"
                "&session_id={CHECKOUT_SESSION_ID}"
            ),
            "cancel_url": f"{frontend_url}/conta/plano?upgrade=cancelled",
            "metadata": {
                "source": "founding",
                "offer_version": "v2_lifetime",
                "offer_mode": "lifetime",
                "price_brl_cents": str(lifetime_price),
                "checkout_source": "upgrade_pro_to_lifetime",
                "upgrade_from_sub_id": stripe_subscription_id,
                "upgrade_user_id": user_id,
            },
        }
        if stripe_customer_id:
            session_params["customer"] = stripe_customer_id
        elif user_email:
            session_params["customer_email"] = user_email

        session = stripe_lib.checkout.Session.create(
            **session_params, api_key=stripe_key
        )
    except stripe_lib.error.StripeError as exc:
        logger.error(
            f"upgrade-to-lifetime: checkout session create failed for user "
            f"{mask_user_id(user_id)}: {exc}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "Sua assinatura foi cancelada e o crédito está disponível, "
                "mas não conseguimos abrir o checkout. Contate o suporte."
            ),
        )

    net_charge = max(lifetime_price - estimated_credit, 0)

    # Step 6 — audit log (best-effort — never blocks)
    try:
        await audit_logger.log(
            event_type="billing.subscription_change",
            actor_id=user_id,
            target_id=user_id,
            details={
                "action": "upgrade_pro_to_lifetime_initiated",
                "stripe_subscription_id": stripe_subscription_id,
                "estimated_credit_cents": estimated_credit,
                "net_charge_cents": net_charge,
                "lifetime_price_cents": lifetime_price,
                "checkout_session_id": session.id,
            },
        )
    except Exception as exc:
        logger.warning(f"upgrade-to-lifetime: audit log failed (non-blocking): {exc}")

    log_user_action(
        logger,
        "subscription-upgrade-to-lifetime-initiated",
        user_id,
        details={
            "stripe_subscription_id": stripe_subscription_id,
            "checkout_session_id": session.id,
            "estimated_credit_cents": estimated_credit,
        },
    )

    return UpgradeToLifetimeResponse(
        checkout_url=session.url,
        session_id=session.id,
        estimated_credit_brl_cents=estimated_credit,
        net_charge_brl_cents=net_charge,
    )
