# Runbook: Backend Wedge Recovery (Stage 4-7 pattern)

**Severity:** P0 (revenue-critical — backend down/saturated affects auth + paywall + checkout)
**Triage time target:** 5 minutos
**Recovery time target:** 15-45 minutos
**On-call role:** Engineer with Railway dashboard + GitHub repo access + `.env` Sentry token
**Created:** 2026-04-29 (pós Stage 4-7 wedge cycle, 9 sessions documentadas)
**Story:** [OPS-RECOVERY-001](../stories/2026-04/OPS-RECOVERY-001-backend-wedge-recovery-runbook.story.md)

> **Versão executável.** Cada bloco é copy-paste pronto. Não tente diagnosticar root cause durante outage — siga decision tree → recovery actions → soak protocol → só investigue post-recovery.

---

## Sintomas (você está aqui se ≥2 destes)

- Frontend produção retorna 5xx em rotas que dependem de backend (`/buscar`, `/conta`, `/checkout`, `/v1/empresa/*/perfil-b2g`)
- Sentry events `slow_request >60s` ou `/sitemap/*after 3 attempts` em spike (>5/5min)
- `curl https://api.smartlic.tech/health/live` timeout (`curl: (28) Connection timed out`) ou retorna 5xx
- Railway dashboard `bidiq-backend` mostra deployment SUCCESS mas serviço unresponsive (silent twin)
- Worker RSS metric `smartlic_backend_worker_rss_bytes` >4GB sustained (hard alert tier — ADR-MEMORY-BUDGET)
- Googlebot/Bingbot crawl wave em logs simultâneo a degradação

**Não é wedge se:**
- Frontend renderiza mas alguns endpoints lentos → saturation, ver [`general-outage.md`](general-outage.md)
- 4xx em rotas específicas → bug de regra de negócio, não outage
- Cloudflare 521/522 globais → infra externa, ver Decision Tree D2

---

## Discriminator Matrix (curl, 1 minuto)

Bypass Cloudflare via Railway direct domain. **Rode os 4 comandos em sequência:**

```bash
# 1. Backend via Cloudflare (api.smartlic.tech)
curl -m 5 -o /dev/null -w "smartlic_api: http=%{http_code} time=%{time_total}s\n" \
  https://api.smartlic.tech/health/live

# 2. Backend Railway direct (bypass Cloudflare)
curl -m 5 -o /dev/null -w "railway_direct: http=%{http_code} time=%{time_total}s\n" \
  https://bidiq-uniformes-production.up.railway.app/health/live

# 3. Frontend via Cloudflare
curl -m 5 -o /dev/null -w "smartlic_front: http=%{http_code} time=%{time_total}s\n" \
  https://smartlic.tech/api/health

# 4. Sentry slow_request count last 1h
SENTRY_TOKEN=$(grep SENTRY_AUTH_TOKEN .env | cut -d= -f2)
curl -s -H "Authorization: Bearer $SENTRY_TOKEN" \
  "https://sentry.io/api/0/organizations/confenge/issues/?project=smartlic-backend&statsPeriod=1h&query=slow_request" \
  | jq -r '.[] | "\(.title) count=\(.count)"' | head -5
```

### Tabela discriminator (interprete os 4 outputs)

| #1 smartlic_api | #2 railway_direct | #3 smartlic_front | Diagnóstico | Próxima ação |
|----------------|-------------------|-------------------|-------------|--------------|
| 200 <2s | 200 <2s | 200 | **Não é wedge.** Investigar Sentry/logs. | Revisar [`general-outage.md`](general-outage.md) |
| 5xx ou 000/timeout | 200 <2s | 5xx | **Cloudflare proxy issue (raro)** | Cloudflare dashboard → cache purge + page rules check |
| 5xx ou 000/timeout | 5xx ou 000/timeout | 5xx | **Backend wedge confirmado** | Recovery Action R1 abaixo |
| 200 mas >5s | 200 mas >5s | 200 OK | **Saturação, não wedge** | Recovery Action R2 (capacity) |
| 200 ok | 200 ok | 5xx | **Frontend isolated** | Verificar Railway `bidiq-frontend` deploy status |

