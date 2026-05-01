# Flowchart — Módulo `ingestion-datalake`

> Gerado pelo **Reversa Archaeologist** em 2026-04-27

## 1. Crawl Schedule (UTC → BRT)

```mermaid
gantt
  title PNCP Ingestion Schedule (UTC)
  dateFormat HH:mm
  axisFormat %H:%M
  section Daily
  Full crawl (4h timeout)        :05:00, 240m
  Incremental (1h timeout)       :11:00, 60m
  Incremental (1h timeout)       :17:00, 60m
  Incremental (1h timeout)       :23:00, 60m
  Purge (10min)                  :07:00, 10m
```

## 2. Full Crawl Flow

```mermaid
flowchart TD
  Start[ARQ cron 5 UTC] --> Flag{DATALAKE_ENABLED?}
  Flag -->|false| Skip[Skip · log]
  Flag -->|true| Init[Create ingestion_run]
  Init --> Loop[For each UF in INGESTION_UFS · 5 paralelo]
  Loop --> Mod[For each modalidade 4,5,6,7,8,12]
  Mod --> Page[Fetch page · max 50 pages]
  Page --> Trans[transform_pncp_item · content_hash]
  Trans --> Up[bulk_upsert · batch 500]
  Up --> RPC[upsert_pncp_raw_bids RPC]
  RPC --> Stats[inserted/updated/unchanged]
  Stats --> Mod
  Mod --> Loop
  Loop --> Wait[sleep 2s entre batches]
  Wait --> Cp[save_checkpoint]
  Cp --> Done[complete_ingestion_run]
  Done --> Metrics[Prometheus counters + Sentry]
```

## 3. Query Path Layer 2 vs Legacy Fallback

```mermaid
flowchart LR
  Search[Search Pipeline · stage_execute] --> Q{DATALAKE_QUERY_ENABLED?}
  Q -->|true| Cache{In-mem cache hit?}
  Cache -->|sim, fresh| Ret1[Return cached]
  Cache -->|não/expired| RPC[search_datalake RPC]
  RPC --> Z{0 results?}
  Z -->|sim| Live[Fall back to live multi-source]
  Z -->|não| Pop[Cache + return]
  Q -->|false| Live
  Live --> Multi[PNCPClient + PCP v2 + ComprasGov v3]
```

## 4. Checkpoint State Machine

```mermaid
stateDiagram-v2
  [*] --> running: create_ingestion_run
  running --> completed: save_checkpoint OK
  running --> failed: mark_checkpoint_failed
  failed --> running: next cron retry (backoff)
  completed --> running: next cron (incremental)
  completed --> [*]
```

## 5. Content-Hash Dedup

```
content_hash = SHA-256(
  objeto_compra.lower().strip() +
  "|" +
  valor_total_estimado +
  "|" +
  situacao_compra.lower().strip()
)
```

UPSERT decide via comparison:
- `inserted` = nova `numero_controle_pncp`
- `updated` = mesmo PK, content_hash diferente
- `unchanged` = mesmo PK, mesmo hash (skip write)
