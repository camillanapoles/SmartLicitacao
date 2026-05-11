"""
Webhook handler registry adapters (REF-MON-002).

Wraps the existing free-function handlers in ``WebhookHandler`` subclasses
and registers them under ``HANDLERS_REGISTRY``. The dispatcher in
``webhooks/stripe.py`` consumes this registry instead of an if-elif chain.

The adapter classes deliberately delegate to the existing functions via
``webhooks.stripe`` module attributes (e.g. ``_handle_subscription_updated``)
so test patches of the form::

    @patch("webhooks.stripe._handle_subscription_updated")

continue to work unchanged. This preserves the entire blast radius of the
brownfield test suite while introducing the ABC + registry pattern.
"""

from __future__ import annotations

from typing import Any

from log_sanitizer import get_sanitized_logger
from webhooks.handlers._base import WebhookHandler, webhook_handler

logger = get_sanitized_logger(__name__)


def _resolve(attr_name: str):
    """Late-bind the dispatcher-level function reference.

    Imported lazily inside each ``process()`` call so that test patches of
    ``webhooks.stripe.<attr_name>`` take effect (Python's @patch replaces
    the name in that module's namespace; resolving late picks up the patch).
    """
    import webhooks.stripe as ws  # local import to avoid circulars at module load
    return getattr(ws, attr_name)


# ---------------------------------------------------------------------------
# Checkout family
# ---------------------------------------------------------------------------


@webhook_handler("checkout.session.completed")
class CheckoutSessionCompletedHandler(WebhookHandler):
    event_type = "checkout.session.completed"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_checkout_session_completed")
        await fn(sb, event)


@webhook_handler("checkout.session.async_payment_succeeded")
class CheckoutAsyncPaymentSucceededHandler(WebhookHandler):
    event_type = "checkout.session.async_payment_succeeded"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_async_payment_succeeded")
        await fn(sb, event)


@webhook_handler("checkout.session.async_payment_failed")
class CheckoutAsyncPaymentFailedHandler(WebhookHandler):
    event_type = "checkout.session.async_payment_failed"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_async_payment_failed")
        await fn(sb, event)


@webhook_handler("checkout.session.expired")
class CheckoutSessionExpiredHandler(WebhookHandler):
    """STORY-BIZ-001: mark founding lead as abandoned when Stripe session expires.

    No-op for non-founding sessions (metadata filter inside the function).
    The underlying function is synchronous; wrap it in an async shim here.
    """

    event_type = "checkout.session.expired"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_founding_checkout_expired_raw")
        fn(sb, event.data.object)


# ---------------------------------------------------------------------------
# Subscription family
# ---------------------------------------------------------------------------


@webhook_handler("customer.subscription.created")
class SubscriptionCreatedHandler(WebhookHandler):
    event_type = "customer.subscription.created"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_subscription_created")
        await fn(sb, event)


@webhook_handler("customer.subscription.updated")
class SubscriptionUpdatedHandler(WebhookHandler):
    event_type = "customer.subscription.updated"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_subscription_updated")
        await fn(sb, event)


@webhook_handler("customer.subscription.deleted")
class SubscriptionDeletedHandler(WebhookHandler):
    event_type = "customer.subscription.deleted"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_subscription_deleted")
        await fn(sb, event)


@webhook_handler("customer.subscription.trial_will_end")
class SubscriptionTrialWillEndHandler(WebhookHandler):
    """STORY-CONV-003a AC4: Stripe fires 3d before trial_end."""

    event_type = "customer.subscription.trial_will_end"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_subscription_trial_will_end")
        await fn(sb, event)


# ---------------------------------------------------------------------------
# Invoice family
# ---------------------------------------------------------------------------


@webhook_handler("invoice.payment_succeeded")
class InvoicePaymentSucceededHandler(WebhookHandler):
    event_type = "invoice.payment_succeeded"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_invoice_payment_succeeded")
        await fn(sb, event)


@webhook_handler("invoice.payment_failed")
class InvoicePaymentFailedHandler(WebhookHandler):
    event_type = "invoice.payment_failed"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_invoice_payment_failed")
        await fn(sb, event)


@webhook_handler("invoice.payment_action_required")
class InvoicePaymentActionRequiredHandler(WebhookHandler):
    event_type = "invoice.payment_action_required"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_payment_action_required")
        await fn(sb, event)


# ---------------------------------------------------------------------------
# Product / Price family (BILL-SYNC-001)
# ---------------------------------------------------------------------------


@webhook_handler("product.updated")
class ProductUpdatedHandler(WebhookHandler):
    event_type = "product.updated"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_product_updated")
        await fn(sb, event)


@webhook_handler("price.created")
class PriceCreatedHandler(WebhookHandler):
    event_type = "price.created"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_price_created")
        await fn(sb, event)


@webhook_handler("price.updated")
class PriceUpdatedHandler(WebhookHandler):
    event_type = "price.updated"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_price_updated")
        await fn(sb, event)


@webhook_handler("price.deleted")
class PriceDeletedHandler(WebhookHandler):
    event_type = "price.deleted"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_price_deleted")
        await fn(sb, event)


# ---------------------------------------------------------------------------
# Intel Report one-time payment failure (#630)
# ---------------------------------------------------------------------------


@webhook_handler("payment_intent.payment_failed")
class IntelReportPaymentFailedHandler(WebhookHandler):
    """#630: Intel Report one-time payment failure.

    NOTE: Stripe Dashboard webhook config must include
    ``payment_intent.payment_failed``.
    """

    event_type = "payment_intent.payment_failed"

    async def process(self, sb, event: Any) -> None:
        fn = _resolve("_handle_intel_report_payment_failed")
        await fn(sb, event)


__all__ = [
    "CheckoutSessionCompletedHandler",
    "CheckoutAsyncPaymentSucceededHandler",
    "CheckoutAsyncPaymentFailedHandler",
    "CheckoutSessionExpiredHandler",
    "SubscriptionCreatedHandler",
    "SubscriptionUpdatedHandler",
    "SubscriptionDeletedHandler",
    "SubscriptionTrialWillEndHandler",
    "InvoicePaymentSucceededHandler",
    "InvoicePaymentFailedHandler",
    "InvoicePaymentActionRequiredHandler",
    "ProductUpdatedHandler",
    "PriceCreatedHandler",
    "PriceUpdatedHandler",
    "PriceDeletedHandler",
    "IntelReportPaymentFailedHandler",
]
