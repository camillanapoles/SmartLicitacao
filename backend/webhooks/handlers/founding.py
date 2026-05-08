"""STORY-BIZ-001 + BIZ-FOUND-002 + #785 + FOUND-CRIT-006: side-effect handlers
that keep ``founding_leads`` in sync with Stripe checkout-session lifecycle
events, plus the cap-violation race guard introduced by BIZ-FOUND-002, and
lifetime entitlement activation (#785).

Invoked from ``webhooks.handlers.checkout.handle_checkout_session_completed``
and from the webhook dispatcher in ``webhooks.stripe`` when session metadata
contains ``source='founding'``.

FOUND-CRIT-006 mode=payment support:
- The founding checkout uses ``mode='payment'`` (one-time R$997 BRL) not
  ``mode='subscription'``. The session object therefore has ``payment_intent``
  populated and ``subscription=None``.
- All handler functions here are already mode-agnostic: ``_is_founding_session``
  reads ``metadata.source``, refund helpers read ``payment_intent``, and
  ``_activate_lifetime_founder_entitlement`` does not reference ``subscription``.
- FOUND-CRIT-003 invite: when the buyer has not yet created an account
  (founding is sold to unauthenticated visitors), ``_send_founding_invite``
  dispatches a Supabase magic-link invite email and stamps
  ``founding_leads.magic_link_sent_at`` for idempotency.

BIZ-FOUND-002 race guard:
- Two concurrent checkouts can both pass the pre-checkout availability gate
  (different requests, different RPC calls, both see seats_remaining > 0).
  When the first one completes the second's pre-check value is now stale.
- The webhook handler therefore re-runs ``check_founding_availability()``
  AFTER the row is marked completed and detects the over-sell. It then
  reverts the row to ``checkout_status='cap_violated'``, refunds the Stripe
  charge, and queues an apology email.
- We do the re-check after marking completed (not before) because the cap
  count is based on completed rows; if we re-checked before flipping, the
  current event itself would not be visible to the count.

#785 Lifetime entitlement:
- After the race guard confirms the checkout is valid (not cap_violated),
  the handler activates the lifetime founder entitlement on ``profiles``.
- If the user hasn't signed up yet (founding is sold to unauthenticated
  visitors), the activation is gracefully deferred AND a Supabase invite
  email is dispatched (FOUND-CRIT-003) so the buyer can create their account.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Any

from log_sanitizer import get_sanitized_logger
from metrics import founders_checkout_success, founders_checkout_failed

logger = get_sanitized_logger(__name__)


def _is_founding_session(session: Any) -> bool:
    """Return True if the checkout session originated from /founding landing."""
    metadata = (session.get("metadata") or {}) if hasattr(session, "get") else {}
    return metadata.get("source") == "founding"


def _session_id(session: Any) -> str | None:
    sid = session.get("id") if hasattr(session, "get") else None
    return str(sid) if sid else None


def _check_availability_via_rpc(sb) -> dict[str, Any] | None:
    """Re-run the availability RPC inside the webhook handler.

    Returns the parsed row dict, or None on failure (failing closed —
    caller should treat unknown availability as "do not refund" to avoid
    reverting a paying customer when the DB is flaky).
    """
    try:
        res = sb.rpc("check_founding_availability").execute()
        rows = getattr(res, "data", None) or []
        if not rows:
            return None
        return rows[0] if isinstance(rows, list) else rows
    except Exception as e:
        logger.warning(f"founding race guard: RPC failed — {e}")
        return None


def _refund_session_charge(session: Any) -> bool:
    """Best-effort Stripe refund for the cap-violated session.

    Returns True if Stripe accepted the refund call. Never raises — the
    webhook returns 200 to Stripe anyway and the operator follow-up email
    is the safety net.
    """
    if not _is_founding_session(session):
        return False

    sid = _session_id(session)
    payment_intent = session.get("payment_intent") if hasattr(session, "get") else None
    api_key = os.getenv("STRIPE_SECRET_KEY")

    if not payment_intent or not api_key:
        logger.warning(
            f"founding race guard: cannot refund — session_id={sid} "
            f"payment_intent_present={bool(payment_intent)} "
            f"stripe_key_present={bool(api_key)}"
        )
        return False

    try:
        import stripe as stripe_lib

        stripe_lib.Refund.create(
            payment_intent=payment_intent,
            reason="duplicate",
            metadata={
                "source": "founding",
                "reason": "cap_violation_race",
                "session_id": sid or "",
            },
            api_key=api_key,
        )
        logger.info(
            f"founding race guard: refund issued — session_id={sid} payment_intent={payment_intent}"
        )
        return True
    except Exception as e:
        logger.error(
            f"founding race guard: refund failed — session_id={sid} err={e}"
        )
        return False


def _send_cap_violation_email(sb, session: Any) -> None:
    """Queue an apology email to the cap-violated founder. Never raises."""
    sid = _session_id(session)
    customer_email = None
    if hasattr(session, "get"):
        customer_email = session.get("customer_email") or (
            session.get("customer_details", {}).get("email") if session.get("customer_details") else None
        )

    if not customer_email:
        # Try to recover from the lead row.
        try:
            res = (
                sb.table("founding_leads")
                .select("email")
                .eq("checkout_session_id", sid)
                .limit(1)
                .execute()
            )
            if res.data:
                customer_email = res.data[0].get("email")
        except Exception:
            pass

    if not customer_email:
        logger.warning(f"founding race guard: no email for cap-violation notice — session_id={sid}")
        return

    subject = "SmartLic Founding — vaga preenchida, reembolso em andamento"
    body_text = (
        "Olá!\n\n"
        "Você acabou de tentar fechar o programa SmartLic Founding (50 vagas, "
        "50% de desconto vitalício). Infelizmente, no exato momento em que "
        "seu pagamento foi processado, outra pessoa garantiu a última vaga.\n\n"
        "Já iniciamos o estorno integral do valor cobrado — deve aparecer no "
        "seu cartão em 5 a 10 dias úteis.\n\n"
        "O plano regular SmartLic Pro continua disponível em "
        "https://smartlic.tech/pricing. Se quiser, respondo este email "
        "pessoalmente para conversar sobre próximos passos.\n\n"
        "Tiago Sasaki — fundador SmartLic\n"
        "tiago.sasaki@confenge.com.br\n"
    )

    try:
        from email_service import send_email_async

        send_email_async(
            to=customer_email,
            subject=subject,
            html=f"<pre style='font-family: sans-serif; white-space: pre-wrap;'>{body_text}</pre>",
            tags=[{"name": "category", "value": "founding_cap_violation"}],
        )
        logger.info(
            f"founding race guard: cap-violation email queued — session_id={sid} email={customer_email}"
        )
    except Exception as e:
        logger.warning(f"founding race guard: email queue failed — session_id={sid} err={e}")


def _resolve_email_from_session(session: Any) -> str | None:
    """Extract customer email from a Stripe checkout session object."""
    if not hasattr(session, "get"):
        return None
    email = session.get("customer_email")
    if not email:
        customer_details = session.get("customer_details") or {}
        email = customer_details.get("email") if isinstance(customer_details, dict) else None
    return email or None


def _resolve_user_id_from_email(sb, email: str) -> str | None:
    """Look up profiles.id by email. Returns None if not found or on DB error."""
    try:
        res = (
            sb.table("profiles")
            .select("id")
            .eq("email", email)
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        if rows:
            return rows[0].get("id")
        return None
    except Exception as e:
        logger.error(f"founding lifetime: failed to resolve user_id for email={email} — {e}")
        return None


def _read_consulting_discount_pct(sb) -> int:
    """Read consulting_discount_pct from the active founding_policy row.

    Falls back to 50 (default) if the table is empty, the column is absent,
    or any DB error occurs — so the entitlement is never blocked by infra issues.
    """
    try:
        res = (
            sb.table("founding_policy")
            .select("consulting_discount_pct")
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        if rows and rows[0].get("consulting_discount_pct") is not None:
            return int(rows[0]["consulting_discount_pct"])
    except Exception as e:
        logger.warning(f"founding lifetime: failed to read consulting_discount_pct — {e} — using default 50")
    return 50


def _resolve_user_display_name(sb, user_id: str, fallback_email: str) -> str:
    """Return profiles.full_name for user_id, falling back to email prefix.

    Never raises — returns fallback_email on any DB error.
    """
    try:
        res = (
            sb.table("profiles")
            .select("full_name")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        if rows and rows[0].get("full_name"):
            return rows[0]["full_name"]
    except Exception as e:
        logger.warning(f"founding lifetime: could not resolve display name for user_id={user_id} — {e}")
    return fallback_email.split("@")[0]


def _dispatch_founders_welcome_email(email: str, user_name: str) -> None:
    """Fire-and-forget dispatch of the founders welcome email.

    Runs in a background daemon thread so it never blocks the webhook handler.
    Uses send_founders_welcome_email which enforces idempotency via
    founding_leads.welcome_sent_at — safe to call multiple times.

    Never raises.
    """
    def _send() -> None:
        try:
            from email_service import send_founders_welcome_email

            email_id = send_founders_welcome_email(user_email=email, user_name=user_name)
            if email_id:
                logger.info(
                    f"founding welcome email sent — email={email} email_id={email_id}"
                )
            else:
                logger.info(
                    f"founding welcome email skipped (already sent or no lead) — email={email}"
                )
        except Exception as exc:
            logger.error(f"founding welcome email dispatch failed — email={email} err={exc}")

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()


def _send_founding_invite(sb, email: str, lead_id: str | None, sid: str | None) -> None:
    """FOUND-CRIT-003: dispatch a Supabase magic-link invite when the founder
    has paid but has not yet created an account.

    Stamps ``founding_leads.magic_link_sent_at`` for idempotency so that
    re-delivery of the webhook does not send multiple invites.

    Never raises — the webhook must always return 200 to Stripe.
    """
    # Idempotency check — skip if invite was already sent for this lead.
    if lead_id:
        try:
            res = (
                sb.table("founding_leads")
                .select("magic_link_sent_at")
                .eq("id", lead_id)
                .limit(1)
                .execute()
            )
            rows = getattr(res, "data", None) or []
            if rows and rows[0].get("magic_link_sent_at"):
                logger.info(
                    f"founding invite: already sent — lead_id={lead_id} email={email}"
                )
                return
        except Exception as e:
            logger.warning(
                f"founding invite: idempotency check failed (proceeding) — "
                f"lead_id={lead_id} err={e}"
            )

    def _invite() -> None:
        try:
            sb.auth.admin.invite_user_by_email(
                email,
                options={
                    "redirect_to": "https://smartlic.tech/fundadores/obrigado",
                    "data": {"is_founder": True},
                },
            )
            logger.info(
                f"founding invite sent — email={email} lead_id={lead_id} session_id={sid}"
            )
            # Stamp magic_link_sent_at for idempotency on webhook re-delivery.
            if lead_id:
                try:
                    sb.table("founding_leads").update({
                        "magic_link_sent_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", lead_id).execute()
                except Exception as stamp_err:
                    logger.warning(
                        f"founding invite: failed to stamp magic_link_sent_at — "
                        f"lead_id={lead_id} err={stamp_err}"
                    )
        except Exception as exc:
            logger.error(
                f"founding invite: Supabase invite_user_by_email failed — "
                f"email={email} lead_id={lead_id} session_id={sid} err={exc}"
            )

    thread = threading.Thread(target=_invite, daemon=True)
    thread.start()


def _activate_lifetime_founder_entitlement(sb, session: Any, lead_id: str | None) -> None:
    """Upsert the lifetime founder entitlement on ``profiles``.

    Sets is_founder=True, founder_since, founder_offer_version,
    founder_checkout_source, consulting_discount_pct, plan_type,
    and clears trial_expires_at.

    On success, dispatches the founders welcome email (fire-and-forget via
    background thread, idempotency enforced inside send_founders_welcome_email).

    FOUND-CRIT-003: if the user profile does not exist yet (founding is sold
    to unauthenticated visitors), dispatches a Supabase magic-link invite
    email instead of silently deferring.

    Never raises — a failure here must not break the 200 response to Stripe.
    """
    sid = _session_id(session)
    metadata = (session.get("metadata") or {}) if hasattr(session, "get") else {}

    email = _resolve_email_from_session(session)
    if not email:
        logger.warning(
            f"founding lifetime: cannot activate — no email in session_id={sid}"
        )
        return

    user_id = _resolve_user_id_from_email(sb, email)
    if not user_id:
        logger.info(
            f"founding lifetime activation deferred — user signup pending, dispatching invite "
            f"(session_id={sid} email={email} lead_id={lead_id})"
        )
        # FOUND-CRIT-003: send Supabase magic-link invite so the buyer can sign up.
        _send_founding_invite(sb, email=email, lead_id=lead_id, sid=sid)
        return

    consulting_discount_pct = _read_consulting_discount_pct(sb)

    offer_version = metadata.get("offer_version") or "v2"
    checkout_source = metadata.get("checkout_source") or "founding_page"

    entitlement_payload: dict[str, Any] = {
        "is_founder": True,
        "founder_since": datetime.now(timezone.utc).isoformat(),
        "founder_offer_version": offer_version,
        "founder_checkout_source": checkout_source,
        "consulting_discount_pct": consulting_discount_pct,
        "plan_type": "smartlic_pro",
        "trial_expires_at": None,
    }

    try:
        sb.table("profiles").update(entitlement_payload).eq("id", user_id).execute()
        logger.info(
            f"founding lifetime activated — user_id={user_id} lead_id={lead_id} "
            f"session_id={sid} offer_version={offer_version} "
            f"consulting_discount_pct={consulting_discount_pct}"
        )
        # Dispatch founders welcome email after successful entitlement activation.
        # Fire-and-forget via background thread — never blocks the webhook response.
        user_name = _resolve_user_display_name(sb, user_id, email)
        _dispatch_founders_welcome_email(email=email, user_name=user_name)
    except Exception as e:
        logger.error(
            f"founding lifetime: profiles upsert failed — user_id={user_id} "
            f"session_id={sid} err={e}"
        )


def mark_founding_lead_completed(sb, session: Any) -> None:
    """Update founding_leads row when Stripe confirms checkout completion.

    BIZ-FOUND-002 race guard:
    - After flipping to ``completed``, re-runs ``check_founding_availability()``.
    - If the RPC reports ``founding_cap_reached``, reverts the row to
      ``checkout_status='cap_violated'``, refunds via Stripe, and emails the
      customer.

    Idempotent on the happy path: if no row matches the session id, logs a
    warning and returns. Silent on DB errors so it never breaks the main
    checkout flow.
    """
    if not _is_founding_session(session):
        return

    sid = _session_id(session)
    if not sid:
        logger.warning("Founding completed event missing session id — skipping")
        return

    payload = {
        "checkout_status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "stripe_customer_id": session.get("customer"),
    }

    lead_id: str | None = None
    try:
        result = (
            sb.table("founding_leads")
            .update(payload)
            .eq("checkout_session_id", sid)
            .execute()
        )
        updated = len(result.data or [])
        if updated == 0:
            logger.warning(
                f"Founding lead row not found for session_id={sid} — Stripe fired "
                f"completed before our backend persisted the lead. Metadata may be missing."
            )
            return

        # Capture lead_id for downstream logging if the update returned the row.
        if result.data and isinstance(result.data, list) and result.data[0].get("id"):
            lead_id = str(result.data[0]["id"])

        logger.info(f"Founding lead marked completed: session_id={sid} rows={updated}")
    except Exception as e:
        logger.error(f"Failed to mark founding lead completed: session_id={sid} err={e}")
        founders_checkout_failed.labels(reason="db_error").inc()
        return

    # BIZ-FOUND-002 race guard — re-check availability AFTER the flip so the
    # count includes this event.
    snapshot = _check_availability_via_rpc(sb)
    if snapshot is None:
        # Fail safe: never auto-refund a paying customer when the DB is
        # uncooperative. Operator alerting (Sentry) can catch the gap.
        logger.warning(f"founding race guard: RPC unavailable, skipping cap re-check — session_id={sid}")
        founders_checkout_success.labels(offer_version="v2_lifetime").inc()
        return

    reason = snapshot.get("reason") or ""
    if reason in ("available", "founding_paused", "founding_disabled", "founding_deadline_passed"):
        # Either the cohort is healthy OR the disable reason is structural
        # (paused/disabled/deadline). In all those cases we already accepted
        # this checkout legitimately before the structural change — do NOT
        # refund post-hoc.
        # #785: activate lifetime founder entitlement on the happy path.
        _activate_lifetime_founder_entitlement(sb, session, lead_id)
        founders_checkout_success.labels(offer_version="v2_lifetime").inc()
        return

    # The only "race" we need to refund for is founding_cap_reached. For
    # founding_policy_missing or other infra problems, log + alert but do
    # not refund.
    if reason != "founding_cap_reached":
        logger.warning(
            f"founding race guard: unexpected post-completion reason={reason} session_id={sid}"
        )
        founders_checkout_success.labels(offer_version="v2_lifetime").inc()
        return

    logger.error(
        f"founding race guard: CAP VIOLATION DETECTED — session_id={sid} "
        f"seats_taken={snapshot.get('seats_total', 0) - snapshot.get('seats_remaining', 0)}/"
        f"{snapshot.get('seats_total', 0)} — initiating refund + email."
    )

    founders_checkout_failed.labels(reason="cap_violated").inc()
    refunded = _refund_session_charge(session)

    try:
        sb.table("founding_leads").update({
            "checkout_status": "cap_violated",
        }).eq("checkout_session_id", sid).execute()
    except Exception as e:
        logger.error(f"founding race guard: failed to revert lead row — session_id={sid} err={e}")

    _send_cap_violation_email(sb, session)

    if not refunded:
        # Operator must intervene — Sentry alert via error-level log.
        logger.error(
            f"founding race guard: REFUND FAILED — manual intervention required "
            f"session_id={sid}"
        )


def mark_founding_lead_abandoned(sb, session: Any) -> None:
    """Update founding_leads when Stripe times out / abandons the session."""
    if not _is_founding_session(session):
        return

    sid = _session_id(session)
    if not sid:
        logger.warning("Founding expired event missing session id — skipping")
        return

    try:
        result = (
            sb.table("founding_leads")
            .update({"checkout_status": "abandoned"})
            .eq("checkout_session_id", sid)
            .eq("checkout_status", "pending")
            .execute()
        )
        updated = len(result.data or [])
        logger.info(f"Founding lead marked abandoned: session_id={sid} rows={updated}")
    except Exception as e:
        logger.error(f"Failed to mark founding lead abandoned: session_id={sid} err={e}")
