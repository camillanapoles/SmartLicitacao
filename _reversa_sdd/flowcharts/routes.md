# Flowchart — Módulo `routes`

> Gerado pelo **Reversa Archaeologist** em 2026-04-27 · Confiança 🟢 CONFIRMADO

## Routing pipeline (FastAPI lifespan)

```mermaid
flowchart TD
    A[uvicorn main:app] --> B[startup.app_factory.create_app]
    B --> C[middleware_setup: CORS, RequestID, Sentry, RateLimit]
    C --> D[exception_handlers]
    D --> E[lifespan startup: register_all_cron_tasks + DB schema check]
    E --> F[register_routes app]
    F --> G[health_core_router root]
    F --> H[for r in _v1_routers: include_router prefix=/v1]
    F --> I[admin_trace, admin_cron, admin_llm_cost, slo self-prefixed]
    F --> J[stripe_webhook_router root /webhooks/stripe]
    G --> X[/health/live, /health/ready, /sources/health]
    H --> Y[~150 endpoints sob /v1/*]
    I --> Z[~10 endpoints /v1/admin/*]
```

## Auth dependency tree

```mermaid
flowchart TD
    R[Endpoint] --> A{Depends?}
    A -->|require_auth| AA[auth.require_auth]
    AA --> AB[extrai Bearer token]
    AB --> AC[L1 cache 60s LRU]
    AC -->|miss| AD[L2 Redis 5min]
    AD -->|miss| AE[validate JWT 3-strategy: JWKS ES256 > PEM > HS256]
    AE --> AF[user dict: id, email, plan_type, ...]
    AC -->|hit| AF
    AD -->|hit| AF
    AF --> R
    A -->|sem auth| RP[Rota pública: observatorio, sitemaps, calculadora, lead_capture, ...]
```

## Request → Response

```mermaid
sequenceDiagram
    participant C as Client (Next.js proxy)
    participant M as Middleware (CORS, RateLimit, RequestID)
    participant R as Router /v1/*
    participant H as Handler async def
    participant S as Service (Supabase, Redis, Stripe, ...)

    C->>M: GET /v1/sectors
    M->>M: rate_limit token bucket per-user
    M->>M: inject X-Request-ID
    M->>R: dispatched
    R->>H: handler(user=Depends(require_auth), query=...)
    H->>S: await sb_execute / await stripe.Subscription.retrieve
    S-->>H: data
    H->>H: Pydantic response_model validation
    H-->>R: ResponseModel
    R-->>M: JSON
    M-->>C: 200
```

## Public vs authenticated routes

```mermaid
flowchart LR
    subgraph "Public (sem auth)"
        P1[observatorio]
        P2[blog_stats]
        P3[sectors_public, stats_public, dados_publicos, alertas_publicos]
        P4[empresa_publica, orgao_publico, contratos_publicos, municipios_publicos, itens_publicos, compliance_publicos]
        P5[sitemap_*]
        P6[calculadora, comparador, indice_municipal]
        P7[lead_capture]
        P8[share GET hash, emails/unsubscribe, trial_emails/unsubscribe + webhook]
        P9[health_core, health]
    end
    subgraph "Authenticated (require_auth)"
        A1[search, pipeline, alerts, sessions, messages, analytics, feedback]
        A2[user, billing, subscriptions, plans, founding, conta, trial_extension]
        A3[onboarding, mfa, organizations, partners, referral, relatorio]
        A4[bid_analysis, export, export_sheets, reports, share POST, emails/send-welcome, notifications]
    end
    subgraph "Admin only (require_admin)"
        AD1[admin/*]
        AD2[admin_trace, admin_cron, admin_llm_cost]
        AD3[slo, seo_admin]
        AD4[feature_flags admin]
        AD5[partners admin/*]
        AD6[trial-emails admin/*]
    end
    subgraph "Webhook (signature gated)"
        W1[stripe /webhooks/stripe]
        W2[trial_emails webhook resend HMAC]
    end
```
