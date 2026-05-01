# HARDEN Sprint — Production Hardening (2026-03-06)

**Origem:** Conselho de CTOs — Auditoria de Fragilidades + Pesquisa de Best Practices
**Total:** 28 stories | 9 quick wins (< 15 min cada)

## Prioridade de Execução

### Quick Wins (~50 min total, ~70% do risco eliminado)

| # | Story | Descrição | Esforço |
|---|-------|-----------|---------|
| 1 | HARDEN-001 | OpenAI timeout 600s → 15s | 5 min |
| 2 | HARDEN-002 | jemalloc no Dockerfile | 5 min |
| 3 | HARDEN-003 | Queue bounded maxsize=500 | 10 min |
| 4 | HARDEN-007 | Gunicorn max_requests 1000 | 2 min |
| 5 | HARDEN-008 | Cache invalidation no webhook | 15 min |
| 6 | HARDEN-009 | Arbiter cache LRU 5000 | 10 min |
| 7 | HARDEN-010 | ComprasGov disable flag | 5 min |
| 8 | HARDEN-017 | Event history reduzir | 10 min |
| 9 | HARDEN-023 | RLS index user_id | 10 min |

### Críticas (restantes)

| # | Story | Descrição | Esforço |
|---|-------|-----------|---------|
| 10 | HARDEN-004 | Tracker cleanup periódico | 30 min |
| 11 | HARDEN-005 | Persist retry + Sentry | 30 min |
| 12 | HARDEN-006 | Dedup merge-enrichment | 1h |

### Altas (restantes)

| # | Story | Descrição | Esforço |
|---|-------|-----------|---------|
| 13 | HARDEN-011 | SSE inactivity timeout | 20 min |
| 14 | HARDEN-012 | Client disconnect check | 15 min |
| 15 | HARDEN-013 | Background results bounded | 15 min |
| 16 | HARDEN-014 | Worker timeout per-future | 30 min |
| 17 | HARDEN-015 | Bulkhead acquire timeout | 45 min |
| 18 | HARDEN-016 | Health liveness vs readiness | 30 min |

### Médias

| # | Story | Descrição | Esforço |
|---|-------|-----------|---------|
| 19 | HARDEN-018 | Local cache dir maxsize | 15 min |
| 20 | HARDEN-019 | Last-Event-ID DB fallback | 20 min |
| 21 | HARDEN-020 | SSE reconnect rate limit | 10 min |
| 22 | HARDEN-021 | Stripe webhook atomicity | 15 min |
| 23 | HARDEN-022 | Graceful shutdown drain | 30 min |
| 24 | HARDEN-024 | Saturation metrics | 30 min |

### Baixas

| # | Story | Descrição | Esforço |
|---|-------|-----------|---------|
| 25 | HARDEN-025 | EmptyResults component | 20 min |
| 26 | HARDEN-026 | localStorage quota check | 10 min |
| 27 | HARDEN-027 | BroadcastChannel cross-tab | 15 min |
| 28 | HARDEN-028 | Stripe events purge | 10 min |

## Métricas de Sucesso

- Zero memory leaks em 72h de operação contínua
- P99 latency /buscar < 30s (all UFs)
- Zero silent data loss
- Graceful degradation em falha de qualquer dependência
- Saturation metrics visíveis em Prometheus/Grafana

## Dependências entre Stories

- HARDEN-004 (cleanup periódico) bloqueia HARDEN-013 (bounded results)
- HARDEN-022 (graceful shutdown) depende de HARDEN-004 (lifespan handler)
- HARDEN-016 (health split) é pré-requisito para alertas de HARDEN-024

## Estimativa Total

- Quick wins: ~50 min
- Críticas: ~2h
- Altas: ~2h 35min
- Médias: ~2h
- Baixas: ~55 min
- **Total: ~8h 20min**
