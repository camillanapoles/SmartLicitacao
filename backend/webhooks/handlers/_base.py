"""
Webhook Handler ABC Base + Registry (REF-MON-002).

Provides a unified contract for Stripe webhook event handlers:

- ``WebhookHandler``: abstract base class with a template-method ``handle()``
  that wraps idempotency around the subclass's ``process()`` implementation.
- ``HANDLERS_REGISTRY``: dict mapping ``event_type`` -> handler instance.
- ``@webhook_handler(event_type)``: class decorator that instantiates the
  handler and registers it.

DESIGN NOTES
============
The actual atomic idempotency for Stripe webhooks lives at the *dispatcher*
level in ``webhooks/stripe.py`` (``stripe_webhook_events`` table + INSERT ON
CONFLICT DO NOTHING). This is the load-bearing mechanism — duplicate Stripe
retries are filtered before any handler runs.

The ``handle()`` template method here provides a **second, in-handler**
idempotency layer using the same table. This is useful for:

1. Handlers invoked outside the standard dispatcher (e.g. background
   reconciliation jobs that replay events).
2. Sub-handler steps that want their own idempotency key (override
   ``idempotency_key()`` to use e.g. ``invoice.id`` instead of ``event.id``).
3. New handlers added in the future that should self-protect.

For existing handlers wrapped via the registry, the dispatcher already gates
them; ``handle()`` is functionally a passthrough to ``process()`` because the
event will not reach ``handle()`` twice via the dispatcher path.

USAGE
=====

    from webhooks.handlers._base import WebhookHandler, webhook_handler

    @webhook_handler("customer.subscription.updated")
    class SubscriptionUpdatedHandler(WebhookHandler):
        event_type = "customer.subscription.updated"

        async def process(self, sb, event) -> None:
            # business logic here
            ...

The registry is then consumed by ``webhooks/stripe.py``::

    from webhooks.handlers._base import HANDLERS_REGISTRY
    handler = HANDLERS_REGISTRY.get(event.type)
    if handler:
        await handler.handle(sb, event)
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, ClassVar

from log_sanitizer import get_sanitized_logger
from pipeline.budget import _run_with_budget

logger = get_sanitized_logger(__name__)

# Per-query budget for in-handler idempotency writes. Matches the dispatcher
# constant in ``webhooks/stripe.py`` to keep both layers consistent.
_HANDLER_IDEMPOTENCY_BUDGET_S = 5.0


class WebhookHandler(ABC):
    """Abstract base for a single Stripe event-type handler.

    Subclasses MUST:
    - Set the ``event_type`` class attribute (string, e.g. ``"invoice.payment_succeeded"``).
    - Implement ``process(sb, event)`` with the actual business logic.

    Subclasses MAY:
    - Override ``idempotency_key(event)`` to use a stable business key
      (e.g. ``invoice.id``) instead of the default Stripe ``event.id``.
    """

    event_type: ClassVar[str] = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def handle(self, sb, event: Any) -> None:
        """Template method: claim idempotency -> process -> log.

        The dispatcher in ``webhooks/stripe.py`` already gates duplicates via
        ``stripe_webhook_events``. This method's claim is a best-effort second
        layer — if the claim fails (DB unavailable, table missing in tests),
        we still proceed to ``process()`` rather than dropping the event.
        """
        claimed = await self._claim_idempotency(sb, event)
        if not claimed:
            logger.info(
                "WebhookHandler.handle: duplicate idempotency_key, skipping process "
                f"event_type={self.event_type}"
            )
            return
        await self.process(sb, event)

    @abstractmethod
    async def process(self, sb, event: Any) -> None:
        """Implement the handler's business logic here. MUST be async."""
        raise NotImplementedError

    def idempotency_key(self, event: Any) -> str:
        """Return a stable string key for this event.

        Default: Stripe ``event.id`` (``evt_...``). Subclasses can override to
        use a business-level key (e.g. ``payment_intent.id`` or
        ``invoice.id``) when that gives stronger replay protection.
        """
        # Support both stripe.Event objects (attribute access) and plain dicts.
        if hasattr(event, "id"):
            return getattr(event, "id")
        if isinstance(event, dict):
            return event.get("id", "")
        return ""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _claim_idempotency(self, sb, event: Any) -> bool:
        """Best-effort INSERT ON CONFLICT DO NOTHING into stripe_webhook_events.

        Returns True if this is the first time we see this key, False if it
        was already claimed by a previous run. On any DB error returns True
        (fail-open) so the handler still runs — the dispatcher layer is the
        authoritative idempotency gate.
        """
        key = self.idempotency_key(event)
        if not key:
            # Nothing to dedup against; allow process() to run.
            return True

        now_iso = datetime.now(timezone.utc).isoformat()
        event_type = self.event_type or getattr(event, "type", "") or ""

        def _sync_claim():
            return sb.table("stripe_webhook_events").upsert(
                {
                    "id": key,
                    "type": event_type,
                    "status": "processing",
                    "received_at": now_iso,
                },
                on_conflict="id",
                ignore_duplicates=True,
            ).execute()

        try:
            result = await _run_with_budget(
                asyncio.to_thread(_sync_claim),
                budget=_HANDLER_IDEMPOTENCY_BUDGET_S,
                phase="route",
                source=f"webhook.handler.{self.event_type}.idempotency_claim",
            )
        except Exception as e:
            logger.warning(
                f"Idempotency claim failed (non-fatal, will process anyway): {e}"
            )
            return True

        data = getattr(result, "data", None)
        # upsert with ignore_duplicates=True returns empty data when the row
        # already existed.
        if not data:
            return False
        return True


# ----------------------------------------------------------------------
# Registry + decorator
# ----------------------------------------------------------------------

HANDLERS_REGISTRY: dict[str, WebhookHandler] = {}


def webhook_handler(event_type: str):
    """Class decorator: instantiate the handler and register it under event_type.

    Example::

        @webhook_handler("invoice.payment_succeeded")
        class InvoicePaymentSucceededHandler(WebhookHandler):
            event_type = "invoice.payment_succeeded"
            async def process(self, sb, event):
                ...
    """

    def decorator(cls):
        if not issubclass(cls, WebhookHandler):
            raise TypeError(
                f"@webhook_handler requires a WebhookHandler subclass, got {cls!r}"
            )
        # Ensure the class-level attribute is set even if the subclass omitted it.
        if not getattr(cls, "event_type", ""):
            cls.event_type = event_type
        instance = cls()
        if event_type in HANDLERS_REGISTRY:
            logger.warning(
                f"webhook_handler: overriding existing registration for {event_type}"
            )
        HANDLERS_REGISTRY[event_type] = instance
        return cls

    return decorator


__all__ = [
    "WebhookHandler",
    "HANDLERS_REGISTRY",
    "webhook_handler",
]
