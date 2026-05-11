# Webhook Handlers — ABC Base + Registry Pattern (REF-MON-002)

## Status

Active — introduced in REF-MON-002 (2026-05-11). Replaces the legacy if-elif
dispatch chain in `webhooks/stripe.py` while preserving 100% test
backward-compatibility (existing `@patch("webhooks.stripe._handle_*")` patches
continue to work).

## Motivation

The original `webhooks/stripe.py` mixed three concerns in a single dispatcher
function:

1. Signature validation (Stripe `construct_event` + envelope sanity).
2. Idempotency (atomic `INSERT ON CONFLICT DO NOTHING` into
   `stripe_webhook_events` + stuck-event recovery).
3. Routing (15+ branch if-elif chain calling one async function per event
   type).

Adding a new event type required editing the dispatcher; handler functions
varied in shape (async vs sync, dict vs `event` object) and there was no
common contract for cross-cutting concerns (logging, error envelope, retry
hooks).

## Design

### Layers

```
┌──────────────────────────────────────────────────────────────┐
│  webhooks/stripe.py  — HTTP entrypoint                       │
│  • signature verification                                    │
│  • dispatcher-level idempotency (stripe_webhook_events)      │
│  • registry lookup: HANDLERS_REGISTRY[event.type].process()  │
└──────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│  webhooks/handlers/_base.py                                  │
│  • WebhookHandler (ABC)                                      │
│  • @webhook_handler(event_type) decorator                    │
│  • HANDLERS_REGISTRY                                         │
└──────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│  webhooks/handlers/_registry.py                              │
│  • thin adapter classes per event type                       │
│  • each delegates to a free function in checkout.py/         │
│    subscription.py/invoice.py/founding.py/                   │
│    stripe_product_price.py                                   │
└──────────────────────────────────────────────────────────────┘
```

### `WebhookHandler` contract

```python
class WebhookHandler(ABC):
    event_type: ClassVar[str]                          # set per subclass

    async def handle(self, sb, event) -> None:         # template method
        # 1. claim idempotency (best-effort)
        # 2. await self.process(sb, event)

    @abstractmethod
    async def process(self, sb, event) -> None: ...   # subclass logic

    def idempotency_key(self, event) -> str:           # overridable
        return event.id                                # Stripe evt_... default
```

### Registry

`HANDLERS_REGISTRY: dict[str, WebhookHandler]` is populated at module-import
time via the `@webhook_handler(event_type)` decorator. Importing
`webhooks.handlers` triggers eager import of `_registry`, which registers all
adapter classes.

### Dispatcher integration

The if-elif chain in `webhooks/stripe.py:_process_event` is replaced by:

```python
handler = HANDLERS_REGISTRY.get(event.type)
if handler is None:
    logger.info(f"Unhandled event type: {event.type}")
    return
# Skip handle()'s own idempotency claim — the dispatcher above has already
# claimed stripe_webhook_events for this event.id. Calling handle() here
# would double-claim and skip processing.
await handler.process(sb, event)
```

`handle()` is reserved for callers **outside** the standard webhook
dispatcher (e.g. background reconciliation jobs that replay events from S3
backup) where the dispatcher-level claim does not apply.

## Two layers of idempotency — why?

| Layer            | Where                  | Mechanism                                 | Authoritative? |
|------------------|------------------------|-------------------------------------------|----------------|
| **Dispatcher**   | `webhooks/stripe.py`   | INSERT ON CONFLICT DO NOTHING + stuck>5m | YES            |
| **Handler ABC**  | `_base.WebhookHandler` | Same table, same mechanism, best-effort  | NO             |

The dispatcher layer is the production gate. Stripe retries hit the HTTP
endpoint, the claim fails atomically, and the second delivery returns
`{"status": "already_processed"}` without invoking any handler.

The ABC-layer claim exists to protect handlers that may be invoked from
*non-HTTP* code paths (reconciliation, manual replay tools, future event
queues). On any DB error during the ABC claim, the layer fails open and
allows `process()` to run — the dispatcher layer is still in front.

## Adding a new handler

1. Implement the business logic as an async function in one of the topical
   handler modules (`subscription.py`, `invoice.py`, ...). Keep it side-
   effect-free aside from the intended DB / Stripe / cache writes.

2. Re-export the function in `webhooks/stripe.py` with the conventional
   `_handle_<name>` alias so existing test patch points keep working:

   ```python
   from webhooks.handlers.subscription import (
       handle_my_new_event as _handle_my_new_event,
   )
   ```

3. Add a thin adapter class in `webhooks/handlers/_registry.py`:

   ```python
   @webhook_handler("customer.subscription.my_new_event")
   class MyNewEventHandler(WebhookHandler):
       event_type = "customer.subscription.my_new_event"

       async def process(self, sb, event):
           fn = _resolve("_handle_my_new_event")
           await fn(sb, event)
   ```

4. No dispatcher edit required — the registry pick-up is automatic.

## Test strategy

- `backend/tests/webhooks/test_webhook_base.py` — covers the ABC base in
  isolation: registry registration, idempotency_key override, replay
  skipping, fail-open on DB error.
- All existing tests in `test_stripe_webhook*.py`, `test_payment_failed_webhook.py`,
  `test_founding_webhook_*.py`, etc. continue to pass unchanged because:
  - Module-level `_handle_*` names in `webhooks/stripe.py` are preserved
    (re-exports unchanged).
  - The adapter classes resolve those names *lazily* inside `process()`, so
    `@patch("webhooks.stripe._handle_*")` decorators take effect.
  - The dispatcher-level idempotency table and flow are unchanged.

## File map

| Path                                            | Role                                          |
|-------------------------------------------------|-----------------------------------------------|
| `backend/webhooks/stripe.py`                    | HTTP route + dispatcher idempotency + registry lookup |
| `backend/webhooks/handlers/_base.py`            | `WebhookHandler` ABC + decorator + registry   |
| `backend/webhooks/handlers/_registry.py`        | Adapter classes (one per event type)          |
| `backend/webhooks/handlers/_shared.py`          | Shared helpers (`resolve_user_id`, cache invalidation) |
| `backend/webhooks/handlers/checkout.py`         | Checkout-family business logic                |
| `backend/webhooks/handlers/subscription.py`     | Subscription-family business logic            |
| `backend/webhooks/handlers/invoice.py`          | Invoice-family business logic                 |
| `backend/webhooks/handlers/founding.py`         | BIZ-FOUND-002 lifetime entitlement side-effects |
| `backend/webhooks/handlers/stripe_product_price.py` | BILL-SYNC-001 product/price sync         |
| `backend/tests/webhooks/test_webhook_base.py`   | ABC + registry unit tests                     |
| `docs/architecture/webhook-handlers.md`         | This document                                 |

## Related

- REF-MON-002 (this refactor)
- DEBT-307 (initial decomposition of webhooks/stripe.py into handler modules)
- SYS-024 (30s asyncio.wait_for timeout)
- STORY-CONV-003a (trial_will_end handling)
- BIZ-FOUND-002 (founding race guard)
- #630 (Intel Report payment_intent.payment_failed)
