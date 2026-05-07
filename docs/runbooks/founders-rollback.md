# Runbook: Rollback do Plano Fundadores

> Versão: 2026-05-07 | Owner: @tiago | Severidade: P1

## Quando usar este runbook

- Checkout failing para >50% das tentativas (Stripe error rate)
- Webhook de entitlement não ativando is_founder=true (Sentry alerts)
- Race condition no cap (fundadores além de 50 sendo ativados)
- Erro crítico no Sentry relacionado a `/founding/` endpoints

## Ação 1: Fast disable sem deploy (< 2 minutos)

```bash
# Opção A: Feature flag via Railway
railway variables set FOUNDERS_OFFER_ENABLED=false

# Opção B: Admin API (se feature flag implementada)
curl -X PATCH https://api.smartlic.tech/v1/admin/founding/policy \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"active": false, "paused_reason": "rollback: <motivo>"}'
```

Isso bloqueia todos os novos checkouts imediatamente, sem redeploy.

## Ação 2: Investigar causa

```bash
# Ver logs Railway
railway logs --tail --service bidiq-backend | grep founding

# Ver erros Sentry (últimas 24h)
# Dashboard: https://confenge.sentry.io/issues/?project=smartlic-backend&query=founding
```

## Ação 3: Reverter entitlements incorretos (se cap violado)

```bash
# Via Supabase Management API ou psql
# Identificar founders ativados indevidamente:
SELECT id, email, is_founder, founder_since
FROM profiles
WHERE is_founder = true
ORDER BY founder_since DESC;

# Se necessário, reverter entitlement específico (coordenar com usuário):
UPDATE profiles
SET is_founder = false, founder_since = null, consulting_discount_pct = null
WHERE id = '<user_id>';
```

## Ação 4: Reverter migrations (último recurso)

Se houver problema nas migrations, aplique os `.down.sql` via Supabase Management API:

```bash
export SUPABASE_ACCESS_TOKEN=$(cat .env | grep SUPABASE_ACCESS_TOKEN | cut -d= -f2)
# Aplicar down migrations na ordem reversa
# 1. Primeiro: 20260507100100_founding_policy_lifetime_pivot.down.sql
# 2. Depois: 20260507100000_profiles_founder_fields.down.sql
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "<conteudo do .down.sql>"}'
```

## Comunicação

Notificar founders por email via Resend se checkout foi interrompido por >30 min. Template: `email_founder_checkout_interruption` (criar se necessário).

## Pós-rollback checklist

- [ ] Sentry sem novos erros por 30min
- [ ] Checkout funcionando para outros planos (não founders)
- [ ] is_founder = false para todos os founders ativados indevidamente (se houver)
- [ ] Post-mortem em `docs/incidents/YYYY-MM-DD-founders-rollback.md`
