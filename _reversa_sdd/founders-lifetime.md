# Founders Lifetime — Módulo Fundadores (R$997 one-time)

> Gerado pelo **Reversa Writer** em 2026-05-12
> Source-of-truth: `backend/routes/founding.py`, `backend/routes/founders.py`, `backend/routes/founders_hall.py`, `backend/routes/upgrade_to_lifetime.py`, `backend/webhooks/handlers/founding.py`, `backend/jobs/cron/founders_auto_disable.py`, `backend/services/trial_email_sequence.py`, `backend/email_service.py`, docs em `docs/founders-policy.md`, `docs/adr/ADR-BIZ-FOUND-002-founding-policy.md`

## Overview

Programa Fundadores SmartLic: early adopters pagam R$997 one-time e recebem acesso vitalício ao SmartLic Pro. Cap de 50 vagas. Deadline 30/06/2026.

### Dados

| Item | Valor |
|------|-------|
| Preço | R$997 one-time (lifetime) |
| Cap | 50 fundadores |
| Deadline | 30/06/2026 23:59 BRT |
| Offer version | `v2_lifetime` |
| Offer mode | `lifetime` |
| Stripe Price ID | `FOUNDING_ONE_TIME_PRICE_ID` env var |
| Checkout mode | `payment` (one-time, não subscription) |
| Payment methods | `card` + `boleto` |

## Arquitetura do Fluxo

```
User → /v1/founding/checkout → check_founding_availability() RPC (SELECT FOR UPDATE)
  ├─ available=false → 410 Gone
  └─ available=true → Stripe Checkout Session (mode=payment, line_items price_data R$997)
       └─ Stripe → checkout.session.completed (webhook)
            ├─ checkout.py: mark founding_leads.checkout_status='completed'
            ├─ founding.py: activate entitlement (profiles.is_founder=TRUE, plan_type='founding_member')
            ├─ email: founders_welcome (Resend)
            └─ auto-invite: invite_user_by_email (Supabase Auth)
```

## Endpoints

| Método | Rota | Auth | Propósito |
|--------|------|------|-----------|
| POST | `/v1/founding/checkout` | auth | Qualifying form → Stripe Checkout R$997 |
| GET | `/v1/founding/availability` | anon | Public seat counter / countdown |
| GET | `/api/founders/availability` | anon | Redis-cached seat counter (60s TTL, <500ms p95) |
| GET | `/api/founders/hall` | anon | Public Hall of Founders (opt-in only, LGPD) |
| POST | `/api/founders/hall/consent` | auth | Toggle LGPD opt-in listing |
| GET | `/api/subscriptions/upgrade-to-lifetime/preview` | auth+MFA | Preview upgrade from monthly → lifetime |
| POST | `/api/subscriptions/upgrade-to-lifetime` | auth+MFA | Execute upgrade (Stripe one-time charge) |
| GET | `/v1/admin/founding/stats` | admin | Admin dashboard — founding metrics |
| POST | `/v1/admin/founding/revoke` | admin | Admin revoke founding status |

## Componentes

### RPC PostgreSQL: `check_founding_availability()`

`SELECT FOR UPDATE` na `founding_policy` row + COUNT de `founding_leads` completed em uma transação atômica. Race guard #1 contra oversell.

### Stripe Checkout (v2 lifetime — BIZ-FOUND-002)

`POST /v1/founding/checkout` em `backend/routes/founding.py`:

1. Chama RPC `check_founding_availability()` — se `available=false`, retorna 410 Gone
2. Cria sessão Stripe `mode=payment`, `line_items` com `price_data` (R$997 one-time, não subscription)
3. Metadata: `offer_version=v2_lifetime`, `offer_mode=lifetime`, `price_brl_cents=99700`, `checkout_source`, `product_type=founding`
4. Insere `founding_leads` com `checkout_status='pending'`, `offer_version='v2_lifetime'`
5. Retorna `{checkout_url, session_id, payment_mode='lifetime'}`

### Webhook Processing

`checkout.session.completed` em `webhooks/handlers/founding.py`:

1. Verifica `metadata.offer_mode == 'lifetime'` (marcador founding)
2. Atualiza `founding_leads.checkout_status='completed'`, `stripe_payment_intent_id`
3. Ativa entitlement: `profiles.is_founder=TRUE`, `plan_type='founding_member'`
4. Dispara email welcome (`founders_welcome.py`)
5. Auto-invite: `invite_user_by_email` via Supabase Auth (idempotent — `invite_sent_at` gate)

`checkout.session.expired` em `_registry.py`:

1. Marca `founding_leads.checkout_status='abandoned'`
2. Libera vaga (decrementa seat count implícito — contagem é agregação, não contador)

### Public Seat Counter

`GET /v1/founding/availability` (anon):

- Query `profiles.is_founder=TRUE` count + `founding_leads.completed` count
- Retorna `{seats_taken, seats_capacity=50, deadline, seats_remaining}`
- Redis cached 60s (fallback conservative)

`GET /api/founders/availability` (anon, `routes/founders.py`):

