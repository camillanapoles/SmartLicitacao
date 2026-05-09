# Spec: Email Templates

> Spec executável (SDD) gerada pelo **Reversa Writer** em 2026-05-08
> Confiança: 🟢 CONFIRMADO

## Component
- **ID**: `email-templates`
- **Path**: `backend/templates/emails/` (15 templates), `backend/email_service.py`, `backend/jobs/cron/trial_emails.py`, `backend/routes/trial_emails.py` (webhook + admin endpoints)

## Purpose

Sistema de templates de email transacionais e marketing via Resend SDK. 15 templates cobrindo trial lifecycle (6-step), dunning sequence, boas-vindas, digest de alertas, quota warning, e programas de referral/parceiro.

## Configuração Resend

| Parâmetro | Valor |
|-----------|-------|
| SDK | `resend` Python SDK |
| Domain verificado | `smartlic.tech` |
| From | `tiago@smartlic.tech` |
| Reply-To | `tiago.sasaki@gmail.com` |
| Style | Plain-text pessoal (não HTML marketing) |

## 15 Templates (backend/templates/emails/)

| # | Template | Trigger | Audiência |
|---|----------|---------|-----------|
| 1 | `base.py` | — | Base HTML wrapper (Jinja-like) |
| 2 | `trial/day0.py` | signup | Novo usuário (welcome + primeiros passos) |
| 3 | `trial/day3.py` | day 3 in trial | Ativação — CTA primeira busca |
| 4 | `trial/day7.py` | day 7 in trial | Engajamento — caso de uso |
| 5 | `trial/day10.py` | day 10 in trial | Urgência soft — upgrade CTA |
| 6 | `trial/day13.py` | day 13 in trial | Urgência — trial expira amanhã |
| 7 | `trial/day16.py` | day 16 (post-expiry) | Win-back — trial expirou |
| 8 | `billing/dunning_day1.py` | payment_failed day 1 | Cobrança falhou — atualizar cartão |
| 9 | `billing/dunning_day3.py` | payment_failed day 3 | Urgência cobrança |
| 10 | `billing/dunning_day7.py` | payment_failed day 7 | Último aviso |
| 11 | `billing/dunning_day14.py` | payment_failed day 14 | Conta cancelada |
| 12 | `welcome.py` | plano ativo pago | Bem-vindo cliente |
| 13 | `welcome_subscriber.py` | newsletter signup | Bem-vindo assinante |
| 14 | `digest.py` | `email_alerts` ARQ cron (diário) | Digest novas licitações |
| 15 | `alert_digest.py` | alertas configurados | Alertas personalizados |
| 16 | `quota.py` | quota 80%+ | Aviso de quota |
| 17 | `day3_activation.py` | day 3 (ativação específica) | CTA ativação 72h |
| 18 | `share_activation.py` | share link clicked | Convidado via share |
| 19 | `referral_invite.py` | partner referral | Convite de parceiro |
| 20 | `referral_reward.py` | referral conversion | Recompensa de referral |
| 21 | `panorama_t1_delivery.py` | Intel Report | Entrega relatório T1 |
| 22 | `boleto_reminder.py` | boleto próximo vencer | Lembrete boleto |

**Nota:** Documentação original menciona 15 templates; contagem expandida ~22 no código (STORY-321 adicionou sequência completa).

## Trial Email Lifecycle (Sequência STORY-321)

```
User signup → INSERT profiles(trial_expires_at=now+14d)

CRON _trial_sequence_loop (tick every TRIAL_SEQUENCE_INTERVAL_SECONDS):
  SELECT users WHERE day_in_trial IN {0,3,7,10,13,16}
    AND NOT EXISTS (SELECT 1 FROM trial_email_log WHERE user_id=me AND day_in_trial=N)
  → batch up to TRIAL_SEQUENCE_BATCH_SIZE

  for each user:
    render template body for day N
    → email_base HTML wrapper
    → Resend SDK send()
        → {id, status: "queued"}
    → INSERT trial_email_log(user_id, day_in_trial, sent_at, message_id, delivery_status=null)
```

### day_in_trial calculation

```python
day_in_trial = (now - profile.created_at).days
# triggers: 0, 3, 7, 10, 13, 16
```

### trial_email_log (table)

```python
{
  "id": uuid,
  "user_id": uuid,
  "day_in_trial": int,  # 0|3|7|10|13|16
  "sent_at": datetime,
  "message_id": str,    # Resend email ID
  "delivery_status": str | None,  # null → queued → delivered|bounced|opened|clicked
  "opened_at": datetime | None,
  "clicked_at": datetime | None
}
```

## Webhook Resend (POST /v1/trial-emails/webhook)

```
POST /v1/trial-emails/webhook
  → HMAC verify (GAP — ainda NÃO implementado — Gap-5 review-report)
  → parse event: {type, data: {email_id, ...}}
  → type in {"email.delivered", "email.bounced", "email.opened", "email.clicked"}?
      → UPDATE trial_email_log
            SET delivery_status=type, opened_at=..., clicked_at=...
            WHERE message_id=email_id
  → 200 OK
```

**Security gap (Gap-5):** HMAC verify via `svix-signature` header NÃO implementado. Webhook aceita qualquer POST. Prioridade P1 para implementar antes de scale.

## Dunning Sequence (jobs/cron/billing.py)