**Memory ref:** `reference_railway_404_triage` documenta 4 causas não-discrimináveis 404 (rootDir/compute limit/crash/domain unassigned). Use ferramentas Railway dashboard se discriminator inconclusivo.

---

## Decision Tree (5min triage)

```
Discriminator output → WEDGE confirmado?
│
├── SIM (#1 fail + #2 fail) → R1: Railway redeploy GraphQL workaround
│   │
│   └── R1 falhou (silent twin redeploy também wedge) → ESCALATE @architect
│
├── SATURAÇÃO (#1 ok mas >5s + #2 ok mas >5s) → R2: capacity check
│   │
│   ├── RSS gauge >4GB → R3: gunicorn restart (ADR Component B kill)
│   └── RSS normal mas DB pool exhausted → R4: Supabase Management API tighten
│
├── NÃO (200 OK, suspeita falsa) → STOP runbook, debug local Sentry
│
└── PARCIAL (#1 ok, #2 fail OU vice-versa) → cobertura DNS/Cloudflare/Railway routing
    └── Verificar Railway service domain assignments (dashboard)
```

---

## Recovery Actions (escalation order)

> Sempre tente R1 primeiro (low-blast-radius). Escalate apenas se R1 falhar.

### R1 — Railway `deploymentRedeploy` GraphQL workaround

**Quando:** wedge confirmado (silent twin FAILED bug rootDirectory recidiva — keen-neumann session 2026-04-29).

**Por que GraphQL e não `railway redeploy --service`:** memory `feedback_chief_warm_stage5plus_no_pivot` documenta que `railway redeploy` repete deployment com mesmo bug latente. GraphQL `deploymentRedeploy(id)` força reuse de um deployment SUCCESS conhecido (skipping rebuild).

**Steps:**

1. **Descobrir `<good_deploy_id>`** — Railway dashboard → bidiq-backend → "Deployments" tab → mais recente deployment com status `SUCCESS` ANTES da janela do wedge.

   ```bash
   # Alternativa CLI (lista últimos 10):
   railway deployments --service bidiq-backend --json | jq -r '.deployments[:10] | .[] | "\(.id) \(.status) \(.createdAt)"'
   ```

2. **Trigger redeploy:**

   ```bash
   railway api --json mutation '
     mutation {
       deploymentRedeploy(id: "<good_deploy_id>") {
         id
         status
       }
     }
   '
   ```

3. **Aguardar 2-3min** + rodar Discriminator Matrix novamente. Se ambos #1 e #2 retornam 200 <2s → seguir para Soak Protocol.

4. **Se R1 redeploy também wedge** (mesmo padrão repetir) → ESCALATE.

### R2 — Capacity check (saturação, não wedge)

```bash
# RSS atual via Prometheus metric scrape (proxy Sentry export):
curl -s -H "Authorization: Bearer $SENTRY_TOKEN" \
  "https://sentry.io/api/0/organizations/confenge/projects/smartlic-backend/stats/?stat=received&statsPeriod=1h" \
  | jq '.[]'

# Worker RSS via /v1/admin/memory-snapshot (master-only auth required):
curl -X GET https://api.smartlic.tech/v1/admin/memory-snapshot \
  -H "Authorization: Bearer <admin_jwt>"
```

Se `rss_bytes >4_000_000_000` → R3.
Se Supabase pool active >80% → R4.

### R3 — Gunicorn restart (RSS critical kill)

ADR-MEMORY-BUDGET Component B: critical tier (>5GB instantâneo) deve disparar restart automático. Manual fallback:

```bash
# Force restart todo serviço (Railway):
railway restart --service bidiq-backend

# Ou: SIGTERM workers via Railway logs panel (deployments tab → restart)
```

### R4 — Supabase Management API tighten

Sob outage com pool exhausted (memory `feedback_pool_leak_caller_timeout_vs_sql_timeout`):

