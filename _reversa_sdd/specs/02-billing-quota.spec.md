# Spec: Billing & Quota

> Spec executável (SDD) gerada pelo **Reversa Writer** em 2026-04-27
> Confiança: 🟢 CONFIRMADO

## Component
- **ID**: `billing-quota`
- **Path**: `backend/services/billing.py`, `backend/quota/`, `backend/webhooks/stripe.py`, `backend/webhooks/handlers/`, `backend/routes/billing.py`, `backend/routes/founding.py`, `backend/routes/subscriptions.py`, `backend/routes/conta.py`, `backend/routes/trial_extension.py`

## Purpose

Gerenciar planos, trial 14 dias, subscriptions Stripe, quota mensal atomic, plan capabilities, founding plan early-adopter, dunning, reconciliation Stripe-DB.

## Plan Catalog (9 planos)

| Plan ID | Nome | Mensal | Semestral 10% off | Anual 25% off |
|---------|------|--------|-------------------|---------------|
| `free_trial` | Trial 14d sem cartão | — | — | — |
| `smartlic_pro` | SmartLic Pro | R$397 | R$357/mês | R$297/mês |
| `smartlic_consultoria` | Consultoria | R$997 | R$897/mês (10%) | R$797/mês (20%) |
| `founding` | Founding (early) | (lifetime discount) | — | — |
| (5 outros: variações antigas + master) | | | | |

Source of truth: `plan_billing_periods` table (Stripe-synced).

## Invariants

1. **Trial 14d** — `trial_expires_at = signup + 14d`. Sem cartão.
2. **Grace period 3d** (`SUBSCRIPTION_GRACE_DAYS=3`) — gap Stripe→DB tolerado
3. **"Fail to last known plan"** — never fallback `free_trial` em transient DB error (UX downgrade prevention)
4. **Atomic quota** — single SQL UPDATE com WHERE clause race-safe (`check_and_increment_quota_atomic`)
5. **Stripe webhook idempotência** — `events_processed` table dedup por `stripe_event_id`
6. **`profiles.plan_type` sync** — TODOS webhook handlers DEVEM atualizar
7. **Master/Admin bypass** — `is_master=true` ou `is_admin=true` bypassa quota+trial+pipeline_limit

## Functional Requirements

- **FR-1**: `GET /v1/plans` retorna catálogo público
- **FR-2**: `POST /v1/checkout` cria Stripe Checkout Session (success_url, cancel_url, metadata user_id)
- **FR-3**: `POST /v1/billing-portal` retorna URL portal customer-self-service
- **FR-4**: `GET /v1/subscription/status` retorna status atual (active, past_due, canceled, expired, ...)
- **FR-5**: `POST /v1/billing/setup-intent` retorna client_secret para SCA card setup
- **FR-6**: `POST /webhooks/stripe` processa 12 eventos: checkout.session.completed, customer.subscription.{created,updated,deleted}, invoice.{paid,payment_failed,upcoming}, customer.{updated,deleted}, charge.refunded
- **FR-7**: `check_quota(user_id) → QuotaInfo` — capabilities + uso atual + plan_id
- **FR-8**: `require_active_plan(user)` raise 403 trial_expired se trial expirou
- **FR-9**: Pipeline limit 5 itens via `_check_pipeline_limit` (trial only)
- **FR-10**: Dunning: Pre-dunning email 7d antes cartão expira; Day 1/3/7/14 dunning sequence; Day 14 cancel
- **FR-11**: Reconciliation cron: detecta drift Stripe ↔ DB, corrige `plan_type` + `subscription_status`
- **FR-12**: Trial extension via `POST /v1/trial/extend` (admin or specific user)
- **FR-13**: Cancel via `POST /v1/api/subscriptions/cancel` + feedback survey
- **FR-14**: Founding plan via `POST /v1/founding/checkout` (early adopter signup)

## Non-Functional Requirements