- Mesmo data, cache layer diferente: Redis 60s + DB fallback 2s timeout
- Rate limited: 60 req/min por IP
- Fallback mode: `vagasRestantes=null, fallback=true` — frontend renderiza banner conservador

### Hall of Founders

`GET /api/founders/hall` (anon):

- Lista fundadores com `founder_public_listing_consent=TRUE`
- ISR: `revalidate=300` (CDN)
- Colunas: `founder_listing_display_name`, `founder_company_logo_url`

`POST /api/founders/hall/consent` (auth):

- LGPD toggle: `{consent: bool, display_name?, logo_url?}`
- Audit trail via `audit_logger.log()` (event `lgpd.consent_change`)

### Upgrade Path: Mensal → Lifetime

`POST /api/subscriptions/upgrade-to-lifetime` (auth + MFA high-impact):

- Para usuários pagantes mensais que querem migrar para lifetime
- Cobra diferença: R$997 - credit_por_pagamentos_ja_feitos (prorata não implementado)
- Cancela subscription Stripe atual, ativa `is_founder=TRUE`, `plan_type='founding_member'`

### ARQ Cron: `founders_auto_disable` (`backend/jobs/cron/founders_auto_disable.py`)

- Após deadline (01/07/2026), desativa endpoint `/v1/founding/checkout` e landing page CTA
- Feature flag `FOUNDERS_ENABLED` em `config/features.py`

### Email Sequence

| Email | Trigger | Template |
|-------|---------|----------|
| Founders Welcome | Imediato pós-checkout | `templates/emails/founders_welcome.py` |
| Day-10 trial → founding cross-sell | Trial cohort D+10 | `services/trial_email_sequence.py` |
| Cap almost full (<5 vagas) | Quota alert | Founding marketing template |

## Tabelas

### `founding_leads`

Vide `_reversa_sdd/data-master.md §11.5` para colunas completas. Destaques:

| Coluna | Tipo | Uso |
|--------|------|-----|
| `checkout_status` | `text` | `pending \| completed \| abandoned \| refunded` |
| `offer_version` | `text | `offer_version=v2_lifetime` (cohort tracking) |
| `stripe_payment_intent_id` | `text UNIQUE` | idempotency |
| `welcome_sent_at` | `timestamptz` | idempotency gate welcome email |
| `invite_sent_at` | `timestamptz` | idempotency gate auto-invite |
| `magic_link_sent_at` | `timestamptz` | FOUND-CRIT-003 |

### `founding_policy_audit_log`

Tabela de audit trail para mudanças no canonical lifetime policy (cap, deadline, price overrides).

### `profiles` (colunas relacionadas)

| Coluna | Tipo | Uso |
|--------|------|-----|
| `is_founder` | `bool DEFAULT false` | É fundador |
| `founder_public_listing_consent` | `bool DEFAULT false` | LGPD opt-in Hall |
| `founder_listing_display_name` | `text NULL` | Display name no hall |
| `founder_company_logo_url` | `text NULL` | Logo URL |
| `founder_consent_changed_at` | `timestamptz NULL` | Audit trail toggle |

## Dependências

| Módulo | Relação |
|--------|---------|
| `routes/founding.py` | Checkout + availability |
| `routes/founders.py` | Public seat counter |
| `routes/founders_hall.py` | Hall + LGPD consent |
| `routes/upgrade_to_lifetime.py` | Mensal→lifetime migration |
| `routes/admin_founding.py` | Admin stats + revoke |
| `webhooks/handlers/founding.py` | Stripe webhook side-effects |
| `webhooks/handlers/checkout.py` | Checkout completion |
| `jobs/cron/founders_auto_disable.py` | Deadline enforcement |
| `services/trial_email_sequence.py` | Cross-sell sequence |
| `email_service.py` + `templates/emails/founders_welcome.py` | Welcome email |
| `config/features.py` | `FOUNDERS_ENABLED` feature flag |

## Métricas Prometheus

- `smartlic_founding_checkout_total{source}` (counter) — checkout attempts
- `smartlic_founding_completed_total{offer_version}` (counter) — successful purchases
- `smartlic_founding_revenue_brl_total` (counter) — gross revenue from founding
- `smartlic_founding_seats_remaining` (gauge) — seats left before cap

## Lacunas

- 🟡 Prorata para upgrade mensal→lifetime não implementado (sempre cobra R$997 cheio)
- 🟡 Auto-invite `invite_user_by_email` usa Supabase Auth magic-link — pode falhar se email já registrado (graceful, loga warning)
- 🟢 Idempotência dupla: `stripe_payment_intent_id UNIQUE` + `welcome_sent_at` / `invite_sent_at` gates em todos os side-effects
- 🟢 Feature flag `FOUNDERS_ENABLED` permite desativar sem deploy
- 🟢 Audit log em toda mutation relevante (`founding_policy_audit_log`, `lgpd.consent_change`)

---

*Atualizado em 2026-05-12 (DOC-COVERAGE-002)*
