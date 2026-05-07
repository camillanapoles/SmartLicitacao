"""STORY-BIZ-001 + BIZ-FOUND-002: Founding customer checkout + canonical policy.

Endpoints:
- ``POST /v1/founding/checkout`` — qualifying form -> Stripe Checkout Session.
- ``GET  /v1/founding/availability`` — public seat counter / countdown feed.

BIZ-FOUND-002 changes:
- Pre-checkout, the route invokes ``public.check_founding_availability()`` RPC.
  The RPC takes ``SELECT FOR UPDATE`` on the founding_policy row + counts
  completed leads in one atomic step (race guard #1).
- When the RPC returns ``available=false`` we respond with 410 Gone and a
  structured ``error_code`` so the frontend can render the right message
  without parsing free-form text.
- The new ``GET /v1/founding/availability`` endpoint is anonymous (no auth)
  and used by the landing-page seat counter + countdown timer.

Pricing model is now canonical:
- Cap = 50 seats, deadline = 2026-05-30, lifetime 50% off forever via
  Stripe coupon ``FOUNDING_LIFETIME``.
- Source of truth lives in ``public.founding_policy`` (migration
  20260428100000) and Stripe (coupon configuration).
"""

from __future__ import annotations

import asyncio
import logging
import os

from pipeline.budget import _run_with_budget
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from rate_limiter import require_rate_limit
from supabase_client import get_supabase


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/founding", tags=["founding"])


# BIZ-FOUND-002: lifetime coupon replaces the old 12-month FOUNDING30 default.
# The old id is still respected if the operator wants to keep STORY-BIZ-001
# semantics in non-prod, but new deploys go through FOUNDING_LIFETIME.
FOUNDING_COUPON_ID = os.getenv("FOUNDING_COUPON_ID", "FOUNDING_LIFETIME")
FOUNDING_PLAN_ID = os.getenv("FOUNDING_PLAN_ID", "smartlic_pro")
FOUNDING_BILLING_PERIOD = os.getenv("FOUNDING_BILLING_PERIOD", "annual")


class FoundingCheckoutRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=320)
    nome: str = Field(..., min_length=2, max_length=200)
    cnpj: str = Field(..., min_length=11, max_length=18)
    razao_social: str | None = Field(default=None, max_length=300)
    motivo: str = Field(..., min_length=140, max_length=1000)

    @field_validator("cnpj")
    @classmethod
    def _validate_cnpj(cls, v: str) -> str:
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) != 14:
            raise ValueError("CNPJ deve conter 14 dígitos")
        if not _is_valid_cnpj_check_digits(digits):
            raise ValueError("CNPJ inválido (dígito verificador)")
        return digits

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@", 1)[1]:
            raise ValueError("Email inválido")
        return v


class FoundingCheckoutResponse(BaseModel):
    checkout_url: str
    lead_id: str


class FoundingAvailabilityResponse(BaseModel):
    """Public availability snapshot for landing-page seat counter + countdown."""

    available: bool
    seats_total: int
    seats_remaining: int
    seats_taken: int
    deadline_at: str | None
    paused: bool
    reason: str
    coupon_code: str
    discount_pct: int
    offer_mode: str = Field(default="lifetime", description="'lifetime' or 'subscription'")
    price_brl_cents: int = Field(default=99700, description="Price in BRL cents")


def _is_valid_cnpj_check_digits(cnpj: str) -> bool:
    """Validate Brazilian CNPJ check digits. `cnpj` must be 14 digits already."""
    if len(cnpj) != 14 or not cnpj.isdigit():
        return False
    if cnpj == cnpj[0] * 14:
        return False

    def _compute(digits: str, weights: list[int]) -> int:
        total = sum(int(d) * w for d, w in zip(digits, weights))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder

    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6] + w1
    d1 = _compute(cnpj[:12], w1)
    if d1 != int(cnpj[12]):
        return False
    d2 = _compute(cnpj[:13], w2)
    return d2 == int(cnpj[13])


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _already_registered(sb, email: str) -> bool:
    """Return True if the email already owns a profile. Best-effort, non-blocking."""
    try:
        res = sb.table("profiles").select("id").eq("email", email).limit(1).execute()
        return bool(res.data)
    except Exception as e:
        logger.warning(f"founding: profile lookup failed (non-blocking): {e}")
        return False


