# Spec: Jobs & Cron

> Spec executável (SDD) gerada pelo **Reversa Writer** em 2026-05-08
> Confiança: 🟢 CONFIRMADO

## Component
- **ID**: `jobs-cron`
- **Path**: `backend/jobs/queue/` (config, jobs, search, result_store, pool, redis_pool, worker, definitions), `backend/jobs/cron/` (canary, billing, notifications, session_cleanup, scheduler, cron_monitor, pncp_canary, llm_batch_poll, new_bids_notifier, indice_municipal, seo_snapshot, trial_emails, trial_risk_detection), `backend/cron/` (cache, billing, health, notifications, pncp_status, _loop), `backend/job_queue.py`, `backend/cron_jobs.py`

## Purpose

Gerenciar execução assíncrona de tarefas pesadas (LLM summaries, Excel generation) via ARQ job queue + Redis, e manter 9 cron jobs ARQ agendados + 19 lifespan loops com Redis distributed locks. Dois modos de operação: `PROCESS_TYPE=web` (enqueue) vs `PROCESS_TYPE=worker` (execute).

## ARQ Worker Architecture

| Processo | PROCESS_TYPE | Função |
|----------|-------------|--------|
| Web (FastAPI) | `web` | `enqueue_job` → Redis ARQ queue |
| Worker (ARQ) | `worker` | poll Redis, execute jobs, persist results |

**7 base ARQ functions:**
1. `search_job` — search pipeline offload
2. `llm_summary_job` — GPT-4.1-nano executive summary
3. `excel_generation_job` — openpyxl workbook generation
4. `llm_batch_poll_job` — batch API polling
5. `new_bids_notifier_job` — alert digests
6. `seo_snapshot_job` — observatory SEO snapshots
7. `ingestion_*` (conditional) — N functions via feature flag `DATALAKE_ENABLED`

## Enqueue Flow

```
Web Handler
  → enqueue_job(func_name, search_id, ...)
      → get_arq_pool() singleton (retry x3, exponential backoff 2^n)
          → pool.ping() healthcheck
          → inject _trace_id, _span_id (OTel context propagation)
          → Redis arq:queue enqueue
              → ARQ Worker poll
              → re-link OTel span via _trace_id
              → execute function
              → persist_job_result: Redis (1h TTL) + Supabase
```

**Graceful degradation:** `get_arq_pool()` retorna `None` se pool indisponível após 3 tentativas → pipeline executa LLM+Excel inline (synchronous fallback).

## Worker Health Check (`is_queue_available`)

```
pool exists? → No → False (inline mode)
              → Yes → pool.ping
                       → fail → False
                       → ok → _check_worker_alive (cache 15s)
                                → arq:queue:health-check key exists?
                                    → Yes → True (async dispatch)
                                    → No → False (inline mode)
```

## Cancel Flag Handshake (STORY-281)

```
POST /search/{id}/cancel
  → SET smartlic:search_cancel:{id} ex=600 em Redis
  → 200 cancelled

Worker (entre stages):
  → GET smartlic:search_cancel:{id}
  → se "1": aborta pipeline, DEL key
```

## Pool Reconnect (Retry x3)

```
get_arq_pool():
  _arq_pool exists AND ping ok → return _arq_pool
  ping fail OR not exists:
    acquire _pool_lock
    for attempt in 1..3:
      await create_pool(redis_settings)
        ok → set _arq_pool, return
        fail → sleep 2^attempt, retry
    exhausted → return None (degraded mode)
```

## Cron Architecture (Dual)

### ARQ Cron (9 jobs, `WorkerSettings.cron_jobs`)

| Job | Schedule | Descrição |
|-----|----------|-----------|
| `daily_digest` | 1x/dia | resumo diário usuários |
| `email_alerts` | 1x/dia | alertas de novas licitações |
| `cron_monitor` | hourly | pg_cron health check + Sentry |
| `ingestion_full` | 1x/dia (05 UTC) | crawl completo 27 UFs × 6 modalidades |
| `ingestion_incremental` | 3x/dia (11/17/23 UTC) | crawl incremental 3-day window |
| `ingestion_purge` | 1x/dia (07 UTC) | purge bids >400d |
| `contracts_crawl` | 3x/semana (seg/qua/sex 06 UTC) | supplier_contracts full crawl |
| `enrich_entities` | 1x/dia (08 UTC) | BrasilAPI enrichment |
| `enrich_municipios` | 1x/dia (09 UTC) | IBGE indice municipal |

### Lifespan Loops (19 asyncio background tasks, FastAPI startup)

Registrados por `register_all_cron_tasks()` em `cron/` package:

- `health_canary`, `cache_cleanup`, `session_cleanup`, `trial_sequence`, `trial_risk_detection`, `pncp_status`, `reconciliation`, `pre_dunning`, `new_bids_notifier`, `seo_snapshot`, `cron_monitor`, `pncp_canary`, `llm_batch_poll`, `indice_municipal`, `seo_snapshot_extended`, + 4 adicionais

**Redis distributed locks** — cada loop adquire lock com TTL antes de executar, prevenindo duplicação quando `WEB_CONCURRENCY > 1` (lock TTL < intervalo).

## Worker On-Startup Hardening

