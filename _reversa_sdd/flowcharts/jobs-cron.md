# Flowchart — Módulo `jobs+cron`

> Gerado pelo **Reversa Archaeologist** em 2026-04-27 · Confiança 🟢 CONFIRMADO

## ARQ enqueue + worker dispatch

```mermaid
sequenceDiagram
    participant W as Web (FastAPI)
    participant Q as job_queue.enqueue_job
    participant R as Redis (ARQ)
    participant Wk as ARQ Worker (PROCESS_TYPE=worker)
    participant DB as Supabase

    W->>Q: enqueue_job(llm_summary_job, search_id, ...)
    Q->>Q: get_arq_pool() (singleton, retry x3)
    alt pool none
        Q-->>W: None (graceful — inline fallback)
    else pool ok
        Q->>Q: inject _trace_id, _span_id
        Q->>R: pool.enqueue_job(name, args, kwargs)
        R-->>Q: Job(job_id)
        Q-->>W: Job
    end
    Wk->>R: poll arq:queue
    R-->>Wk: job payload
    Wk->>Wk: re-link OTel span via _trace_id
    Wk->>Wk: execute function
    Wk->>DB: persist_job_result (Redis 1h TTL + Supabase)
    Wk->>R: SET smartlic:job_result:{search_id}:{field}
```

## Worker alive check (CRIT-033)

```mermaid
flowchart TD
    A[is_queue_available?] --> B{pool exists?}
    B -->|não| F[False — inline mode]
    B -->|sim| C[pool.ping]
    C -->|fail| F
    C -->|ok| D[_check_worker_alive cache 15s]
    D --> E{arq:queue:health-check key exists?}
    E -->|sim| OK[True — async dispatch]
    E -->|não| F
    F --> G[Pipeline executa LLM+Excel inline]
```

## Cancel flag handshake (STORY-281)

```mermaid
sequenceDiagram
    participant U as User
    participant API as POST /search/{id}/cancel
    participant R as Redis
    participant Wk as Worker

    U->>API: POST cancel
    API->>R: SET smartlic:search_cancel:{id} ex=600
    API-->>U: 200 cancelled
    Wk->>R: GET smartlic:search_cancel:{id} (poll between stages)
    alt flag set
        R-->>Wk: "1"
        Wk->>Wk: abort pipeline
        Wk->>R: DEL key
    end
```

## Cron architecture (dual)

```mermaid
flowchart TD
    subgraph "Web/Worker Startup (FastAPI lifespan)"
        L1[register_all_cron_tasks]
        L1 --> L2[19 background loops asyncio.create_task]
        L2 --> L3[health_canary, cache_cleanup, session_cleanup, ...]
        L2 --> L4[Redis distributed locks evitam duplicação se WEB_CONCURRENCY>1]
    end
    subgraph "ARQ Worker Cron (job_queue.WorkerSettings.cron_jobs)"
        A1[arq.cron schedules]
        A1 --> A2[daily_digest 1x/dia]
        A1 --> A3[email_alerts 1x/dia]
        A1 --> A4[cron_monitor hourly]
        A1 --> A5[ingestion full 1x/dia, incremental 3x/dia, purge 1x/dia]
        A1 --> A6[contracts crawl 3x/sem]
        A1 --> A7[enrich_entities 08 UTC, enrich_municipios 09 UTC]
    end
```

## Worker on_startup hardening

```mermaid
flowchart TD
    A[arq starts worker] --> B[_worker_on_startup ctx]
    B --> C[CRIT-051: setup_logging stdout]
    C --> D{ctx.redis.connection_pool?}
    D -->|sim| E[CRIT-038: socket_timeout=30s, socket_connect_timeout=10s, socket_keepalive=True]
    D -->|não| W[warn: pool not accessible]
    E --> R[ready]
    W --> R
```

## Pool reconnect retry

```mermaid
flowchart TD
    A[get_arq_pool] --> B{_arq_pool exists?}
    B -->|sim| C[pool.ping]
    C -->|ok| OK[return _arq_pool]
    C -->|fail| D[_arq_pool = None]
    B -->|não| D
    D --> E[acquire _pool_lock]
    E --> F[for attempt in 1..3]
    F --> G[await create_pool]
    G -->|ok| H[set _arq_pool, return]
    G -->|fail| I[sleep 2^attempt, retry]
    I -->|attempts exhausted| J[return None — degraded mode]
```