def _lookup_promotion_code(stripe_lib, api_key: str) -> dict | None:
    """Resolve the founding coupon into a promotion_code for use in discounts.

    Prefer PromotionCode (user-facing) over raw Coupon when available so
    Stripe enforces any restrictions configured at the promo-code level.
    Falls back to the raw coupon id if no promotion_code exists (the
    FOUNDING_LIFETIME coupon is created without a promotion_code by default
    via scripts/create_founding_lifetime_coupon.py).
    """
    try:
        promos = stripe_lib.PromotionCode.list(
            code=FOUNDING_COUPON_ID,
            active=True,
            limit=1,
            api_key=api_key,
        )
        if promos.data:
            return {"promotion_code": promos.data[0].id}
    except Exception as e:
        logger.warning(f"founding: promotion_code lookup failed: {e}")

    return {"coupon": FOUNDING_COUPON_ID}


def _check_availability(sb) -> dict[str, Any]:
    """Call ``check_founding_availability()`` RPC; return normalized dict.

    On any DB error returns ``available=False`` with reason ``'unavailable'``
    so the route fails closed (never accidentally over-sell the cohort).
    """
    try:
        res = sb.rpc("check_founding_availability").execute()
        rows = getattr(res, "data", None) or []
        if not rows:
            logger.warning("founding: check_founding_availability returned empty")
            return {
                "available": False,
                "seats_total": 0,
                "seats_remaining": 0,
                "deadline_at": None,
                "paused": False,
                "reason": "unavailable",
            }
        row = rows[0] if isinstance(rows, list) else rows
        return {
            "available": bool(row.get("available")),
            "seats_total": int(row.get("seats_total") or 0),
            "seats_remaining": int(row.get("seats_remaining") or 0),
            "deadline_at": row.get("deadline_at"),
            "paused": bool(row.get("paused")),
            "reason": str(row.get("reason") or "unavailable"),
            "offer_mode": str(row.get("offer_mode") or "lifetime"),
            "price_brl_cents": int(row.get("price_brl_cents") or 99700),
        }
    except Exception as e:
        logger.error(f"founding: check_founding_availability RPC failed: {e}")
        return {
            "available": False,
            "seats_total": 0,
            "seats_remaining": 0,
            "deadline_at": None,
            "paused": False,
            "reason": "unavailable",
            "offer_mode": "lifetime",
            "price_brl_cents": 99700,
        }


def _user_message_for_reason(reason: str) -> str:
    """Map RPC reason enum -> user-facing Portuguese message."""
    mapping = {
        "founding_cap_reached": (
            "As 50 vagas founding já foram preenchidas. Obrigado pelo interesse — "
            "entre em contato para entrar na lista de espera."
        ),
        "founding_deadline_passed": (
            "O período de inscrição founding (até 30/05/2026) terminou. O plano "
            "regular SmartLic Pro continua disponível em /pricing."
        ),
        "founding_paused": (
            "As inscrições founding estão temporariamente pausadas. Tente novamente em algumas horas."
        ),
        "founding_disabled": (
            "O programa founding não está aceitando novas inscrições no momento."
        ),
        "founding_policy_missing": (
            "Configuração founding indisponível. Tente novamente em instantes."
        ),
        "unavailable": (
            "Não foi possível validar disponibilidade founding agora. Tente novamente em instantes."
        ),
    }
    return mapping.get(reason, mapping["unavailable"])