- **NFR-1**: Webhook latency p95 <500ms (sem DB lookups overhead)
- **NFR-2**: Stripe webhook 30s hard timeout (`WEBHOOK_DB_TIMEOUT_S`)
- **NFR-3**: Plan status cache 5min Redis (`PLAN_STATUS_CACHE_TTL=300`)
- **NFR-4**: Plan capabilities cache 5min LRU 1000 entries
- **NFR-5**: Reconciliation diário tolerável até 1h drift
- **NFR-6**: 0 over-charge — quota check ATOMIC com row lock

## Constraints

- **CON-1**: Stripe handles proration (NUNCA custom prorata code)
- **CON-2**: Webhook signature verify via `stripe.Webhook.construct_event` antes de qualquer DB write
- **CON-3**: Single registration `/webhooks/stripe` (DEBT-324) — não em `_v1_routers`
- **CON-4**: `MIXPANEL_TOKEN` required em prod (memory: backend gap até piped-cray)

## Acceptance Criteria

- AC-1: Trial signup gera `profiles.plan_type='free_trial' AND trial_expires_at = now+14d`
- AC-2: `POST /v1/checkout` retorna `{checkout_url}` com Stripe session válida
- AC-3: Webhook `checkout.session.completed` cria/atualiza `user_subscriptions` + `profiles.plan_type` em <500ms
- AC-4: Webhook `customer.subscription.deleted` mantém grace 3d antes de bloquear acesso
- AC-5: Atomic quota `check_and_increment_quota_atomic` race-safe (10 concurrent calls cap em limit)
- AC-6: `require_active_plan` raise 403 trial_expired quando `trial_expires_at < now`
- AC-7: Reconciliation detecta + corrige drift > 5min entre Stripe e DB

## Errors

| Code | HTTP | Trigger |
|------|------|---------|
| `trial_expired` | 403 | trial_expires_at < now |
| `quota_exceeded` | 429 | uso >= limit |
| `pipeline_limit_exceeded` | 403 | trial pipeline >= 5 |
| `pipeline_not_available` | 403 | caps.allow_pipeline=false |
| `webhook_signature_invalid` | 400 | Stripe signature mismatch |
| `webhook_processing_error` | 500 | DB error in handler |
| `subscription_not_found` | 404 | user sem subscription |

## Code traceability

- `backend/services/billing.py` — Stripe SDK wrapper, plan defs, checkout/portal
- `backend/quota/quota_core.py` — `check_quota`, `QuotaInfo` dataclass
- `backend/quota/quota_atomic.py` — `check_and_increment_quota_atomic`
- `backend/quota/plan_enforcement.py` — `require_active_plan`, capabilities matrix
- `backend/quota/plan_auth.py` — auth helpers
- `backend/quota/session_tracker.py` — concurrent search cap
- `backend/webhooks/stripe.py` — main webhook router, signature verify
- `backend/webhooks/handlers/checkout.py` — `checkout.session.completed`
- `backend/webhooks/handlers/subscription.py` — subscription created/updated/deleted
- `backend/webhooks/handlers/invoice.py` — invoice paid/failed/upcoming
- `backend/webhooks/handlers/founding.py` — founding plan
- `backend/routes/billing.py` — 5 endpoints
- `backend/routes/founding.py` — founding checkout
- `backend/routes/subscriptions.py` — update-billing-period, cancel, cancel-feedback
- `backend/routes/conta.py` — cancelar-trial info+ação
- `backend/routes/trial_extension.py` — extend, extensions
- `backend/jobs/cron/billing.py` — reconciliation, pre-dunning, revenue share, plan reconciliation, stripe events purge

## Dependencies

- Stripe SDK
- Supabase (`profiles`, `user_subscriptions`, `plan_billing_periods`, `plan_features`, `monthly_quota`, `trial_extensions`, `events_processed`/`stripe_webhook_events`)
- Redis (cache + locks)
- Resend (dunning emails via `templates/emails/dunning.py`, `boleto_reminder.py`)
- Mixpanel (paywall_hit, trial_started, conversion events)