```bash
# Tighten service_role statement_timeout (FLOOR=15s não-negociável; 8s testado e PIOROU Stage 6):
SUPABASE_TOKEN=$(grep SUPABASE_ACCESS_TOKEN .env | cut -d= -f2)
curl -X POST "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "ALTER ROLE service_role SET statement_timeout = '\''15s'\''; SELECT pg_reload_conf();"}'
```

**Memory ref:** `reference_supabase_management_api_query` — Management API funciona sob Disk IO degradado quando CLI rejeita.

### R5 — Last resort: rollback to known good main commit

```bash
# Identificar último commit verde:
gh run list --workflow=deploy.yml --status=success --limit=5 --json headSha,createdAt

# Force redeploy esse commit (Railway watcher pega):
git checkout main
git reset --hard <good_sha>
git push --force origin main  # ATTENTION: requer @devops, ver Authority gate
```

> **⚠️ R5 requer @devops (push --force authority).** Não execute autonomamente sob outage; SCALA via Slack/PagerDuty. Memory `reference_auto_merge_disabled` documenta merge train manual.

---

## Soak Protocol (30min post-recovery)

Após R1/R2/R3/R4 retornar 200 OK, **NÃO declare resolved imediatamente.** Stage 5 outage 2026-04-29 mostrou "API not crashed = saturated" — recovery aparente pode regressar em 5-10min.

```bash
# Loop 30 iterações × 60s sleep = 30 minutos:
for i in {1..30}; do
  result=$(curl -m 5 -o /dev/null -w "%{time_total}s %{http_code}" https://api.smartlic.tech/health/live)
  echo "[$(date +%H:%M:%S)] iter=$i $result"
  sleep 60
done | tee /tmp/soak-$(date +%Y%m%d-%H%M).log
```

### Critérios

| Resultado | Interpretação | Ação |
|-----------|---------------|------|
| **30/30 200 < 2s** | OK, stable | Declare resolved + post-mortem agendado |
| **≤2/30 timeout/5xx** | Aceitável (network jitter) | Monitor +30min antes de declare |
| **≥3/30 timeout/5xx** | **REGRESSION — nova wedge** | Voltar para Discriminator Matrix |

**Paralelo: monitor Sentry slow_request:**

```bash
# Tripwire 5.5GB RSS (active until 2026-05-06):
SENTRY_TOKEN=$(grep SENTRY_AUTH_TOKEN .env | cut -d= -f2)
curl -s -H "Authorization: Bearer $SENTRY_TOKEN" \
  "https://sentry.io/api/0/organizations/confenge/issues/?project=smartlic-backend&statsPeriod=24h&query=slow_request%20%3E60s" \
  | jq -r '[.[] | .count | tonumber] | add'
# Se total >25/24h → escalate para SEN-BE-010 fix
```

---

## Escalation (quando manual falha)

### Escalation triggers

- R1 redeploy também wedge (silent twin recidiva)
- 30min soak mostra ≥3/30 regression
- 5GB RSS persistente (gauge > critical tier mesmo após R3 restart)
- Múltiplos services degradados simultaneamente (backend + frontend + DB)

### Cadeia de escalation

1. **Slack #incidents** — post discriminator matrix output + recovery actions tentadas + soak log
2. **`/chief`** com prompt "Stage N wedge ativo — runbook OPS-RECOVERY-001 R1+R3 falhou — preciso pivot estrutural"
3. **@architect** — Aria via direct mention para hipótese root cause baseada em Sentry + memory snapshot
4. **PagerDuty** — se revenue impact >1h ou >100 affected users (paywall + checkout impacto direto)

### Documentar a sessão

Após resolution, criar session doc em `docs/sessions/YYYY-MM/YYYY-MM-DD-<adjective>-<scientist>.md` com:
- Timeline (timestamps UTC)
- Discriminator output + interpretação
- Recovery actions tentadas + resultados
- Memory updates (novo `feedback_*` ou `project_*` se aprendizado novo)

---

## Reference

### Memory mandatórias