@router.get("/availability", response_model=FoundingAvailabilityResponse)
async def founding_availability(response: Response) -> Any:
    """Public seat counter + countdown feed.

    No auth — the landing page calls this anonymously to render the
    countdown and the X/50 seat counter. Falls open with ``available=False``
    on transient DB error so the CTA is disabled rather than over-selling.
    """
    from config.features import get_feature_flag

    if not get_feature_flag("FOUNDERS_OFFER_ENABLED"):
        return FoundingAvailabilityResponse(
            available=False,
            seats_total=0,
            seats_remaining=0,
            seats_taken=0,
            deadline_at=None,
            paused=False,
            reason="founders_offer_disabled",
            coupon_code="",
            discount_pct=0,
            offer_mode="lifetime",
            price_brl_cents=99700,
        )

    sb = get_supabase()
    snapshot = await _run_with_budget(
        asyncio.to_thread(_check_availability, sb),
        budget=3.0,
        phase="route",
        source="founding.availability",
    )
    # Cache-Control for Googlebot fanout — short-lived public cache so the
    # seat counter stays accurate but bursty crawls don't hammer the RPC.
    response.headers["Cache-Control"] = "public, s-maxage=30"

    seats_total = snapshot["seats_total"]
    seats_remaining = snapshot["seats_remaining"]
    seats_taken = max(0, seats_total - seats_remaining)
    deadline_iso: str | None = None
    if snapshot["deadline_at"]:
        deadline_iso = (
            snapshot["deadline_at"].isoformat()
            if hasattr(snapshot["deadline_at"], "isoformat")
            else str(snapshot["deadline_at"])
        )

    return FoundingAvailabilityResponse(
        available=snapshot["available"],
        seats_total=seats_total,
        seats_remaining=seats_remaining,
        seats_taken=seats_taken,
        deadline_at=deadline_iso,
        paused=snapshot["paused"],
        reason=snapshot["reason"],
        coupon_code=FOUNDING_COUPON_ID,
        discount_pct=50,
        offer_mode=snapshot.get("offer_mode", "lifetime"),
        price_brl_cents=snapshot.get("price_brl_cents", 99700),
    )