```
Day 1 após payment_failed:
  → send dunning_day1.py
Day 3: dunning_day3.py
Day 7: dunning_day7.py
Day 14: dunning_day14.py + cancel subscription

Pre-dunning (7d antes cartão expira):
  → Stripe webhook `customer.updated` card_exp approaching
  → send pre_dunning email
```

## Email Service (`email_service.py`)

```python
def send_email(
    to: str,
    subject: str,
    html_body: str,
    from_email: str = "tiago@smartlic.tech",
    reply_to: str = "tiago.sasaki@gmail.com",
    tags: list[str] = [],
) -> dict:
    """Send via Resend SDK. Returns {id, status}. Raises on failure."""
    result = resend.Emails.send({
        "from": from_email,
        "to": [to],
        "subject": subject,
        "html": html_body,
        "reply_to": reply_to,
        "tags": [{"name": t} for t in tags],
    })
    return result
```

**Style:** Plain-text pessoal (não HTML genérico) — tom de founder B2B, sem banners/images, assinatura "Tiago, SmartLic".

## Admin Endpoints (routes/trial_emails.py)

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| `GET` | `/v1/trial-emails/log` | admin | listar trial_email_log com filtros |
| `POST` | `/v1/trial-emails/send-test` | admin | enviar email de teste (any template) |
| `GET` | `/v1/trial-emails/stats` | admin | delivery stats (open rate, click rate, bounce) |
| `POST` | `/v1/trial-emails/webhook` | public (sig gap) | Resend delivery webhook |
| `POST` | `/v1/emails/send-welcome` | system | enviar welcome pós-signup |
| `GET` | `/v1/emails/unsubscribe` | public | unsubscribe link (token-based) |

## Functional Requirements

- **FR-1**: Trial sequence envia email para days {0,3,7,10,13,16} exatamente uma vez por user (idempotência via `trial_email_log`)
- **FR-2**: `_trial_sequence_loop` processa em batch (`TRIAL_SEQUENCE_BATCH_SIZE`) para escala
- **FR-3**: Dunning sequence envia 4 emails em D+1/D+3/D+7/D+14 de `payment_failed`
- **FR-4**: Webhook `email.delivered` + `email.opened` + `email.clicked` atualiza `trial_email_log`
- **FR-5**: `send_email` lança exceção em falha Resend (caller decide retry policy)
- **FR-6**: Admin `send-test` envia qualquer template para email especificado
- **FR-7**: Unsubscribe link com token single-use (seguro para click tracking)
- **FR-8**: Tags Resend usadas para filtragem (`trial`, `dunning`, `day_N`, etc.)

## Non-Functional Requirements

- **NFR-1**: Trial sequence loop: latência por user <500ms (Resend API é fast)
- **NFR-2**: Batch size configurável via `TRIAL_SEQUENCE_BATCH_SIZE` (default 50)
- **NFR-3**: Delivery status atualizado em <60s após evento Resend (webhook latency)
- **NFR-4**: 0 duplicate emails (idempotência obrigatória via `trial_email_log`)

## Constraints

- **CON-1**: Domain `smartlic.tech` verificado no Resend — emails de outros domínios falham
- **CON-2**: HMAC verify ausente em webhook (Gap-5) — não escalar até implementado
- **CON-3**: `RESEND_API_KEY` em env var (nunca hardcoded)
- **CON-4**: Reply-to `tiago.sasaki@gmail.com` (pessoal) — não processar respostas automaticamente
- **CON-5**: Unsubscribe token deve ser invalidado após uso (one-time)

## Acceptance Criteria

- AC-1: Signup de novo usuário → day0 email enviado em até 1h (próximo tick do loop)
- AC-2: day3 email NÃO reenviado se já existe `trial_email_log(day_in_trial=3)` para user
- AC-3: `email.opened` webhook → `trial_email_log.opened_at` atualizado
- AC-4: Dunning D+1 enviado em até 24h de `payment_failed` Stripe webhook
- AC-5: Admin `send-test` com template `day7` → email recebido no endereço especificado
- AC-6: Unsubscribe link válido → user marcado como unsubscribed (sem mais emails trial)

## Errors

| Code | HTTP | Trigger |
|------|------|---------|
| `resend_api_error` | 502 | Resend API falha (network/quota) |
| `template_not_found` | 404 | template name inválido em send-test |
| `unsubscribe_token_invalid` | 400 | token expirado ou já usado |
| `webhook_parse_error` | 400 | Resend webhook payload malformed |

## Code Traceability

- `backend/templates/emails/` — todos 15+ templates
- `backend/email_service.py` — `send_email` wrapper Resend SDK
- `backend/jobs/cron/trial_emails.py` — `_trial_sequence_loop` (lifespan cron)
- `backend/routes/trial_emails.py` — webhook + admin endpoints
- `backend/webhooks/handlers/invoice.py` — dunning trigger (payment_failed)
- `backend/jobs/cron/billing.py` — pre-dunning + reconciliation
- Supabase `trial_email_log` — idempotência + delivery tracking

## Dependencies

- Resend Python SDK (`resend.Emails.send`)
- Supabase (`trial_email_log`, `profiles`, `user_subscriptions`)
- Redis (rate limiting + unsubscribe token store)
- Stripe Webhooks (dunning trigger via `invoice.payment_failed`)
- ARQ (daily_digest job para alert digests)
- `email_service.py` (único entry point para envio)