- `feedback_chief_warm_stage5plus_no_pivot` — warm continuation 7× falhou Stage 6+; pivot estrutural mandatory
- `feedback_pool_leak_caller_timeout_vs_sql_timeout` — caller `wait_for` cancela await mas SQL persists; tighten service_role statement_timeout
- `feedback_audit_env_vars_after_incident` — PYTHONASYNCIODEBUG=1 e similar persisting flags pós-recovery
- `feedback_supabase_disk_io_root_cause_pattern` — 3 sintomas convergentes (sitemap DB-bound + service_role NULL + SEN-FE-001) = causa única
- `feedback_dual_deploy_railway_gh_actions` — push to main triggera 2 DEPLOYING (Railway watcher + deploy.yml race)
- `feedback_web_concurrency_4_amplifier` — WC=4 amplifier de Supabase saturation; manter WC=1 em Hobby
- `reference_railway_404_triage` — 4 causas não-discrimináveis 404 (rootDir/compute/crash/domain)
- `reference_supabase_management_api_query` — bypass CLI sob Disk IO degradado
- `reference_supabase_service_role_no_timeout_default` — service_role statement_timeout NULL default; setar 60s preventivo
- `reference_crit080_not_applicable_public_repo` — billing issue NÃO aplica em repo público; saturação GH Actions é normal

### Sessions reference (Stage 4-7 cycle 2026-04-27→29)

- `docs/sessions/2026-04/2026-04-29-chief-stage7-wedge-discriminator.md` — Stage 7 ativo + discriminator drill
- `docs/sessions/2026-04/2026-04-29-chief-drift-paulo.md` — recovery orgânico + tripwire 5.5GB RSS
- `docs/sessions/2026-04/2026-04-29-chief-savvy-jasmine.md` — Stage 5 saturation (10 routes Sentry-priorized)
- `docs/sessions/2026-04/2026-04-29-chief-swift-mendel.md` — Stage 4-5 transition
- `docs/sessions/2026-04/2026-04-29-chief-trusty-pasteur.md`
- `docs/sessions/2026-04/2026-04-29-chief-urgent-codd.md`
- `docs/sessions/2026-04/2026-04-29-chief-stage65-firefight.md` — capacity bump test
- `docs/sessions/2026-04/2026-04-29-keen-neumann.md` — `deploymentRedeploy` GraphQL workaround discovery
- `_reversa_sdd/incidents-2026-04-27-29.md` — timeline consolidado
- `docs/analysis/chief-stage7-definitive-solution.md` — root cause análise

### Related ADRs/Stories

- [`docs/adr/MEMORY-BUDGET.md`](../adr/MEMORY-BUDGET.md) — 3-tier RSS threshold + Combined restart policy
- [`SEN-BE-010`](../stories/2026-04/SEN-BE-010-memory-leak-rss-guard-profiling.story.md) — Phase 0 observability + root cause discovery
- [`RES-BE-002c`](../stories/2026-04/RES-BE-002c-execute-audit-sweep-remaining.story.md) — `.execute()` sweep universal pattern
- [`OPS-POSTMORTEM-001`](../stories/2026-04/OPS-POSTMORTEM-001-stage-4-7-audit-consolidado.story.md) — postmortem audit consolidado

### Railway/Sentry CLI quick reference

```bash
# Status
railway status --service bidiq-backend
railway logs --service bidiq-backend --tail

# Deployments
railway deployments --service bidiq-backend
railway redeploy --service bidiq-backend -y      # standard redeploy
railway api --json mutation '...'                # GraphQL workaround (R1)

# Variables (audit pós-incident — memory feedback_audit_env_vars_after_incident):
railway variables --service bidiq-backend --kv | grep -iE "DEBUG|DEV|TRACE"

# Sentry (statsPeriod accept 24h or 14d only):
SENTRY_TOKEN=$(grep SENTRY_AUTH_TOKEN .env | cut -d= -f2)
curl -s -H "Authorization: Bearer $SENTRY_TOKEN" \
  "https://sentry.io/api/0/organizations/confenge/issues/?project=smartlic-backend&statsPeriod=24h&query=is:unresolved" \
  | jq '.[] | {title, count, culprit}' | head -20
```
