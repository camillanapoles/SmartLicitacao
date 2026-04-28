"""STORY-BIZ-001 + BIZ-FOUND-002: side-effect handlers that keep
``founding_leads`` in sync with Stripe checkout-session lifecycle events,
plus the cap-violation race guard introduced by BIZ-FOUND-002.

Invoked from ``webhooks.handlers.checkout.handle_checkout_session_completed``
and from the webhook dispatcher in ``webhooks.stripe`` when session metadata
contains ``source='founding'``.

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
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from log_sanitizer import get_sanitized_logger

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
        "tiago@smartlic.tech\n"
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

        logger.info(f"Founding lead marked completed: session_id={sid} rows={updated}")
    except Exception as e:
        logger.error(f"Failed to mark founding lead completed: session_id={sid} err={e}")
        return

    # BIZ-FOUND-002 race guard — re-check availability AFTER the flip so the
    # count includes this event.
    snapshot = _check_availability_via_rpc(sb)
    if snapshot is None:
        # Fail safe: never auto-refund a paying customer when the DB is
        # uncooperative. Operator alerting (Sentry) can catch the gap.
        logger.warning(f"founding race guard: RPC unavailable, skipping cap re-check — session_id={sid}")
        return

    reason = snapshot.get("reason") or ""
    if reason in ("available", "founding_paused", "founding_disabled", "founding_deadline_passed"):
        # Either the cohort is healthy OR the disable reason is structural
        # (paused/disabled/deadline). In all those cases we already accepted
        # this checkout legitimately before the structural change — do NOT
        # refund post-hoc.
        return

    # The only "race" we need to refund for is founding_cap_reached. For
    # founding_policy_missing or other infra problems, log + alert but do
    # not refund.
    if reason != "founding_cap_reached":
        logger.warning(
            f"founding race guard: unexpected post-completion reason={reason} session_id={sid}"
        )
        return

    logger.error(
        f"founding race guard: CAP VIOLATION DETECTED — session_id={sid} "
        f"seats_taken={snapshot.get('seats_total', 0) - snapshot.get('seats_remaining', 0)}/"
        f"{snapshot.get('seats_total', 0)} — initiating refund + email."
    )

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
