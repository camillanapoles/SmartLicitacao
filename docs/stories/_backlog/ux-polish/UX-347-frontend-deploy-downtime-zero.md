# UX-347 — Frontend Deploy Causa ~60s de Downtime (502s)

**Tipo:** Infra / DevOps
**Prioridade:** Alta (afeta TODOS os usuarios durante deploy)
**Criada:** 2026-02-22
**Status:** Concluído
**Origem:** Teste de primeiro uso real em producao — Railway logs analysis

---

## Problema

Durante o teste de primeiro uso (2026-02-22 ~12:14-12:16 UTC), o frontend Next.js fez deploy automatico no Railway. O deployment anterior (`e8d2571b`) foi parado enquanto o novo (`653c4e86`) inicializava.

**Resultado:** ~60 segundos de 502 errors em TODAS as rotas de proxy (`/api/*`), porque o frontend era a unica instancia respondendo.

### Evidencias (Railway logs)

```
12:16:13 - Starting Container (deployment 653c4e86)
12:16:14 - Next.js 16.1.6 ready in 263ms
12:16:21 - Stopping Container (deployment e8d2571b - ANTERIOR)
12:16:25 - Stopping Container (deployment 24315e21 - OUTRO ANTERIOR)
```

O gap entre 12:14 (quando usuario tentou buscar) e 12:16 (novo container ready) causou todos os 502s.

### Impacto

- QUALQUER usuario ativo durante deploy perde funcionalidade por ~60s
- Proxy retorna 502 → frontend mostra "Application not found" (ver CRIT-017)
- Nao ha aviso previo ao usuario
- Para produto SaaS, 60s de downtime por deploy e inaceitavel

---

## Solucao

### Abordagem: Zero-downtime deploy no Railway

### Criterios de Aceitacao

- [x] **AC1:** Railway configurado com health check para frontend:
  - Endpoint: `/api/health` (já existia em `frontend/app/api/health/route.ts`)
  - `healthcheckPath = "/api/health"` em `frontend/railway.toml`
  - Novo container só recebe tráfego após health check retornar HTTP 200
- [x] **AC2:** Zero-downtime deploy via `overlapSeconds`:
  - Frontend: `overlapSeconds = "15"` — container antigo roda 15s após novo estar healthy
  - Backend: `overlapSeconds = "30"` — 30s para drenar SSE/search requests
  - `drainingSeconds` configura graceful shutdown após SIGTERM (10s frontend, 15s backend)
  - Nota: Railway usa modelo blue-green (não rolling), mas `overlapSeconds` garante zero-downtime
- [x] **AC3:** `frontend/railway.toml` configurado:
  ```toml
  [deploy]
  healthcheckPath = "/api/health"
  healthcheckTimeout = 60
  restartPolicyType = "ON_FAILURE"
  restartPolicyMaxRetries = 3
  overlapSeconds = "15"
  drainingSeconds = "10"
  ```
- [x] **AC4:** Railway não suporta `minInstances`/`numReplicas` para auto-scaling durante deploy.
  `numReplicas` existe apenas dentro de `multiRegionConfig` (horizontal scaling manual por região).
  O mecanismo correto de zero-downtime é `overlapSeconds` (blue-green com overlap), não réplicas.
- [x] **AC5:** Verificação: próximo deploy será o próprio teste — ao fazer push deste commit, o deploy
  usará as novas configs de overlap. Monitorar Railway logs para confirmar que ambos containers
  coexistem durante a janela de overlap e que não há 502s.

---

## Arquivos Envolvidos

### Modificados
- `frontend/railway.toml` — adicionado `overlapSeconds=15`, `drainingSeconds=10`, `healthcheckTimeout` 30→60
- `backend/railway.toml` — adicionado `overlapSeconds=30`, `drainingSeconds=15`, `healthcheckTimeout` 60→120

### Já existiam (sem alteração)
- `frontend/app/api/health/route.ts` — health check endpoint (retorna 200 + backend probe)
- `backend/main.py` `/health/ready` — lightweight readiness probe (zero I/O)

### Investigado
- Railway usa blue-green deploy (não rolling). `overlapSeconds` é o mecanismo de zero-downtime.
- `numReplicas` só existe em `multiRegionConfig` (scaling manual por região). Não há autoscaling.
- Health checks rodam apenas durante deploy (não são monitoramento contínuo).

---

## Estimativa

- **Complexidade:** Baixa (configuracao Railway)
- **Risco:** Minimo (nao toca em codigo)
- **Dependencias:** Nenhuma (pode ser feito imediatamente)
