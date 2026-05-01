# Mixpanel Runbook — MON-FN-005

## Obter o MIXPANEL_TOKEN

1. Acesse [Mixpanel](https://mixpanel.com) → projeto `confenge`
2. Settings → Project Settings → **Project Token** (NOT the API Secret)
3. O token começa com letras/números (não tem prefixo `mp_`)

## Setar em Railway

```bash
railway variables --service bidiq-backend set MIXPANEL_TOKEN=<token>
```

Se o serviço worker também usa analytics:

```bash
railway variables --service bidiq-worker set MIXPANEL_TOKEN=<token>
```

## Validar pós-deploy

Após o deploy, verificar no Mixpanel **Live View**:

1. Mixpanel → projeto confenge → Live View
2. Filtrar por evento `backend_boot`
3. Deve aparecer em ≤2 minutos após o deploy concluir
4. Properties: `environment=production`, `release=<sentry-release>`

Se não aparecer em 5 min, verifique Railway logs:

```bash
railway logs --service bidiq-backend --tail | grep -i "mixpanel\|MON-FN-005"
```

## Audit de env vars

```bash
railway variables --service bidiq-backend --kv | grep -i mixpanel
```

Seguindo feedback `feedback_audit_env_vars_after_incident`: também verificar flags de debug:

```bash
railway variables --service bidiq-backend --kv | grep -iE "DEBUG|DEV|TRACE"
```

## Boot fail por MIXPANEL_TOKEN ausente

**Sintoma:** Backend não sobe em prod com mensagem `FATAL: Required environment variables missing`.

**Diagnóstico:**

```bash
railway logs --service bidiq-backend | grep "FATAL\|MIXPANEL"
```

**Fix:**

```bash
railway variables --service bidiq-backend set MIXPANEL_TOKEN=<token>
railway redeploy --service bidiq-backend -y
```

**Escape hatch (uso exclusivo em emergência, audita em logs CRITICAL):**

```bash
railway variables --service bidiq-backend set BYPASS_REQUIRED_ENV_ASSERTIONS=true
# Após resolver: remover
railway variables --service bidiq-backend unset BYPASS_REQUIRED_ENV_ASSERTIONS
```

## /health/ready check

Em prod, o endpoint `/health/ready` retorna 503 se Mixpanel não estiver configurado:

```bash
curl https://api.smartlic.tech/health/ready | jq .checks.mixpanel
# Esperado: {"status": "configured"}
# Se "not_configured" em prod → 503
```

## Referências

- Story: `docs/stories/2026-04/MON-FN-005-mixpanel-token-startup-assertion.md`
- Memory: `reference_mixpanel_backend_token_gap_2026_04_24`
- Memory: `feedback_audit_env_vars_after_incident`
- Assertions code: `backend/startup/assertions.py`
- Prometheus counter: `smartlic_mixpanel_init_failed_total{reason}`
