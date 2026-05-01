# Spec: Ingestion + DataLake

> Spec executável (SDD) gerada pelo **Reversa Writer** em 2026-04-27
> Confiança: 🟢 CONFIRMADO

## Component
- **ID**: `ingestion-datalake`
- **Path**: `backend/ingestion/`, `backend/datalake_query.py`, `backend/jobs/queue/config.py` (worker cron)

## Purpose

Layer 1 ETL: PNCP raw bids + supplier_contracts → Supabase. Powered DataLake elimina pre-warming cache. Fonte primária de busca (`search_datalake` RPC <100ms p95). Dual ingestion tracks: bids (daily) + contracts (3x/sem).

## Schedule

| Job | Frequência | UTC | BRT | Timeout |
|-----|-----------|-----|-----|---------|
| `ingestion_full_crawl_job` | daily | 5h (env `INGESTION_FULL_CRAWL_HOUR_UTC`) | 2am | 14400s (4h) |
| `ingestion_incremental_job` | 3x/dia | 11/17/23h (`INGESTION_INCREMENTAL_HOURS`) | 8/14/20h | 3600s |
| `ingestion_purge_job` | daily | 7h (full+2) | 4am | 600s |
| `contracts_full_crawl_job` | 3x/sem mon/wed/fri | 6h (full+1) | 3am | env CONTRACTS_FULL_CRAWL_TIMEOUT |
| `contracts_incremental_job` | 3x/sem | 12/18/0h | 9am/3pm/9pm | env CONTRACTS_INCREMENTAL_TIMEOUT |
| `enrich_entities_job` (BrasilAPI) | daily | 8h | 5am | 7200s |
| `enrich_municipios_job` (IBGE) | daily | 9h | 6am | 3600s |

## Invariants

1. **Full daily 5 UTC, incremental 11/17/23 UTC** — complementary windows
2. **27 UFs × 6 modalidades** (4,5,6,7,8,12) — 162 (UF, mod) combinations
3. **10-day window full**, **3-day incremental**
4. **5 UFs parallel, 2s delay** — `_BATCH_SIZE=5, _BATCH_DELAY_S=2.0`
5. **max 50 pages per (UF, modalidade)** — ceiling protection
6. **PNCP `tamanhoPagina ≤ 50`** (Feb 2026 breaking change, canary STORY-4.5)
7. **Upsert content_hash dedup** — `upsert_pncp_raw_bids` RPC, 500 rows/batch
8. **400 days retention** — pg_cron `purge_old_bids(400)` daily 7 UTC (STORY-OBS-001)
9. **Checkpoint resumable** — `ingestion_checkpoints` (active progress) + `ingestion_runs` (audit)
10. **DataLake-first query** — `DATALAKE_QUERY_ENABLED=true` (default); fallback live só se 0 results

## Functional Requirements

- **FR-1**: `ingestion_full_crawl_job` itera 27 UF × 6 mod, 10d window, paginate até 50 pages, upsert bids
- **FR-2**: Incremental 3-day window (mais barato)
- **FR-3**: Purge `purge_old_bids(400)` via pg_cron + ARQ as backup
- **FR-4**: Contracts crawler: similar para `pncp_supplier_contracts` (~2M+ rows)
- **FR-5**: Enrichment BrasilAPI (`enrich_entities_job`): popula `enriched_entities` (CNPJ master)
- **FR-6**: Enrichment IBGE (`enrich_municipios_job`): popula `municipios`
- **FR-7**: Backfill: `ingestion_backfill_func` para gaps históricos (manual trigger via admin)
- **FR-8**: Query principal: `search_datalake(params)` RPC retorna bids filtered + paginated
- **FR-9**: Frontend integration: SEO programmatic queries via RPCs (`get_panorama_setor`, `get_contratos_orgao`, etc.)
- **FR-10**: Live API fallback (legacy) se datalake retorna 0 results — `DATALAKE_QUERY_ENABLED` toggleable

## Non-Functional Requirements

- **NFR-1**: Full crawl completion <4h (timeout 14400s)
- **NFR-2**: Incremental crawl completion <30min
- **NFR-3**: `search_datalake` RPC p95 <100ms (GIN tsvector + composite indexes)
- **NFR-4**: Upsert batch 500 rows (~5s per batch)
- **NFR-5**: 0 missed bids (resumable checkpoint)

## Constraints

- **CON-1**: PNCP rate limit não-documentado — circuit breaker 15 fails / 60s cooldown
- **CON-2**: PNCP HTTP 422 retryable (max 1 retry) — observado em prod
- **CON-3**: Crawler runs em ARQ worker (não em web)
- **CON-4**: Lock distribuído NÃO necessário (1 worker apenas)
- **CON-5**: Disk usage `pncp_raw_bids` ~1.5M rows × 400d → ~500MB; `supplier_contracts` ~2M rows ~700MB

## Acceptance Criteria

- AC-1: Full crawl em prod completa em <4h sem timeout
- AC-2: `pncp_raw_bids` count crescimento ~5-10k bids/dia
- AC-3: Purge mantém table ≤ 400 dias old
- AC-4: `search_datalake` retorna resultados em <100ms p95 sob carga normal
- AC-5: Crawler resumable: kill -9 mid-run + restart continua de checkpoint
- AC-6: Canary `pncp_canary_job` detecta breaking change (tamanhoPagina=51 sucesso) → Sentry FATAL
- AC-7: BrasilAPI enrichment popula `enriched_entities.razao_social, atividade_principal`

## Errors

| Code | HTTP | Trigger |
|------|------|---------|
| `pncp_circuit_open` | 503 | 15 consecutive fails |
| `pncp_shape_drift` | — | Sentry alert (canary) |
| `upsert_failed` | — | log + retry batch |
| `checkpoint_corrupt` | — | restart from scratch (admin) |

## Code traceability

- `backend/ingestion/config.py` — `DATALAKE_ENABLED`, `INGESTION_FULL_CRAWL_HOUR_UTC`, `INGESTION_INCREMENTAL_HOURS`
- `backend/ingestion/scheduler.py` — `ingestion_full_crawl_job`, `ingestion_incremental_job`, `ingestion_purge_job`, `ingestion_backfill_func`, `contracts_*`, `enrich_entities_job`, `enrich_municipios_job`
- `backend/ingestion/crawler.py` — page-by-page PNCP fetcher
- `backend/ingestion/contracts_crawler.py` — supplier_contracts variant
- `backend/ingestion/transformer.py` — PNCP raw → unified schema
- `backend/ingestion/loader.py` — upsert via RPC
- `backend/ingestion/checkpoint.py` — resumable state
- `backend/ingestion/enricher.py` — BrasilAPI + IBGE enrichment
- `backend/datalake_query.py` — `query_datalake(params)` wrapper
- `backend/jobs/cron/pncp_canary.py` — STORY-4.5 breaking change detector
- Migrations: `20260326000000_datalake_raw_bids.sql`, `20260331400000_debt210_optimize_upsert_and_tsvector.sql`, `20260413000002_trigram_index_objeto_compra.sql`, `20260424133500_extend_pncp_retention_400d.sql`, `20260424161923_seo013_index_orgao_cnpj_raw_bids.sql`

## Dependencies

- httpx (async HTTP)
- Supabase RPC (`upsert_pncp_raw_bids`, `purge_old_bids`, `search_datalake`)
- ARQ (cron schedules)
- BrasilAPI, IBGE (enrichment)