```
arq starts worker → _worker_on_startup(ctx)
  → CRIT-051: setup_logging(stdout)
  → ctx.redis.connection_pool?
      → Yes: CRIT-038 — set socket_timeout=30s, socket_connect_timeout=10s, socket_keepalive=True
      → No: warn — pool not accessible
  → ready
```

## Job Result Persistence

```
Worker executa job
  → SET smartlic:job_result:{search_id}:{field} (Redis, 1h TTL)
  → Supabase INSERT job_results (durable)
  → SSE event emitido via progress.py asyncio.Queue
```

## Invariants

1. **Pool singleton** — `_arq_pool` e `_pool_lock` globais; reconnect via lock evita races
2. **OTel context propagation** — `_trace_id`, `_span_id` injetados no enqueue e re-linked no worker
3. **Distributed lock** — lifespan loops usam Redis `SET NX EX` para deduplicar em WC>1
4. **Inline fallback obrigatório** — `is_queue_available() = False` → pipeline síncrono (nunca drop silencioso)
5. **Cancel check entre stages** — worker checa Redis cancel flag entre cada stage do pipeline
6. **pg_cron backup** — purge-old-bids tem pg_cron server-side (STORY-1.2) além do ARQ job

## Functional Requirements

- **FR-1**: `enqueue_job(func, *args)` retorna `Job` object ou `None` (graceful)
- **FR-2**: `get_arq_pool()` reconecta com retry x3 exponential backoff
- **FR-3**: `is_queue_available()` verifica pool + worker health-check (cacheado 15s)
- **FR-4**: Worker executa 7 base functions + N ingestion functions condicionais
- **FR-5**: 9 ARQ cron jobs agendados em `WorkerSettings.cron_jobs`
- **FR-6**: 19 lifespan loops com Redis distributed locks
- **FR-7**: On-startup hardening: logging + socket_timeout
- **FR-8**: Cancel flag via Redis key `smartlic:search_cancel:{id}`
- **FR-9**: Job result: Redis 1h TTL + Supabase durable + SSE event

## Non-Functional Requirements

- **NFR-1**: `enqueue_job` latência <100ms (Redis roundtrip)
- **NFR-2**: Worker reconnect em <10s (retry x3 com backoff 2/4/8s)
- **NFR-3**: Lock TTL < intervalo do loop (prevenção duplicação)
- **NFR-4**: OTel span propagation — trace continuidade Web→Worker

## Constraints

- **CON-1**: `PROCESS_TYPE=worker` ativa WorkerSettings; `PROCESS_TYPE=web` só enqueue
- **CON-2**: ARQ worker roda sem acesso a `WEB_CONCURRENCY` — stateless (Railway worker service)
- **CON-3**: `DATALAKE_ENABLED=false` remove ingestion functions do WorkerSettings
- **CON-4**: WEB_CONCURRENCY=3 (Railway Pro) — distributed locks obrigatórias (WEB_CONCURRENCY amplification CRIT-038)

## Acceptance Criteria

- AC-1: `enqueue_job` retorna Job quando pool ok; `None` (sem exception) quando pool offline
- AC-2: Inline fallback executa LLM+Excel quando `is_queue_available() = False`
- AC-3: Cancel via `POST /search/{id}/cancel` aborta worker em até 15s (próximo stage check)
- AC-4: `daily_digest` + `ingestion_full` executam nos schedules definidos (±2min tolerância)
- AC-5: Redis lock previne double-execution de lifespan loops em WC>1
- AC-6: Worker on-startup seta socket_timeout=30s e socket_keepalive=True

## Errors

| Code | Trigger | Resposta |
|------|---------|----------|
| Pool connect fail after x3 | Redis offline | return None → inline mode |
| Job timeout | ARQ job_timeout exceeded | Sentry capture + inline fallback |
| Lock acquisition fail | outro worker processando | skip tick (next interval) |
| Cancel key not found | TTL expirado (>600s) | worker continua normalmente |

## Code Traceability

- `backend/job_queue.py` — façade `enqueue_job`, `is_queue_available`, `WorkerSettings`
- `backend/jobs/queue/pool.py` — `get_arq_pool`, `_arq_pool`, `_pool_lock`, reconnect retry
- `backend/jobs/queue/worker.py` — `_worker_on_startup`, socket hardening (CRIT-038)
- `backend/jobs/queue/jobs.py` — `llm_summary_job`, `excel_generation_job`
- `backend/jobs/queue/search.py` — `search_job` (ARQ offload do pipeline)
- `backend/jobs/queue/result_store.py` — `persist_job_result` Redis+Supabase
- `backend/jobs/cron/cron_monitor.py` — hourly pg_cron health + Sentry alert
- `backend/jobs/cron/pncp_canary.py` — PNCP breaking change canary (STORY-4.5)
- `backend/cron/` (cache, billing, health, _loop) — lifespan loops
- `backend/cron_jobs.py` — façade `register_all_cron_tasks`

## Dependencies

- Redis (ARQ queue + distributed locks + cancel flags + job results cache)
- Supabase (job_results durable, pg_cron backup)
- OpenTelemetry (trace propagation via _trace_id/_span_id)
- Sentry (cron health alerts, job failure capture)
- `backend/pipeline/` (search_job calls pipeline stages)
- `backend/ingestion/` (ingestion ARQ functions)
