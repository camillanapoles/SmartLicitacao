---
id: ADR-WEBHOOK-ABC-001
title: Webhook Handler ABC Base Pattern (REF-MON-002)
status: Accepted
authors: [@architect, @dev]
date: 2026-05-12
deciders: [Tiago Sasaki]
---

# ADR-WEBHOOK-ABC-001: Webhook Handler ABC Base Pattern (REF-MON-002)

## Context

SmartLic processes webhooks from multiple external services — Stripe billing events, Resend email delivery status, and potentially more in the future (e.g. Slack notifications, partner API callbacks). Each webhook source shares a common lifecycle:

1. **Signature verification**: the incoming request must be authenticated (Stripe HMAC, Resend HMAC, etc.)
2. **Idempotency check**: duplicate events (from retries or at-least-once delivery) must be detected and dropped without side effects
3. **Business logic execution**: the actual handler logic specific to each event type
4. **Error handling**: failed webhooks must be logged, alerted, and recoverable
5. **Audit trail**: every processed event must leave a trace for debugging and compliance

Before REF-MON-002, Stripe webhook handling was a single file (`backend/webhooks/stripe.py`) with inline handler functions for each event type. Every new event type required copy-pasting the same `try/except/log/audit` wrapper. The Reversa Architect analysis identified this as an opportunity for the **ABC / Template Method pattern** (ADR-ARCH-001 §3.2).

The Stripe webhook dispatcher processes 12 distinct event types across billing, subscriptions, invoices, founding purchases, and Intel Reports. Each handler must:
- Validate the Stripe event
- Check idempotency (via `stripe_webhook_events` table)
- Execute business logic (update `profiles.plan_type`, sync subscription status, record purchase)
- Log success or failure with structured context

## Decision

1. **WebhookHandler ABC** (`backend/webhooks/handlers/_base.py`): an abstract base class that provides a template method `handle()` wrapping idempotency around the subclass's `process()` implementation.

   ```python
   class WebhookHandler(ABC):
       event_type: ClassVar[str] = ""

       async def handle(self, sb, event) -> None:
           """Template method: claim idempotency -> process -> log."""
           claimed = await self._claim_idempotency(sb, event)
           if not claimed:
               return  # duplicate, skip
           await self.process(sb, event)

       @abstractmethod
       async def process(self, sb, event) -> None:
           """Implement the handler's business logic here."""
   ```

2. **Two-layer idempotency**: the dispatcher in `webhooks/stripe.py` performs the load-bearing idempotency check (INSERT ON CONFLICT DO NOTHING on `stripe_webhook_events` before any handler runs). The ABC's `_claim_idempotency` provides a second layer for handlers invoked outside the dispatcher (background reconciliation jobs, replay).

3. **Handler Registry**: `HANDLERS_REGISTRY` maps `event_type` strings to handler instances, populated by the `@webhook_handler(event_type)` class decorator. The dispatcher consumes the registry:

   ```python
   handler = HANDLERS_REGISTRY.get(event.type)
   if handler:
       await handler.handle(sb, event)
   ```

4. **Current handler implementations** in `backend/webhooks/handlers/`:

   | Handler | File | Event Types |
   |---------|------|-------------|
   | CheckoutHandler | `checkout.py` | `checkout.session.completed`, `checkout.session.async_payment_succeeded/failed`, intel report payment failed |
   | SubscriptionHandler | `subscription.py` | `customer.subscription.created/updated/deleted`, `customer.subscription.trial_will_end` |
   | InvoiceHandler | `invoice.py` | `invoice.payment_succeeded/failed`, `payment_intent.payment_action_required` |
   | FoundingHandler | `founding.py` | founding customer checkout events |
   | StripeProductPriceHandler | `stripe_product_price.py` | `product.created/updated`, `price.created/updated` |

5. **Separate dispatcher files** (not in the ABC hierarchy): `backend/webhooks/stripe.py` is the Stripe-specific dispatcher that handles signature verification, dispatcher-level idempotency, timeout protection (30s `asyncio.wait_for`), and event logging. The ABC handles only in-handler concerns.

