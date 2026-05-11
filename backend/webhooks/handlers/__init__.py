"""
Stripe webhook event handlers — decomposed from webhooks/stripe.py (DEBT-307).

REF-MON-002 — Refactored to use ABC base + registry pattern. Each module
handles a group of related Stripe event types:

- checkout: checkout.session.completed, async_payment_succeeded/failed,
  checkout.session.expired
- subscription: customer.subscription.created/updated/deleted/trial_will_end
- invoice: invoice.payment_succeeded/failed/action_required
- stripe_product_price: product.updated, price.created/updated/deleted
- founding: BIZ-FOUND-002 lifetime entitlement side-effects

The ABC base + registry lives in ``_base.py`` and ``_registry.py``. Importing
``_registry`` triggers handler registration via the ``@webhook_handler``
decorator.
"""

from webhooks.handlers._base import HANDLERS_REGISTRY, WebhookHandler, webhook_handler

# Eager import of _registry populates HANDLERS_REGISTRY via decorators.
# Side-effect import; the names aren't used directly here.
from webhooks.handlers import _registry  # noqa: F401

from webhooks.handlers.checkout import (
    handle_async_payment_failed,
    handle_async_payment_succeeded,
    handle_checkout_session_completed,
)
from webhooks.handlers.invoice import (
    handle_invoice_payment_failed,
    handle_invoice_payment_succeeded,
    handle_payment_action_required,
)
from webhooks.handlers.subscription import (
    handle_subscription_deleted,
    handle_subscription_updated,
)

# Legacy: event-type -> handler-function mapping. Preserved for backward
# compatibility with any caller importing ``EVENT_HANDLERS`` directly. New
# code SHOULD use ``HANDLERS_REGISTRY`` (returns ``WebhookHandler`` instances).
EVENT_HANDLERS: dict[str, object] = {
    "checkout.session.completed": handle_checkout_session_completed,
    "checkout.session.async_payment_succeeded": handle_async_payment_succeeded,
    "checkout.session.async_payment_failed": handle_async_payment_failed,
    "customer.subscription.updated": handle_subscription_updated,
    "customer.subscription.deleted": handle_subscription_deleted,
    "invoice.payment_succeeded": handle_invoice_payment_succeeded,
    "invoice.payment_failed": handle_invoice_payment_failed,
    "invoice.payment_action_required": handle_payment_action_required,
}

__all__ = [
    "EVENT_HANDLERS",
    "HANDLERS_REGISTRY",
    "WebhookHandler",
    "webhook_handler",
    "handle_checkout_session_completed",
    "handle_async_payment_succeeded",
    "handle_async_payment_failed",
    "handle_subscription_updated",
    "handle_subscription_deleted",
    "handle_invoice_payment_succeeded",
    "handle_invoice_payment_failed",
    "handle_payment_action_required",
]
