# Flowchart — Módulo `webhook-abc` (REF-MON-002)

> Gerado pelo **Reversa Writer** em 2026-05-12

## 1. Stripe Webhook Dispatcher + ABC Handler

```mermaid
flowchart TD
    Stripe[Stripe POST /webhooks/stripe] --> Sig{stripe-signature header present?}
    Sig -->|missing| 400[HTTP 400]
    Sig -->|present| Verify{construct_event valid?}
    Verify -->|invalid sig| 400
    Verify -->|valid| Idem[INSERT stripe_webhook_events\nid=event.id ON CONFLICT DO NOTHING]
    Idem --> Dup{already exists?}
    Dup -->|processing + >5min| ReProc[reprocess · log WARN]
    Dup -->|completed/timeout| Done[HTTP 200 already_processed]
    Dup -->|no / reprocess| Dispatch[dispatch via HANDLERS_REGISTRY]
    ReProc --> Dispatch
    Dispatch --> Find{event.type in registry?}
    Find -->|no| Unsup[log unknown event · HTTP 200 OK]
    Find -->|yes| Handler[handler.handle(sb, event)]
    Handler --> Sub[WebhookHandler template method]
```

## 2. WebhookHandler ABC Template Method

```mermaid
sequenceDiagram
    participant D as Dispatcher (stripe.py)
    participant H as WebhookHandler.handle()
    participant P as WebhookHandler.process()
    participant DB as stripe_webhook_events

    D->>H: handle(sb, event)
    H->>H: idempotency_key(event)
    H->>DB: INSERT ON CONFLICT DO NOTHING
    DB-->>H: claimed? (True/False)
    alt not claimed (duplicate)
        H-->>D: return (skip)
    else claimed or fail-open
        H->>P: process(sb, event)
        P->>P: business logic (async)
        P-->>H: done
        H-->>D: return
    end
    D->>D: mark status=completed
```

## 3. Handler Registry (16 event types)

```mermaid
flowchart LR
    subgraph HANDLERS_REGISTRY
        C1[checkout.session.completed]
        C2[checkout.session.async_payment_succeeded]
        C3[checkout.session.async_payment_failed]
        C4[checkout.session.expired]
        S1[customer.subscription.created]
        S2[customer.subscription.updated]
        S3[customer.subscription.deleted]
        S4[customer.subscription.trial_will_end]
        I1[invoice.payment_succeeded]
        I2[invoice.payment_failed]
        I3[invoice.payment_action_required]
        I4[product.updated]
        I5[price.created]
        I6[price.updated]
        I7[price.deleted]
        I8[payment_intent.payment_failed]
    end
    C1 --> checkout.py
    C2 --> checkout.py
    C3 --> checkout.py
    C4 --> founding.py
    S1 --> subscription.py
    S2 --> subscription.py
    S3 --> subscription.py
    S4 --> subscription.py
    I1 --> invoice.py
    I2 --> invoice.py
    I3 --> invoice.py
    I4 --> stripe_product_price.py
    I5 --> stripe_product_price.py
    I6 --> stripe_product_price.py
    I7 --> stripe_product_price.py
    I8 --> checkout.py
```

## 4. In-Handler Idempotency Flow

```mermaid
flowchart TD
    Process[handler.handle] --> Key[idempotency_key(event)]
    Key --> Upsert[INSERT stripe_webhook_events upsert ignore_duplicates]
    Upsert --> Result{data returned?}
    Result -->|sim (fresh claim)| Run[run process()]
    Result -->|não (already existed)| Skip[skip · log duplicate]
    Result -->|DB error| FailOpen[return True · proceed anyway]
```