6. **Resend webhook** (`backend/routes/trial_emails.py`): uses HMAC signature verification (`_verify_svix_signature`) independent of the ABC. This is because the Resend webhook lifecycle (verify signature -> update delivery status) is simple enough that the ABC abstraction adds overhead without benefit. If Resend webhooks grow additional event types, they should be refactored into the ABC pattern.

### Dead Letter Queue

Failed webhooks (after all retries are exhausted) are recorded in a dead letter queue:

- **Stripe DLQ**: failed webhook processing (e.g. Stripe API returns 500, or handler raises unexpected exception) is retried 3 times with exponential backoff (30s, 2min, 5min). If all retries fail, the event is logged to Sentry with fingerprint `["webhook_dlq", event_type]` and recorded in the `stripe_webhook_events` table with status `failed`. Manual recovery via admin replay endpoint.
- **Trial email DLQ**: `backend/services/trial_email_dlq.py` implements a separate DLQ for Resend email delivery failures (STORY-418). Uses the same exponential backoff pattern but with its own table (`trial_email_dlq`).

The DLQ pattern across both implementations shares:
- Exponential backoff with configurable max retries
- Structured logging with event context
- Sentry alert on final exhaustion
- Manual re-queue support for ops recovery

## Consequences

### Positive

- Adding a new Stripe event handler requires one file (~20 lines) and a decorator. No changes to the dispatcher, no copy-paste of try/except/log wrapper.
- The ABC enforces the `handle()` template lifecycle: every handler gets idempotency and audit logging for free.
- The registry is introspectable: `HANDLERS_REGISTRY.keys()` returns all registered event types, useful for test coverage reports and admin dashboards.
- Dispatcher and handler concerns are cleanly separated: signature verification stays in the dispatcher, business logic stays in the handler.
- DLQ provides a recovery path for transient failures without losing events.

### Negative / Risks

- **R1 (Low)**: ABC inheritance hierarchy can proliferate if handlers grow divergent needs. Mitigation: the ABC contract is minimal (one abstract method). Handlers that need different scaffolding should use composition, not inheritance.
- **R2 (Low)**: Two-layer idempotency (dispatcher + handler) means the same dedup logic exists in two places. Mitigation: the handler layer is explicitly documented as a best-effort second layer — it fail-opens (allows processing) on DB error so it never blocks legitimate events.
- **R3 (Low)**: The Resend webhook does NOT use the ABC, creating a divergence. If Resend grows to 5+ event types, it should be refactored into the pattern. Mitigation: this ADR documents the expectation; tech debt tracked as a follow-up issue.
- **R4 (Low)**: The DLQ implementations for Stripe and trial emails are separate, with different tables and recovery mechanisms. Mitigation: both follow the same backoff pattern; a unified DLQ framework is tracked for future consolidation.

### Neutral

- The exist-ok marker `# rls-exempt: webhook` on RLS-exempt tables used by webhook handlers (stripe_webhook_events, trial_email_dlq) follows the convention established in ADR-RLS-MANDATORY-001.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| **Continue with inline handler functions** | The pre-REF-MON-002 state. Every new event type required copy-pasting the same try/except/log/idempotency wrapper. Violates DRY and is error-prone. |
| **Pluggable event bus (publish/subscribe)** | Over-engineered for 12 event types. Pub/sub makes sense when producers and consumers are decoupled services; here, the dispatcher and handler share the same process and database. |
| **Middleware-based approach (decorator chain)** | Would require each handler to be decorated with `@idempotent`, `@audit_log`, etc. The ABC keeps the lifecycle explicit in one place rather than scattered across decorators. |
| **Single handler function with event-type dispatch** | This was the pre-refactor state — a single function with an `if/elif/else` chain for all 12 event types. Already exceeded 400 LOC and growing. |

## References

- ADR-ARCH-001 §3.2 — ABC / Template Method pattern canonical reference
- `backend/webhooks/handlers/_base.py` — WebhookHandler ABC + registry
- `backend/webhooks/stripe.py` — Stripe dispatcher
- `backend/webhooks/handlers/` — Handler implementations
- `backend/services/trial_email_dlq.py` — Trial email dead letter queue
- `backend/routes/trial_emails.py` — Resend webhook (HMAC-based)
- Issue REF-MON-002 — ABC pattern for webhook handlers
- Story STORY-418 — Trial email pipeline resilience + DLQ