@router.post("/checkout", response_model=FoundingCheckoutResponse)
async def founding_checkout(
    payload: FoundingCheckoutRequest,
    request: Request,
    _rl=Depends(require_rate_limit(3, 3600)),
) -> Any:
    """Create a founding-customer Stripe Checkout Session with the canonical coupon applied.

    BIZ-FOUND-002 gate:
    - Calls ``check_founding_availability()`` BEFORE creating the lead row.
    - On ``available=false`` returns 410 Gone with structured ``error_code`` +
      ``error_reason`` so the frontend can render the right copy.

    Side effects (when available):
    - Inserts a ``founding_leads`` row with ``checkout_status='pending'``.
    - Subsequent webhook events (``checkout.session.completed`` / ``expired``)
      update it. The webhook also re-checks availability for race guard
      (handled in webhooks.handlers.founding).
    """
    from config.features import get_feature_flag

    if not get_feature_flag("FOUNDERS_OFFER_ENABLED"):
        raise HTTPException(
            status_code=410,
            detail={
                "message": "Oferta Fundadores encerrada.",
                "error_code": "founders_offer_disabled",
            },
        )

    import stripe as stripe_lib

    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_key:
        logger.error("founding: STRIPE_SECRET_KEY not configured")
        raise HTTPException(status_code=500, detail="Erro ao processar pagamento. Tente novamente.")

    sb = get_supabase()

    # BIZ-FOUND-002 gate — atomic cap + deadline + paused check.
    snapshot = await _run_with_budget(
        asyncio.to_thread(_check_availability, sb),
        budget=3.0,
        phase="route",
        source="founding.checkout_gate",
    )
    if not snapshot["available"]:
        reason = snapshot["reason"]
        logger.info(
            f"founding: checkout rejected — reason={reason} "
            f"seats_taken={snapshot['seats_total'] - snapshot['seats_remaining']}/"
            f"{snapshot['seats_total']}"
        )
        raise HTTPException(
            status_code=410,
            detail={
                "message": _user_message_for_reason(reason),
                "error_code": reason,
                "seats_total": snapshot["seats_total"],
                "seats_remaining": snapshot["seats_remaining"],
            },
        )

    if await asyncio.to_thread(_already_registered, sb, payload.email):
        raise HTTPException(
            status_code=409,
            detail="Este email já possui conta SmartLic. Faça login para gerenciar sua assinatura.",
        )

    def _fetch_price_id():
        return (
            sb.table("plan_billing_periods")
            .select("stripe_price_id")
            .eq("plan_id", FOUNDING_PLAN_ID)
            .eq("billing_period", FOUNDING_BILLING_PERIOD)
            .limit(1)
            .execute()
        )

    bp_result = await _run_with_budget(
        asyncio.to_thread(_fetch_price_id),
        budget=5.0,
        phase="route",
        source="founding.checkout",
    )
    stripe_price_id = (bp_result.data[0] or {}).get("stripe_price_id") if bp_result.data else None
    if not stripe_price_id:
        logger.error(
            f"founding: no stripe_price_id for plan={FOUNDING_PLAN_ID} "
            f"billing_period={FOUNDING_BILLING_PERIOD}"
        )
        raise HTTPException(status_code=400, detail="Plano sem configuração de preço")

    lead_row = {
        "email": payload.email,
        "nome": payload.nome,
        "cnpj": payload.cnpj,
        "razao_social": payload.razao_social,
        "motivo": payload.motivo,
        "ip_address": _client_ip(request),
        "user_agent": request.headers.get("user-agent", "")[:500],
    }

    def _insert_lead():
        return sb.table("founding_leads").insert(lead_row).execute()

    lead_insert = await _run_with_budget(
        asyncio.to_thread(_insert_lead),
        budget=5.0,
        phase="route",
        source="founding.checkout.insert_lead",
    )
    lead_record = (lead_insert.data or [{}])[0]
    lead_id = lead_record.get("id")
    if not lead_id:
        logger.error("founding: Supabase insert returned no id")
        raise HTTPException(status_code=500, detail="Erro ao registrar sua solicitação.")

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    discount = _lookup_promotion_code(stripe_lib, stripe_key)

    session_params = {
        "payment_method_types": ["card"],
        "line_items": [{"price": stripe_price_id, "quantity": 1}],
        "mode": "subscription",
        "success_url": f"{frontend_url}/founding/obrigado?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{frontend_url}/founding?cancelled=true",
        "customer_email": payload.email,
        "metadata": {
            "source": "founding",
            "founding_lead_id": lead_id,
            "cnpj": payload.cnpj,
            "plan_id": FOUNDING_PLAN_ID,
            "billing_period": FOUNDING_BILLING_PERIOD,
        },
        "discounts": [discount],
    }

    try:
        session = stripe_lib.checkout.Session.create(**session_params, api_key=stripe_key)
    except stripe_lib.error.InvalidRequestError as e:
        logger.error(
            f"founding: Stripe InvalidRequestError — cnpj={payload.cnpj} "
            f"lead_id={lead_id} err={e}"
        )
        raise HTTPException(
            status_code=400,
            detail="Não foi possível iniciar o checkout. Verifique os dados e tente novamente.",
        )
    except stripe_lib.error.StripeError as e:
        logger.error(f"founding: Stripe error — lead_id={lead_id} err={e}")
        raise HTTPException(
            status_code=503,
            detail="Serviço de pagamento temporariamente indisponível. Tente novamente em instantes.",
        )

    try:
        _session_id = session.id

        def _update_session_id():
            return (
                sb.table("founding_leads")
                .update({"checkout_session_id": _session_id})
                .eq("id", lead_id)
                .execute()
            )

        await _run_with_budget(
            asyncio.to_thread(_update_session_id),
            budget=5.0,
            phase="route",
            source="founding.checkout.update_session_id",
        )
    except Exception as e:
        logger.warning(f"founding: failed to persist session_id — lead_id={lead_id} err={e}")

    logger.info(
        f"founding: checkout session created — lead_id={lead_id} "
        f"session_id={session.id} email={payload.email} cnpj={payload.cnpj[:4]}***"
    )

    return FoundingCheckoutResponse(checkout_url=session.url, lead_id=lead_id)
